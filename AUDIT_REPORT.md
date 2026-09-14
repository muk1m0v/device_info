# Device Info Security & Quality Audit

**Project:** Device Info v1.0.0 (`https://github.com/muk1m0v/device_info`)
**Auditor:** automated audit via code review + runtime tests (Windows, Python 3.14, no device attached)
**Date:** 2026-09-14
**Scope:** `main.py`, `app/`, `cli/`, `requirements.txt`, `README.md`, `.gitignore`, `LICENSE`, git tracked files.
**Re-audit:** 2026-09-14 — all fixes verified (see "Verification" below).

Runtime tests performed on v1.0.0: `compileall` clean; banner/menu/exit work;
`adb devices` with no phone handled; summary with no phone handled;
`py main.py` works; scrcpy found via PATH and launches (fails only with
"Could not find any ADB device" — correct without a phone);
dashboard imports, free-port search and routes (`/`, `/api/info`) OK;
`rich` auto-install + process restart verified.

## Critical

### SEC-001 — Unsafe ZIP extraction (Zip Slip)
- **Severity:** Critical
- **File:** `cli/installers.py` (`safe_extract_zip`)
- **Problem:** `zipfile.extractall()` is called without validating member paths.
  A malicious/compromised archive could contain `../../malware.exe` entries
  escaping `tools/`.
- **Risk:** Arbitrary file overwrite (path traversal) if a download source is
  ever compromised or redirected.
- **Fix:** Validate every member before extraction: reject absolute paths,
  `..` segments, and any resolved path outside the target dir.
- **Status:** Fixed (`_member_target()` in `cli/installers.py`; unit-tested
  with a malicious `../../evil.txt` zip — blocked, plus a good zip — extracts)

## High

### SEC-002 — Download hardening gaps
- **Severity:** High
- **File:** `cli/installers.py` (`download_file`, `get_scrcpy_download_url`)
- **Problem:** No HTTPS-scheme enforcement (only host allowlist), no
  `Content-Length`/minimum-size check (only empty-file check), no SHA-256
  verification, scrcpy asset URL not checked for scheme/extension.
- **Risk:** Truncated or substituted payload accepted more easily; MITM
  downgrade surface larger than necessary.
- **Fix:** Require `https://`, check `Content-Length` when present plus a
  minimum sane size, require `.zip` extension for release assets. SHA-256
  pinning documented as not feasible (Google rolling zip, GitHub dynamic
  releases) — integrity enforced via size + ZIP validity + post-install
  `adb.exe`/`scrcpy.exe` presence check.
- **Status:** Fixed (HTTPS enforced in `_check_host_allowed`, Content-Length
  + 1 MB minimum in `download_file`, `.zip` URL check for release assets)

### FUNC-001 — Multiple ADB devices ignored
- **Severity:** High
- **File:** `cli/menu.py` (`option_summary`), `app/dashboard.py` (`api_info`)
- **Problem:** Code silently uses `authorized[0]`. All ADB commands already use
  `-s SERIAL`, but the user is never offered a choice.
- **Risk:** Wrong device diagnosed/mirrored; confusing with 2+ phones.
- **Fix:** Device picker (`[1] Samsung … [2] Pixel …`) in menu flows and
  `?serial=` support in dashboard API + a device dropdown on the page.
- **Status:** Fixed (`select_device()` picker in menu flows, `?serial=` +
  dropdown in dashboard; API falls back to the first authorized device)

### FUNC-002 — scrcpy launched without `--serial`
- **Severity:** High
- **File:** `cli/installers.py` (`run_scrcpy`)
- **Problem:** `Popen([exe])` with no `--serial`; scrcpy fails or picks
  arbitrarily when several devices are attached. Corrupted/missing binary not
  validated before launch.
- **Risk:** Mirror of the wrong device / cryptic failure.
- **Fix:** `run_scrcpy(serial=None)` → `scrcpy --serial SERIAL` when a device
  is selected; verify the exe is a file before launch.
