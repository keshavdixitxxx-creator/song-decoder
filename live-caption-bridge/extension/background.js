const LOCAL_ENDPOINT = "http://127.0.0.1:39471";
const BLOCKED_HOSTS = ["youtube.com", "youtu.be", "youtube-nocookie.com", "spotify.com"];
let activeTabId = null;
let lastError = "";

function hostIsBlocked(hostname) {
  const host = String(hostname || "").toLowerCase();
  return BLOCKED_HOSTS.some((blocked) => host === blocked || host.endsWith("." + blocked));
}

function notifyPopup(payload) {
  chrome.runtime.sendMessage(payload).catch(() => {});
}

async function sendToTerminal(payload) {
  const response = await fetch(LOCAL_ENDPOINT + "/caption", {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=UTF-8" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error("Python terminal returned HTTP " + response.status);
}

async function checkTerminal() {
  const response = await fetch(LOCAL_ENDPOINT + "/health");
  if (!response.ok) throw new Error("Python terminal is not responding.");
  return response.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "GET_STATUS") {
    sendResponse({ active: activeTabId !== null, message: lastError || "Start the Python terminal, then choose a video tab." });
    return false;
  }

  if (message.type === "START_CAPTURE") {
    (async () => {
      const tabId = Number(message.tabId);
      let pageUrl;
      try { pageUrl = new URL(String(message.url || "")); }
      catch (_) { sendResponse({ ok: false, message: "Could not identify this tab." }); return; }

      if (hostIsBlocked(pageUrl.hostname)) {
        sendResponse({ ok: false, message: "YouTube, YouTube Music and Spotify are deliberately unsupported." });
        return;
      }
      const local = pageUrl.protocol === "file:" || pageUrl.hostname === "localhost" || pageUrl.hostname === "127.0.0.1";
      if (pageUrl.protocol !== "https:" && !local) {
        sendResponse({ ok: false, message: "Use an HTTPS page or the local video demo (file:// or localhost)." });
        return;
      }
      if (!Number.isInteger(tabId)) {
        sendResponse({ ok: false, message: "No active browser tab found." });
        return;
      }

      try {
        await checkTerminal();
        await sendToTerminal({ type: "start", pageTitle: String(message.title || "Caption page") });
        activeTabId = tabId;
        await chrome.scripting.executeScript({ target: { tabId }, files: ["caption_reader.js"] });
        lastError = "";
        sendResponse({ ok: true, message: "Connected. Waiting for visible native captions…" });
      } catch (error) {
        activeTabId = null;
        const detail = error && error.message ? error.message : String(error);
        const fileHint = pageUrl.protocol === "file:" ? " Enable 'Allow access to file URLs' in the extension details." : "";
        lastError = detail;
        sendResponse({ ok: false, message: detail + fileHint });
      }
    })();
    return true;
  }

  if (message.type === "CAPTION_EVENT") {
    if (activeTabId === null || sender.tab?.id !== activeTabId) return false;
    sendToTerminal({
      type: "caption",
      text: String(message.text || "").slice(0, 4000),
      pageTitle: String(message.pageTitle || sender.tab.title || "Caption page").slice(0, 160)
    }).catch((error) => {
      lastError = error.message || String(error);
      notifyPopup({ type: "BRIDGE_STATUS", message: lastError });
    });
    return false;
  }

  if (message.type === "CAPTION_STATUS") {
    if (activeTabId === null || sender.tab?.id !== activeTabId) return false;
    sendToTerminal({ type: "status", message: String(message.message || "").slice(0, 500) }).catch(() => {});
    return false;
  }

  if (message.type === "STOP_CAPTURE") {
    if (activeTabId !== null) {
      chrome.tabs.sendMessage(activeTabId, { type: "STOP_CAPTION_READER" }).catch(() => {});
    }
    sendToTerminal({ type: "stop" }).catch(() => {});
    activeTabId = null;
    sendResponse({ ok: true, message: "Caption capture stopped." });
    return false;
  }
  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeTabId) {
    activeTabId = null;
    sendToTerminal({ type: "stop" }).catch(() => {});
  }
});
