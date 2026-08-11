
import os
import sys
import time
import logging
import argparse

import matisse_client as mc
import thin_etalon as te
import slow_piezo as sp
import scan_device as sd
import step_to_next_window as sw

MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

SCAN_DEVICE_SLOW_PIEZO = 1
SCAN_DEVICE_NONE = 0

PIEZO_RETURN_TOLERANCE = 0.02
PIEZO_RETURN_TIMEOUT = 15.0

WINDOW_STEP_GHZ = 16.8
SKIP_THRESHOLD_WINDOWS = 1.5

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S",
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("test_piezo_return.log")])
logger = logging.getLogger(__name__)


def wait_for_piezo_at_lower_limit(sock):
    lower_limit = sd.get_lower_limit(sock)
    start_time = time.time()

    while True:
        position = sp.get_position(sock)

        if abs(position - lower_limit) <= PIEZO_RETURN_TOLERANCE:
            logger.info(f"Slow piezo back at {position:.4f} after "
                        f"{time.time() - start_time:.1f} s")
            return position

        if time.time() - start_time > PIEZO_RETURN_TIMEOUT:
            logger.warning(f"Slow piezo did not return to {lower_limit} within "
                           f"{PIEZO_RETURN_TIMEOUT} s, last position {position:.4f}")
            return position

        time.sleep(0.02)


def one_cycle(sock, scan_seconds, wait_for_limit, use_gate,
              direction, flank, fraction, span, step):
    sd.set_device(sock, SCAN_DEVICE_NONE)
    lock = sw.acquire_locks(sock, flank, fraction, span, step)

    motor_before = lock["motor_settled"]
    minimum_before = lock["minimum"]
    period = lock["fringe_period"]

    sd.set_device(sock, SCAN_DEVICE_SLOW_PIEZO)
    sd.start(sock)
    logger.info(f"Scanning for {scan_seconds} s")
    time.sleep(scan_seconds)

    if wait_for_limit:
        wait_for_piezo_at_lower_limit(sock)

    piezo_at_stop = sp.get_position(sock)
    sd.stop(sock)
    sd.set_device(sock, SCAN_DEVICE_NONE)

    motor_after = te.get_thin_etalon_position(sock)
    drift = motor_after - motor_before

    logger.info(f"piezo at stop     {piezo_at_stop:.4f}")
    logger.info(f"motor {motor_before} -> {motor_after}   drift {drift:+d} steps  "
                f"(period {period:.0f}, half {period / 2:.0f})")

    step_ghz = None
    gate_fired = False
    try:
        step_result = sw.step_to_next_window(
            sock, direction, flank, fraction, span, step,
            previous_minimum=minimum_before if use_gate else None)
        step_ghz = step_result["step_ghz"]
    except sw.WindowStepFailed as e:
        gate_fired = True
        logger.warning(f"gate fired: {e}")

    windows_moved = None
    if step_ghz is not None:
        windows_moved = abs(step_ghz) / WINDOW_STEP_GHZ
        verdict = "ok" if windows_moved < SKIP_THRESHOLD_WINDOWS else "SKIPPED A WINDOW"
        logger.info(f"step {step_ghz:+.2f} GHz  ->  {windows_moved:.2f} windows")
        logger.info(f"verdict           {verdict}")

    return {"drift": drift,
            "period": period,
            "piezo_at_stop": piezo_at_stop,
            "step_ghz": step_ghz,
            "windows_moved": windows_moved,
            "gate_fired": gate_fired}


def main(matisse_host, cycles, scan_seconds, wait_for_limit, use_gate,
         direction, flank, fraction, span, step):
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info(f"Connected to {matisse_host}:{MATISSE_PORT}")
    logger.info(f"wait_for_limit = {wait_for_limit}, use_gate = {use_gate}, "
                f"scan_seconds = {scan_seconds}")

    results = []
    try:
        for cycle_index in range(cycles):
            logger.info(f"===== cycle {cycle_index + 1} / {cycles} =====")
            results.append(one_cycle(sock, scan_seconds, wait_for_limit, use_gate,
                                     direction, flank, fraction, span, step))
    finally:
        sd.set_device(sock, SCAN_DEVICE_NONE)
        mc.disconnect_from_matisse(sock)
        logger.info(f"Disconnected from {matisse_host}")

        if results:
            drifts = [r["drift"] for r in results]
            steps_ghz = [r["step_ghz"] for r in results if r["step_ghz"] is not None]
            gates = [r for r in results if r["gate_fired"]]
            skipped = [r for r in results if r["windows_moved"] is not None
                       and r["windows_moved"] >= SKIP_THRESHOLD_WINDOWS]

            logger.info("--- summary ---")
            logger.info(f"cycles            {len(results)}")
            logger.info(f"drifts            {drifts}")
            logger.info(f"largest drift     {max(drifts, key=abs):+d} steps")
            logger.info(f"steps GHz         {[round(s, 2) for s in steps_ghz]}")
            logger.info(f"skipped windows   {len(skipped)} / {len(steps_ghz)}")
            logger.info(f"gate fired        {len(gates)} / {len(results)}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--cycles", type=int, default=5)
        parser.add_argument("--scan-seconds", type=float, default=35.0)
        parser.add_argument("--wait-for-limit", action="store_true")
        parser.add_argument("--use-gate", action="store_true")
        parser.add_argument("--direction", choices=("left", "right"), default="left")
        parser.add_argument("--flank", choices=("left", "right"), default="left")
        parser.add_argument("--fraction", type=float, default=0.5)
        parser.add_argument("--span", type=int, default=4000)
        parser.add_argument("--step", type=int, default=20)
        args = parser.parse_args()

        main(args.matisse_host, args.cycles, args.scan_seconds,
             args.wait_for_limit, args.use_gate, args.direction,
             args.flank, args.fraction, args.span, args.step)

    except Exception as e:
        logger.exception(f"{type(e).__name__}: {e}")
        sys.exit(1)
