"""
scan_current_window.py

Runs a full scan cycle on the Sirah Matisse Ti:Sapphire laser via
Matisse Commander, and reports the scan's frequency statistics to the
lab's shared LabServer so they can be associated with the correct
experimental image.

Main flow:
1. Connect to Matisse Commander and to LabServer, then subscribe to
   image ID changes via SERVER_WAIT (labserver_client.py) and start a
   scan (matisse_client.py).
2. Poll the scan status; while the scan is running, repeatedly read the
   laser frequency from the HighFinesse wavemeter on channel 7
   (wavemeter_client.py), and check whether LabServer has pushed a new
   image ID.
3. Whenever the image ID changes mid-scan, compute the mean frequency
   and frequency span (max - min) for the readings collected under the
   previous image ID, upload them to LabServer under per-image keys,
   then re-subscribe to further image ID changes.
4. Once the scan stops (or the user presses Ctrl+C), upload the final
   (still pending) segment the same way, then disconnect from both
   Matisse and LabServer.

This means several images can be taken during a single scan, and each
one gets its own mean/span frequency values, tagged with the image ID
that was current while those readings were taken.

Some Matisse Scan Stop Modes (e.g. "increase voltage, stop at neither
limit") never stop the scan on their own -- for those, the scan must be
stopped manually with Ctrl+C, which sends an explicit "SCAN:STATUS
STOP" command to physically stop the scan (equivalent to clicking
Scanning off in Matisse Commander) before uploading the final segment.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-21 -- added stop_scan() and Ctrl+C handling in
wait_until_done(), for Scan Stop Modes that never stop on their own.
"""

import sys
import time
import matisse_client as mc
import os
# MATISSE_HOST can be set via an environment variable (e.g. running
# `export MATISSE_HOST=<lab-computer-ip>` in the terminal before starting
# this script) when connecting from the lab computer, so the real IP
# is never committed. Defaults to localhost if not set.
MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

LABSERVER_HOST = os.environ.get("LABSERVER_HOST", "127.0.0.1")
LABSERVER_PORT = 47123
LABSERVER_CLIENT_ID = "WLM&Matisse"


import argparse
import logging
import wavemeter_client
import labserver_client

#!!!level=logging.DEBUG
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S", handlers=[logging.StreamHandler(),
              logging.FileHandler("scan_current_window.log")])
logger = logging.getLogger(__name__)


import scan_device as sd
import slow_piezo as sp

PIEZO_RETURN_TOLERANCE = 0.02
PIEZO_RETURN_TIMEOUT = 15.0


def wait_for_piezo_at_lower_limit(sock):
    lower_limit = sd.get_lower_limit(sock)
    start_time = time.time()

    while True:
        position = sp.get_position(sock)

        if abs(position - lower_limit) <= PIEZO_RETURN_TOLERANCE:
            logger.info(f"Slow piezo back at {position:.4f} after "
                        f"{time.time() - start_time:.1f} s")
            return position

        if time.time() - start_time > PIEZO_RETURN_TIMEOUT:
            logger.warning(f"Slow piezo did not return to {lower_limit} within "
                           f"{PIEZO_RETURN_TIMEOUT} s, last position {position:.4f}")
            return position

        time.sleep(0.02)

def wait_until_done(sock, sock_labServer, image_id, image_limit, image_timeout):
    frequencies = []
    results = []
    error_count = 0
    start_time = time.time()
    image_counter = 0
    last_change_time = time.time()
    try:
        while True:
            current_status = sd.get_status(sock)
            if current_status == "STOP":
                break
            f = wavemeter_client.get_frequency(7)
            if f is None:
                error_count += 1
            else:
                frequencies.append(f)
            current_image_id = image_id
            image_id, frequencies = check_image_change(sock_labServer, image_id, frequencies,results)
            if current_image_id != image_id:
                image_counter += 1
                last_change_time = time.time()
        
            if image_limit <= image_counter:
                logger.info("Number of images reached!")
                wait_for_piezo_at_lower_limit(sock)
                sd.stop(sock)
                break
            time.sleep(0.1)
            if time.time() - last_change_time > image_timeout:
                sd.stop(sock)
                raise RuntimeError(f"No new image ID for {image_timeout} s "
                                   f"after image {image_id}")
    except KeyboardInterrupt:
        logger.info("Ctrl+C received, stopping scan...")
        sd.stop(sock)
        raise 
    duration = time.time() - start_time
    uploaded = [r for r in results if r["mean"] is not None]
    total_readings = sum(r["reading_count"] for r in results)

    logger.info("--- window summary ---")
    logger.info(f"duration            {duration:.1f} s")
    logger.info(f"images processed    {len(results)}")
    logger.info(f"uploaded            {len(uploaded)}")
    logger.info(f"empty               {len(results) - len(uploaded)}")
    if results:
        logger.info(f"readings per image  {total_readings / len(results):.0f}")
    if uploaded:
        means = [r["mean"] for r in uploaded]
        logger.info(f"frequency span      {(max(means) - min(means)) * 1e6:.1f} MHz")
    logger.info(f"wavemeter failures  {error_count}")

    empty_ids = [r["image_id"] for r in results if r["mean"] is None]
    if empty_ids:
        logger.warning(f"images with no readings  {empty_ids}")
    return results
