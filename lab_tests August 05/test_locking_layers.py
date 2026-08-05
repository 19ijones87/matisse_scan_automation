
import os
import sys
import time
import argparse

import matisse_client as mc
import thin_etalon as te

MATISSE_HOST = os.environ.get("MATISSE_HOST", "127.0.0.1")
MATISSE_PORT = 30000

SETTLE_SAMPLE_TIMES = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0)
"""
Test 1   difference  0.000xxx      küçük olmalı (TE:CNTRERR formüle uyuyor)
Test 2   iki farklı sayı           donmuş/sıfır değil
Test 3   left -> -200/-4           GUI'de de Left yazmalı
         right -> +200/+4          GUI'de de Right yazmalı
Test 4   moved +0 steps            motor kıpırdamamalı
         lock status RUN
         error küçük               0.05'in çok altında
Test 5   hata azalan bir tablo     0.1 sn'de oturuyorsa iyi

"""


def pause(text):
    print()
    print("-" * 70)
    print(text)
    answer = input("Enter to continue, q to stop: ")
    if answer.strip().lower() == "q":
        raise KeyboardInterrupt
    print()


def read_all(sock):
    values = {
        "MOTTE:POS": te.get_thin_etalon_position(sock),
        "TE:CNTRSTA": te.get_thin_etalon_lock_status(sock),
        "TE:CNTRPROP": te.get_control_proportional(sock),
        "TE:CNTRINT": te.get_control_integral(sock),
        "TE:CNTRSP": te.get_control_setpoint(sock),
        "TE:CNTRERR": te.get_control_error(sock),
        "TE:DC": te.get_thin_etalon_dc(sock),
        "DPOW:DC": te.get_diode_power(sock),
    }
    for name, value in values.items():
        print(f"   {name:<14} {value}")
    return values


def test_1_read_only(sock):
    pause("TEST 1 - reading every control value\n"
          "Nothing is written. Confirms that the new getters work.")

    values = read_all(sock)

    ratio = values["TE:DC"] / values["DPOW:DC"]
    expected_error = values["TE:CNTRSP"] - ratio

    print()
    print(f"   ratio TE:DC / DPOW:DC        {ratio:.6f}")
    print(f"   TE:CNTRSP - ratio            {expected_error:+.6f}")
    print(f"   TE:CNTRERR as reported       {values['TE:CNTRERR']:+.6f}")
    print(f"   difference                   {abs(expected_error - values['TE:CNTRERR']):.6f}")
    print()
    print("   The last two should agree. If they do, TE:CNTRERR is the error")
    print("   of the documented formula and can be trusted.")

    return values


def test_2_error_when_unlocked(sock):
    pause("TEST 2 - what TE:CNTRERR reports while the loop is stopped\n"
          "The lock is released and the error read again. The motor stays\n"
          "where it is.")

    before = te.get_control_error(sock)
    status_before = te.get_thin_etalon_lock_status(sock)
    print(f"   lock {status_before}, TE:CNTRERR {before:+.6f}")

    if status_before == "RUN":
        te.unlock_thin_etalon(sock)
        time.sleep(0.5)

    after = te.get_control_error(sock)
    print(f"   lock STOP, TE:CNTRERR {after:+.6f}")
    print()
    print("   Still changing with the laser  -> the reading is live")
    print("   Frozen or zero                 -> it is only valid while locked,")
    print("                                     and the settle wait matters")


def test_3_flank_orientation(sock, flank):
    pause("TEST 3 - set_flank_orientation\n"
          "Open Thin Etalon > Control Setup in Matisse Commander and watch\n"
          "the Flank Orientation setting. The motor is not touched.")

    for wanted in ("left", "right", flank):
        te.set_flank_orientation(sock, wanted)
        proportional = te.get_control_proportional(sock)
        integral = te.get_control_integral(sock)
        print(f"   asked for {wanted:<5}  ->  "
              f"TE:CNTRPROP {proportional:+.1f}, TE:CNTRINT {integral:+.1f}")
        input(f"   Does Matisse Commander show {wanted.capitalize()}? Enter: ")

    print()
    print(f"   Left ended as a negative sign and right as a positive one,")
    print(f"   matching the reading taken on 2026-07-31.")


