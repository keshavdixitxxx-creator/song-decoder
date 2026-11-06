#!/usr/bin/env python3
"""
lyrics_terminal.py  -  stylish live captions in your terminal (Windows + macOS)

It starts (or connects to) Chrome / Edge / Brave by itself, finds the YouTube /
YouTube Music / Spotify Web tab that is playing, reads the captions that are on
screen and types them in this terminal with colours, gradient and a fancy font.

RUN
    python lyrics_terminal.py                 (Windows)
    python3 lyrics_terminal.py                (macOS)

OPTIONS
    --style script|fraktur|bolditalic|sans|mono|bold|plain     (default: script)
    --browser "C:\\path\\to\\chrome.exe"          use a specific browser
    --no-cc                                    don't auto-turn-on YouTube captions
    --url https://www.youtube.com/             page to open on first start

Needs one package (installed automatically on first run):  websocket-client
"""
import argparse
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request

PORT = 9222
PROFILE = os.path.join(os.path.expanduser("~"), ".lyrics_terminal_profile")
SITES = ("youtube.com", "spotify.com")

os.system("")  # enable ANSI colours in Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ------------------------------------------------------------------ fonts
_STYLE_RANGES = {            # (first capital, first lowercase) in Unicode
    "script": (0x1D4D0, 0x1D4EA),      # 𝓛𝔂𝓻𝓲𝓬𝓼
    "fraktur": (0x1D56C, 0x1D586),     # 𝕷𝖞𝖗𝖎𝖈𝖘
    "bolditalic": (0x1D468, 0x1D482),  # 𝑳𝒚𝒓𝒊𝒄𝒔
    "sans": (0x1D63C, 0x1D656),        # 𝙇𝙮𝙧𝙞𝙘𝙨
    "mono": (0x1D670, 0x1D68A),        # 𝙻𝚢𝚛𝚒𝚌𝚜
    "bold": (0x1D400, 0x1D41A),        # 𝐋𝐲𝐫𝐢𝐜𝐬
}


def make_font(name):
    if name not in _STYLE_RANGES:
        return lambda s: s
    up, lo = _STYLE_RANGES[name]
    table = {}
    for i in range(26):
        table[ord("A") + i] = chr(up + i)
        table[ord("a") + i] = chr(lo + i)
    return lambda s: s.translate(table)


# ------------------------------------------------------------------ look
GRADIENTS = [
    [199, 205, 211, 217, 223, 217, 211, 205],   # pink
    [51, 45, 39, 33, 39, 45],                   # cyan -> blue
    [226, 220, 214, 208, 214, 220],             # gold
    [147, 183, 219, 213, 219, 183],             # lilac
    [118, 82, 48, 49, 48, 82],                  # green
]
SPARKLES = ["✦", "❃", "✧", "❋", "✺", "✿"]
BOLD, DIM, RESET = "\033[1m", "\033[38;5;245m", "\033[0m"
HIDE, SHOW = "\033[?25l", "\033[?25h"
IDLE_CLOSE = 2.5


def c(n):
    return f"\033[38;5;{n}m"


def width():
    return max(30, shutil.get_terminal_size((80, 20)).columns)


