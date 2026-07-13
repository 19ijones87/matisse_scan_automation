"""
matisse_client.py

TCP/IP client for communicating with the Matisse Commander software
controlling a Sirah Matisse Ti:Sapphire laser (port 30000). Handles the
socket connection and length-prefixed message framing used to send
commands and reliably read responses, including partial reads.


Author: A. Halil Ceylan
        Koç University,Istanbul - LENS, Florence.
"""

def connect_to_matisse(host, port, timeout = 1.0):
    pass