- **Status:** Fixed (`run_scrcpy(serial)` builds `--serial SERIAL`;
  verified via mocked Popen; single-device case auto-selected)

### REL-001 — pip bootstrap/repair without timeout or offline handling
- **Severity:** High
- **File:** `main.py` (`bootstrap`), `cli/menu.py` (`option_repair`)
- **Problem:** `pip install` can hang forever without internet; failure path
  prints and continues, so the dashboard later crashes with
  `ModuleNotFoundError` instead of a clean exit.
- **Risk:** Hanging startup; confusing late crash.
- **Fix:** `timeout=120` on pip calls, catch `TimeoutExpired`/`OSError`,
  exit(1) with a clear message if required packages are still missing.
- **Status:** Fixed (`PIP_TIMEOUT = 120`, `TimeoutExpired`/`OSError` handled,
  `exit(1)` when deps still missing; same treatment in menu repair)

### UX-001 — Menu crashes on EOF / Ctrl+C
- **Severity:** High
- **File:** `cli/menu.py` (`menu_loop`, `prompt_install_*` in `installers.py`)
- **Problem:** Bare `input()` raises `EOFError` on piped/closed stdin and
  `KeyboardInterrupt` on Ctrl+C → traceback. Verified: piping
  `"2","0","","0"` ends in `EOFError` traceback.
- **Risk:** Crash instead of graceful return/exit.
- **Fix:** `safe_input()` wrapper; EOF/Ctrl+C exits cleanly (or returns to
  the previous prompt for sub-prompts).
- **Status:** Fixed (`safe_input()` everywhere incl. installer prompts;
  EOF/Ctrl+C exits cleanly; tested with piped `abc`/`99`/empty input)

### REL-002 — Browser opened before server listens; port check-then-use race
- **Severity:** High
- **File:** `app/dashboard.py` (`run_dashboard`, `find_free_port`)
- **Problem:** `webbrowser.open(url)` runs before `app.run()` listens, so the
  first page load can fail. A port found free can be grabbed by another
  process before Flask binds.
- **Risk:** Blank/failed first load; rare startup crash (`OSError`).
- **Fix:** Open the browser via `threading.Timer` after the server starts;
  retry the next ports if binding fails.
- **Status:** Fixed (`threading.Timer(1.0)` browser open after listen;
  bind probe + retry over the next 10 ports; `OSError` prints cleanly)

## Medium

### DQ-001 — Battery temperature assumes tenths; `?` instead of `N/A`
- **Severity:** Medium
- **File:** `app/adb.py` (`get_summary`)
- **Problem:** `int(raw)/10` unconditionally — a device reporting whole
  degrees (e.g. `42`) would show `4.2°C`; absurd values (e.g. `42000`) pass
  through. Missing values use `?`.
- **Risk:** Misleading diagnostics.
- **Fix:** `normalize_battery_temp()` with sane-range validation; missing
  values → `N/A`.
- **Status:** Fixed (unit-tested: `294`→29.4°C, `42`→42.0°C, `42000`/`abc`→N/A;
  live device reports a sane value)

### PERF-001 — Dashboard re-queries static data on every poll
- **Severity:** Medium
- **File:** `app/dashboard.py` (`api_info`)
- **Problem:** Every `/api/info` request (each open tab, every 5 s) runs
  ~10 adb processes including static `getprop` calls.
- **Risk:** Process churn with several tabs/devices.
- **Fix:** TTL cache (120 s) for static per-serial data
  (model/manufacturer/android/sdk/resolution); dynamic data stays live.
- **Status:** Fixed (`get_cached_static()` in `app/dashboard.py`)

### GIT-001 — `.gitignore` does not cover co-located SystemUI artifacts
- **Severity:** Medium
- **File:** `.gitignore`
- **Problem:** Only `tools/platform-tools/` and `tools/scrcpy/` are ignored.
  A plain `git add .` in this folder would stage `SystemUI-src/`,
  `*.apk`, `build/`, apktool files into the Device Info repo.
