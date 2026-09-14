# Changelog

## Unreleased (stays v1.1.1, no tag)

### Fixed
- CLI banner is now horizontally centered using the real terminal width
  (`shutil.get_terminal_size()`, no hardcoded spaces); narrow terminals
  fall back to reduced ASCII or plain `DEVICE INFO` text without breaking.
  Orange color and centered `DEVICE INFO vX` / subtitle lines kept.
- Unified dashboard launcher: `python main.py -> [1]` now opens the same
  orange/white dashboard as the global `device info` command (single
  reusable entry point `app.dashboard_launcher.open_dashboard`, subprocess
  delegation to `cli/device.py info` — no copied HTML/CSS, no second
  frontend). Falls back to the local Flask dashboard only when the
  orange-dashboard project is not installed next to the checkout.
- Fixed missing `shutil` import in `cli/banner.py` (centering relied on a
  `NameError`-to-fallback path).

## v1.1.1

### Fixed
- Audit count correction: the v1.1.0 delivery summary stated "8 Medium /
  20 total"; the labeled findings actually tally to 1 Critical / 7 High /
  7 Medium / 4 Low = 19 (DEP-002 is High, no Medium entry was missing).
  Documented in `AUDIT_REPORT.md`.
- Replaced the last `os.system` call (`clear_screen`) with argv-list
  `subprocess.run` (no `shell=True`); screen clearing is skipped for piped
  output and never breaks startup.

## v1.1.0

### Security
- Hardened ZIP extraction against Zip Slip / path traversal (every archive
  member is validated before `extractall`)
- HTTPS-scheme enforcement + host allowlist for all downloads
- Content-Length and minimum-size checks for downloaded archives
- Dashboard bound to `127.0.0.1` only (verified), no debug mode, browser
  opens only after the server listens, port bind-retry loop
- Documented why SHA-256 pinning is not applied (rolling Google zip,
  dynamic GitHub releases); integrity enforced via size + ZIP validity +
  post-install binary presence check

### Fixed
- Multi-device handling: device picker in summary/scrcpy/dashboard flows,
  `scrcpy --serial SERIAL`, `?serial=` API support + device dropdown
- `pip` bootstrap/repair: 120 s timeout, clean `exit(1)` with a clear
  message when offline or install fails (no more late `ModuleNotFoundError`)
- Menu no longer crashes on invalid input, EOF (piped stdin) or Ctrl+C
- Battery temperature normalization with sane-range validation
  (tenths vs whole degrees); missing values now report `N/A`, never an
  exception or a nonsense temperature
- Distinct message for `offline` devices; removed dead code branch
- `get_device_info` no longer wastes an extra ADB probe process

### Improved
- Static device data (model/Android) cached with 120 s TTL in the dashboard
- Minimal rotating file logger (`logs/device-info.log`, 256 KB x2, serials
  truncated, no secrets)
- Pinned requirements (`rich==15.0.0`, `flask==3.1.2`)
- `.gitignore` hardened for the co-located SystemUI project
- Version bumped to 1.1.0 everywhere (CLI, dashboard, README)

## v1.0.0

- Initial public release: `python main.py` launcher with dependency
  bootstrap, ADB/scrcpy auto-install, ASCII banner, CLI menu (7+1 options),
  Flask dashboard on localhost, read-only ADB diagnostics.
