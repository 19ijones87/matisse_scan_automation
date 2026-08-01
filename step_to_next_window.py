"""
Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-08-01
"""

import os
import sys
import logging
import argparse

import matisse_client as mc
import matisse_locking as ml
import find_minima as fm

MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s, %(levelname)s, %(message)s")
logger = logging.getLogger(__name__)


def main(matisse_host, direction, flank, fraction, span, step):
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    try:
        lock_status = ml.get_thin_etalon_lock_status(sock)
        start_position = ml.get_thin_etalon_position(sock)
        setpoint_before = ml.get_control_setpoint(sock)

        logger.info(f"Thin etalon lock: {lock_status}")
        logger.info(f"Thin etalon position: {start_position}")
        logger.info(f"Control setpoint: {setpoint_before:.6f}")

        if lock_status == "RUN":
            ml.unlock_thin_etalon(sock)

        scan_start = start_position - span // 2
        scan_stop = start_position + span // 2
        logger.info(f"Scanning {scan_start} -> {scan_stop}, step {step}")

        samples = ml.scan_thin_etalon(sock, scan_start, scan_stop, step)

        positions = [row[0] for row in samples]
        te_values = [row[1] for row in samples]

        minima_indices = fm.find_minima(positions, te_values)
        period = fm.fringe_period(positions, minima_indices)
        window_length = fm.window_for_period(period, step)
        maxima_indices = fm.find_maxima(positions, te_values,
                                        window_length=window_length)

        logger.info(f"{len(minima_indices)} minima: "
                    f"{[positions[i] for i in minima_indices]}")
        logger.info(f"{len(maxima_indices)} maxima: "
                    f"{[positions[i] for i in maxima_indices]}")
        logger.info(f"Fringe period {period:.0f} steps, window {window_length}")

        current_index = fm.current_minimum(positions, minima_indices,
                                           start_position)
        next_index = fm.neighbour_minimum(minima_indices, current_index,
                                          direction)
        lock_position = fm.pick_lock_point(positions, maxima_indices,
                                           next_index, flank, fraction)

        logger.info(f"Current minima {positions[current_index]}, "
                    f"{direction} neighbour {positions[next_index]}, "
                    f"lock point {lock_position} ")

        ml.set_thin_etalon_position(sock, lock_position)
        ml.wait_for_motor(sock)
        logger.info(f"Motor at {ml.get_thin_etalon_position(sock)}")
        ml.lock_thin_etalon(sock, flank)



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