- **Risk:** Repository pollution / accidental binary publish.
- **Fix:** Explicit ignore rules for the co-located non-Device-Info paths
  plus `work*.md` task files; keep all Device Info paths tracked.
- **Status:** Fixed (verified: `git status` no longer shows SystemUI/`*.apk`/
  `build/` paths at all; only Device Info files are modified/untracked)

### DEP-001 — Unpinned requirements
- **Severity:** Medium
- **File:** `requirements.txt`
- **Problem:** `rich` / `flask` unpinned → non-reproducible installs.
- **Risk:** Future breaking release pulled silently.
- **Fix:** Pin to audited versions (`rich==15.0.0`, `flask==3.1.2`) after
  vulnerability check.
- **Status:** Fixed (`rich==15.0.0`, `flask==3.1.3` — see DEP-002 below)

### DEP-002 — Flask 3.1.2 has known CVEs (found during this audit)
- **Severity:** High
- **File:** `requirements.txt`
- **Problem:** `python -m pip_audit -r requirements.txt` reported 2 known
  vulnerabilities in `flask 3.1.2` (`PYSEC-2026-2151`, fixed in 3.1.3).
  `pip-audit` was used as a one-off dev tool only, not added to runtime deps.
- **Risk:** Known CVE in the shipped web dashboard dependency.
- **Fix:** Upgraded to `flask==3.1.3`; re-ran `pip-audit` → "No known
  vulnerabilities found"; dashboard smoke-tested on 3.1.3.
- **Status:** Fixed

### UX-002 — Sub-prompts use unguarded `input()`
- **Severity:** Medium
- **File:** `cli/installers.py` (`prompt_install_adb`, `prompt_install_scrcpy`)
- **Problem:** Same EOF/Ctrl+C crash class as UX-001 in installer prompts.
- **Risk:** Crash during install flow.
- **Fix:** Reuse the shared `safe_input()` helper.
- **Status:** Fixed (installer prompts use `_safe_input()`; unknown options
  reported instead of falling through)

### OBS-001 — No logging
- **Severity:** Medium
- **File:** (new) `app/logging_setup.py`
- **Problem:** No log file; diagnosing field issues relies on screenshots.
  `logs/` is gitignored but nothing writes there.
- **Risk:** Poor debuggability.
- **Fix:** Minimal stdlib rotating logger (`logs/device-info.log`, 256 KB,
  2 backups); log lifecycle events only, serials truncated, no secrets.
- **Status:** Fixed (new `app/logging_setup.py`, wired into startup/menu/
  installer/dashboard flows)

### QUAL-001 — Dead code in `option_summary`
- **Severity:** Medium
- **File:** `cli/menu.py:128`
- **Problem:** `prompt_install_scrcpy() if False else prompt_install_adb()` —
  confusing leftover branch.
- **Risk:** Reader mistakes it for logic; hides intent.
- **Fix:** Call `prompt_install_adb()` directly.
- **Status:** Fixed

## Low

### L-001 — `offline` devices reported generically
- **Severity:** Low
- **File:** `cli/menu.py` (`option_check_devices`)
- **Problem:** Any non-`device`/non-`unauthorized` state prints `Device
  {serial}: {state}` without hint text.
- **Risk:** Minor UX gap.
- **Fix:** Distinct message for `offline` (re-plug / restart adb server).
- **Status:** Fixed

### L-002 — Extra ADB processes in `get_device_info`
- **Severity:** Low
- **File:** `app/adb.py` (`get_device_info`)
- **Problem:** Runs a probe `shell echo ok` plus a full `adb devices` on top
  of the caller's listing.
- **Risk:** Slightly wasteful; harmless.
- **Fix:** Drop the probe; trust the device list state.
- **Status:** Fixed