def upload_results_to_labServer(sock, image_id, mean, span):
    mean_key = "TiSaFreq" + str(image_id)
    #span_key = "TiSaSpanFreq" + str(image_id)

    labserver_client.upload_data(sock, mean_key, mean, span)
    #logger.debug(f"Uploaded {mean_key}, {span_key}")



def check_image_change(sock_labserver, current_image_id, frequencies, results):
    try:
        new_image_id = labserver_client.read_image_id(sock_labserver, timeout=0)
    except (TimeoutError, BlockingIOError):
        return current_image_id, frequencies   # no change

    if new_image_id is None or new_image_id == current_image_id:
        return current_image_id, frequencies

    elif new_image_id != current_image_id:
        if len(frequencies) > 0:
            mean, span = wavemeter_client.calculate_statistics(frequencies)
            upload_results_to_labServer(sock_labserver, current_image_id, mean, span)
            logger.info(f"Image {current_image_id}  {mean:.6f} THz  "
                        f"span {span * 1e6:.1f} MHz  {len(frequencies)} readings")
        else:
            mean, span = None, None
            logger.warning(f"Image {current_image_id}  no readings, nothing uploaded")
        results.append({"image_id": current_image_id, "mean": mean, "span": span, "reading_count": len(frequencies), "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        labserver_client.send_wait_for_image_id(sock_labserver)   # new wait op
        return new_image_id, []


def scan_current_window(sock, sock_labServer, image_count, image_timeout = 120.0):
    labserver_client.send_wait_for_image_id(sock_labServer)
    image_id = labserver_client.read_image_id(sock_labServer, timeout=None)

    sd.start(sock)
    first_id = image_id
    waited_since = time.time()
    while image_id == first_id:
        image_id, _ = check_image_change(sock_labServer, image_id, [], [])
        if image_id == first_id:
            if time.time() - waited_since > image_timeout:
                sd.stop(sock)
                raise RuntimeError(f"No image ID change within {image_timeout} s, "
                                   f"still on image {first_id}")
            time.sleep(0.1)
    logger.info(f"Skipped the in-progress image {first_id}, counting from {image_id}")

    results = wait_until_done(sock, sock_labServer, image_id, image_count, image_timeout)

    #if (mean is not None) and (span is not None):
        #upload_results_to_labServer(sock_labServer, image_id, mean, span) that is to upload last image statistics which are not completed

    return results


def main(matisse_host, labserver_host, image_limit):
    logger.info(f"Connecting to Matisse at {matisse_host}:{MATISSE_PORT}")
    sock_matisse = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    sock_labServer = None
    try:
        sock_labServer = labserver_client.connect_to_labserver(LABSERVER_CLIENT_ID, labserver_host, LABSERVER_PORT)
        results = scan_current_window(sock_matisse, sock_labServer, image_limit)

    
    finally:
        mc.disconnect_from_matisse(sock_matisse)
        labserver_client.disconnect_from_labserver(sock_labServer)
        logger.info(f"Disconnected from {matisse_host}")

    
    
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--labserver-host", default=LABSERVER_HOST)
        args = parser.parse_args()
        image_limit = int(input("How many images should be taken at this laser setting? "))
        main(args.matisse_host, args.labserver_host, image_limit)
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)