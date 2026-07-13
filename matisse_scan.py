"""
matisse_scan.py

Runs a full scan cycle on the Sirah Matisse Ti:Sapphire laser via
Matisse Commander: starts a scan, polls its status until it completes,
then disconnects. Built on top of the TCP connection and framing logic
in matisse_client.py.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence
"""

import time
import matisse_client as mc

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
    pass

def main():
    pass