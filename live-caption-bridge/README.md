# Live Caption to Terminal (Chrome / Edge + Python)

This project forwards new caption lines that are currently visible on a video to a colourful VS Code terminal. The extension checks active HTML5 caption/subtitle cues about every 120 ms. The terminal animates new words in colour in about half a second per caption.

## Scope

- Reads only active cues from native HTML5 caption tracks whose mode is showing.
- Requires captions to be enabled and visible in the player.
- Does not record audio, run speech recognition, download captions, or inspect hidden transcript data.
- Does not read Chrome's separate Live Caption overlay or custom website subtitle renderers.
- YouTube, YouTube Music and Spotify are blocked.
- Use only videos/captions you created or are authorized to process.

## Setup (Windows 10/11, Chrome or Edge)

1. Open VS Code in this folder.
2. Start the Python receiver in the integrated terminal:

       py caption_terminal.py

   Keep it running. No extra Python packages are needed.

3. In Chrome open chrome://extensions (Edge: edge://extensions). Turn on Developer mode, choose Load unpacked, and select this project's extension folder.
4. Open your own video page that uses standard HTML5 captions, turn on CC/subtitles, click the extension icon, then click Start on this tab. New visible caption text should appear in the terminal.

## Test with a local video

1. Open caption_demo.html in Chrome or Edge.
2. On the extension details page, enable Allow access to file URLs (required for this local demo page).
3. Select your video file and a WebVTT .vtt caption file, then click Load video and captions. This folder includes sample_captions.vtt for a visual test.
4. Play the video and check that captions are visibly showing on the video.
5. Click the extension icon and choose Start on this tab. The captions should appear in the terminal with the word animation.

For an .srt subtitle file, convert it to WebVTT .vtt first. The demo page uses the browser's native HTML5 caption track.

## Controls and troubleshooting

- Start on this tab starts capture on the selected tab; Stop capture ends it.
- Press Ctrl+C in VS Code to stop the Python receiver.
- Change animation speed with py caption_terminal.py --animation 0.3.
- If no text appears, start Python first, enable CC, and check that the page uses native HTML5 text tracks. Some video sites draw captions in custom overlays that this extension cannot read.
- If the local demo is not accessible, enable Allow access to file URLs in the extension details.
- YouTube, YouTube Music and Spotify are deliberately unsupported.
