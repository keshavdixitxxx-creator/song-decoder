"""Auto Karaoke Terminal for Windows 10/11.

Detects the active Windows media session (for example, YouTube in Chrome/Edge
or Spotify) and displays matching local lyric files in a styled live terminal.

Lyrics are read from UTF-8 .lrc (timestamp-synced) or .txt (plain text) files
inside ./lyrics. Use lyrics you wrote, supplied, or are licensed to use.

Install:
    py -m pip install winrt-Windows.Media.Control rich

Run:
    py auto_karaoke_terminal.py
    py auto_karaoke_terminal.py --theme sunset
    py auto_karaoke_terminal.py --theme ocean

Themes: neon, sunset, ocean, monochrome
"""

from __future__ import annotations

import argparse
import asyncio
import bisect
import difflib
import re
import unicodedata
from pathlib import Path
from typing import Any

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager,
    )
except ImportError as exc:
    raise SystemExit(
        "Missing Windows media-control package. Install it with:\n"
        "  py -m pip install winrt-Windows.Media.Control rich"
    ) from exc

BASE_DIR = Path(__file__).resolve().parent
LYRICS_DIR = BASE_DIR / "lyrics"
POLL_SECONDS = 0.30
PLAIN_TEXT_SECONDS_PER_LINE = 2.8

THEMES: dict[str, dict[str, Any]] = {
    "neon": {
        "border": "bright_magenta",
        "title": "bold bright_white",
        "artist": "italic bright_cyan",
        "active": "bold white on dark_magenta",
        "palette": ["bright_magenta", "bright_cyan", "bright_yellow", "bright_green", "bright_blue"],
        "accent": "bright_magenta",
    },
    "sunset": {
        "border": "bright_red",
        "title": "bold bright_white",
        "artist": "italic bright_yellow",
        "active": "bold black on bright_yellow",
        "palette": ["bright_red", "bright_yellow", "orange1", "bright_magenta", "white"],
        "accent": "bright_yellow",
    },
    "ocean": {
        "border": "bright_cyan",
        "title": "bold bright_white",
        "artist": "italic bright_blue",
        "active": "bold white on dark_cyan",
        "palette": ["bright_cyan", "bright_blue", "bright_white", "turquoise2", "deep_sky_blue1"],
        "accent": "bright_cyan",
    },
    "monochrome": {
        "border": "white",
        "title": "bold white",
        "artist": "italic bright_white",
        "active": "bold black on white",
        "palette": ["white", "grey82", "bright_white", "grey70"],
        "accent": "white",
    },
}

# LRC timestamps such as [01:23.45] or [01:23:456].
LRC_TAG = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")


def enum_name(value: Any) -> str:
    """Get a readable enum name across PyWinRT versions."""
    return str(value).rsplit(".", 1)[-1].strip(" <>").upper()


def normalize(value: str) -> str:
    """Unicode-aware normalization; keeps Punjabi, Hindi, Korean, etc."""
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in value if char.isalnum())


