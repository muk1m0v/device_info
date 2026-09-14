"""Interactive CLI menu for Device Info v1."""

from __future__ import annotations

import subprocess
import sys
import webbrowser

from app import __version__
from app import adb as adb_mod
from cli import installers

GITHUB_URL = "https://github.com/muk1m0v/device_info"


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
        if state != "device":
            _err(f"Device {serial}: {state}")
            continue
        _ok("Device connected")
        info = adb_mod.get_device_info(serial)
        print(f"Serial: {serial}")
        print(f"Model: {info.get('model', '?')}")
        print(f"Android: {info.get('android', '?')}")
        print("Status: authorized")


def option_summary() -> None:
    adb_path = adb_mod.find_adb()
    if not adb_path:
        _err("ADB not installed")
        installers.prompt_install_scrcpy() if False else installers.prompt_install_adb()
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
    serial = authorized[0]["serial"]
    s = adb_mod.get_summary(serial)
    print()
    print(f"Device: {s.get('device', '?')}")
    print(f"Android: {s.get('android', '?')}")
    print(f"Battery: {s.get('battery', '?')}")
    print(f"Battery temp: {s.get('battery_temp', '?')}")
    print(f"RAM: {s.get('ram', '?')}")
    print(f"Storage: {s.get('storage', '?')}")
    print(f"Resolution: {s.get('resolution', '?')}")
    print(f"ADB: {s.get('adb', '?')}")


def option_dashboard() -> None:
    if adb_mod.find_adb() is None:
        _err("ADB not installed")
        installers.prompt_install_adb()
        # continue anyway: dashboard can show "no device"
    from app import dashboard
    dashboard.run_dashboard()


def option_scrcpy() -> None:
    installers.run_scrcpy()


def option_repair() -> None:
    _info("Checking Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        _ok("Python dependencies OK")
    except subprocess.CalledProcessError as exc:
        _err(f"pip install failed: {exc}")
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
    while True:
        show_menu()
        choice = input("\nSelect: ").strip()
        if choice == "1":
            option_dashboard()
        elif choice == "2":
            option_check_devices()
        elif choice == "3":
            option_scrcpy()
        elif choice == "4":
            option_summary()
        elif choice == "5":
            option_repair()
        elif choice == "6":
            webbrowser.open(GITHUB_URL)
            _info(f"Opened {GITHUB_URL}")
        elif choice == "7":
            option_about()
        elif choice == "0":
            _info("Bye!")
            break
        else:
            _err("Unknown option, try again.")
        input("\nPress Enter to continue...")
