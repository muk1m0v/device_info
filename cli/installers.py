"""Automatic download / install helpers for ADB Platform Tools and scrcpy.

Security: only official sources are used:
  - ADB:  https://dl.google.com / https://developer.android.com
  - scrcpy: https://github.com/Genymobile/scrcpy (official GitHub releases)

No admin rights required: everything is unpacked under tools/.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLATFORM_TOOLS_DIR = PROJECT_ROOT / "tools" / "platform-tools"
SCRCPY_DIR = PROJECT_ROOT / "tools" / "scrcpy"

PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
PLATFORM_TOOLS_PAGE = "https://developer.android.com/tools/releases/platform-tools"
SCRCPY_PAGE = "https://github.com/Genymobile/scrcpy/releases/latest"
SCRCPY_API_LATEST = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
SCRCPY_FALLBACK_URL = "https://github.com/Genymobile/scrcpy/releases/latest/download/scrcpy-win64.zip"

ALLOWED_HOSTS = ("dl.google.com", "developer.android.com", "github.com", "api.github.com", "objects.githubusercontent.com")


def _safe_cprint(text: str) -> None:
    try:
        from rich.console import Console
        Console().print(text)
    except Exception:
        import re

        plain = re.sub(r"\[/?[a-zA-Z0-9 #;:]+\]", "", text)
        try:
            print(plain)
        except Exception:
            print(plain.encode("ascii", "replace").decode("ascii"))


def _print_ok(text: str) -> None:
    _safe_cprint(f"[green]OK {text}[/green]")


def _print_err(text: str) -> None:
    _safe_cprint(f"[red]{text}[/red]")


def _print_info(text: str) -> None:
    _safe_cprint(text)


def _check_host_allowed(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return host in ALLOWED_HOSTS or host.endswith(".githubusercontent.com")


def find_scrcpy() -> str | None:
    found = shutil.which("scrcpy")
    if found:
        return found
    local = SCRCPY_DIR / "scrcpy.exe"
    if local.exists():
        return str(local)
    # release zips sometimes nest one level: tools/scrcpy/scrcpy-win64-*/scrcpy.exe
    for candidate in SCRCPY_DIR.glob("**/scrcpy.exe"):
        return str(candidate)
    return None


def download_file(url: str, dest: Path, timeout: int = 60) -> bool:
    """Download URL to dest. Returns True on success, False with message otherwise."""
    if not _check_host_allowed(url):
        _print_err(f"Blocked untrusted host: {url}")
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "device-info-v1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                _print_err(f"HTTP {status} for {url}")
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
        if not dest.exists() or dest.stat().st_size == 0:
            _print_err("Downloaded file is empty.")
            return False
        return True
    except urllib.error.HTTPError as exc:
        _print_err(f"HTTP error {exc.code} for {url}")
    except urllib.error.URLError as exc:
        _print_err(f"Download failed: {exc.reason}")
    except OSError as exc:
        _print_err(f"Download failed: {exc}")
    return False


def safe_extract_zip(zip_path: Path, target_dir: Path) -> bool:
    """Extract zip, verifying archive integrity first."""
    try:
        if not zipfile.is_zipfile(zip_path):
            _print_err("Downloaded file is not a valid zip archive.")
            return False
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                _print_err(f"Archive is corrupted (bad file: {bad}).")
                return False
            zf.extractall(target_dir)
        return True
    except zipfile.BadZipFile:
        _print_err("Archive is corrupted (BadZipFile).")
    except OSError as exc:
        _print_err(f"Unpack failed: {exc}")
    return False


def get_scrcpy_download_url(timeout: int = 20) -> str:
    """Resolve latest official scrcpy win64 zip URL via GitHub API, else fallback."""
    try:
        req = urllib.request.Request(SCRCPY_API_LATEST, headers={"User-Agent": "device-info-v1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            if "win64" in name and name.endswith(".zip") and _check_host_allowed(url):
                return url
    except Exception:
        pass
    return SCRCPY_FALLBACK_URL


def install_platform_tools() -> bool:
    _print_info(f"Downloading Platform Tools from {PLATFORM_TOOLS_URL} ...")
    with tempfile.TemporaryDirectory() as tmp:
        zipp = Path(tmp) / "platform-tools.zip"
        if not download_file(PLATFORM_TOOLS_URL, zipp):
            return False
        # zip contains top-level "platform-tools/" -> extract into tools/
        if not safe_extract_zip(zipp, PROJECT_ROOT / "tools"):
            return False
    adb = PLATFORM_TOOLS_DIR / "adb.exe"
    if adb.exists():
        _print_ok(f"ADB installed: {adb}")
        return True
    _print_err("Install finished but adb.exe not found.")
    return False


def install_scrcpy() -> bool:
    url = get_scrcpy_download_url()
    _print_info(f"Downloading scrcpy from {url} ...")
    with tempfile.TemporaryDirectory() as tmp:
        zipp = Path(tmp) / "scrcpy.zip"
        if not download_file(url, zipp):
            return False
        SCRCPY_DIR.mkdir(parents=True, exist_ok=True)
        if not safe_extract_zip(zipp, SCRCPY_DIR):
            return False
    found = find_scrcpy()
    if found:
        _print_ok(f"scrcpy installed: {found}")
        return True
    _print_err("Install finished but scrcpy.exe not found.")
    return False


def prompt_install_adb() -> None:
    print("\nAndroid Platform Tools not found.\n")
    print("[1] Install automatically")
    print("[2] Open download page")
    print("[0] Back")
    choice = input("Select: ").strip()
    if choice == "1":
        ok = install_platform_tools()
        if not ok:
            _print_err("Automatic install failed. Try option [2].")
    elif choice == "2":
        webbrowser.open(PLATFORM_TOOLS_PAGE)
        _print_info("Download Platform Tools, unpack to tools/platform-tools/")
    # else back


def prompt_install_scrcpy() -> None:
    print("\nscrcpy not found.\n")
    print("[1] Install automatically")
    print("[2] Open official download page")
    print("[0] Back")
    choice = input("Select: ").strip()
    if choice == "1":
        ok = install_scrcpy()
        if not ok:
            _print_err("Automatic install failed. Try option [2].")
    elif choice == "2":
        webbrowser.open(SCRCPY_PAGE)
        _print_info("Download scrcpy release, unpack to tools/scrcpy/")
    # else back


def run_scrcpy() -> None:
    exe = find_scrcpy()
    if not exe:
        prompt_install_scrcpy()
        return
    _print_info(f"Starting scrcpy: {exe}")
    try:
        subprocess.Popen([exe])
        _print_ok("scrcpy launched.")
    except OSError as exc:
        _print_err(f"Failed to start scrcpy: {exc}")