### L-003 — `os.system("cls"/"clear")`
- **Severity:** Low
- **File:** `cli/banner.py` (`clear_screen`)
- **Problem:** Shell invocation (constant string — no injection), flagged by
  strict linters.
- **Risk:** None in practice.
- **Fix:** Replaced with `subprocess.run()` argv-list form (no `shell=True`):
  `["cmd", "/c", "cls"]` on Windows, `["clear"]` elsewhere; skips clearing
  when stdout is piped; `OSError` swallowed so a missing binary never breaks
  startup.
- **Status:** Fixed in v1.1.1

### L-004 — Hardcoded dashboard title / README version staleness risk
- **Severity:** Low
- **File:** `app/dashboard.py`, `README.md`
- **Problem:** Page header hardcodes "DEVICE INFO v1"; README badge pins
  1.0.0 manually.
- **Risk:** Version drift.
- **Fix:** Pass `__version__` into the dashboard; bump README to v1.1.0.
- **Status:** Fixed (page title + header use `__version__`; badge v1.1.0)

## Code quality

- No `shell=True`, no string-built commands; `subprocess` list-args
  everywhere — good.
- `pathlib.Path(__file__)` used for all project paths — good; run-from-`C:\`
  verified working.
- Broad `except Exception` in menu/API paths is intentional (menu must never
  crash); narrowed where a specific outcome matters (pip timeout).
- ASCII fallback for cp1252/cp866/piped output verified working.
- `requirements.txt` contains only real third-party deps (`rich`, `flask`).

## Compatibility

- Windows 10/11 + PowerShell: verified. `cmd` and redirected output: covered
  by ASCII fallback. Linux/macOS: code paths use `shutil.which` and local
  `tools/` dirs; not tested here (no Linux host).
- Python 3.10+ required by spec; tested on 3.14.

## Git / repository

- Tracked (`git ls-files`): only Device Info files — correct (now 17 with
  `AUDIT_REPORT.md`, `CHANGELOG.md`, `app/logging_setup.py`).
- Untracked/ignored after hardening: `SystemUI-*/`, `*.apk`, `build/`,
  apktool files, `work3.md` (deleted after the task per instructions) —
  stay out (see GIT-001).
- Remote `origin` correct; no secrets/tokens in code (grep clean);
  MIT LICENSE author MUKIMOV present.

## Verification (re-audit 2026-09-14, v1.1.0)

### Count correction (v1.1.1)
The delivery summary for v1.1.0 stated "8 Medium / 20 total". That was a
counting error in the summary text, not a missing entry: every finding in
this file is severity-labeled, and the labels tally to **1 Critical /
7 High / 7 Medium / 4 Low = 19 total**. DEP-002 (Flask CVEs) is correctly
labeled High; no Medium entry is missing, so the number was corrected
instead of inventing one.

- `python -m compileall main.py app cli` — clean.
- Secret/grep sweep (`shell=True`, passwords, tokens, hardcoded serial,
  `TODO`/`FIXME`, `0.0.0.0`, `debug=True`) — only hit is a comment stating
  localhost-only; clean.
- Unit checks: Zip-Slip blocked / good-zip extracts; temp normalization
  matrix; device-list parse (device/unauthorized/offline); URL policy
  (https-only, allowlist); scrcpy `--serial` command construction.
- `pip-audit` — clean after Flask 3.1.3 upgrade.
- Live runs (a Samsung phone on Android 13 was attached during the audit):
  banner v1.1.0, menu, invalid input (`abc`/`99`/empty → no crash), exit,
  option [2] authorized path, option [4] full summary, Flask `test_client`
  `/` + `/api/info` incl. bad-serial fallback, run from `C:\` cwd.
- `git status` shows only Device Info files; SystemUI/`*.apk`/`build/`
  fully ignored.

## Recommendations

All recommendations applied. Open items remaining: none, except the
documented SHA-256 limitation (SEC-002). L-003 was fixed in v1.1.1.
