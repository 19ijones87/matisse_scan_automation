import logging
import matisse_client as mc

logger = logging.getLogger(__name__)


def set_baseline(sock, value):
    command = f"PZETL:BASE {value}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond!r}") #!!!
    if respond != "OK":
        raise RuntimeError(f"Expected 'OK' but got: {respond}")
