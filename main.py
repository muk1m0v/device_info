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
PIP_TIMEOUT = 120


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
    """Install missing requirements and restart process once.

    Uses the current interpreter (`sys.executable -m pip`), so venvs work.
    On failure prints a clear error and exits(1) — continuing without the
    deps would only crash later with a confusing ModuleNotFoundError.
    """
    missing = _missing_packages()
    if not missing:
        return
    if os.environ.get("DEVICE_INFO_BOOTSTRAPPED") == "1":
        print(f"Still missing packages after install attempt: {', '.join(missing)}")
        print("Install manually with: python -m pip install -r requirements.txt")
        sys.exit(1)
    print(f"Missing Python packages: {', '.join(missing)}")
    print("Installing via pip...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            timeout=PIP_TIMEOUT,
            check=True,
        )
    except subprocess.TimeoutExpired:
        print(f"pip install timed out after {PIP_TIMEOUT}s. Check your internet "
              f"connection and run: python -m pip install -r requirements.txt")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"pip install failed: {exc}")
        sys.exit(1)
    except OSError:
        print("pip not found for current Python.")
        sys.exit(1)
    if _missing_packages():
        print("Packages still missing after install. Install manually with: "
              "python -m pip install -r requirements.txt")
        sys.exit(1)
    # Restart current process to pick up freshly installed imports.
    os.environ["DEVICE_INFO_BOOTSTRAPPED"] = "1"
    os.execv(sys.executable, [sys.executable, str(PROJECT_ROOT / "main.py"), *sys.argv[1:]])


def main() -> None:
    bootstrap()

    from app import __version__
    from app.logging_setup import get_logger
    from cli.banner import show_banner
    from cli.menu import menu_loop

    get_logger().info("startup version=%s", __version__)
    show_banner(__version__)
    menu_loop()


if __name__ == "__main__":
    main()