def test_4_lock_in_place(sock, flank):
    pause("TEST 4 - lock_thin_etalon without moving the motor\n"
          "The lock is closed again where the etalon already sits. This is\n"
          "the whole of layer 8 on its own, with no scan and no analysis.")

    if te.get_thin_etalon_lock_status(sock) == "RUN":
        te.unlock_thin_etalon(sock)
        time.sleep(0.5)

    position_before = te.get_thin_etalon_position(sock)
    te.lock_thin_etalon(sock, flank)
    position_after = te.get_thin_etalon_position(sock)

    print()
    print(f"   motor before {position_before}, after {position_after}, "
          f"moved {position_after - position_before:+d} steps")
    print(f"   lock status  {te.get_thin_etalon_lock_status(sock)}")
    print()
    print("   The laser should be running as it was, at the same frequency.")
    print("   A large motor movement means the setpoint was written wrongly.")


def test_5_settle_time(sock, flank):
    pause("TEST 5 - how long the loop takes to settle\n"
          "The lock is released and closed again while the error is sampled.\n"
          "This is the measurement LOCK_SETTLE_TIME is guessed from.")

    if te.get_thin_etalon_lock_status(sock) == "RUN":
        te.unlock_thin_etalon(sock)
        time.sleep(0.5)

    te_dc = te.get_thin_etalon_dc(sock)
    dpow = te.get_diode_power(sock)
    te.set_control_setpoint(sock, te_dc / dpow)
    te.set_flank_orientation(sock, flank)

    command = "TE:CNTRSTA RUN"
    mc.send_command(sock, command)
    if mc.receive_response(sock) != "OK":
        raise RuntimeError(f"{command} was refused")

    start_time = time.time()
    print()
    print(f"   {'t (s)':>7}  {'TE:CNTRERR':>12}")
    for sample_time in SETTLE_SAMPLE_TIMES:
        while time.time() - start_time < sample_time:
            time.sleep(0.005)
        print(f"   {time.time() - start_time:>7.3f}  "
              f"{te.get_control_error(sock):>+12.6f}")

    print()
    print(f"   Settled within 0.1 s  -> LOCK_SETTLE_TIME can come down")
    print(f"   Still moving at 2.0 s -> raise it, and ask why")
    print(f"   A jump at the first sample -> the integrator kept its old")
    print(f"                                 value through the stop")


def main(matisse_host, flank, wanted_tests):
    sock = mc.connect_to_matisse(matisse_host, MATISSE_PORT)
    print(f"Connected to {matisse_host}\n")

    saved = None
    try:
        saved = {
            "proportional": te.get_control_proportional(sock),
            "integral": te.get_control_integral(sock),
            "setpoint": te.get_control_setpoint(sock),
        }
        print("Saved the values found in the machine, to be written back "
              "at the end:")
        for name, value in saved.items():
            print(f"   {name:<14} {value}")

        tests = {
            1: lambda: test_1_read_only(sock),
            2: lambda: test_2_error_when_unlocked(sock),
            3: lambda: test_3_flank_orientation(sock, flank),
            4: lambda: test_4_lock_in_place(sock, flank),
            5: lambda: test_5_settle_time(sock, flank),
        }

        for number in sorted(wanted_tests):
            tests[number]()

        pause(f"Tests {sorted(wanted_tests)} are done.")

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        if saved is not None:
            print("\nWriting the original values back:")
            te.set_control_proportional(sock, saved["proportional"])
            te.set_control_integral(sock, saved["integral"])
            te.set_control_setpoint(sock, saved["setpoint"])
            for name, value in saved.items():
                print(f"   {name:<14} {value}")
            print("\nThe thin etalon lock is left as the last test set it. "
                  "Check it in Matisse Commander.")
        mc.disconnect_from_matisse(sock)
        print(f"Disconnected from {matisse_host}")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--matisse-host", default=MATISSE_HOST)
        parser.add_argument("--flank", choices=("left", "right"),
                            default="left",
                            help="the flank the laser should be left on")
        parser.add_argument("--tests", default="1,2,3,4,5",
                            help="which tests to run, e.g. --tests 3,4")
        args = parser.parse_args()

        wanted_tests = {int(piece) for piece in args.tests.split(",")}
        if not wanted_tests <= {1, 2, 3, 4, 5}:
            raise ValueError(f"--tests must be chosen from 1..5, got {args.tests}")

        main(args.matisse_host, args.flank, wanted_tests)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)
