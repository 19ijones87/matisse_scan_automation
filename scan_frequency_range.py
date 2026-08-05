
import os
import sys
import csv
import logging
import argparse

import matisse_client as mc
import labserver_client
import scan_device as sd
import scan_current_window as scw
import step_to_next_window as stnw

import time
import json


MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

LABSERVER_HOST = os.environ.get("LABSERVER_HOST", "127.0.0.1")
LABSERVER_PORT = 47123
LABSERVER_CLIENT_ID = "WLM&Matisse"

SCAN_DEVICE_SLOW_PIEZO = 1
SCAN_DEVICE_NONE = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(),
              logging.FileHandler("scan_frequency_range.log")])

logger = logging.getLogger(__name__)


def scan_frequency_range(sock, sock_labserver, windows,window_count , image_count, direction, flank, fraction, span, step):
    start_time = time.time()
    sd.set_device(sock, SCAN_DEVICE_NONE)
    lock_result = stnw.acquire_locks(sock, flank, fraction, span, step)
    logger.info(f"Starting at {lock_result['lock_frequency']} THz, "
                f"thin etalon motor {lock_result['motor_settled']}")
    windows = []
    current_window = lock_result

    for window_index in range(window_count):
            logger.info(f"===== window {window_index + 1} / {window_count} =====")

            sd.set_device(sock, SCAN_DEVICE_SLOW_PIEZO)
            results = scw.scan_current_window(sock, sock_labserver, image_count)
            sd.set_device(sock, SCAN_DEVICE_NONE)


            windows.append({"window_index": window_index,
                            "lock": current_window,
                            "images": results})

            if window_index < window_count - 1:
                current_window = stnw.step_to_next_window(sock, direction, flank, fraction, span, step)
    
    duration = time.time() - start_time

    all_means = []
    total_images = 0
    uploaded_images = 0
    for window in windows:
        for image_record in window["images"]:
            total_images += 1
            if image_record["mean"] is not None:
                uploaded_images += 1
                all_means.append(image_record["mean"])

    steps = []
    for window in windows:
        step_ghz = window["lock"].get("step_ghz")
        if step_ghz is not None:
            steps.append(step_ghz)

    logger.info("--- run summary ---")
    logger.info(f"windows completed   {len(windows)} / {window_count}")
    logger.info(f"images uploaded     {uploaded_images} / {total_images}")
    if all_means:
        logger.info(f"frequency covered   {min(all_means):.6f} -> {max(all_means):.6f} THz  "
                    f"({(max(all_means) - min(all_means)) * 1e3:.1f} GHz)")
    if steps:
        logger.info(f"window steps        avg {sum(steps) / len(steps):+.2f} GHz  "
                    f"(min {min(steps):+.2f}, max {max(steps):+.2f})")
    logger.info(f"duration            {duration / 60:.1f} min")


    return windows


def write_csv(windows, path):
    with open(path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["window_index", "lock_frequency", "motor", "step_ghz",
                         "image_id", "mean", "span", "reading_count", "finished_at"])
        for window in windows:
            lock = window["lock"]
            for image_record in window["images"]:
                writer.writerow([window["window_index"],
                                 lock["lock_frequency"],
                                 lock["motor_settled"],
                                 lock.get("step_ghz"),
                                 image_record["image_id"],
                                 image_record["mean"],
                                 image_record["span"],
                                 image_record["reading_count"],
                                 image_record["finished_at"]])
    logger.info(f"Wrote {path}")

def write_json(windows, path):
    with open(path, "w") as json_file:
        json.dump(windows, json_file, indent=2)
    logger.info(f"Wrote {path}")

def main(matisse_host, labserver_host, window_count, image_count,
         direction, flank, fraction, span, step):
    logger.info(f"Connecting to Matisse at {matisse_host}:{MATISSE_PORT}")
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    sock_labserver = None
    windows = []
    run_name = "run_" + time.strftime("%Y%m%d_%H%M%S")

    try:
        sock_labserver = labserver_client.connect_to_labserver(
            LABSERVER_CLIENT_ID, labserver_host, LABSERVER_PORT)
        scan_frequency_range(sock, sock_labserver, windows, window_count,
                             image_count, direction, flank, fraction, span, step)
    except KeyboardInterrupt:
        logger.warning("Ctrl+C received, ending the run without reaching the number of images")
    finally:
        if windows:
            write_csv(windows, run_name + ".csv")
            write_json(windows, run_name + ".json")
        mc.disconnect_from_matisse(sock)
        labserver_client.disconnect_from_labserver(sock_labserver)
        logger.info(f"Disconnected from {matisse_host}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--labserver-host", default=LABSERVER_HOST)
        parser.add_argument("--windows", type=int, required=True)
        parser.add_argument("--images-per-window", type=int, required=True)
        parser.add_argument("--direction", choices=("left", "right"), required=True)
        parser.add_argument("--flank", choices=("left", "right"), required=True)
        parser.add_argument("--fraction", type=float, default=0.5)
        parser.add_argument("--span", type=int, default=4000)
        parser.add_argument("--step", type=int, default=20)
        args = parser.parse_args()

        main(args.matisse_host, args.labserver_host, args.windows,
             args.images_per_window, args.direction, args.flank,
             args.fraction, args.span, args.step)

    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)
