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
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = parsed.hostname or ""
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


# Minimum sane download sizes (bytes). Guards against truncated payloads.
# Real archives are tens of MB; 1 MB is a generous lower bound.
MIN_ARCHIVE_SIZE = 1_000_000


def download_file(url: str, dest: Path, timeout: int = 60,
                  min_size: int = MIN_ARCHIVE_SIZE) -> bool:
    """Download URL to dest. Returns True on success, False with message otherwise."""
    if not _check_host_allowed(url):
        _print_err(f"Blocked untrusted URL (HTTPS + allowlist required): {url}")
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "device-info-v1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                _print_err(f"HTTP {status} for {url}")
                return False
            declared = resp.headers.get("Content-Length")
            if declared is not None:
                try:
                    if int(declared) < min_size:
                        _print_err(
                            f"Server reports suspiciously small file "
                            f"({declared} bytes) for {url}"
                        )
                        return False
                except ValueError:
                    pass
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as fh:
                shutil.copyfileobj(resp, fh)
        if not dest.exists():
            _print_err("Downloaded file is missing.")
            return False
        size = dest.stat().st_size
        if size < min_size:
            _print_err(f"Downloaded file too small ({size} bytes) — likely truncated.")
            try:
                dest.unlink()
            except OSError:
                pass
            return False
        return True
    except urllib.error.HTTPError as exc:
        _print_err(f"HTTP error {exc.code} for {url}")
    except urllib.error.URLError as exc:
        _print_err(f"Download failed (no internet?): {exc.reason}")
    except TimeoutError:
        _print_err("Download timed out.")
    except OSError as exc:
        _print_err(f"Download failed: {exc}")
    return False


def _member_target(zip_path: str, target_dir: Path) -> Path | None:
    """Resolve one archive member; return None if it escapes target_dir."""
    member = Path(zip_path)
    if member.is_absolute():
        return None
    if ".." in member.parts:
        return None
    # Resolve against target without touching the filesystem.
    resolved = (target_dir / member).resolve()
    try:
        resolved.relative_to(target_dir.resolve())
    except ValueError:
        return None
    return resolved


def safe_extract_zip(zip_path: Path, target_dir: Path) -> bool:
    """Extract zip, verifying archive integrity and blocking Zip Slip."""
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
            for name in zf.namelist():
                # Skip directory entries (they resolve fine but carry nothing).
                if name.endswith("/"):
                    continue
                if _member_target(name, target_dir) is None:
                    _print_err(f"Blocked unsafe archive entry: {name}")
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
            if (
                "win64" in name
                and name.endswith(".zip")
                and url.endswith(".zip")
                and _check_host_allowed(url)
            ):
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


def _safe_input(prompt: str) -> str | None:
    """Prompt that returns None on EOF/Ctrl+C instead of raising."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def prompt_install_adb() -> None:
    print("\nAndroid Platform Tools not found.\n")
    print("[1] Install automatically")
    print("[2] Open download page")
    print("[0] Back")
    choice = _safe_input("Select: ")
    if choice is None or choice == "0":
        return
    if choice == "1":
        ok = install_platform_tools()
        if not ok:
            _print_err("Automatic install failed. Try option [2].")
    elif choice == "2":
        try:
            webbrowser.open(PLATFORM_TOOLS_PAGE)
        except Exception:
            _print_err("Could not open the browser.")
            return
        _print_info("Download Platform Tools, unpack to tools/platform-tools/")
    else:
        _print_err("Unknown option.")
    # else back


def prompt_install_scrcpy() -> None:
    print("\nscrcpy not found.\n")
    print("[1] Install automatically")
    print("[2] Open official download page")
    print("[0] Back")
    choice = _safe_input("Select: ")
    if choice is None or choice == "0":
        return
    if choice == "1":
        ok = install_scrcpy()
        if not ok:
            _print_err("Automatic install failed. Try option [2].")
    elif choice == "2":
        try:
            webbrowser.open(SCRCPY_PAGE)
        except Exception:
            _print_err("Could not open the browser.")
            return
        _print_info("Download scrcpy release, unpack to tools/scrcpy/")
    else:
        _print_err("Unknown option.")
    # else back


def run_scrcpy(serial: str | None = None) -> None:
    exe = find_scrcpy()
    if not exe:
        prompt_install_scrcpy()
        return
    if not Path(exe).is_file():
        _print_err("scrcpy binary is missing or corrupted. Reinstall it.")
        prompt_install_scrcpy()
        return
    cmd = [exe]
    if serial:
        cmd += ["--serial", serial]
    _print_info(f"Starting scrcpy: {exe}")
    try:
        subprocess.Popen(cmd)
        _print_ok("scrcpy launched.")
    except OSError as exc:
        _print_err(f"Failed to start scrcpy: {exc}")
