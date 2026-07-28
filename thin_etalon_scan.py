"""
thin_etalon_scan.py

Records a thin etalon scan and writes it to a CSV file, so that the
fringe pattern can be plotted and analysed away from the lab computer.

The script reads the current motor position, scans a symmetric range
around it, and puts the motor back where it found it. Leaving the motor
at the end of the scan would be a problem twice over: the wavelength the
operator had set up would be lost, and because the scan range is derived
from the current position, every further run would drift another half
span away.

Each measurement is stored together with the raw readings it came from:

    motor_position, te_dc, dpow_dc

The reflex intensity alone would be enough to locate the fringes, but the
thin etalon control loop works on the ratio of the two, so the output
power is recorded as well. It costs one column and makes it possible to
tell later which of the two signals misbehaved.

The thin etalon lock has to be released before running this. While the PI
loop is active it pulls the motor back as the scan moves it, and the
resulting data is meaningless — without any error being raised.

Usage:
    python thin_etalon_scan.py
    python thin_etalon_scan.py --matisse-host <lab-computer-ip>
    python thin_etalon_scan.py --span 4000 --step 20

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-28
"""

import matisse_client as mc
import matisse_locking as ml
import os, sys, csv, logging, argparse
from datetime import datetime


MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

logging.basicConfig(level=logging.INFO, format="%(asctime)s, %(levelname)s, %(message)s", 
                    handlers=[logging.StreamHandler(), logging.FileHandler("thin_etalon_scan.log")])
logger = logging.getLogger(__name__)

def save_scan(samples, filename):
    with open(filename,"w",newline = "") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["motor_position", "te_dc", "dpow_dc"])
        writer.writerows(samples)


def main(matisse_host, span, step):
    logger.info(f"Connecting to Matisse at {matisse_host}:{MATISSE_PORT}")
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    logger.info("Connection established")

    try:
        current_motor_position = ml.get_thin_etalon_position(sock)
        start = current_motor_position - span//2
        stop = current_motor_position + span//2
        samples = ml.scan_thin_etalon(sock, start, stop, step)
        filename = datetime.now().strftime("thin_etalon_scan_%Y%m%d_%H%M%S.csv")
        save_scan(samples, filename)
        logger.info(f"Saved {len(samples)} samples to {filename}")
        ml.set_thin_etalon_position(sock, current_motor_position)
        ml.wait_for_motor(sock)
    finally:
        mc.disconnect_from_matisse(sock)
       
        logger.info(f"Disconnected from {matisse_host}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--span", type=int, default=4000)
        parser.add_argument("--step", type=int, default=20)
        args = parser.parse_args()

        main(args.matisse_host, args.span, args.step)
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        sys.exit(1)

