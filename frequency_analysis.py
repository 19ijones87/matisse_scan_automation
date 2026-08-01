WINDOW_STEP_GHZ = 17.0
WINDOW_STEP_TOLERANCE_GHZ = 5.0

def verify_window_step(frequency_before, frequency_after, expected_within_range_ghz=WINDOW_STEP_GHZ, tolerance_ghz=WINDOW_STEP_TOLERANCE_GHZ):
    if frequency_before is None or frequency_after is None:
        raise RuntimeError(f"Cannot verify the window step without a frequency reading: "f"before={frequency_before}, after={frequency_after}")
    difference_f_thz = frequency_after - frequency_before 
    difference_f_ghz = difference_f_thz * 1000
    if abs(abs(difference_f_ghz)-expected_within_range_ghz) > tolerance_ghz:
        raise RuntimeError(f"Expected a window step of {expected_within_range_ghz} ± {tolerance_ghz} GHz "f"but got: {difference_f_ghz:+.2f} GHz")
    return difference_f_ghz

