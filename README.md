# Aesthetic Caption Terminal

A small Python program that prints caption lines in the terminal one character at a time, using rotating colours to create the effect shown in the reference clip.

## What it does

- Types each caption gradually, in multiple terminal colours.
- Reads UTF-8 subtitle files in `.srt` or `.vtt` format.
- Supports plain `.txt` files, showing one line at a time.
- Works with multilingual text, including Hindi, when your terminal font supports it.
- Uses only Python's standard library; no packages to install.

## Run

Show the built-in demo:

```powershell
py aesthetic_caption_player.py --demo
```

Play the included sample captions:

```powershell
py aesthetic_caption_player.py --file sample_captions.vtt
```

Use your own subtitle file:

```powershell
py aesthetic_caption_player.py --file "my_captions.srt"
```

Adjust the typing speed (seconds per character):

```powershell
py aesthetic_caption_player.py --file "my_captions.srt" --speed 0.03
```

For a plain text file, set the pause between lines:

```powershell
py aesthetic_caption_player.py --file "my_lines.txt" --interval 2.5
```

Press `Ctrl+C` to stop.

## Important

This program animates caption text that you provide. It does not listen to browser audio, connect to Spotify, or automatically retrieve song lyrics. Use subtitle files you created or are authorized to process.
