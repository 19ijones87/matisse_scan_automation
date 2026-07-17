"""
matisse_scan.py

Runs a full scan cycle on the Sirah Matisse Ti:Sapphire laser via
Matisse Commander: starts a scan, polls its status until it completes,
then disconnects. Built on top of the TCP connection and framing logic
in matisse_client.py.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence
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

import argparse
import logging
import wavemeter_client

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



def main(host):
    logger.info(f"Connecting to Matisse at {host}:{MATISSE_PORT}")
    sock = mc.connect_to_matisse(host, MATISSE_PORT)
    logger.info("Connection established")
    try:
        start_scan(sock)
        wait_until_done(sock)
    finally:
        mc.disconnect_from_matisse(sock)
        logger.info(f"Disconnected from {host}")
        

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default=MATISSE_HOST)
        args = parser.parse_args()
        main(args.host)
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)