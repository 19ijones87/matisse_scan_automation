"""
Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-08-04
"""

import os
import sys
import time
import logging
import argparse

import matisse_client as mc
import thin_etalon as te
import piezo_etalon as pe
import slow_piezo as sp
import scan
import find_minima as fm
import wavemeter_client
import frequency_analysis as fa

MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

WAVEMETER_CHANNEL = 7
PIEZO_SETTLE_TIME = 0.5

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s, %(levelname)s, %(message)s")
logger = logging.getLogger(__name__)


class WindowStepFailed(RuntimeError):
    pass


def require_locks_running_status(sock):
    thin_etalon_status = te.get_thin_etalon_lock_status(sock)
    piezo_etalon_status = pe.get_piezo_etalon_lock_status(sock)
    logger.info(f"Thin etalon {thin_etalon_status}, "
                f"piezo etalon {piezo_etalon_status}")
    if thin_etalon_status != "RUN" or piezo_etalon_status != "RUN":
        raise WindowStepFailed(f"both locks must be running: thin etalon "
                               f"{thin_etalon_status}, piezo etalon "
                               f"{piezo_etalon_status}")


def scan_and_lock(sock, flank, fraction, span, step, target, direction=None):
    if target not in ("neighbour", "current"):
        raise ValueError("target must be 'neighbour' or 'current'")
    if target == "neighbour" and direction is None:
        raise ValueError("a neighbouring minimum needs a direction")

    thin_etalon_motor_start = te.get_thin_etalon_position(sock)

    te.unlock_thin_etalon(sock)
    pe.unlock_piezo_etalon(sock)

    scan_lower_limit = scan.get_lower_limit(sock)
    sp.set_position(sock, scan_lower_limit)
    logger.info(f"Slow piezo set to the scan lower limit {scan_lower_limit}")

    pe.set_baseline(sock, 0.0)
    time.sleep(PIEZO_SETTLE_TIME)

    scan_start = thin_etalon_motor_start - span // 2
    scan_stop = thin_etalon_motor_start + span // 2
    logger.info(f"Thin etalon at motor {thin_etalon_motor_start}, "
                f"scanning {scan_start} -> {scan_stop}, step {step}")

    samples = te.scan_thin_etalon(sock, scan_start, scan_stop, step)
    positions = [row[0] for row in samples]
    te_values = [row[1] for row in samples]

    minima_indices = fm.find_minima(positions, te_values)
    period = fm.fringe_period(positions, minima_indices)
    window_length = fm.window_for_period(period, step)
    maxima_indices = fm.find_maxima(positions, te_values,
                                    window_length=window_length)

    logger.info(f"{len(minima_indices)} minima: "
                f"{[positions[i] for i in minima_indices]}")
    logger.debug(f"{len(maxima_indices)} maxima: "
                 f"{[positions[i] for i in maxima_indices]}")
    logger.info(f"Fringe period {period:.0f} steps, window {window_length}")

    current_index = fm.current_minimum(positions, minima_indices,
                                       thin_etalon_motor_start)

    if target == "neighbour":
        chosen_index = fm.neighbour_minimum(minima_indices, current_index,
                                            direction)
        logger.info(f"Current minimum {positions[current_index]}, "
                    f"{direction} neighbour {positions[chosen_index]}")
    else:
        chosen_index = current_index
        logger.info(f"Staying on the current minimum {positions[current_index]}")

    lock_position = fm.pick_lock_point(positions, maxima_indices,
                                       chosen_index, flank, fraction)

    te.set_thin_etalon_position(sock, lock_position)
    te.wait_for_motor(sock)
    thin_etalon_motor_arrived = te.get_thin_etalon_position(sock)

    te.lock_thin_etalon(sock, flank)
    pe.lock_piezo_etalon(sock)
    thin_etalon_motor_settled = te.get_thin_etalon_position(sock)

    logger.info(f"Thin etalon motor: lock point {lock_position}, "
                f"arrived {thin_etalon_motor_arrived}, "
                f"settled {thin_etalon_motor_settled}")

    return {
        "thin_etalon_motor_start": thin_etalon_motor_start,
        "thin_etalon_lock_position": lock_position,
        "thin_etalon_motor_arrived": thin_etalon_motor_arrived,
        "thin_etalon_motor_settled": thin_etalon_motor_settled,
        "fringe_period": period,
        "minima": [positions[i] for i in minima_indices],
    }


def step_to_next_window(sock, direction, flank, fraction, span, step):
    require_locks_running_status(sock)

    frequency_before = wavemeter_client.get_frequency(WAVEMETER_CHANNEL)
    slow_piezo_before = sp.get_position(sock)

    result = scan_and_lock(sock, flank, fraction, span, step,
                           target="neighbour", direction=direction)

    frequency_after = wavemeter_client.get_frequency(WAVEMETER_CHANNEL)
    slow_piezo_after = sp.get_position(sock)

    if abs(slow_piezo_after - slow_piezo_before) > 1e-4:
        logger.warning(f"Slow piezo moved from {slow_piezo_before} to "
                       f"{slow_piezo_after}, the frequency difference "
                       f"contains that move as well")

    step_ghz = fa.verify_window_step(frequency_before, frequency_after)
    logger.info(f"Window step {step_ghz:+.2f} GHz")

    result["frequency_before"] = frequency_before
    result["frequency_after"] = frequency_after
    result["step_ghz"] = step_ghz
    return result


def acquire_locks(sock, flank, fraction, span, step):
    diode_power = te.get_diode_power(sock)
    if diode_power <= 0:
        raise WindowStepFailed(f"the laser is not lasing, DPOW:DC = {diode_power}")

    result = scan_and_lock(sock, flank, fraction, span, step, target="current")

    result["frequency"] = wavemeter_client.get_frequency(WAVEMETER_CHANNEL)
    logger.info(f"Locked at {result['frequency']} THz")
    return result


def main(matisse_host, direction, flank, fraction, span, step):
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    try:
        step_to_next_window(sock, direction, flank, fraction, span, step)
    finally:
        mc.disconnect_from_matisse(sock)
        logger.info(f"Disconnected from {matisse_host}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--direction", choices=("left", "right"),
                            required=True, help="which neighbouring valley")
        parser.add_argument("--flank", choices=("left", "right"),
                            required=True, help="which flank of that valley")
        parser.add_argument("--fraction", type=float, default=0.5,
                            help="0 = valley bottom, 1 = peak")
        parser.add_argument("--span", type=int, default=4000)
        parser.add_argument("--step", type=int, default=20)
        args = parser.parse_args()

        main(args.matisse_host, args.direction, args.flank, args.fraction,
             args.span, args.step)

    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)
