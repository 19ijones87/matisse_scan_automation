import logging
import matisse_client as mc

logger = logging.getLogger(__name__)

BASELINE_MIN = -1.0
BASELINE_MAX = 1.0


def unlock_piezo_etalon(sock):
    command = "PZETL:CNTRSTA STOP"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")

    logger.info("Piezo etalon unlocked")


def get_piezo_etalon_lock_status(sock):
    command = "PZETL:CNTRSTA?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"{command} returned an error: {respond}")
    logger.debug(f"Raw response to {command}: {respond!r}")

    respond_splitted_list = respond.split()
    lock_status = respond_splitted_list[-1]

    if lock_status not in ("RUN", "STOP"):
        raise RuntimeError(f"Expected 'RUN' or 'STOP' but got: {lock_status}")
    return lock_status


def lock_piezo_etalon(sock):
    command = "PZETL:CNTRSTA RUN"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")

    lock_status = get_piezo_etalon_lock_status(sock)
    if lock_status != "RUN":
        raise RuntimeError(f"{command} was accepted but the loop is {lock_status}")

    logger.info(f"Piezo etalon locked, baseline {get_baseline(sock):+.1f}")


def get_baseline(sock):
    command = "PZETL:BASE?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"{command} returned an error: {respond}")
    logger.debug(f"Raw response to {command}: {respond!r}")

    respond_splitted_list = respond.split()
    baseline = float(respond_splitted_list[-1])

    if baseline < BASELINE_MIN or baseline > BASELINE_MAX:
        raise RuntimeError(f"Expected a baseline in [-1, 1] but got: {baseline}")
    return baseline


def set_baseline(sock, value):
    if value < BASELINE_MIN or value > BASELINE_MAX:
        raise RuntimeError(f"Expected a baseline in [-1, 1] but got: {value}")

    command = f"PZETL:BASE {value:.4f}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")


