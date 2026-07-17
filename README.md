# Matisse Scan Automation

A small Python tool that automates the "scan" command on a Sirah Matisse
Ti:Sapphire laser through the Matisse Commander software, over raw TCP/IP.
It starts a scan, reads the laser's actual frequency from a HighFinesse
wavemeter while the scan runs, and once the scan completes, uploads the
mean frequency and frequency span to the lab's shared LabServer so they
can be associated with the correct experimental image — no GUI
interaction needed.

Last updated: 2026-07-17


## Requirements

- Python 3
- No external dependencies for the Matisse/LabServer parts (uses only
  the Python standard library)
- Wavemeter reading (`wavemeter_client.py`) requires Windows and the
  HighFinesse `wlmData.dll`.

## Files

- `matisse_client.py` — low-level TCP client for Matisse Commander: opens
  the connection and handles the length-prefixed message framing used to
  send commands and read responses.
- `wavemeter_client.py` — reads laser frequency from the HighFinesse
  wavemeter (via `wlmData.py`/`wlmConst.py`), and computes mean/span
  statistics from a set of readings. Windows-only.
- `labserver_client.py` — TCP/IP client for the lab's shared LabServer:
  connects, looks up the current experimental image ID, and uploads data
  tagged under that image.
- `matisse_scan.py` — the main script. Connects to Matisse, starts a
  scan, reads the wavemeter while the scan runs, computes statistics
  once it's done, uploads them to LabServer, and disconnects.
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
2026-07-17 12:00:00,000, INFO, Connecting to Matisse at 127.0.0.1:30000
2026-07-17 12:00:00,001, INFO, Connection established
2026-07-17 12:00:00,001, INFO, Scan started successfully!
2026-07-17 12:00:05,102, INFO, Scan completed in 5.1s
2026-07-17 12:00:05,102, INFO, Collected 48 valid readings, 2 failed
2026-07-17 12:00:05,102, INFO, Mean frequency: 384.230123 THz, Span: 0.012400 THz
2026-07-17 12:00:05,150, INFO, Image ID: 42
2026-07-17 12:00:05,180, INFO, Uploaded mean/span to LabServer under keys: TiSaMeanFreq42, TiSaSpanFreq42
2026-07-17 12:00:05,205, INFO, Disconnected from 127.0.0.1
```

If something goes wrong (connection refused, unexpected reply, a NACK
from LabServer, etc.), the script logs the error and exits with a
non-zero exit code:

```
2026-07-17 12:05:11,579, ERROR, RuntimeError: Expected 'OK' but got: !ERROR 1
```
