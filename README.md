# Auto Karaoke Terminal

This repository contains small Windows terminal experiments for media metadata and caption display.

## 1. Media metadata + local lyric files

The original `auto_karaoke_terminal.py` detects the currently active Windows media session and displays matching local lyric files.

Install:

```powershell
py -m pip install -r requirements.txt
```

Run:

```powershell
py auto_karaoke_terminal.py
```

Themes: `neon`, `sunset`, `ocean`, `monochrome`.

The metadata detector does not retrieve lyrics from streaming services. It reads locally supplied UTF-8 `.lrc` or `.txt` files from `lyrics/`.

## 2. Visible YouTube captions in the terminal

`youtube_caption_terminal.py` opens a dedicated Chrome or Edge profile, connects to that browser through the Chrome DevTools Protocol, and reads only the caption text currently rendered in YouTube's visible CC overlay. It animates newly displayed caption text in different terminal colors.

It does not download subtitle tracks or scrape hidden transcripts.

Install:

```powershell
py -m pip install -r requirements-captions.txt
```

Run:

```powershell
py youtube_caption_terminal.py
```

Or use Edge:

```powershell
py youtube_caption_terminal.py --browser edge
```

The script opens a separate browser profile under your local application data. Sign into YouTube in that browser if you need to, open a video, and turn on the **CC** button. The program will display captions while they are visible in the player. Press `Ctrl+C` to stop.

You can change the typing speed or polling interval:

```powershell
py youtube_caption_terminal.py --type-speed 0.01 --poll 0.15
```

Use this caption display only with videos/captions you own or are authorized to process. Captions must be enabled and available for the video. If a video has no captions, the terminal cannot create them.

### Why does it open a separate browser profile?

Recent Chrome versions require remote debugging to use a non-default user-data directory. This script creates a dedicated profile so it does not need access to your normal browser profile. The first run may require you to sign in again in that separate profile.

## 3. Microphone speech transcription

`live_speech_terminal.py` uses a local Whisper model to transcribe speech from a selected microphone/input device.

Install:

```powershell
py -m pip install -r requirements-live-speech.txt
```

Run:

```powershell
py live_speech_terminal.py
```

List input devices:

```powershell
py live_speech_terminal.py --list-devices
```

This microphone mode does not connect to browser audio.

## 4. Aesthetic terminal caption animation

`aesthetic_caption_player.py` recreates the character-by-character, multi-colour typing effect. It accepts UTF-8 `.srt`, `.vtt`, and `.txt` caption files; SRT/VTT timestamps determine when each line appears.

Run the original demo:

```powershell
py aesthetic_caption_player.py --demo
```

Animate the included sample captions:

```powershell
py aesthetic_caption_player.py --file sample_captions.vtt
```

Adjust the typing speed (seconds per character):

```powershell
py aesthetic_caption_player.py --file sample_captions.vtt --speed 0.03
```

No third-party packages are required. Use caption files you created or are authorized to process. This is a caption-file animator; it does not capture browser audio or fetch lyrics.

## Troubleshooting

- For visible YouTube captions, make sure the program-launched browser is open, a video is playing, and CC is enabled.
- If Chrome is not installed, use `--browser edge`.
- If the caption overlay does not appear in the terminal, the video may not provide captions or YouTube may have changed its page markup.
- For microphone transcription, check Windows microphone permissions and select the correct input device.
- For unsupported scripts/glyphs, use a terminal font with appropriate Unicode coverage.

## Permissions and licensing

Use the caption and transcription features only with content you own or are authorized to process. Do not add copyrighted caption or lyric text to this repository without permission. Choose and add an open-source license before redistributing the project.
