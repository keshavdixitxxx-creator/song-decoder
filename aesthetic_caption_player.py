#!/usr/bin/env python3
"""Aesthetic terminal caption animator.

Recreates the character-by-character, multi-colour terminal effect shown in
short coding videos. It displays captions from a user-supplied SRT/VTT file
(or plain text file). It does not capture browser audio or fetch lyrics.

Examples:
    py aesthetic_caption_player.py --demo
    py aesthetic_caption_player.py --file my_captions.vtt
    py aesthetic_caption_player.py --file my_captions.srt --speed 0.04
    py aesthetic_caption_player.py --file my_lines.txt --interval 2.5

Use caption files you created or are authorized to use. Save them as UTF-8.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Iterable

# ANSI 256-colour palette inspired by the terminal in the reference video.
C1 = "\033[38;5;147m"  # lavender
C2 = "\033[38;5;175m"  # rose
C3 = "\033[38;5;180m"  # warm gold
C4 = "\033[38;5;168m"  # pink-purple
FAINT = "\033[38;5;250m"
BOLD = "\033[1m"
RESET = "\033[0m"
COLORS = (C1, C2, C3, C4)

TIMESTAMP_RE = re.compile(
    r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{1,3})"
)


def timestamp_seconds(value: str) -> float | None:
    match = TIMESTAMP_RE.search(value.strip())
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    fraction = (match.group(4) + "00")[:3]
    millis = int(fraction)
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_subtitles(path: Path) -> list[tuple[float, str]]:
    """Parse simple SRT or WebVTT cues, preserving multilingual UTF-8 text."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save your caption file as UTF-8 to support all languages.") from exc

    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[tuple[float, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue

        left, right = line.split("-->", 1)
        start = timestamp_seconds(left)
        if start is None:
            i += 1
            continue

        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            value = re.sub(r"<[^>]+>", "", lines[i]).strip()
            # Ignore common SRT positioning / WebVTT cue metadata lines.
            if value and not value.startswith(("NOTE", "STYLE", "REGION")):
                text_lines.append(value)
            i += 1

        text = " ".join(text_lines).strip()
        if text:
            cues.append((start, text))
        i += 1

    return sorted(cues, key=lambda item: item[0])


def parse_plain_text(path: Path) -> list[tuple[float, str]]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("Save your text file as UTF-8 to support all languages.") from exc
    return [(index, line.strip()) for index, line in enumerate(lines) if line.strip()]


def aesthetic_typing(text: str, color: str, speed: float = 0.045) -> None:
    """Print one caption character-by-character, as in the reference clip."""
    sys.stdout.write(BOLD + color)
    sys.stdout.flush()
    if speed <= 0:
        sys.stdout.write(text)
        sys.stdout.write(RESET + "\n")
        sys.stdout.flush()
        return

    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(speed)
    sys.stdout.write(RESET + "\n")
    sys.stdout.flush()


def demo_lines() -> list[tuple[float, str]]:
    # Original sample text only; replace it with your own authorized captions.
    return [
        (0.0, "A new line appears in the terminal..."),
        (2.3, "Each character arrives with its own rhythm..."),
        (5.0, "Soft colours make the words glow."),
        (7.8, "Your captions can use any Unicode language."),
    ]


def animate_cues(cues: Iterable[tuple[float, str]], speed: float, offset: float) -> None:
    start_clock = time.monotonic()
    for index, (cue_time, text) in enumerate(cues):
        target = max(0.0, cue_time + offset)
        wait = target - (time.monotonic() - start_clock)
        if wait > 0:
            time.sleep(wait)
        color = COLORS[index % len(COLORS)]
        aesthetic_typing(text, color, speed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display your own/authorized captions with an aesthetic terminal typing effect."
    )
    parser.add_argument("--file", type=Path, help="UTF-8 .srt, .vtt, or .txt caption file")
    parser.add_argument("--demo", action="store_true", help="Play original sample lines")
    parser.add_argument("--speed", type=float, default=0.045, help="Seconds per character; 0 disables animation")
    parser.add_argument("--interval", type=float, default=2.5, help="Delay between lines in a plain text file")
    parser.add_argument("--offset", type=float, default=0.0, help="Shift all cue times by this many seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.speed < 0 or args.interval < 0 or args.offset < 0:
        print("speed, interval, and offset must be zero or greater.", file=sys.stderr)
        return 2
    if args.demo:
        cues = demo_lines()
    elif args.file:
        if not args.file.is_file():
            print(f"Caption file not found: {args.file}", file=sys.stderr)
            return 2
        suffix = args.file.suffix.lower()
        if suffix in {".srt", ".vtt"}:
            cues = parse_subtitles(args.file)
        elif suffix == ".txt":
            cues = [(i * args.interval, text) for i, (_, text) in enumerate(parse_plain_text(args.file))]
        else:
            print("Use an .srt, .vtt, or .txt file.", file=sys.stderr)
            return 2
    else:
        print("Choose --demo or provide --file captions.vtt", file=sys.stderr)
        return 2

    if not cues:
        print("No caption lines were found.", file=sys.stderr)
        return 1

    print(f"{BOLD}{C3}♫  AESTHETIC CAPTION TERMINAL{RESET}")
    print(f"{FAINT}Timed caption animation • UTF-8 / multilingual • Ctrl+C to stop{RESET}\n")
    try:
        animate_cues(cues, args.speed, args.offset)
    except KeyboardInterrupt:
        print(f"\n{FAINT}Stopped.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