# ------------------------------------------------------------------ printer
class Printer:
    """Takes the caption text as it is on the page and types only what is new."""

    def __init__(self, font, out=sys.stdout, animate=True):
        self.font, self.out, self.animate = font, out, animate
        self.prev = []          # words of last caption seen
        self.col = 0            # visible characters on the open line
        self.open = False
        self.idx = 0
        self.words_in_line = 0
        self.last = time.time()

    def reset(self):
        self.prev, self.col, self.open, self.idx, self.words_in_line = [], 0, False, 0, 0

    # -- low level
    def _w(self, s):
        self.out.write(s)
        self.out.flush()

    def _type(self, word):
        # one colour per word (colouring single characters breaks Hindi etc.)
        grad = GRADIENTS[self.idx % len(GRADIENTS)]
        col = c(grad[self.words_in_line % len(grad)])
        self.words_in_line += 1
        styled = self.font(word)
        delay = min(0.04, 0.5 / max(len(styled), 1)) if self.animate else 0
        self._w(f"{BOLD}{col}")
        for ch in styled:
            self._w(ch)
            if delay:
                time.sleep(delay * random.uniform(0.6, 1.4))
        self._w(RESET)
        self.col += len(styled)

    def close_line(self):
        if self.open:
            self._w(f" {DIM}{SPARKLES[self.idx % len(SPARKLES)]}{RESET}\n")
            self.open, self.col, self.words_in_line = False, 0, 0
            self.idx += 1

    def note(self, text):
        self.close_line()
        self._w(f"{DIM}{text}{RESET}\n")

    def idle_check(self):
        if self.open and time.time() - self.last > IDLE_CLOSE:
            self.close_line()

    # -- word helpers
    def _add_words(self, words):
        for w in words:
            if self.open and self.col + len(w) + 1 > width() - 6:
                self.close_line()
            if self.open:
                self._w(" ")
                self.col += 1
            self.open = True
            self._type(w)

    def feed(self, text):
        text = re.sub(r"\[[^\]]*\]|♪|♫", " ", text)      # remove [Music] [संगीत] ♪ tags
        words = text.split()
        if not words or words == self.prev:
            return
        self.last = time.time()
        prev = self.prev

        if prev and words[: len(prev)] == prev:                 # same line grew
            new = words[len(prev):]
        elif prev and prev[: len(words)] == words:              # shrank/flicker
            self.prev = words
            return
        else:
            k = 0                                               # rolling captions
            for n in range(min(len(prev), len(words)), 0, -1):
                if prev[-n:] == words[:n]:
                    k = n
                    break
            if k == len(words):                                 # old tail only
                self.prev = words
                return
            if k >= 3:
                new = words[k:]
            else:                                               # brand new line
                self.close_line()
                new = words
        self.prev = words
        self._add_words(new)


