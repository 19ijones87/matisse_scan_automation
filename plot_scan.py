"""
plot_scan.py

Plots a thin etalon scan recorded by thin_etalon_scan.py.

Both signals are drawn on the same axes, since they correspond to the two
traces shown in the Thin Etalon > Scan window of Matisse Commander: the
reflex intensity of the etalon and the total output power of the laser.
Comparing the two makes it easy to see whether a feature in the fringe
pattern comes from the etalon or merely follows a drift in laser power.

This script is meant to be run on an ordinary machine rather than on the
lab computer, which has no matplotlib installed and no internet
connection to install it from. The CSV file is what travels between the
two.

Usage:
    python plot_scan.py thin_etalon_scan_20260728_160121.csv

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-28
"""

import sys
import csv
import matplotlib.pyplot as plt

filename = sys.argv[1]

positions = []
te_values = []
dpow_values = []

with open(filename, newline="") as f:
    reader = csv.reader(f)
    next(reader)                          # basligi atla
    for row in reader:
        positions.append(int(row[0]))     
        te_values.append(float(row[1]))  
        dpow_values.append(float(row[2])) 

plt.figure(figsize=(10, 4))
plt.plot(positions, te_values, ".-",linewidth=1, markersize=3, label="TE:DC (reflex)")
plt.plot(positions, dpow_values, ".-", linewidth=1, markersize=3, label="DPOW:DC (power)")
plt.xlabel("Thin etalon motor position")
plt.ylabel("volts")
plt.title(filename)
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()