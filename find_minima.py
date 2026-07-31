"""
find_minima.py

Finds the transmission minima and maxima in a thin etalon scan and picks a
point on the flank of a chosen minimum to lock to.

The module holds no connection to the laser. It takes two plain lists, the
motor positions and the corresponding TE:DC readings, and returns positions
and indices. Keeping it free of sockets means it can be run on recorded CSV
files at a desk, which is how every function here was checked before it was
used in the laboratory.

A raw scan cannot be searched for minima directly. Three problems get in the
way, and the module answers each of them:

- The reading is quantised by the ADC, so the floor of a valley is flat and
  broken up by single-sample bumps. A naive search reports several minima
  where there is one. The curve is therefore smoothed with a Savitzky-Golay
  filter, which fits a low-order polynomial to a sliding window and, unlike
  a moving average, leaves the depth and the position of a valley alone.
- Noise produces shallow dips that look like valleys. Only dips deeper than
  a set fraction of the depth of the whole fringe pattern are kept. The
  threshold is relative rather than absolute because TE:DC scales with the
  output power of the laser, and an absolute threshold that works at one
  power silently starts discarding real valleys at half that power.
- The smoothing filter distorts both ends of the record, so any minimum
  found within half a window of an edge is dropped.

The width of the smoothing window has to match the scan. A window that is
too narrow leaves the ADC bumps in place, one that is too wide swallows the
valley itself. The right width depends on how many samples fall inside one
fringe, which depends in turn on the step size the scan was taken with and
on the fringe period, and the period is only known once the minima have been
found. find_minima therefore works in two passes: a first pass with a
deliberately narrow window that is safe at any step size, just good enough
to measure the period, and a second pass with the window that period
implies.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-08-01
"""

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


def minima_indices(values, window_length, polyorder, min_prominence_fraction, edge_margin):
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

def find_maxima(positions, values, polyorder=POLYORDER, min_prominence_fraction=MIN_PROMINENCE_FRACTION, window_length=None):

    inverted = [-value for value in values]
    return find_minima(positions, inverted, polyorder, min_prominence_fraction, window_length)


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


def current_minimum(positions, minima_indices, current_position):

    current_minimum_index = minima_indices[0]
    best_distance = abs(positions[current_minimum_index] - current_position)

    for index in minima_indices[1:]:
        distance = abs(positions[index] - current_position)

        if distance < best_distance:
            current_minimum_index = index
            best_distance = distance

    return current_minimum_index


def neighbour_minimum(minima_indices, current_minimum_index, direction):
    order = minima_indices.index(current_minimum_index)

    if direction == "left":
        order -= 1
    elif direction == "right":
        order += 1
    else:
        raise ValueError("direction must be 'left' or 'right'")

    if order < 0 or order >= len(minima_indices):
        raise RuntimeError(f"No valley to the {direction} in this scan")

    return minima_indices[order]

def pick_lock_point(positions, maximum_indices, minima_index, flank, fraction=0.5):

    maxima_index = None

    if flank == "right":
        for index in maximum_indices:
            if index > minima_index:
                maxima_index = index
                break

    elif flank == "left":
        for index in maximum_indices:
            if index < minima_index:
                maxima_index = index

    else:
        raise ValueError("flank must be 'left' or 'right'")

    if maxima_index is None:
        raise RuntimeError(f"No peak on the {flank} of {positions[minima_index]}")

    minima_position = positions[minima_index]
    maxima_position = positions[maxima_index]

    locking_position = int(round(minima_position + fraction * (maxima_position - minima_position)))
    return locking_position
