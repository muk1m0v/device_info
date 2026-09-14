# DEVICE INFO

Android diagnostics, monitoring and device dashboard powered by ADB.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![Android](https://img.shields.io/badge/Android-ADB-green)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.0.0-orange)

A modern Android device diagnostics dashboard powered by ADB.

## Screenshots

Dashboard screenshot:

![dashboard](docs/screenshots/dashboard.png)

> If the image above does not load yet, just put your screenshot at
> `docs/screenshots/dashboard.png` — the path is already wired in.

## Features

- Android device detection via ADB
- Live battery monitoring
- CPU and thermal information
- RAM monitoring
- Storage usage
- Display information
- Network status
- Sensors
- Installed applications
- Processes
- Raw ADB diagnostics
- Live charts
- scrcpy integration
- Automatic dependency checking
- Local Web Dashboard
- Read-only diagnostics

## Requirements

- Windows 10 / 11
- Python 3.10+
- Android phone with USB debugging enabled
- Internet (only on first run, to auto-install missing deps)

Python libraries are listed in `requirements.txt` and installed automatically.

## Installation

```powershell
git clone https://github.com/muk1m0v/device_info.git
cd device_info
python main.py
```

Or with the `py` launcher:

```powershell
py main.py
```

On first start the program installs missing Python dependencies itself
(`python -m pip install -r requirements.txt`) and restarts.

## Quick start

1. Enable USB debugging on the phone.
2. Connect it via USB.
3. Run `python main.py`.
4. Accept the RSA fingerprint on the phone if asked.
5. Use the menu.

## CLI menu

```
DEVICE INFO v1.0.0

[1] Open Device Dashboard
[2] Check connected devices
[3] Open scrcpy screen
[4] Show device summary
[5] Install / Repair dependencies
[6] Open project GitHub
[7] About
[0] Exit

Select:
```

- **[1]** finds a free port, starts the backend, opens the browser automatically,
  shows the URL. `Ctrl+C` stops the server cleanly.
- **[2]** shows `ADB STATUS` (installed / connected / serial / model / Android /
  authorized, `No Android device detected.`, or
  `Device found but not authorized. Unlock the phone and accept USB debugging.`).
- **[3]** runs `scrcpy`; if missing, offers automatic install.
- **[4]** prints a short summary (device, Android, battery, temp, RAM, storage,
  resolution, ADB state) right in the terminal.
- **[5]** re-checks and repairs dependencies.
- **[6]** opens `https://github.com/muk1m0v/device_info` in the browser.
- **[7]** about screen.

## Web dashboard

Local Flask dashboard (default `http://127.0.0.1:5000+`, first free port):

- device card, battery, RAM, storage, resolution
- `/api/info` JSON endpoint for raw ADB diagnostics
- auto-refresh every 5 seconds

## ADB info

Detection order:

1. `shutil.which("adb")` (system PATH),
2. `tools/platform-tools/adb.exe` (local auto-install).

If nothing is found:

```
Android Platform Tools not found.

[1] Install automatically
[2] Open download page
[0] Back
```

Auto-install downloads only from the official Google URL
(`dl.google.com`), unpacks to `tools/platform-tools/`, needs no admin
rights and does not touch system PATH. Already-installed tools are never
re-downloaded.

## scrcpy integration

Detection order:

1. `shutil.which("scrcpy")`,
2. `tools/scrcpy/scrcpy.exe`.

If missing:

```
scrcpy not found.

[1] Install automatically
[2] Open official download page
[0] Back
```

Auto-install uses only official Genymobile/scrcpy GitHub releases and
unpacks to `tools/scrcpy/`.

## Supported systems

| Component | Status |
|-----------|--------|
| Windows 10 / 11 | ✅ supported |
| Python 3.10+ | ✅ required |
| ADB Platform Tools | ✅ auto-install |
| scrcpy | ✅ auto-install |
| Linux / macOS | ⚠️ should work, paths use `adb`/`scrcpy` from PATH |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No Android device detected.` | Check cable, enable USB debugging, run `adb devices` |
| `unauthorized` | Unlock phone, accept RSA dialog, re-plug |
| `adb not found` | Menu → [5], or [2] → [1] auto-install |
| `scrcpy not found` | Menu → [3] → [1] auto-install |
| pip install fails | Run `python -m pip install -r requirements.txt` manually |
| Port busy | App picks the next free port automatically |
| Blank dashboard | No authorized device — connect one first |

## Security

- Downloads only from `dl.google.com` / `developer.android.com`
  (ADB) and `github.com/Genymobile/scrcpy` (scrcpy).
- HTTP status, file existence and zip integrity are verified.
- Failed downloads never crash the app — a readable error is shown.
- Diagnostics are read-only by default (`getprop`, `dumpsys battery`,
  `/proc/meminfo`, `df`, `wm size`).
- No passwords, tokens or private keys are stored. Device serials are
  detected at runtime via `adb devices`, never hardcoded.

## Project structure

```
device_info/
├── main.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── app/
│   ├── __init__.py      # __version__ = "1.0.0"
│   ├── adb.py           # find_adb, devices, summary
│   └── dashboard.py     # Flask app, free port, browser
├── cli/
│   ├── __init__.py
│   ├── banner.py        # ASCII DEVICE INFO v1
│   ├── menu.py          # options 1-7, 0
│   └── installers.py    # platform-tools + scrcpy helpers
├── docs/
│   └── screenshots/
│       └── dashboard.png
└── tools/
    ├── .gitkeep
    ├── platform-tools/  # auto-downloaded, git-ignored
    └── scrcpy/          # auto-downloaded, git-ignored
```

> Note: this checkout may additionally contain unrelated local
> Android/SystemUI reverse-engineering folders (`SystemUI-src/`, `build/` …).
> They are not part of Device Info v1 and do not affect `python main.py`.

## License

MIT — see [LICENSE](LICENSE). Author: MUKIMOV.

## Author

Created by **MUKIMOV** — Android diagnostics via ADB.
GitHub: [muk1m0v/device_info](https://github.com/muk1m0v/device_info)
