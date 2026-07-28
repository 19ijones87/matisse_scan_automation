# Matisse Scan Automation

A set of small Python tools that drive a Sirah Matisse Ti:Sapphire laser
through the Matisse Commander software over raw TCP/IP, replacing work
that would otherwise be done by hand in the GUI.

The first part automates the "scan" command itself. It starts a scan,
reads the laser's actual frequency from a HighFinesse wavemeter while the
scan runs, and tracks the experimental image ID via LabServer. Whenever
the image ID changes (several images can be taken during one scan), it
uploads the mean frequency and frequency span measured during that image
to LabServer, tagged with the correct image ID.

The second part is concerned with the frequency-selective elements of the
laser. A scan only covers about 20 GHz, the free spectral range of the
thick etalon, and reaching the next window means moving the thin etalon
lock to the neighbouring transmission minimum and locking everything
again. The current stage of this work records the thin etalon fringe
pattern so that those minima can be located from the data.

Last updated: 2026-07-28


## Requirements

- Python 3
- No external dependencies for the Matisse/LabServer parts (uses only
  the Python standard library)
- Wavemeter reading (`wavemeter_client.py`) requires Windows and the
  HighFinesse `wlmData.dll`.
- Plotting (`plot_scan.py`) requires matplotlib. It is meant to be run on
  an ordinary machine rather than on the lab computer, which has neither
  matplotlib nor an internet connection to install it from.

## Files

- `matisse_client.py` — low-level TCP client for Matisse Commander: opens
  the connection and handles the length-prefixed message framing used to
  send commands and read responses.
- `matisse_locking.py` — reads and controls the frequency-selective
  elements: scan limits and piezo positions, thin etalon motor and diode
  signals, and a routine that scans the thin etalon motor across a range.
  The Thin Etalon > Scan window of Matisse Commander cannot be reached
  over TCP, so that scan is rebuilt here.
- `wavemeter_client.py` — reads laser frequency from the HighFinesse
  wavemeter (via `wlmData.py`/`wlmConst.py`), and computes mean/span
  statistics from a set of readings. Windows-only.
- `labserver_client.py` — TCP/IP client for the lab's shared LabServer:
  connects, looks up the current experimental image ID (either with a
  one-off request, or by subscribing to changes via SERVER_WAIT), and
  uploads data tagged under an image ID.
- `matisse_scan.py` — the main script. Connects to Matisse and
  LabServer, starts a scan, reads the wavemeter while tracking image ID
  changes, uploads mean/span frequency data per image, and disconnects.
- `thin_etalon_scan.py` — records a thin etalon scan around the current
  motor position and writes it to a timestamped CSV file, then returns
  the motor to where it started.
- `plot_scan.py` — plots a CSV written by `thin_etalon_scan.py`, showing
  the etalon reflex and the total power together.
- `wlmData.py` / `wlmConst.py` — HighFinesse's official Python wrapper
  for `wlmData.dll` (redistributed here under their permissive license).
- `LabServerDef.py` — the lab's shared LabServer protocol definition.
  **Not included in this repository** (it contains the real internal
  LabServer IP address) — copy it from the lab's shared files before
  running the LabServer-related parts of this project.

## Usage

By default, the script assumes Matisse Commander and LabServer are both
running on the same computer as the script (`127.0.0.1`), using their
standard ports (30000 for Matisse, 47123 for LabServer).

```
python3 matisse_scan.py
```

### Connecting from a different computer

If Matisse Commander or LabServer are running on another computer on the
lab network, you need to tell the script their IP addresses. There are
two ways to do this for each — pick whichever is more convenient:

**Option 1 — command-line flags:**

```
python3 matisse_scan.py --matisse-host <lab-computer-ip> --labserver-host <labserver-ip>
```

**Option 2 — environment variables** (useful if you always run the
script from the same computer and don't want to type the flags every
time; note that on Windows, `export` doesn't work — use `set VAR=value`
in Command Prompt, or `$env:VAR="value"` in PowerShell):

```
export MATISSE_HOST=<lab-computer-ip>
export LABSERVER_HOST=<labserver-ip>
python3 matisse_scan.py
```

Replace `<lab-computer-ip>` / `<labserver-ip>` with the actual IP
addresses. Real internal lab IP addresses are intentionally never
written in this repository (it's public), since anyone can see it — the
command-line flags are the most reliable way to supply them, on any
operating system.

### What you'll see

On a successful run, the script prints progress to the terminal and also
appends the same lines to `matisse_scan.log` (this file is not committed
to the repository, it's created locally on first run):

```
2026-07-21 12:00:00,000, INFO, Connecting to Matisse at 127.0.0.1:30000
2026-07-21 12:00:00,001, INFO, Connection established
2026-07-21 12:00:00,001, INFO, Scan started successfully!
2026-07-21 12:00:15,050, INFO, Image ID: 100
2026-07-21 12:00:15,080, INFO, Uploaded mean/span to LabServer under keys: TiSaMeanFreq100, TiSaSpanFreq100
2026-07-21 12:00:20,102, INFO, Scan completed in 20.1s
2026-07-21 12:00:20,102, INFO, Collected 33 valid readings, 0 failed
2026-07-21 12:00:20,102, INFO, Mean frequency: 384.230123 THz, Span: 0.012400 THz
2026-07-21 12:00:20,150, INFO, Image ID: 101
2026-07-21 12:00:20,180, INFO, Uploaded mean/span to LabServer under keys: TiSaMeanFreq101, TiSaSpanFreq101
2026-07-21 12:00:20,205, INFO, Disconnected from 127.0.0.1
```
Note that a "Image ID" / "Uploaded mean/span..." pair can appear more than once per scan — once for every image ID change detected during the scan, plus one final time for whatever data is left when the scan stops.

If something goes wrong (connection refused, unexpected reply, a NACK
from LabServer, etc.), the script logs the error and exits with a
non-zero exit code:

```
2026-07-21 12:05:11,579, ERROR, RuntimeError: Expected 'OK' but got: !ERROR 1
```

## Recording a thin etalon scan

`thin_etalon_scan.py` steps the thin etalon motor across a range centred
on its current position and records the etalon reflex and the total
output power at every step. The result is written to a CSV file named
after the time of the scan, and the motor is returned to where it
started.

**Release the thin etalon lock before running this.** While the PI loop
is active it pulls the motor back as the scan moves it, and the data
comes out meaningless without any error being raised. The lock is the
"Free" button in the Thin Etalon section of Matisse Commander.

```
python3 thin_etalon_scan.py --matisse-host <lab-computer-ip>
```

The scan defaults to 4000 motor steps in increments of 20, which covers
roughly five fringes. Both can be changed:

```
python3 thin_etalon_scan.py --span 2000 --step 10
```

A smaller run is worth doing first, to confirm that the connection and
the motor commands work without moving the laser far from its setting:

```
python3 thin_etalon_scan.py --span 200 --step 20
```

The output file has one row per measurement:

```
motor_position,te_dc,dpow_dc
50105,0.05566406,0.0625
50125,0.03222656,0.06347656
```

## Plotting a scan

`plot_scan.py` draws the two signals of a recorded scan. It needs
matplotlib, so it is meant to be run wherever the CSV file ends up rather
than on the lab computer itself:

```
python3 plot_scan.py thin_etalon_scan_20260728_160121.csv
```
