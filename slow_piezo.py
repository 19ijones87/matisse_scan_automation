import logging
import matisse_client as mc

logger = logging.getLogger(__name__)

PIEZO_POSITION_MIN = 0.0
PIEZO_POSITION_MAX = 0.7


def get_position(sock):
    command = "SPZT:NOW?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    logger.debug(f"Raw response: {respond!r}")
    respond_splitted_list = respond.split()
    position_value = respond_splitted_list[-1]

    position_value_float = float(position_value)
    if position_value_float < PIEZO_POSITION_MIN or position_value_float > PIEZO_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {position_value_float}")
    return position_value_float


def set_position(sock, position):
    if position < PIEZO_POSITION_MIN or position > PIEZO_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {position}")

    command = "SPZT:NOW {:.4f}".format(position)
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")
