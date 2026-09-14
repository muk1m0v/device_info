"""Interactive CLI menu for Device Info v1."""

from __future__ import annotations

import subprocess
import sys
import webbrowser

from app import __version__
from app import adb as adb_mod
from app.logging_setup import get_logger, short_serial
from cli import installers

GITHUB_URL = "https://github.com/muk1m0v/device_info"
PIP_TIMEOUT = 120


def _console():
    try:
        from rich.console import Console
        return Console()
    except ImportError:
        return None


def _safe_print(console, *args, **kwargs) -> None:
    try:
        console.print(*args, **kwargs)
    except Exception:
        # Fallback for consoles that can't encode rich/unicode output
        # (e.g. cp1252 when piped): strip markup crudely and use print().
        import re

        text = " ".join(str(a) for a in args)
        text = re.sub(r"\[/?[a-zA-Z0-9 #;:]+\]", "", text)
        try:
            print(text)
        except Exception:
            print(text.encode("ascii", "replace").decode("ascii"))


def _ok(text: str) -> None:
    c = _console()
    if c:
        _safe_print(c, f"[green]OK {text}[/green]")
    else:
        print(f"[OK] {text}")


def _err(text: str) -> None:
    c = _console()
    if c:
        _safe_print(c, f"[red]{text}[/red]")
    else:
        print(f"[ERROR] {text}")


def _info(text: str) -> None:
    c = _console()
    if c:
        _safe_print(c, text)
    else:
        print(text)


