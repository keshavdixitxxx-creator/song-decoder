"""Live Speech Terminal — multilingual, colorful microphone transcription.

This version transcribes spoken audio from the selected microphone/input device.
It does not connect to browser/music-app audio sessions or retrieve song lyrics.
Use it for your own speech and audio you have permission to transcribe.

Install:
    py -m pip install -r requirements-live-speech.txt

Run:
    py live_speech_terminal.py
    py live_speech_terminal.py --model base
    py live_speech_terminal.py --list-devices
    py live_speech_terminal.py --device 2

The first run downloads the selected Whisper model. Transcription then runs locally.
"""

from __future__ import annotations

import argparse
import queue
import sys
import time
from collections import deque
from typing import Iterable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

SAMPLE_RATE = 16_000
CHANNELS = 1
BLOCK_SECONDS = 0.25
CHUNK_SECONDS = 6.0
OVERLAP_SECONDS = 0.8
COLORS = ["bright_magenta", "bright_cyan", "bright_yellow", "bright_green", "bright_blue"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Colorful multilingual live speech transcription from a microphone."
    )
    parser.add_argument(
        "--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size. Larger models are usually more accurate but slower.",
    )
    parser.add_argument("--device", type=int, default=None, help="Input device index (see --list-devices).")
    parser.add_argument("--list-devices", action="store_true", help="List available audio input devices and exit.")
    parser.add_argument("--language", default=None, help="Optional language code, e.g. en, hi, pa, es. Default: auto-detect.")
    parser.add_argument("--chunk-seconds", type=float, default=CHUNK_SECONDS, help="Audio window size (minimum 3 seconds).")
    parser.add_argument("--no-typewriter", action="store_true", help="Print recognized lines without the typing animation.")
    return parser.parse_args()


def print_devices() -> None:
    print("Available audio devices:")
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            print(f"  [{index}] {device['name']}  (inputs: {device['max_input_channels']})")


def typewriter(console: Console, value: str, color: str, enabled: bool) -> None:
    if not enabled:
        console.print(Text(value, style=f"bold {color}"))
        return
    for char in value:
        console.print(char, style=f"bold {color}", end="")
        console.file.flush()
        time.sleep(0.012)
    console.print()


def audio_callback(indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags,
                   audio_queue: queue.Queue[np.ndarray]) -> None:
    # Keep callback short; inference happens on the main thread.
    if status:
        # Device overflow/underflow notices are reported by sounddevice; audio continues.
        pass
    try:
        audio_queue.put_nowait(indata[:, 0].copy())
    except queue.Full:
        # Drop the oldest block rather than blocking the real-time audio callback.
        try:
            audio_queue.get_nowait()
            audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Empty:
            pass


def collect_audio(audio_queue: queue.Queue[np.ndarray], needed_samples: int,
                  carry: deque[np.ndarray]) -> np.ndarray:
    pieces: list[np.ndarray] = list(carry)
    total = sum(piece.size for piece in pieces)
    while total < needed_samples:
        try:
            block = audio_queue.get(timeout=2.0)
        except queue.Empty:
            continue
        pieces.append(block)
        total += block.size
    combined = np.concatenate(pieces).astype(np.float32, copy=False)
    chunk = combined[-needed_samples:]
    overlap_samples = int(OVERLAP_SECONDS * SAMPLE_RATE)
    carry.clear()
    if overlap_samples:
        carry.append(chunk[-overlap_samples:].copy())
    return chunk


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def transcribe_chunk(model: WhisperModel, samples: np.ndarray, language: str | None) -> tuple[str | None, list[str]]:
    segments, info = model.transcribe(
        samples,
        language=language,
        task="transcribe",
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
        without_timestamps=True,
    )
    lines = [segment.text.strip() for segment in segments if segment.text and segment.text.strip()]
    detected_language = getattr(info, "language", None)
    return detected_language, lines


def main() -> int:
    args = parse_args()
    console = Console()
    if args.list_devices:
        print_devices()
        return 0
    if args.chunk_seconds < 3:
        console.print("[bold red]--chunk-seconds must be at least 3.[/bold red]")
        return 2

    console.print(Panel.fit(
        "[bold bright_white]♫ LIVE SPEECH TERMINAL[/bold bright_white]\n"
        "[bright_cyan]Multilingual microphone transcription[/bright_cyan]\n"
        "[dim]Listening to microphone/input audio — not browser or song lyrics.[/dim]",
        border_style="bright_magenta",
    ))
    console.print("[dim]Press Ctrl+C to stop. First run may download the Whisper model.[/dim]")
    console.print(f"[dim]Loading Whisper {args.model} model on CPU (int8)…[/dim]")

    try:
        model = WhisperModel(args.model, device="cpu", compute_type="int8")
    except Exception as exc:
        console.print(f"[bold red]Could not load speech model:[/bold red] {exc}")
        return 1

    audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=32)
    callback = lambda indata, frames, time_info, status: audio_callback(
        indata, frames, time_info, status, audio_queue
    )
    needed_samples = int(args.chunk_seconds * SAMPLE_RATE)
    carry: deque[np.ndarray] = deque()
    last_text = ""
    color_index = 0

    try:
        with sd.InputStream(
            device=args.device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,