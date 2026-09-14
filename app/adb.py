"""ADB helpers: locate adb, query devices, read-only diagnostics."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_adb() -> str | None:
    """Return path to adb.exe or None if not found."""
    found = shutil.which("adb")
    if found:
        return found
    local = PROJECT_ROOT / "tools" / "platform-tools" / "adb.exe"
    if local.exists():
        return str(local)
    # Also accept adb without .exe (MSYS/Git-bash) and PATH-less local dir
    local_nix = PROJECT_ROOT / "tools" / "platform-tools" / "adb"
    if local_nix.exists():
        return str(local_nix)
    return None


def run_adb(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run adb with given args. Returns (returncode, stdout, stderr)."""
    adb = find_adb()
    if not adb:
        return 127, "", "adb not found"
    try:
        proc = subprocess.run(
            [adb, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "adb command timed out"
    except OSError as exc:
        return 127, "", str(exc)


def parse_adb_devices(output: str) -> list[dict]:
    """Parse `adb devices` output into list of {serial, state}."""
    devices: list[dict] = []
    lines = output.strip().splitlines()
    for line in lines[1:]:  # skip "List of devices attached"
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def get_connected_devices() -> list[dict]:
    """Return list of connected devices (may be empty)."""
    code, out, _ = run_adb(["devices"])
    if code != 0:
        return []
    return parse_adb_devices(out)


def authorized_devices() -> list[dict]:
    """Connected devices in `device` state (usable for diagnostics)."""
    return [d for d in get_connected_devices() if d["state"] == "device"]


def normalize_battery_temp(raw: str) -> str:
    """Turn a `dumpsys battery` temperature reading into `XX.X°C` or `N/A`.

    Stock Android reports tenths of a degree (294 -> 29.4°C), but some
    devices report whole degrees (42 -> 42.0°C). Values outside any sane
    range are rejected instead of producing nonsense like 4200.0°C.
    """
    try:
        value = float(raw.strip())
    except (ValueError, AttributeError):
        return "N/A"
    if 100 <= abs(value) <= 1000:
        celsius = value / 10
    elif -50 <= value <= 100:
        celsius = value
    else:
        return "N/A"
    if not -50 <= celsius <= 100:
        return "N/A"
    return f"{celsius:.1f}°C"


def _getprop(serial: str, prop: str) -> str:
    code, out, _ = run_adb(["-s", serial, "shell", "getprop", prop])
    if code != 0:
        return ""
    return out.strip()


def get_device_info(serial: str) -> dict:
    """Collect read-only info for one device serial."""
    info: dict = {"serial": serial, "status": "unknown"}
    devices = get_connected_devices()
    for dev in devices:
        if dev["serial"] == serial:
            info["status"] = dev["state"]
            break
    if info["status"] != "device":
        return info
    info["model"] = _getprop(serial, "ro.product.model") or "Unknown"
    info["manufacturer"] = _getprop(serial, "ro.product.manufacturer") or ""
    info["android"] = _getprop(serial, "ro.build.version.release") or "Unknown"
    info["sdk"] = _getprop(serial, "ro.build.version.sdk") or ""
    return info


def _shell(serial: str, *cmd: str) -> str:
    code, out, _ = run_adb(["-s", serial, "shell", *cmd])
    return out.strip() if code == 0 else ""


def get_summary(serial: str) -> dict:
    """Short terminal summary for option [4]. All read-only."""
    summary: dict = {"serial": serial, "adb": "Disconnected"}
    devices = get_connected_devices()
    state = next((d["state"] for d in devices if d["serial"] == serial), "")
    if state != "device":
        summary["adb"] = "Unauthorized" if state == "unauthorized" else "Disconnected"
        summary["status"] = state or "no device"
        return summary
    summary["adb"] = "Connected"
    summary["status"] = "device"
    manufacturer = _getprop(serial, "ro.product.manufacturer")
    model = _getprop(serial, "ro.product.model")
    summary["device"] = f"{manufacturer} {model}".strip() or model or "Unknown"
    summary["android"] = _getprop(serial, "ro.build.version.release") or "N/A"

    # Battery
    battery_out = _shell(serial, "dumpsys", "battery")
    level = re.search(r"level:\s*(\d+)", battery_out)
    temp = re.search(r"temperature:\s*(-?[\d.]+)", battery_out)
    summary["battery"] = f"{level.group(1)}%" if level else "N/A"
    summary["battery_temp"] = normalize_battery_temp(temp.group(1)) if temp else "N/A"

    # RAM (MemTotal / MemAvailable from /proc/meminfo)
    meminfo = _shell(serial, "cat", "/proc/meminfo")
    total = re.search(r"MemTotal:\s*(\d+)", meminfo)
    avail = re.search(r"MemAvailable:\s*(\d+)", meminfo)
    if total and avail:
        try:
            t_gb = int(total.group(1)) / 1024 / 1024
            a_gb = int(avail.group(1)) / 1024 / 1024
            summary["ram"] = f"{t_gb - a_gb:.1f} / {t_gb:.1f} GB"
        except ValueError:
            summary["ram"] = "N/A"
    else:
        summary["ram"] = "N/A"

    # RAM (MemTotal / MemAvailable from /proc/meminfo)
    meminfo = _shell(serial, "cat", "/proc/meminfo")
    total = re.search(r"MemTotal:\s*(\d+)", meminfo)
    avail = re.search(r"MemAvailable:\s*(\d+)", meminfo)
    if total and avail:
        try:
            t_gb = int(total.group(1)) / 1024 / 1024
            a_gb = int(avail.group(1)) / 1024 / 1024
            summary["ram"] = f"{t_gb - a_gb:.1f} / {t_gb:.1f} GB"
        except ValueError:
            summary["ram"] = "N/A"
    else:
        summary["ram"] = "N/A"

    # Storage (df /data)
    df_out = _shell(serial, "df", "/data")
    storage = "N/A"
    for line in df_out.splitlines():
        if "/data" in line:
            parts = line.split()
            if len(parts) >= 5:
                # columns vary; try to find size/used like 52G 14G
                storage = " ".join(parts[1:3])
                break
    summary["storage_raw"] = storage
    # Humanize via df -h
    df_h = _shell(serial, "df", "-h", "/data")
    for line in df_h.splitlines():
        if "/data" in line:
            parts = line.split()
            if len(parts) >= 4:
                #Filesystem Size Used ... -> Size Used
                summary["storage"] = f"{parts[2]} / {parts[1]}"
                break
    else:
        summary["storage"] = storage

    # Resolution
    wm_out = _shell(serial, "wm", "size")
    m = re.search(r"(\d+x\d+)", wm_out)
    summary["resolution"] = m.group(1) if m else "N/A"
    return summary
