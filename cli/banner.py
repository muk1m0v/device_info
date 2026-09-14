"""Big ASCII banner for Device Info v1."""

from __future__ import annotations

import os

BANNER = r"""
██████╗ ███████╗██╗   ██╗██╗ ██████╗███████╗
██╔══██╗██╔════╝██║   ██║██║██╔════╝██╔════╝
██║  ██║█████╗  ██║   ██║██║██║     █████╗
██║  ██║██╔══╝  ╚██╗ ██╔╝██║██║     ██╔══╝
██████╔╝███████╗ ╚████╔╝ ██║╚██████╗███████╗
╚═════╝ ╚══════╝  ╚═══╝  ╚═╝ ╚═════╝╚══════╝

                     INFO v1
"""


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


BANNER_ASCII = r"""
 ____  _____ __   __ ___ ____ _____
|  _ \| ____|\ \ / /|_ _/ ___| ____|
| | | |  _|   \ V /  | || |   |  _|
| |_| | |___   | |   | || |___| |___
|____/|_____|  |_|  |___\____|_____|

                     INFO v1
"""


def _safe_rich_print(console, *args, **kwargs) -> bool:
    """Print via rich; return False if console encoding can't handle it."""
    try:
        console.print(*args, **kwargs)
        return True
    except Exception:
        return False


def show_banner(version: str = "1.0.0") -> None:
    """Clear terminal and print the banner with pleasant colors."""
    clear_screen()
    try:
        from rich.console import Console

        console = Console()
        if not _safe_rich_print(console, BANNER, style="orange1"):
            # Fallback for cp1252 / piped consoles: plain ASCII.
            print(BANNER_ASCII)
            print(f"DEVICE INFO v{version}")
            print("Android diagnostics via ADB  -  read-only")
            print()
            return
        _safe_rich_print(console, f"DEVICE INFO v{version}", style="bold white", justify="center")
        _safe_rich_print(console, "Android diagnostics via ADB  -  read-only", style="grey62", justify="center")
        try:
            console.print()
        except Exception:
            print()
    except ImportError:
        print(BANNER_ASCII)
        print(f"DEVICE INFO v{version}")
        print("Android diagnostics via ADB  -  read-only")
        print()
