# Auto Karaoke Terminal

A Windows terminal app that detects the currently active media session (such as YouTube in Chrome/Edge or Spotify) and displays matching lyric files in a colorful, live terminal.

## Requirements

- Windows 10 or Windows 11
- Python 3.11+
- A browser or music app that exposes playback metadata through Windows media controls

## Install

Open PowerShell or the VS Code terminal in this folder:

```powershell
py -m pip install -r requirements.txt
```

## Run

```powershell
py auto_karaoke_terminal.py
```

Choose a theme:

```powershell
py auto_karaoke_terminal.py --theme neon
py auto_karaoke_terminal.py --theme sunset
py auto_karaoke_terminal.py --theme ocean
py auto_karaoke_terminal.py --theme monochrome
```

Press `Ctrl+C` to quit.

## Lyrics

The app detects the song title, artist, playback status, and position. It does **not** retrieve lyrics from YouTube or Spotify.

Place lyric files that you wrote, supplied, or are licensed to use in the `lyrics/` folder:

- `.lrc` for timestamp-synchronized lyrics
- `.txt` for plain text (scrolling is approximate)

Save files as UTF-8. Unicode text is supported, including Punjabi, Hindi, Arabic, Korean, Japanese, Spanish, and other languages. Exact display depends on the terminal's font support.

The filename should approximately match the cleaned song title, for example `Softly.lrc`. The app also supports artist-plus-title filenames and cautious fuzzy matching.

## Troubleshooting

- If no song appears, check that the browser/app exposes its media session to Windows.
- If lyrics are not found, verify the filename and place the UTF-8 `.lrc` or `.txt` file in `lyrics/`.
- For unsupported glyphs, change the VS Code terminal font to one with the required script coverage.

## License

Choose and add a license before redistributing this project. Do not add copyrighted song lyrics to the repository without permission.
