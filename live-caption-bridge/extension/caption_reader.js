(() => {
  if (window.__liveCaptionTerminalReader) return;
  window.__liveCaptionTerminalReader = true;

  let stopped = false;
  let lastCaption = "";
  let lastStatus = "";

  function sendStatus(message) {
    if (message === lastStatus) return;
    lastStatus = message;
    try { chrome.runtime.sendMessage({ type: "CAPTION_STATUS", message }); } catch (_) {}
  }

  function sendCaption(text) {
    if (stopped || !text) return;
    try {
      chrome.runtime.sendMessage({ type: "CAPTION_EVENT", text, pageTitle: document.title });
    } catch (_) {}
  }

  // Only inspect active cues on native caption/subtitle tracks that are enabled.
  function getVisibleCaptionText() {
    const lines = [];
    for (const video of document.querySelectorAll("video")) {
      for (const track of Array.from(video.textTracks || [])) {
        const kind = String(track.kind || "").toLowerCase();
        if ((kind !== "captions" && kind !== "subtitles") || track.mode !== "showing") continue;
        for (const cue of Array.from(track.activeCues || [])) {
          const value = String(cue.text || "")
            .replace(/<[^>]*>/g, " ")
            .replace(/&nbsp;/gi, " ")
            .replace(/&amp;/gi, "&")
            .replace(/\s+/g, " ")
            .trim();
          if (value && !lines.includes(value)) lines.push(value);
        }
      }
    }
    return lines.join(" ").trim();
  }

  function newPart(previous, current) {
    if (!current || current === previous) return "";
    if (previous && current.startsWith(previous)) return current.slice(previous.length).trim();
    return current;
  }

  function poll() {
    if (stopped) return;
    const current = getVisibleCaptionText();
    if (!current) {
      sendStatus("No visible native caption cue yet. Turn on CC/subtitles in the video player.");
      lastCaption = "";
      return;
    }
    lastStatus = "";
    const freshText = newPart(lastCaption, current);
    lastCaption = current;
    if (freshText) sendCaption(freshText);
  }

  const timer = window.setInterval(poll, 120);
  const observer = new MutationObserver(poll);
  if (document.documentElement) observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("visibilitychange", poll);
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "STOP_CAPTION_READER") {
      stopped = true;
      window.clearInterval(timer);
      observer.disconnect();
      document.removeEventListener("visibilitychange", poll);
      window.__liveCaptionTerminalReader = false;
    }
  });

  sendStatus("Connected to this tab. Waiting for active captions…");
  poll();
})();