def clean_video_title(raw_title: str, artist: str) -> str:
    """Turn a YouTube upload title into a likely track title."""
    title = unicodedata.normalize("NFKC", raw_title).strip()

    # Most music video uploads put the track name before the first pipe.
    title = title.split("|", 1)[0].strip()

    # Remove common upload labels, whether parenthesized or not.
    title = re.sub(
        r"\s*[\[(](?:official\s*)?(?:music\s*)?(?:video|audio|lyrics?|lyric video|visualizer|4k|hd)[^\])]*[\])]",
        " ", title, flags=re.IGNORECASE,
    )
    title = re.sub(
        r"\b(?:official\s+)?(?:music\s+)?(?:video|audio|lyrics?|lyric video|visualizer)\b",
        " ", title, flags=re.IGNORECASE,
    )
    title = re.sub(r"\b(?:latest|new|full|hd|4k)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(?:19|20)\d{2}\b", " ", title)

    # Remove artist text when the uploader includes "Artist - Song" or
    # "Song - Artist" in the first title segment.
    if artist:
        artist_escaped = re.escape(artist.strip())
        title = re.sub(rf"^\s*{artist_escaped}\s*[-–—:|]+\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(rf"\s*[-–—:|]+\s*{artist_escaped}\s*$", "", title, flags=re.IGNORECASE)
        # Some uploads write "Song Name ARTIST NAME" with no separator.
        if title.casefold().endswith(artist.strip().casefold()):
            possible_song = title[: -len(artist.strip())].rstrip()
            if possible_song:
                title = possible_song

    title = re.sub(r"\s+", " ", title).strip(" -–—:|·")
    return title or raw_title.strip()


def find_lyrics(raw_title: str, artist: str) -> tuple[Path | None, str]:
    """Find .lrc or .txt using cleaned title, artist, and fuzzy matching."""
    LYRICS_DIR.mkdir(parents=True, exist_ok=True)
    clean_title = clean_video_title(raw_title, artist)
    wanted = [normalize(clean_title)]
    if artist:
        wanted.extend([
            normalize(f"{clean_title} {artist}"),
            normalize(f"{artist} {clean_title}"),
        ])

    candidates = [
        path for path in LYRICS_DIR.iterdir()
        if path.is_file() and path.suffix.casefold() in {".lrc", ".txt"}
    ]
    # Prefer exact .lrc (synchronized), then exact .txt.
    for suffix in (".lrc", ".txt"):
        for path in candidates:
            if path.suffix.casefold() == suffix and normalize(path.stem) in wanted:
                return path, clean_title

    # Fuzzy matching helps when punctuation or minor title wording differs.
    # Require a strong score to avoid selecting lyrics for the wrong song.
    best: tuple[float, Path] | None = None
    for path in candidates:
        stem = normalize(path.stem)
        if not stem:
            continue
        score = max(difflib.SequenceMatcher(None, key, stem).ratio() for key in wanted if key)
        if best is None or score > best[0]:
            best = (score, path)
    if best and best[0] >= 0.88:
        return best[1], clean_title

    return None, clean_title


def read_text_file(path: Path) -> list[str]:
    """Read Unicode lyric text. UTF-8 is the recommended file encoding."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"{path.name} is not UTF-8. Save it as UTF-8 so non-English text displays correctly."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read {path.name}: {exc}") from exc
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def load_lrc(path: Path) -> list[tuple[float, str]]:
    """Parse synchronized .lrc lines, including multiple tags per line."""
    try:
        raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"{path.name} is not UTF-8. Save it as UTF-8 for multilingual lyrics."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read {path.name}: {exc}") from exc

    lines: list[tuple[float, str]] = []
    for raw in raw_lines:
        tags = list(LRC_TAG.finditer(raw))
        if not tags:
            continue
        lyric = LRC_TAG.sub("", raw).strip()
        for tag in tags:
            minutes = int(tag.group(1))
            seconds = int(tag.group(2))
            fraction = tag.group(3) or "0"
            millis = int((fraction + "00")[:3])
            timestamp = minutes * 60 + seconds + millis / 1000
            lines.append((timestamp, lyric))

    return sorted(lines, key=lambda item: item[0])


async def read_session(session: Any) -> dict[str, Any] | None:
    """Read metadata and playback position from one Windows media session."""
    try:
        props = await session.try_get_media_properties_async()
        playback = session.get_playback_info()
        timeline = session.get_timeline_properties()
        title = (props.title or "").strip()
        if not title:
            return None
        return {
            "title": title,
            "artist": (props.artist or "").strip(),
            "status": enum_name(playback.playback_status),
            "position": max(0.0, timeline.position.total_seconds()),
            "source": session.source_app_user_model_id or "Browser / media app",
        }
    except Exception:
        # A browser tab may close or change tracks while metadata is read.
        return None


async def get_active_track(manager: Any) -> dict[str, Any] | None:
    """Prefer the session that is currently playing; fall back to paused media."""
    sessions = list(manager.get_sessions())
    current = manager.get_current_session()
    ordered: list[Any] = []
    if current is not None:
        ordered.append(current)
    ordered.extend(session for session in sessions if session is not current)

    paused_fallback = None
    for session in ordered:
        data = await read_session(session)
        if not data:
            continue
        status = data["status"]
        if "PLAYING" in status or status == "4":
            return data
        if ("PAUSED" in status or status == "5") and paused_fallback is None:
            paused_fallback = data
    return paused_fallback


def lyric_window(
    lines: list[tuple[float, str]], position: float,
) -> tuple[int, int, int]:
    stamps = [line[0] for line in lines]
    current = bisect.bisect_right(stamps, position) - 1
    current = max(0, min(current, len(lines) - 1))
    return current, max(0, current - 2), min(len(lines), current + 5)


def render_screen(
    track: dict[str, Any] | None,
    lyric_lines: list[tuple[float, str]],
    plain_lines: list[str],
    lyric_path: Path | None,
    clean_title: str,
    theme_name: str,
    error: str | None = None,
) -> Panel:
    theme = THEMES[theme_name]
    border = theme["border"]

    if track is None:
        body = Group(
            Text("♫  Waiting for music…", style=f"bold {theme['accent']}"),
            Text("Play a song in YouTube (Chrome / Edge) or Spotify.", style="dim"),
            Text("The app or browser must expose its media session to Windows.", style="dim"),
        )
        return Panel(Align.center(body, vertical="middle"), title="AUTO KARAOKE", border_style=border, padding=(1, 3))

    title = clean_title or track["title"]
    artist = track["artist"] or "Artist not provided by the player"
    position = track["position"]
    status = track["status"].replace("_", " ")

    header = Text()
    header.append("♫  ", style=f"bold {theme['accent']}")
    header.append(title, style=theme["title"])
    header.append("\n" + artist, style=theme["artist"])
    header.append(f"\n{track['source']}  •  {status}  •  {position:0.1f}s", style="dim")
    blocks: list[Any] = [header, Text("")]

    if error:
        blocks.append(Text(error, style="bold yellow", justify="center"))
    elif lyric_path is None:
        blocks.append(Text("♫  No matching lyric file yet", style="bold yellow", justify="center"))
        blocks.append(Text("Put an authorized UTF-8 .lrc or .txt file in the lyrics folder.", style="dim", justify="center"))
        blocks.append(Text(f"Try: {clean_title}.lrc  or  {clean_title} - {artist}.lrc", style="dim", justify="center"))
        blocks.append(Text("Unicode lyrics are supported (Punjabi, Hindi, Korean, Spanish, etc.).", style="dim", justify="center"))
    elif lyric_path.suffix.casefold() == ".lrc" and lyric_lines:
        current, first, last = lyric_window(lyric_lines, position)
        for idx in range(first, last):
            text = lyric_lines[idx][1] or "♪"
            style = theme["active"] if idx == current else theme["palette"][idx % len(theme["palette"])]
            blocks.append(Text(text, style=style, justify="center", overflow="fold"))
        blocks.append(Text(f"\nSYNCED LYRICS  •  LINE {current + 1}/{len(lyric_lines)}", style="dim", justify="center"))
    elif lyric_path.suffix.casefold() == ".txt" and plain_lines:
        # Plain text cannot be precisely synchronized; scroll at an estimate.
        current = min(int(position / PLAIN_TEXT_SECONDS_PER_LINE), len(plain_lines) - 1)
        first = max(0, current - 2)
        last = min(len(plain_lines), current + 5)
        for idx in range(first, last):
            style = theme["active"] if idx == current else theme["palette"][idx % len(theme["palette"])]
            blocks.append(Text(plain_lines[idx], style=style, justify="center", overflow="fold"))
        blocks.append(Text(f"\nPLAIN TEXT  •  APPROXIMATE SCROLL  •  LINE {current + 1}/{len(plain_lines)}", style="dim", justify="center"))
    else:
        blocks.append(Text("The lyric file contains no readable lines.", style="bold yellow", justify="center"))

    return Panel(Align.center(Group(*blocks)), title=f"NOW PLAYING  •  {theme_name.upper()} THEME", border_style=border, padding=(1, 3))


async def main(theme_name: str) -> None:
    console = Console()
    LYRICS_DIR.mkdir(parents=True, exist_ok=True)
    theme = THEMES[theme_name]
    console.print(f"[bold {theme['accent']}]AUTO KARAOKE TERMINAL[/bold {theme['accent']}]")
    console.print(f"[dim]Theme: {theme_name}  •  Press Ctrl+C to quit[/dim]\n")

    try:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    except Exception as exc:
        console.print(f"[bold red]Could not connect to Windows media controls:[/bold red] {exc}")
        return

    cached_key: tuple[str, str] | None = None
    cached_path: Path | None = None
    cached_title = ""
    cached_lrc: list[tuple[float, str]] = []
    cached_txt: list[str] = []
    cached_error: str | None = None

    with Live(console=console, refresh_per_second=8, screen=True) as live:
        try:
            while True:
                track = await get_active_track(manager)
                if track is not None:
                    key = (track["title"], track["artist"])
                    if key != cached_key:
                        cached_key = key
                        cached_path, cached_title = find_lyrics(*key)
                        cached_lrc = []
                        cached_txt = []
                        cached_error = None
                        if cached_path:
                            try:
                                if cached_path.suffix.casefold() == ".lrc":
                                    cached_lrc = load_lrc(cached_path)
                                    if not cached_lrc:
                                        cached_error = f"No timestamped lines found in {cached_path.name}."
                                else:
                                    cached_txt = read_text_file(cached_path)
                                    if not cached_txt:
                                        cached_error = f"No text lines found in {cached_path.name}."
                            except RuntimeError as exc:
                                cached_error = str(exc)
                live.update(
                    render_screen(
                        track, cached_lrc, cached_txt, cached_path,
                        cached_title, theme_name, cached_error,
                    ),
                    refresh=True,
                )
                await asyncio.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatic styled lyrics terminal")
    parser.add_argument("--theme", choices=sorted(THEMES), default="neon", help="Terminal color theme")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args().theme))
    except KeyboardInterrupt:
        pass
