"""Device Info v1 - single entry point: `python main.py` / `py main.py`.

Bootstrap order on every start:
  1. check Python deps from requirements.txt, auto-install via pip if missing,
     then restart the current process (no infinite import loop);
  2. check adb / scrcpy presence (prompt auto-install, never re-download
     what is already installed);
  3. check connected Android via `adb devices`;
  4. show banner + CLI menu.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"


def _parse_requirements() -> list[str]:
    if not REQUIREMENTS.exists():
        return []
    names: list[str] = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # strip version specifiers / extras / markers
        for sep in (";", " ", "["):
            if sep in line:
                line = line.split(sep, 1)[0].strip()
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in line:
                line = line.split(sep, 1)[0].strip()
        if line:
            names.append(line)
    return names


def _missing_packages() -> list[str]:
    import importlib.util

    missing: list[str] = []
    for name in _parse_requirements():
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    return missing


def bootstrap() -> None:
    """Install missing requirements and restart process once."""
    missing = _missing_packages()
    if not missing:
        return
    if os.environ.get("DEVICE_INFO_BOOTSTRAPPED") == "1":
        print(f"Still missing packages after install attempt: {', '.join(missing)}")
        print("Install manually with: python -m pip install -r requirements.txt")
        return
    print(f"Missing Python packages: {', '.join(missing)}")
    print("Installing via pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    except subprocess.CalledProcessError as exc:
        print(f"pip install failed: {exc}")
        return
    except FileNotFoundError:
        print("pip not found for current Python.")
        return
    # Restart current process to pick up freshly installed imports.
    os.environ["DEVICE_INFO_BOOTSTRAPPED"] = "1"
    os.execv(sys.executable, [sys.executable, str(PROJECT_ROOT / "main.py"), *sys.argv[1:]])


def main() -> None:
    bootstrap()

    from app import __version__
    from cli.banner import show_banner
    from cli.menu import menu_loop

    show_banner(__version__)
    menu_loop()


if __name__ == "__main__":
    main()
