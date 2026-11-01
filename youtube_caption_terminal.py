"""YouTube Visible-Caption Terminal

Opens a dedicated Chrome/Edge profile, then reads ONLY caption text currently
rendered in the YouTube player's visible caption overlay. It does not download
subtitle tracks, scrape hidden transcripts, or use audio recognition.

Use this only with videos/captions you own or are authorized to process.

Install:
    py -m pip install -r requirements-captions.txt

Run:
    py youtube_caption_terminal.py
    py youtube_caption_terminal.py --browser edge
    py youtube_caption_terminal.py --connect-url http://127.0.0.1:9222

The browser window opened by this script uses its own profile. Sign in there if
needed, open a video, and turn on YouTube's CC button. Chrome 136+ requires a
non-default user-data directory for remote debugging; this script uses one.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

COLORS = ["bright_magenta", "bright_cyan", "bright_yellow", "bright_green", "bright_blue"]
CAPTION_JS = r"""() => {
  const selectors = [
    '#movie_player .ytp-caption-window-container .ytp-caption-segment',
    '#movie_player .ytp-caption-segment',
    '.ytp-caption-window-container .ytp-caption-segment'
  ];
  for (const selector of selectors) {
    const nodes = Array.from(document.querySelectorAll(selector));
    const value = nodes.map(node => node.innerText || node.textContent || '')
                      .join(' ').replace(/\s+/g, ' ').trim();
    if (value) return value;
  }
  return '';
}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Animate visible YouTube CC captions in a colorful terminal."
    )
    parser.add_argument("--browser", choices=["chrome", "edge"], default="chrome")
    parser.add_argument(
        "--connect-url", default=None,
        help="Attach to an already-debuggable Chromium browser, e.g. http://127.0.0.1:9222",
    )
    parser.add_argument("--type-speed", type=float, default=0.018, help="Seconds per character (0 disables animation).")
    parser.add_argument("--poll", type=float, default=0.20, help="Caption check interval in seconds.")
    return parser.parse_args()


def find_browser(browser: str) -> str:
    candidates: list[Path] = []
    if browser == "chrome":
        names = ["chrome.exe", "chrome"]
        roots = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Google/Chrome/Application/chrome.exe",
        ]
    else:
        names = ["msedge.exe", "msedge"]
        roots = [
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft/Edge/Application/msedge.exe",
        ]
    for root in roots:
        if root.is_file():
            return str(root)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError(
        f"Could not find {browser.title()}. Install it or pass --connect-url to an existing Chromium browser."
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_cdp(port: int, process: subprocess.Popen[Any], timeout: float = 30.0) -> None:
    endpoint = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Browser exited unexpectedly (code {process.returncode}).")
        try:
            with urllib.request.urlopen(endpoint, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"Browser debugging endpoint did not start: {last_error}")


def launch_debug_browser(browser_name: str) -> tuple[int, subprocess.Popen[Any]]:
    executable = find_browser(browser_name)
    port = free_port()
    local_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    profile_dir = local_root / "CaptionTerminal" / f"{browser_name}-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    command = [
        executable,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        "https://www.youtube.com/",
    ]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    wait_for_cdp(port, process)
    return port, process


def choose_youtube_page(browser: Browser) -> Page | None:
    pages = [page for context in browser.contexts for page in context.pages]
    youtube_pages = [page for page in pages if "youtube.com" in page.url.lower()]
    if not youtube_pages:
        return None

    # Prefer a tab whose video is actively playing; otherwise use the first YouTube tab.
    for page in reversed(youtube_pages):
        try:
            playing = page.evaluate("() => { const v=document.querySelector('video'); return !!v && !v.paused && !v.ended; }")
            if playing:
                return page
        except Exception:
            continue
    return youtube_pages[-1]


def delta_caption(previous: str, current: str) -> str:
    """Avoid reprinting a caption prefix as YouTube reveals words incrementally."""
    if not current or current == previous:
        return ""
    if previous and current.startswith(previous):
        return current[len(previous):].strip()
    return current


def print_animated(console: Console, value: str, color: str, speed: float) -> None:
    if speed <= 0:
        console.print(Text(value, style=f"bold {color}"))
        return
    for char in value:
        console.print(Text(char, style=f"bold {color}"), end="")
        console.file.flush()
        time.sleep(speed)
    console.print()


def main() -> int:
    args = parse_args()
    console = Console()
    if args.poll < 0.05:
        console.print("[bold red]--poll must be at least 0.05 seconds.[/bold red]")
        return 2

    browser_process = None
    port = None
    if args.connect_url:
        endpoint = args.connect_url
    else:
        try:
            port, browser_process = launch_debug_browser(args.browser)
        except Exception as exc:
            console.print(f"[bold red]Could not launch browser:[/bold red] {exc}")
            return 1
        endpoint = f"http://127.0.0.1:{port}"

    console.print(Panel.fit(
        "[bold bright_white]♫ YOUTUBE CAPTION TERMINAL[/bold bright_white]\n"
        "[bright_cyan]Reads caption text currently visible in the YouTube player[/bright_cyan]\n"
        "[dim]Open a video and enable CC. Only on-screen captions are read.[/dim]",
        border_style="bright_magenta",
    ))
    if not args.connect_url:
        console.print("[dim]Use THIS newly opened browser window for YouTube. The script cannot see videos playing in a different, already-open browser window.[/dim]")
    console.print("[dim]Use only with captions you own or are authorized to process. Press Ctrl+C to stop.[/dim]\n")

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(endpoint)
        console.print("[bold green]● Browser connected[/bold green]")
        last_caption = ""
        color_index = 0
        no_caption_notice = False
        while True:
            page = choose_youtube_page(browser)
            if page is None:
                if not no_caption_notice:
                    console.print("[yellow]Waiting for a YouTube tab… Open a video in the launched browser.[/yellow]")
                    no_caption_notice = True
                time.sleep(args.poll)
                continue

            try:
                caption = page.evaluate(CAPTION_JS)
                title = page.title()
            except Exception:
                time.sleep(args.poll)
                continue

            if not caption:
                if not no_caption_notice:
                    console.print("[yellow]No visible captions yet. Turn on YouTube's CC button.[/yellow]")
                    no_caption_notice = True
                time.sleep(args.poll)
                continue

            no_caption_notice = False
            if caption != last_caption:
                new_text = delta_caption(last_caption, caption)
                last_caption = caption
                if new_text:
                    color = COLORS[color_index % len(COLORS)]
                    color_index += 1
                    console.print(f"[dim]{title}[/dim]")
                    print_animated(console, new_text, color, args.type_speed)
            time.sleep(args.poll)

    except KeyboardInterrupt:
        console.print("\n[bold bright_magenta]Caption display stopped.[/bold bright_magenta]")
        return 0
    except Exception as exc:
        console.print(f"[bold red]Browser connection error:[/bold red] {exc}")
        console.print("[dim]Try closing the program and launching it again. For manual connection, use --connect-url.[/dim]")
        return 1
    finally:
        # Disconnect Playwright without intentionally closing the user's browser window.
        try:
            playwright.stop()
        except Exception:
            pass
        # Keep the dedicated browser open so the user can continue watching.


if __name__ == "__main__":
    raise SystemExit(main())
