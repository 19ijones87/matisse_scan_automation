import logging
import matisse_client as mc

logger = logging.getLogger(__name__)

SCAN_POSITION_MIN = 0.0
SCAN_POSITION_MAX = 0.7
VALID_SCAN_MODES = (1, 2, 4, 8, 16, 32, 64, 128)


def get_lower_limit(sock):
    command = "SCAN:LLM?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    logger.debug(f"Raw response: {respond!r}")
    respond_splitted_list = respond.split()
    lower_limit = respond_splitted_list[-1]

    lower_limit_float = float(lower_limit)
    if lower_limit_float < SCAN_POSITION_MIN or lower_limit_float > SCAN_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {lower_limit_float}")
    return lower_limit_float


def get_upper_limit(sock):
    command = "SCAN:ULM?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond!r}")
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")

    respond_splitted_list = respond.split()
    upper_limit = respond_splitted_list[-1]
    upper_limit_float = float(upper_limit)

    if upper_limit_float < SCAN_POSITION_MIN or upper_limit_float > SCAN_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {upper_limit_float}")
    return upper_limit_float


def get_mode(sock):
    command = "SCAN:MODE?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    mode = respond_splitted_list[-1]
    mode_int = int(mode)

    if mode_int not in VALID_SCAN_MODES:
        raise RuntimeError(f"Expected one of {VALID_SCAN_MODES} but got: {mode_int}")
    return mode_int


def get_device(sock):
    command = "SCAN:DEV?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    #0 = no device, 1 = slow cavity piezo, 2 = reference cell piezo
    scan_device_num = int(respond_splitted_list[-1])

    if scan_device_num < 0 or scan_device_num > 2:
        raise RuntimeError("Invalid device")
    return scan_device_num
