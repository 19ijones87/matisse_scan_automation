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

COMMAND_LENGTH_BYTES = 4 #in bytes

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
    command_packet_bytes = b""

    command_bytes = command.encode()

    command_len = len(command)
    command_len_bytes = command_len.to_bytes(COMMAND_LENGTH_BYTES, "big")

    command_packet_bytes += (command_len_bytes + command_bytes)

    sock.sendall(command_packet_bytes)
def receive_exact_bytes(sock, n):
    pass

def receive_response(sock):
    pass
