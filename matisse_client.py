"""
matisse_client.py

TCP/IP client for communicating with the Matisse Commander software
controlling a Sirah Matisse Ti:Sapphire laser (port 30000). Handles the
socket connection and length-prefixed message framing used to send
commands and reliably read responses, including partial reads.


Author: A. Halil Ceylan
        Koç University,Istanbul - LENS, Florence.
"""

import socket

def connect_to_matisse(host, port, timeout = 1.0):
    s = socket.socket()
    s.settimeout(timeout)

    try:
        s.connect((host, port))
        return s
    
    except socket.gaierror:
        s.close()
        raise
  
    except ConnectionRefusedError:
        s.close()
        raise

    except TimeoutError:
        s.close()
        raise

def disconnect_from_matisse(sock):
    if sock is None:
        return

    sock.close()

def send_command(sock, command):
    pass

def receive_exact_bytes(sock, n):
    pass

def receive_response(sock):
    pass