# ------------------------------------------------------------------ browser
def find_browser(custom=None):
    if custom:
        return custom
    sysname = platform.system()
    paths = []
    if sysname == "Windows":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        la = os.environ.get("LOCALAPPDATA", "")
        paths = [
            rf"{pf}\Google\Chrome\Application\chrome.exe",
            rf"{pf86}\Google\Chrome\Application\chrome.exe",
            rf"{la}\Google\Chrome\Application\chrome.exe",
            rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
            rf"{pf}\Microsoft\Edge\Application\msedge.exe",
            rf"{pf}\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
    elif sysname == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
            p = shutil.which(n)
            if p:
                return p
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def http_json(path, timeout=1.0):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def browser_up():
    try:
        http_json("/json/version")
        return True
    except Exception:
        return False


def start_browser(custom, url):
    if browser_up():
        return True
    exe = find_browser(custom)
    if not exe:
        print("Could not find Chrome/Edge/Brave. Use:  --browser \"full\\path\\to\\chrome.exe\"")
        return False
    print(f"Starting browser: {exe}")
    subprocess.Popen(
        [exe, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if browser_up():
            return True
        time.sleep(0.5)
    print("Browser did not open its control port. Close ALL windows of that browser and try again.")
    return False


def ensure_websocket():
    try:
        import websocket
        return websocket
    except ImportError:
        print("Installing the 'websocket-client' package (one time)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "websocket-client"])
        import importlib
        importlib.invalidate_caches()
        try:
            import websocket
            return websocket
        except ImportError:
            sys.exit(f"Please run:  {sys.executable} -m pip install websocket-client")


# JS that runs inside the page and returns what is playing + caption text
PROBE_JS = r"""
(() => {
  const host = location.host;
  const v = document.querySelector('video');
  const playing = !!v && !v.paused && !v.ended;
  let text = '';
  if (host.includes('spotify.com')) {
    const els = document.querySelectorAll('[data-testid="lyrics-line"],[data-testid="fullscreen-lyric"],[class*="lyrics-lyricsContent-lyric"]');
    let best = -1;
    els.forEach(el => {
      const cs = getComputedStyle(el), m = cs.color.match(/\d+(\.\d+)?/g);
      if (!m) return;
      const s = ((+m[0] + +m[1] + +m[2]) / 3) * (m[3] !== undefined ? +m[3] : 1) * (+cs.opacity || 1);
      const t = el.textContent.trim();
      if (t && s > best) { best = s; text = t; }
    });
  } else {
    const btn = document.querySelector('.ytp-subtitles-button');
    if (AUTOCC && btn && btn.getAttribute('aria-pressed') === 'false' && window.__ccTried !== location.href
        && !document.querySelector('.ad-showing')) {
      window.__ccTried = location.href; btn.click();
    }
    let segs = document.querySelectorAll('.ytp-caption-segment');
    if (!segs.length) segs = document.querySelectorAll('.captions-text span, .caption-visual-line span');
    text = [...segs].map(s => s.textContent).join(' ');
  }
  return JSON.stringify({playing, title: document.title.replace(/^\(\d+\)\s*/, ''), url: location.href, text});
})()
"""


class Cdp:
    def __init__(self, websocket, auto_cc):
        self.websocket, self.conns, self.n = websocket, {}, 0
        self.js = PROBE_JS.replace("AUTOCC", "true" if auto_cc else "false")

    def probe(self, tab):
        tid = tab["id"]
        try:
            ws = self.conns.get(tid)
            if ws is None:
                ws = self.websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=2, suppress_origin=True)
                self.conns[tid] = ws
            self.n += 1
            ws.send(json.dumps({"id": self.n, "method": "Runtime.evaluate",
                                "params": {"expression": self.js, "returnByValue": True}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == self.n:
                    return json.loads(msg["result"]["result"]["value"])
        except Exception:
            try:
                self.conns.pop(tid).close()
            except Exception:
                pass
            return None

    def tabs(self):
        try:
            return [t for t in http_json("/json")
                    if t.get("type") == "page" and any(s in t.get("url", "") for s in SITES)
                    and t.get("webSocketDebuggerUrl")]
        except Exception:
            return None


# ------------------------------------------------------------------ main
def banner(title=None):
    t = "♪  live lyrics  ♪"
    line = "─" * (len(t) + 4)
    print(f"{c(213)}╭{line}╮\n│  {t}  │\n╰{line}╯{RESET}")
    if title:
        short = title if len(title) < width() - 4 else title[: width() - 7] + "..."
        print(f"{DIM}{short}{RESET}\n")
    else:
        print(f"{DIM}play a video with captions (CC) in the browser - Ctrl+C to quit{RESET}\n")


def new_screen(title=None):
    os.system("cls" if os.name == "nt" else "clear")
    banner(title)


GENERIC_TITLES = {"", "youtube", "youtube music", "spotify", "spotify – web player", "spotify - web player"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="script", choices=list(_STYLE_RANGES) + ["plain"])
    ap.add_argument("--browser")
    ap.add_argument("--no-cc", action="store_true")
    ap.add_argument("--url", default="https://www.youtube.com/")
    a = ap.parse_args()

    websocket = ensure_websocket()
    os.system("cls" if os.name == "nt" else "clear")
    banner()
    if not start_browser(a.browser, a.url):
        sys.exit(1)

    cdp = Cdp(websocket, not a.no_cc)
    pr = Printer(make_font(a.style))
    sys.stdout.write(HIDE)
    shown_key, shown_title, pending_since, said_wait = None, None, None, False
    try:
        while True:
            tabs = cdp.tabs()
            if tabs is None:
                time.sleep(2)
                if not browser_up():
                    break
                continue
            chosen = None
            for tab in tabs:
                info = cdp.probe(tab)
                if info and info["playing"]:
                    chosen = info
                    break
            if not chosen:
                if not said_wait and shown_key is None:
                    pr.note("waiting for a playing video / song...")
                    said_wait = True
                pr.idle_check()
                time.sleep(0.4)
                continue

            title = chosen["title"].strip()
            generic = title.lower() in GENERIC_TITLES
            key = chosen["url"]
            if key != shown_key or (title != shown_title and not generic):
                # new video/song: wait briefly for its real title, then fresh screen
                if generic and pending_since is None:
                    pending_since = time.time()
                if not generic or time.time() - pending_since > 3:
                    new_screen(title if not generic else None)
                    pr.reset()
                    shown_key, shown_title, pending_since = key, title, None
                else:
                    time.sleep(0.2)
                    continue
            if chosen["text"]:
                pr.feed(chosen["text"])
            pr.idle_check()
            time.sleep(0.12)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW + RESET + "\n")


if __name__ == "__main__":
    main()
