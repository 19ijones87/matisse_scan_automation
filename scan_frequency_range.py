
import os
import sys
import csv
import logging
import argparse

import matisse_client as mc
import labserver_client
import scan_device as sd
import scan_current_window as scw
import step_to_next_window as sw


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


def scan_frequency_range(sock, sock_labserver, window_count , image_count, direction, flank, fraction, span, step):
    sd.set_device(sock, SCAN_DEVICE_NONE)
    lock_result = sw.acquire_locks(sock, flank, fraction, span, step)
    logger.info(f"Starting at {lock_result['frequency']} THz, "
                f"thin etalon motor {lock_result['motor_settled']}")
    windows = []

    for window_index in range(window_count):
            logger.info(f"===== window {window_index + 1} / {window_count} =====")

            sd.set_device(sock, SCAN_DEVICE_SLOW_PIEZO)
            results = scw.scan_current_window(sock, sock_labserver, image_count)
            sd.set_device(sock, SCAN_DEVICE_NONE)

            uploaded = 0
            for image_record in results:
                if image_record["mean"] is not None:
                    uploaded += 1

            windows.append({"window_index": window_index,
                            "motor": current_position["motor_settled"],
                            "frequency": current_position["frequency"],
                            "step_ghz": None,
                            "images": results})

            if window_index < window_count - 1:
                step_result = sw.step_to_next_window(sock, direction, flank,
                                                    fraction, span, step)
                windows[-1]["step_ghz"] = step_result["step_ghz"]
                current_position = step_result

            logger.info(f"window {window_index + 1} done  "
                    f"{windows[-1]['frequency']:.6f} THz  "
                    f"step {windows[-1]['step_ghz']}")

            