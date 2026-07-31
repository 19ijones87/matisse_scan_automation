"""
matisse_locking.py

Reads and controls the frequency-selective elements of the Matisse over
the Matisse Commander TCP interface, using the low-level framing from
matisse_client.py.

The module covers three groups of operations:

- Queries on the scan piezo and the piezo etalon (scan limits, scan mode,
  scan device, current piezo position), together with a routine that
  returns both piezos to the position a scan is expected to start from.
- Queries on the thin etalon: the motor position and its upper bound, the
  motor controller status word, the intensity of the etalon reflex, and
  the total output power of the laser.
- Driving the thin etalon motor and scanning it across a range, which is
  the software equivalent of the Thin Etalon > Scan window in Matisse
  Commander. That window cannot be reached over TCP, so the scan is
  rebuilt here: the motor is stepped through the range and both diodes
  are read once the motor has come to rest at each step.

Together these form the groundwork for automating the locking procedure
that is normally carried out by hand in the GUI. Before a scan can be
started in a new frequency window, the piezos have to be brought back to
a known starting position, and the thin and piezo etalons have to be
re-locked to the mode selected by the birefringent filter.

Positions of the scan piezo are given in the [0, 0.7] interval used by
Matisse Commander; the piezo etalon baseline is in [-1, 1]. Thin etalon
motor positions are integers bounded by MOTTE:MAX?.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-28
"""

import time
import logging
import matisse_client as mc

logger = logging.getLogger(__name__)

SCAN_POSITION_MIN = 0.0
SCAN_POSITION_MAX = 0.7
VALID_SCAN_MODES = (1, 2, 4, 8, 16, 32, 64, 128)

# Bits of the MOTTE:STA? status word we care about.
MOTOR_ERROR_BIT = 1 << 7      # 128 -- controller is in an error state
MOTOR_RUNNING_BIT = 1 << 8    # 256 -- motor is still moving

_thin_etalon_max = None


def get_piezo_position(sock):
    command = "SPZT:NOW?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    logger.debug(f"Raw response: {respond!r}") #!!!
    respond_splitted_list = respond.split()
    position_value = respond_splitted_list[-1]

    position_value_float = float(position_value)
    if position_value_float < SCAN_POSITION_MIN or position_value_float > SCAN_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {position_value_float}")
    return position_value_float


def get_scan_lower_limit(sock):
    command = "SCAN:LLM?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    logger.debug(f"Raw response: {respond!r}") #!!!
    respond_splitted_list = respond.split()
    lower_limit = respond_splitted_list[-1]

    lower_limit_float = float(lower_limit)
    if lower_limit_float < SCAN_POSITION_MIN or lower_limit_float > SCAN_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {lower_limit_float}")
    return lower_limit_float

def reset_piezo_positions(sock):
    command = "PZETL:BASE 0"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond!r}") #!!!
    if respond != "OK":
        raise RuntimeError(f"Expected 'OK' but got: {respond}")

    lower_limit = get_scan_lower_limit(sock)
    command_low_limit = "SPZT:NOW {:.4f}".format(lower_limit)
    mc.send_command(sock, command_low_limit)

    respond_limit = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond_limit!r}") #!!!
    if respond_limit != "OK":
        raise RuntimeError(f"Expected 'OK' but got: {respond_limit}")

    logger.info("Piezo positions reset to scan starting position")
    
def get_scan_upper_limit(sock):
    command = "SCAN:ULM?"
    mc.send_command(sock, command)

    respond = mc.receive_response(sock)
    logger.debug(f"Raw response: {respond!r}") #!!!
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")

    respond_splitted_list = respond.split()
    upper_limit = respond_splitted_list[-1]
    upper_limit_float = float(upper_limit)

    if upper_limit_float < SCAN_POSITION_MIN or upper_limit_float > SCAN_POSITION_MAX:
        raise RuntimeError(f"Expected a position in [0, 0.7] but got: {upper_limit_float}")
    return upper_limit_float

def get_scan_mode(sock):
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

def get_scan_device(sock):
    command = "SCAN:DEV?"
    mc.send_command(sock, command)
    
    respond = mc.receive_response(sock)
    if respond.startswith("!ERROR"):
        raise RuntimeError(f"Matisse returned an error: {respond}")
    respond_splitted_list = respond.split()
    #0 = None, 1 = slow cavity piezo, 2 = reference cell piezo
    scan_device_num = int(respond_splitted_list[-1])

    if scan_device_num < 0 or scan_device_num > 2:
        raise RuntimeError("Invalid device")
    return scan_device_num


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

    while True:
        motor_status = get_motor_status(sock)

        if motor_status & MOTOR_ERROR_BIT:
            raise RuntimeError(f"Thin etalon motor is in an error state, status: {motor_status}")

        if not (motor_status & MOTOR_RUNNING_BIT):
            return

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