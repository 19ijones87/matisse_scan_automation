# Matisse Scan Automation

A small Python tool that automates the "scan" command on a Sirah Matisse
Ti:Sapphire laser through the Matisse Commander software, over raw TCP/IP.
It starts a scan, waits for it to finish, and reports the result — no
GUI interaction needed.


## Requirements

- Python 3
- No external dependencies (uses only the Python standard library)

## Files

- `matisse_client.py` — low-level TCP client: opens the connection to
  Matisse Commander and handles the length-prefixed message framing used
  to send commands and read responses.
- `matisse_scan.py` — the main script. Connects, starts a scan, waits
  until it completes, and disconnects.


## Usage

By default, the script assumes Matisse Commander is running on the same
computer (`127.0.0.1`, port 30000 — the default port used by Matisse
Commander's TCP server).

```
python3 matisse_scan.py
```

### Connecting from a different computer

If Matisse Commander is running on another computer on the lab network,
you need to tell the script that computer's IP address. There are two
ways to do this — pick whichever is more convenient:

**Option 1 — command-line flag:**

```
python3 matisse_scan.py --host <lab-computer-ip>
```

**Option 2 — environment variable** (useful if you always run the script
from the same computer and don't want to type `--host` every time):

```
export MATISSE_HOST=<lab-computer-ip>
python3 matisse_scan.py
```

Replace `<lab-computer-ip>` with the actual IP address of the computer
running Matisse Commander. Real internal lab IP addresses are intentionally
never written in this repository (it's public), since anyone can see it —
you'll need to fill it in yourself, e.g. from Matisse Commander's
"Connection Options" menu.

### What you'll see

On a successful run, the script prints progress to the terminal and also
appends the same lines to `matisse_scan.log` (this file is not committed
to the repository, it's created locally on first run):

```
2026-07-13 22:56:07,403, INFO, Connecting to Matisse at 127.0.0.1:30000
2026-07-13 22:56:07,404, INFO, Connection established
2026-07-13 22:56:07,404, INFO, Scan started successfully!
2026-07-13 22:56:07,608, INFO, Scan completed in 0.2s
2026-07-13 22:56:07,608, INFO, Disconnected from 127.0.0.1
```

If something goes wrong (connection refused, unexpected reply from
Matisse Commander, etc.), the script logs the error and exits with a
non-zero exit code:

```
2026-07-13 22:59:11,579, ERROR, RuntimeError: Expected 'OK' but got: !ERROR 1
```
