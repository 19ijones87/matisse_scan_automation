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

def start_scan(sock):
    command = "SCAN:STATUS RUN"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond != "OK":
        raise RuntimeError("Expected 'OK' but got: {}".format(respond))


def get_status(sock):
    command = "SCAN:STATUS?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    respond_splitted_list = respond.split(" ")
    status_value = respond_splitted_list[-1]

    if status_value != "RUN" and status_value != "STOP":
        raise RuntimeError(f"Expected 'RUN' or 'STOP' but got: {status_value}")
    return status_value


def wait_until_done(sock):
    while True:
        current_status = get_status(sock)
        if current_status == "STOP":
            break
        time.sleep(0.1)

def main(host):
    sock = mc.connect_to_matisse(host, MATISSE_PORT)
    try:
        start_scan(sock)
        wait_until_done(sock)
    finally:
        mc.disconnect_from_matisse(sock)

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default=MATISSE_HOST)
        args = parser.parse_args()
        main(args.host)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)