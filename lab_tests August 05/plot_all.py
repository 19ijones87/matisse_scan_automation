"""
plot_all.py

Draws several thin etalon scans one above the other, so that they can be
compared at a glance.

plot_scan.py shows a single scan. This one takes any number of CSV files on
the command line and gives each of them its own panel, with a shared
vertical axis so that the curves can be compared by eye. Each panel carries
the raw reading, the smoothed curve, the minima that find_minima found and
the fringe period measured from them.

It was written to answer two questions that a single scan cannot settle. The
first is whether the analysis behaves the same way on scans taken at
different times and at different motor positions, since the fringe period
changes with position and the output power changes with the state of the
laser. The second is how far the reported valley positions move from one
scan to the next, which decides whether it is worth fitting a parabola to
each valley to get a better estimate than the sampling interval allows.

This runs on a desk, not in the laboratory. It needs matplotlib and touches
nothing but the files it is given.

Usage:
    python plot_all.py datas/*.csv
    python plot_all.py scan_a.csv scan_b.csv

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-08-01
"""

import sys
import csv

import matplotlib.pyplot as plt

from find_minima import smooth_curve, find_minima, fringe_period

WINDOW_LENGTH = 9

filenames = sys.argv[1:]

figure, axes = plt.subplots(len(filenames), 1,
                            figsize=(12, 2.6 * len(filenames)),
                            sharey=True)
if len(filenames) == 1:
    axes = [axes]

for axis, filename in zip(axes, filenames):
    positions = []
    te_values = []

    with open(filename, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            positions.append(int(row[0]))
            te_values.append(float(row[1]))

    smoothed = smooth_curve(te_values, WINDOW_LENGTH)
    minima = find_minima(positions, te_values, window_length=WINDOW_LENGTH)
    period = fringe_period(positions, minima)

    axis.plot(positions, te_values, ".-", linewidth=0.8, markersize=3,
              color="0.75", label="ham")
    axis.plot(positions, smoothed, "-", linewidth=1.6, color="tab:blue",
              label=f"savgol w={WINDOW_LENGTH}")
    axis.plot([positions[i] for i in minima],
              [smoothed[i] for i in minima],
              "v", markersize=11, color="tab:red",
              label=f"minima ({len(minima)})")

    for index in minima:
        axis.annotate(str(positions[index]), (positions[index], smoothed[index]),
                      textcoords="offset points", xytext=(0, -16),
                      ha="center", fontsize=7)

    axis.set_title(f"{filename}   —   periyot {period:.0f} adim",
                   fontsize=9, loc="left")
    axis.set_ylabel("TE:DC")
    axis.legend(loc="lower right", fontsize=8)
    axis.grid(alpha=0.3)

axes[-1].set_xlabel("Thin etalon motor position")

plt.tight_layout()
plt.show()
