"""Unified Device Info dashboard launcher — single source of truth.

Background (work4): the global command

    device info

opens the correct beautiful orange/white dashboard (FastAPI + uvicorn,
``check_phone/app/main.py`` + ``templates/index.html`` + ``static/``),
while ``python main.py -> [1]`` used to open a different simplified Flask
site (``app/dashboard.py``). Both must launch absolutely the same dashboard.

This module is the single reusable entry point:

    open_dashboard(preferred_serial=None)

It delegates to the SAME launcher that ``device info`` uses
(``cli/device.py info`` from the orange-dashboard project) via subprocess —
no HTML/CSS copy, no second frontend, no duplicated Flask app. Module-name
collision (both projects have a top-level ``app`` package) is exactly why a
subprocess is used instead of an in-process import.

If the orange dashboard project is not found next to this checkout (e.g. a
fresh ``git clone`` with only this repo), it falls back to the local Flask
``app.dashboard.run_dashboard`` so the published repo stays standalone.

Search order for the orange dashboard root (must contain
``cli/device.py`` + ``app/main.py`` + ``app/templates/index.html``):
  1. ``$DEVICE_INFO_DASHBOARD_ROOT`` env var,
  2. sibling ``../check_phone`` next to this repo,
  3. path parsed from the ``device`` launcher on PATH
     (``device.cmd`` references ``...\\cli\\device.py``),
  4. ``~/.device-info`` install layout hint.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765  # same default as `device info --port`


def _looks_like_orange_root(root: Path) -> bool:
    try:
        return (
            (root / "cli" / "device.py").is_file()
            and (root / "app" / "main.py").is_file()
            and (root / "app" / "templates" / "index.html").is_file()
        )
    except OSError:
        return False


def _root_from_device_cmd() -> Path | None:
    """Parse check_phone root from the `device` launcher on PATH.

    ``device.cmd`` looks like:
        "...\\.venv\\Scripts\\python.exe" "...\\cli\\device.py" %*
    so the project root is the parent of ``cli/device.py``.
    """
    device_cmd = shutil.which("device")
    if not device_cmd:
        return None
    try:
        text = Path(device_cmd).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'"([^"]*cli[\\/]device\.py)"', text)
    if not m:
        m = re.search(r"([A-Za-z]:[^\s\"%]*cli[\\/]device\.py)", text)
    if not m:
        return None
    device_py = Path(m.group(1))
    root = device_py.parent.parent
    return root if _looks_like_orange_root(root) else None


def find_orange_dashboard_root() -> Path | None:
    """Locate the orange/white dashboard project, or None if absent."""
    candidates: list[Path] = []
    env = os.environ.get("DEVICE_INFO_DASHBOARD_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(PROJECT_ROOT.parent / "check_phone")
    from_device_cmd = _root_from_device_cmd()
    if from_device_cmd is not None:
        candidates.append(from_device_cmd)
    candidates.append(Path.home() / "check_phone")
    for cand in candidates:
        try:
            if _looks_like_orange_root(cand):
                return cand.resolve()
        except OSError:
            continue
    return None


def _python_for(root: Path) -> str:
    """Prefer the dashboard project's venv python, else current interpreter."""
    venv_py = root / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    venv_nix = root / ".venv" / "bin" / "python"
    if venv_nix.is_file():
        return str(venv_nix)
    return sys.executable


def open_dashboard(
    preferred_serial: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Launch THE orange/white dashboard — same as `device info`.

    Delegates to ``cli/device.py info`` so backend, frontend, HTML, CSS, JS,
    API, live monitoring, port logic and ADB device selection are identical.
    Falls back to the local Flask dashboard only when the orange project is
    not installed next to this checkout.
    """
    from app.logging_setup import get_logger

    log = get_logger()
    root = find_orange_dashboard_root()
    if root is not None:
        device_py = root / "cli" / "device.py"
        python = _python_for(root)
        cmd = [
            python,
            str(device_py),
            "info",
            "--host",
            host,
            "--port",
            str(port),
        ]
        if preferred_serial:
            cmd += ["--serial", preferred_serial]
        if os.environ.get("DEVICE_INFO_NO_BROWSER") == "1":
            cmd += ["--no-browser"]
        log.info("dashboard start unified root=%s serial=%s", root, preferred_serial or "")
        print(f"Opening Device Info dashboard (unified launcher, {root})...")
        try:
            subprocess.run(cmd, check=False)
        except OSError as exc:
            print(f"Could not start the unified dashboard: {exc}")
            log.warning("unified dashboard failed: %s", exc)
        finally:
            log.info("dashboard stop unified")
        return

    # Standalone fallback (fresh clone without the sibling project).
    print("Orange dashboard project not found; using local fallback dashboard.")
    log.warning("orange dashboard root not found, using local Flask fallback")
    from app import dashboard

    dashboard.run_dashboard(preferred_serial)
