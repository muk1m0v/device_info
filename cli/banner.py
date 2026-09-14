"""Big ASCII banner for Device Info v1."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

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
    """Clear the terminal via argv-list subprocess (no shell=True)."""
    try:
        if not sys.stdout.isatty():
            return  # piped output: nothing to clear
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "cls"], check=False)
        else:
            subprocess.run(["clear"], check=False)
    except OSError:
        pass


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


def _terminal_width(default: int = 80) -> int:
    """Real terminal width; safe fallback when redirected or unknown."""
    try:
        width = shutil.get_terminal_size(fallback=(default, 24)).columns
        return width if width > 0 else default
    except Exception:
        return default


def _split_art(block: str) -> list[str]:
    """Art lines without blanks; glyph-internal spaces are preserved."""
    return [ln.rstrip() for ln in block.splitlines() if ln.strip()]


def _art_width(lines: list[str]) -> int:
    return max((len(ln) for ln in lines), default=0)


def _center_block(lines: list[str], width: int) -> list[str]:
    """Center the whole block with one computed pad (no fixed spaces)."""
    content = [ln for ln in lines if ln.strip()]
    pad = max(0, (width - _art_width(content)) // 2)
    prefix = " " * pad
    return [prefix + ln for ln in content]


def _center_text(text: str, width: int) -> str:
    pad = max(0, (width - len(text)) // 2)
    return " " * pad + text


def _plain_print(text: str) -> None:
    try:
        print(text)
    except Exception:
        print(text.encode("ascii", "replace").decode("ascii"))


def show_banner(version: str = "1.1.1") -> None:
    """Clear the terminal and print the banner horizontally centered.

    Width tiers (narrow terminals never break):
      1. full block art, if it fits;
      2. reduced ASCII art, if *it* fits;
      3. plain "DEVICE INFO" text.
    A rich encoding failure (e.g. cp1252) steps down to the next tier.
    """
    clear_screen()
    width = _terminal_width()
    title = f"DEVICE INFO v{version}"
    subtitle = "Android diagnostics via ADB  -  read-only"

    box = _split_art(BANNER)
    ascii_art = _split_art(BANNER_ASCII)
    tiers: list[list[str]] = []
    if width >= _art_width(box):
        tiers.append(box)
    if width >= _art_width(ascii_art):
        tiers.append(ascii_art)
    tiers.append(["DEVICE INFO"])

    try:
        from rich.console import Console

        # Same width source for art padding and rich centering.
        console = Console(width=width)
        for art in tiers:
            block = "\n".join(_center_block(art, width))
            if _safe_rich_print(console, block, style="orange1"):
                break
        else:
            raise RuntimeError("banner print failed")
        _safe_rich_print(console, title, style="bold white", justify="center")
        _safe_rich_print(console, subtitle, style="grey62", justify="center")
        try:
            console.print()
        except Exception:
            print()
        return
    except Exception:
        pass
    # Last-resort plain path (no rich, or rich unusable): still centered,
    # ASCII-only so it cannot raise UnicodeEncodeError.
    for art in tiers:
        if all(ch.isascii() for ch in "\n".join(art)):
            chosen = art
            break
    else:
        chosen = ["DEVICE INFO"]
    for line in _center_block(chosen, width):
        _plain_print(line)
    _plain_print(_center_text(title, width))
    _plain_print(_center_text(subtitle, width))
    print()