def safe_input(prompt: str) -> str | None:
    """Input that returns None on EOF/Ctrl+C instead of raising."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def select_device(devices: list[dict]) -> dict | None:
    """Let the user pick one device when several are attached."""
    authorized = [d for d in devices if d["state"] == "device"]
    if not authorized:
        return None
    if len(authorized) == 1:
        return authorized[0]
    print("\nList of devices:")
    for i, dev in enumerate(authorized, 1):
        try:
            info = adb_mod.get_device_info(dev["serial"])
            label = f"{info.get('manufacturer', '')} {info.get('model', '')}".strip()
        except Exception:
            label = ""
        print(f"[{i}] {dev['serial']}" + (f"  {label}" if label else ""))
    choice = safe_input("Select device (0 = back): ")
    if choice is None or choice == "0":
        return None
    try:
        idx = int(choice) - 1
    except ValueError:
        _err("Unknown option.")
        return None
    if 0 <= idx < len(authorized):
        return authorized[idx]
    _err("Unknown option.")
    return None


def show_menu() -> None:
    c = _console()
    title = f"DEVICE INFO v{__version__}"
    if c:
        _safe_print(c, f"\n[bold white]{title}[/bold white]")
        _safe_print(c, "[orange1][1][/orange1] Open Device Dashboard")
        _safe_print(c, "[orange1][2][/orange1] Check connected devices")
        _safe_print(c, "[orange1][3][/orange1] Open scrcpy screen")
        _safe_print(c, "[orange1][4][/orange1] Show device summary")
        _safe_print(c, "[orange1][5][/orange1] Install / Repair dependencies")
        _safe_print(c, "[orange1][6][/orange1] Open project GitHub")
        _safe_print(c, "[orange1][7][/orange1] About")
        _safe_print(c, "[orange1][0][/orange1] Exit")
    else:
        print(f"\n{title}\n")
        print("[1] Open Device Dashboard")
        print("[2] Check connected devices")
        print("[3] Open scrcpy screen")
        print("[4] Show device summary")
        print("[5] Install / Repair dependencies")
        print("[6] Open project GitHub")
        print("[7] About")
        print("[0] Exit")


def option_check_devices() -> None:
    adb_path = adb_mod.find_adb()
    print("\nADB STATUS\n")
    if not adb_path:
        _err("ADB not installed")
        installers.prompt_install_adb()
        return
    _ok("ADB installed")
    try:
        code, out, _ = adb_mod.run_adb(["devices"])
        devices = adb_mod.parse_adb_devices(out) if code == 0 else []
    except Exception as exc:  # never crash the menu
        _err(f"adb devices failed: {exc}")
        return
    if not devices:
        print("No Android device detected.")
        return
    for dev in devices:
        serial, state = dev["serial"], dev["state"]
        if state == "unauthorized":
            print("Device found but not authorized.")
            print("Unlock the phone and accept USB debugging.")
            print(f"Serial: {serial}")
            continue
        if state == "offline":
            _err(f"Device {serial} is offline. Re-plug the cable or run "
                 "`adb kill-server` + `adb devices` and try again.")
            continue
        if state != "device":
            _err(f"Device {serial}: {state}")
            continue
        _ok("Device connected")
        info = adb_mod.get_device_info(serial)
        print(f"Serial: {serial}")
        print(f"Model: {info.get('model', 'N/A')}")
        print(f"Android: {info.get('android', 'N/A')}")
        print("Status: authorized")


def option_summary() -> None:
    adb_path = adb_mod.find_adb()
    if not adb_path:
        _err("ADB not installed")
        installers.prompt_install_adb()
        return
    devices = adb_mod.get_connected_devices()
    authorized = [d for d in devices if d["state"] == "device"]
    if not authorized:
        if any(d["state"] == "unauthorized" for d in devices):
            print("Device found but not authorized.")
            print("Unlock the phone and accept USB debugging.")
        else:
            print("No Android device detected.")
        return
    picked = select_device(devices)
    if picked is None:
        return
    serial = picked["serial"]
    get_logger().info("summary device=%s", short_serial(serial))
    s = adb_mod.get_summary(serial)
    print()
    print(f"Device: {s.get('device', 'N/A')}")
    print(f"Android: {s.get('android', 'N/A')}")
    print(f"Battery: {s.get('battery', 'N/A')}")
    print(f"Battery temp: {s.get('battery_temp', 'N/A')}")
    print(f"RAM: {s.get('ram', 'N/A')}")
    print(f"Storage: {s.get('storage', 'N/A')}")
    print(f"Resolution: {s.get('resolution', 'N/A')}")
    print(f"ADB: {s.get('adb', 'N/A')}")


def option_dashboard() -> None:
    if adb_mod.find_adb() is None:
        _err("ADB not installed")
        installers.prompt_install_adb()
        # continue anyway: dashboard can show "no device"
    serial = None
    devices = adb_mod.get_connected_devices()
    if any(d["state"] == "device" for d in devices):
        picked = select_device(devices)
        if picked is None and len([d for d in devices if d["state"] == "device"]) > 1:
            return  # user backed out of the picker
        serial = picked["serial"] if picked else None
    # Single source: same orange/white dashboard as `device info`.
    from app import dashboard_launcher
    dashboard_launcher.open_dashboard(serial)


def option_scrcpy() -> None:
    serial = None
    if adb_mod.find_adb():
        devices = adb_mod.get_connected_devices()
        authorized = [d for d in devices if d["state"] == "device"]
        if len(authorized) > 1:
            picked = select_device(devices)
            if picked is None:
                return
            serial = picked["serial"]
        elif len(authorized) == 1:
            serial = authorized[0]["serial"]
    installers.run_scrcpy(serial)


def option_repair() -> None:
    _info("Checking Python dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            timeout=PIP_TIMEOUT,
            check=True,
        )
        _ok("Python dependencies OK")
    except subprocess.TimeoutExpired:
        _err(f"pip install timed out after {PIP_TIMEOUT}s (no internet?).")
        return
    except subprocess.CalledProcessError as exc:
        _err(f"pip install failed: {exc}")
        return
    except OSError as exc:
        _err(f"Could not run pip: {exc}")
        return
    if adb_mod.find_adb():
        _ok("ADB installed")
    else:
        installers.prompt_install_adb()
    if installers.find_scrcpy():
        _ok("scrcpy installed")
    else:
        installers.prompt_install_scrcpy()


def option_about() -> None:
    print()
    print("Device Info v1")
    print("Created by MUKIMOV")
    print("Android diagnostics via ADB")
    print("Read-only by default")
    print("GitHub: muk1m0v/device_info")


def menu_loop() -> None:
    log = get_logger()
    while True:
        show_menu()
        choice = safe_input("\nSelect: ")
        if choice is None:
            _info("Bye!")
            log.info("menu exit (EOF/Ctrl+C)")
            break
        if choice == "1":
            log.info("menu dashboard")
            option_dashboard()
        elif choice == "2":
            log.info("menu check-devices")
            option_check_devices()
        elif choice == "3":
            log.info("menu scrcpy")
            option_scrcpy()
        elif choice == "4":
            option_summary()
        elif choice == "5":
            log.info("menu repair")
            option_repair()
        elif choice == "6":
            try:
                webbrowser.open(GITHUB_URL)
            except Exception:
                _err("Could not open the browser.")
                continue
            _info(f"Opened {GITHUB_URL}")
        elif choice == "7":
            option_about()
        elif choice == "0":
            _info("Bye!")
            log.info("menu exit")
            break
        else:
            _err("Unknown option, try again.")
        if safe_input("\nPress Enter to continue...") is None:
            _info("Bye!")
            log.info("menu exit (EOF/Ctrl+C)")
            break
