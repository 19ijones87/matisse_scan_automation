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

