/**
 * Background Service Worker for YouTube Video ID Fetcher
 * Handles communication between content script and backend server
 */

const API_BASE_URL = "http://127.0.0.1:5000";
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms

/**
 * Sleep utility for retry delays
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Send video ID to backend with retry logic
 */
async function sendVideoIdWithRetry(videoId, retries = 0) {
  try {
    console.log(`📤 Sending video ID to backend: ${videoId} (attempt ${retries + 1})`);

    const response = await fetch(`${API_BASE_URL}/video-id`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ video_id: videoId }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    console.log("✅ Video ID sent successfully:", data);

    return { success: true, data };

  } catch (error) {
    console.error(`❌ Error sending video ID (attempt ${retries + 1}):`, error.message);

    // Retry logic
    if (retries < MAX_RETRIES) {
      console.log(`🔄 Retrying in ${RETRY_DELAY}ms...`);
      await sleep(RETRY_DELAY);
      return sendVideoIdWithRetry(videoId, retries + 1);
    }

    return {
      success: false,
      error: error.message,
      retriesExhausted: true
    };
  }
}

/**
 * Message listener for content script communication
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "sendVideoId") {
    // Handle async response
    sendVideoIdWithRetry(message.videoId)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({
        success: false,
        error: error.message
      }));

    // Return true to indicate async response
    return true;
  }

  if (message.action === "ping") {
    // Health check
    sendResponse({ status: "ok" });
    return true;
  }
});

/**
 * Extension installation handler
 */
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("🎉 YouTube Video ID Fetcher installed successfully!");
  } else if (details.reason === "update") {
    console.log("🔄 YouTube Video ID Fetcher updated!");
  }
});

console.log("🚀 YouTube Video ID Fetcher background service worker loaded");
