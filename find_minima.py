
import statistics

from scipy.signal import savgol_filter, find_peaks

POLYORDER = 2

# How deep a valley has to be to count, as a fraction of the depth of the
# whole fringe pattern. Relative rather than absolute, because TE:DC scales
# with the output power of the laser: an absolute threshold that works at
# one power silently starts discarding real valleys at half that power.
#
# The setting is not delicate. In five scans the real valleys came out
# around 0.7 of the pattern depth and the spurious ones around 0.002, so
# anything from 0.01 to 0.60 gave the same five valleys.
MIN_PROMINENCE_FRACTION = 0.15

# Narrow enough to be safe whatever the scan step, wide enough to remove the
# one and two sample bumps left by the ADC. Only used for the first pass,
# which just has to be good enough to measure the fringe period.
SAFE_WINDOW = 7


def smooth_curve(values, window_length, polyorder=POLYORDER):
    return savgol_filter(values, window_length, polyorder)


def window_for_period(period, step):
    samples_per_fringe = period / step
    window = int(samples_per_fringe / 4)

    if window % 2 == 0:
        window += 1
    return max(5, window)


def minima_indices(values, window_length, polyorder, min_prominence_fraction,
                    edge_margin):
    smoothed = smooth_curve(values, window_length, polyorder)
    inverted = [-i for i in smoothed]

    pattern_depth = max(smoothed) - min(smoothed)
    min_prominence = min_prominence_fraction * pattern_depth

    indices, properties = find_peaks(inverted, prominence=min_prominence)

    last_index = len(values) - 1 - edge_margin
    result = []

    for index in indices:
        if edge_margin <= index <= last_index:
            result.append(int(index))

    return result


def find_minima(positions, values, polyorder=POLYORDER, min_prominence_fraction=MIN_PROMINENCE_FRACTION,window_length=None):
    if window_length is None:
        step = positions[1] - positions[0]

        first_pass = minima_indices(values, SAFE_WINDOW, polyorder,
                                     min_prominence_fraction, SAFE_WINDOW // 2)
        period = fringe_period(positions, first_pass)
        window_length = window_for_period(period, step)

    return minima_indices(values, window_length, polyorder,
                           min_prominence_fraction, window_length // 2)


def fringe_period(positions, indices):
  
    if len(indices) < 2:
        raise ValueError(
            f"Need at least two minima to measure a period, got {len(indices)}")

    gaps = []

    for i in range(len(indices) - 1):
        a = indices[i]
        b = indices[i + 1]
        gaps.append(positions[b] - positions[a])

    return statistics.median(gaps)
