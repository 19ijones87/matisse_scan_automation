"""
matisse_scan.py

Runs a full scan cycle on the Sirah Matisse Ti:Sapphire laser via
Matisse Commander, and reports the scan's frequency statistics to the
lab's shared LabServer so they can be associated with the correct
experimental image.

Main flow:
1. Connect to Matisse Commander and start a scan (matisse_client.py).
2. Poll the scan status; while the scan is running, repeatedly read the
   laser frequency from the HighFinesse wavemeter on channel 7
   (wavemeter_client.py).
3. Once the scan stops, compute the mean frequency and frequency span
   (max - min) from the collected readings.
4. Connect to LabServer, look up the current image ID, and upload the
   mean/span values under per-image keys (labserver_client.py).

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-17
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
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s, %(levelname)s, %(message)s", 
                    handlers=[logging.StreamHandler(), logging.FileHandler("matisse_scan.log")])
logger = logging.getLogger(__name__)


def start_scan(sock):
    command = "SCAN:STATUS RUN"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond != "OK":
        raise RuntimeError("Expected 'OK' but got: {}".format(respond))
    logger.info("Scan started successfully!")


def get_status(sock):
    command = "SCAN:STATUS?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond!r}") #!!!
    respond_splitted_list = respond.split()
    status_value = respond_splitted_list[-1]

    if status_value != "RUN" and status_value != "STOP":
        raise RuntimeError(f"Expected 'RUN' or 'STOP' but got: {status_value}")
    return status_value


def wait_until_done(sock):
    frequencies = []
    error_count = 0
    start_time = time.time()
    while True:
        current_status = get_status(sock)
        if current_status == "STOP":
            break
        f = wavemeter_client.get_frequency(7)
        if f is None:
            error_count += 1
        else:
            frequencies.append(f)
        time.sleep(0.1)
    end_time = time.time()
    duration = end_time - start_time

    logger.info(f"Scan completed in {duration:.1f}s")
    logger.info(f"Collected {len(frequencies)} valid readings, {error_count} failed")

    mean, span = wavemeter_client.calculate_statistics(frequencies)
    logger.info(f"Mean frequency: {mean:.6f} THz, Span: {span:.6f} THz")
    return mean, span

def upload_results_to_labServer(sock, mean, span):
    image_id = labserver_client.get_image_id(sock)
    logger.info(f"Image ID: {image_id}")

    mean_key = "TiSaMeanFreq" + str(image_id)
    span_key = "TiSaSpanFreq" + str(image_id)

    labserver_client.upload_data(sock, mean_key, mean)
    labserver_client.upload_data(sock, span_key, span)
    logger.info(f"Uploaded mean/span to LabServer under keys: {mean_key}, {span_key}")

    

def main(matisse_host, labserver_host):
    logger.info(f"Connecting to Matisse at {matisse_host}:{MATISSE_PORT}")
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    sock_labServer = None
    try:
        start_scan(sock)
        mean, span = wait_until_done(sock)
        sock_labServer = labserver_client.connect_to_labserver(LABSERVER_CLIENT_ID, labserver_host, LABSERVER_PORT)

        upload_results_to_labServer(sock_labServer, mean, span)
    finally:
        mc.disconnect_from_matisse(sock)
        labserver_client.disconnect_from_labserver(sock_labServer)
        logger.info(f"Disconnected from {matisse_host}")
        

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--labserver-host", default=LABSERVER_HOST)
        args = parser.parse_args()
        main(args.matisse_host, args.labserver_host)
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)