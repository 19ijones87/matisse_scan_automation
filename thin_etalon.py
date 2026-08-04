import time
import logging
import matisse_client as mc

logger = logging.getLogger(__name__)

# Bits of the MOTTE:STA? status word we care about.
MOTOR_ERROR_BIT = 1 << 7      # 128 -- controller is in an error state
MOTOR_RUNNING_BIT = 1 << 8    # 256 -- motor is still moving

LOCK_TOLERANCE = 0.05
LOCK_SETTLE_TIME = 1.0

_thin_etalon_max = None


def get_thin_etalon_max(sock):
    global _thin_etalon_max
    if _thin_etalon_max is not None:
        return _thin_etalon_max

    command = "MOTTE:MAX?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()

    _thin_etalon_max = int(respond_splitted_list[-1])
    return _thin_etalon_max


def get_thin_etalon_position(sock):
    command = "MOTTE:POS?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    position = int(respond_splitted_list[-1])
    max_position = get_thin_etalon_max(sock)
    if position < 0 or position > max_position:
        raise RuntimeError(f"Expected a position in [0, {max_position}] but got: {position}")
    return position

def get_motor_status(sock):
    command = "MOTTE:STA?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    motor_status = int(respond_splitted_list[-1])
    return motor_status

def get_thin_etalon_dc(sock):
    command = "TE:DC?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    thin_etalon_reflex = float(respond_splitted_list[-1])
    return thin_etalon_reflex

def get_diode_power(sock):
    command = "DPOW:DC?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    total_power = float(respond_splitted_list[-1])
    return total_power


def set_thin_etalon_position(sock, position):

    max_position = get_thin_etalon_max(sock)
    if position < 0 or position > max_position:
        raise RuntimeError(f"Expected a position in [0, {max_position}] but got: {position}")

    command = f"MOTTE:POS {position}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")


def wait_for_motor(sock, timeout=5.0):
    start_time = time.time()
    polls = 0

    while True:
        motor_status = get_motor_status(sock)
        polls += 1

        if motor_status & MOTOR_ERROR_BIT:
            raise RuntimeError(f"Thin etalon motor is in an error state, status: {motor_status}")

        if not (motor_status & MOTOR_RUNNING_BIT):
            return time.time() - start_time, polls

        if time.time() - start_time > timeout:
            raise TimeoutError(
                f"Motor still running after {timeout}s, status: {motor_status}")

        time.sleep(0.02)


def scan_thin_etalon(sock, start, stop, step, averages=1):
    max_position = get_thin_etalon_max(sock)
    if start < 0 or stop > max_position:
        raise RuntimeError(
            f"Scan range [{start}, {stop}] is outside the motor range [0, {max_position}]")

    samples = []

    for position in range(start, stop + 1, step):
        set_thin_etalon_position(sock, position)
        wait_for_motor(sock)

        te_total = 0.0
        dpow_total = 0.0

        for i in range(averages):
            te_total += get_thin_etalon_dc(sock)
            dpow_total += get_diode_power(sock)

        samples.append((position, te_total / averages, dpow_total / averages))

    return samples


def unlock_thin_etalon(sock):
    command = "TE:CNTRSTA STOP"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")

    logger.info("Thin etalon lock released")

def get_thin_etalon_lock_status(sock):
    command = "TE:CNTRSTA?"
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

def get_control_setpoint(sock):
    command = "TE:CNTRSP?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"{command} returned an error: {respond}")
    logger.debug(f"Raw response to {command}: {respond!r}")

    respond_splitted_list = respond.split()
    control_setpoint = float(respond_splitted_list[-1])
    return control_setpoint


def get_control_proportional(sock):
    command = "TE:CNTRPROP?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"{command} returned an error: {respond}")
    logger.debug(f"Raw response to {command}: {respond!r}")

    respond_splitted_list = respond.split()
    pid_proportion = float(respond_splitted_list[-1])
    return pid_proportion

def get_control_integral(sock):
    command = "TE:CNTRINT?"
    mc.send_command(sock, command)
    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"{command} returned an error: {respond}")
    logger.debug(f"Raw response to {command}: {respond!r}")

    respond_splitted_list = respond.split()
    pid_integral = float(respond_splitted_list[-1])
    return pid_integral

def set_control_proportional(sock, v):
    command = f"TE:CNTRPROP {v:.4f}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")


def set_control_integral(sock, v):
    command = f"TE:CNTRINT {v:.4f}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")

def set_flank_orientation(sock, flank):
    if flank != "left" and flank != "right":
        raise ValueError("flank must be 'left' or 'right'")
    else:
        pid_proportional = get_control_proportional(sock)
        pid_integral     = get_control_integral(sock)
        if pid_integral == 0 or pid_proportional == 0:
            raise RuntimeError("Control gains are zero, the lock would have no feedback")
        if flank == "left":
            sign = -1
        elif flank == "right":
            sign = +1

        pid_proportional = sign * abs(pid_proportional)
        pid_integral = sign * abs(pid_integral)

        set_control_proportional(sock, pid_proportional)
        set_control_integral(sock, pid_integral)

        written_proportional = get_control_proportional(sock)
        written_integral = get_control_integral(sock)
        if written_proportional * sign <= 0:
            raise RuntimeError(
                f"Expected a {flank} flank sign on TE:CNTRPROP but got: {written_proportional}")

        if written_integral * sign <= 0:
            raise RuntimeError(
                f"Expected a {flank} flank sign on TE:CNTRINT but got: {written_integral}")
        logger.info(f"Flank orientation set to {flank} "
            f"(proportional {written_proportional:.1f}, "
            f"integral {written_integral:.1f})")


def set_control_setpoint(sock, setpoint):
    command = f"TE:CNTRSP {setpoint:.4f}"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response to {command}: {respond!r}")
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")


def get_control_error(sock):
    setpoint = get_control_setpoint(sock)
    te = get_thin_etalon_dc(sock)
    dpow = get_diode_power(sock)

    if dpow <= 0:
        raise RuntimeError(f"No output power: DPOW:DC = {dpow}")

    return setpoint - (te / dpow)

def lock_thin_etalon(sock, flank, averages=10):
    position = get_thin_etalon_position(sock)

    te_total = 0.0
    dpow_total = 0.0
    for i in range(averages):
        te_total += get_thin_etalon_dc(sock)
        dpow_total += get_diode_power(sock)

    dpow = dpow_total / averages
    if dpow <= 0:
        raise RuntimeError(f"No output power, cannot lock: DPOW:DC = {dpow}")
    te = te_total / averages
    setpoint = te / dpow
    logger.info(f"te: {te:.4f} dpow: {dpow:.4f} setpoint: {setpoint:.4f}")

    set_control_setpoint(sock, setpoint)

    set_flank_orientation(sock, flank)

    command = "TE:CNTRSTA RUN"
    mc.send_command(sock, command)
    respond = mc.receive_response(sock)
    if respond != "OK":
        raise RuntimeError(f"{command}: expected 'OK' but got: {respond}")

    time.sleep(LOCK_SETTLE_TIME)

    error = get_control_error(sock)
    if abs(error) > LOCK_TOLERANCE:
        raise RuntimeError(f"Lock did not hold: error {error:+.4f} exceeds {LOCK_TOLERANCE}")


    logger.info(f"Thin etalon has locked at motor {position}, "f"setpoint {setpoint:.4f}, error {error:+.4f}")
