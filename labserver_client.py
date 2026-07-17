"""
labserver_client.py

TCP/IP client for the lab's shared LabServer (see LabServerDef.py for the
protocol definition). Used to look up the current experimental image ID
and to upload data (e.g. mean/span laser frequency) tagged under that
image, so other lab programs (e.g. siscam) can associate it with the
correct image.

Protocol notes:
- Every command starts with a mandatory client ID handshake.
- Reading a value of unknown length is a two-step process: SERVER_NUM
  first asks how many bytes the value is, then SERVER_GET requests that
  many bytes. Both can return SERVER_NACK if the key does not exist.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-17
"""

import socket
import LabServerDef

def connect_to_labserver(client_id, host, port, timeout=10.0):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.sendall(LabServerDef.server_cmd(LabServerDef.SERVER_CLIENT_ID, client_id, 0))
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

def receive_exact_bytes(sock, n):
    response_buffer = b""
    while (n > len(response_buffer)):
        
        data = sock.recv(n-len(response_buffer))
        if not data:
            raise ConnectionError(" {} bytes expected, but got {} bytes".format(n, len(response_buffer)))
        response_buffer += data

    return response_buffer 

def get_image_id(sock):
    sock.sendall(LabServerDef.server_cmd(LabServerDef.SERVER_NUM, "IMGid", 6))
    length_bytes = receive_exact_bytes(sock, 3)

    if(length_bytes.decode() == LabServerDef.SERVER_NACK):
        raise RuntimeError("Server returned NACK for key 'IMGid' (key not found)")

    length_bytes += receive_exact_bytes(sock, 3)

    image_id_length = int(length_bytes.decode())

    sock.sendall(LabServerDef.server_cmd(LabServerDef.SERVER_GET, "IMGid", image_id_length))
    id_bytes = receive_exact_bytes(sock, 3)
    if(id_bytes.decode() == LabServerDef.SERVER_NACK):
        raise RuntimeError("Server returned NACK for key 'IMGid' (key not found)")

    id_bytes += receive_exact_bytes(sock, image_id_length - 3)
    image_id = int(id_bytes.decode())


    return image_id


def upload_data(sock, data_key, data):
    data_bytes = str(data).encode()
    sock.sendall(LabServerDef.server_cmd(LabServerDef.SERVER_SET, data_key, len(data_bytes)))
    sock.sendall(data_bytes)

    response = receive_exact_bytes(sock, 3)
    if(response.decode() == LabServerDef.SERVER_ACK):
        return
    else:
        raise RuntimeError("Expected ACK for key '{}', but got {!r}".format(data_key, response))

def disconnect_from_labserver(sock):
    if sock is None:
        return
    sock.close()