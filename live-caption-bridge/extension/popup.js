const statusBox = document.getElementById("status");
const startButton = document.getElementById("start");
const stopButton = document.getElementById("stop");

function showStatus(message) { statusBox.textContent = message || "Ready."; }

async function refreshStatus() {
  try {
    const result = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
    showStatus(result?.message || "Start the Python terminal first.");
  } catch (error) { showStatus("Extension error: " + (error.message || error)); }
}

startButton.addEventListener("click", async () => {
  startButton.disabled = true;
  showStatus("Connecting to Python and checking this tab…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url) { showStatus("Could not read the active tab."); return; }
    const result = await chrome.runtime.sendMessage({
      type: "START_CAPTURE", tabId: tab.id, url: tab.url, title: tab.title || "Caption page"
    });
    showStatus(result?.message || "Capture request sent.");
  } catch (error) { showStatus("Could not start: " + (error.message || error)); }
  finally { startButton.disabled = false; }
});

stopButton.addEventListener("click", async () => {
  try {
    const result = await chrome.runtime.sendMessage({ type: "STOP_CAPTURE" });
    showStatus(result?.message || "Stopped.");
  } catch (error) { showStatus("Could not stop: " + (error.message || error)); }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "BRIDGE_STATUS") showStatus(message.message);
});
refreshStatus();
