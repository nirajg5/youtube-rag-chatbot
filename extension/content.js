/**
 * Content Script for YouTube Video ID Detection
 * Monitors YouTube pages and extracts video IDs
 */

const CHECK_INTERVAL = 1000; // Check every second
const SEND_DELAY = 500; // Delay before sending to avoid rapid changes

let lastVideoId = null;
let sendTimeout = null;
let isProcessing = false;

/**
 * Extract video ID from current page URL
 */
function getVideoId() {
  // Method 1: Check URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const videoIdFromParam = urlParams.get("v");

  if (videoIdFromParam) {
    return videoIdFromParam;
  }

  // Method 2: Check for shorts format
  const shortsMatch = window.location.pathname.match(/\/shorts\/([a-zA-Z0-9_-]{11})/);
  if (shortsMatch) {
    return shortsMatch[1];
  }

  // Method 3: Check embed format
  const embedMatch = window.location.pathname.match(/\/embed\/([a-zA-Z0-9_-]{11})/);
  if (embedMatch) {
    return embedMatch[1];
  }

  return null;
}

/**
 * Validate video ID format
 */
function isValidVideoId(videoId) {
  if (!videoId) return false;

  // YouTube video IDs are typically 11 characters
  // Contains alphanumeric characters, hyphens, and underscores
  const videoIdPattern = /^[a-zA-Z0-9_-]{11}$/;
  return videoIdPattern.test(videoId);
}

/**
 * Send video ID to background script
 */
function sendVideoId(videoId) {
  if (isProcessing) {
    console.log("⏳ Already processing a video ID, skipping...");
    return;
  }

  isProcessing = true;

  console.log("🎬 Detected video:", videoId);

  chrome.runtime.sendMessage(
    {
      action: "sendVideoId",
      videoId: videoId,
    },
    (response) => {
      isProcessing = false;

      if (chrome.runtime.lastError) {
        console.error("❌ Extension error:", chrome.runtime.lastError.message);
        return;
      }

      if (response) {
        if (response.success) {
          console.log("✅ Video ID sent successfully:", response.data);
        } else {
          console.error("❌ Failed to send video ID:", response.error);
          if (response.retriesExhausted) {
            console.error("⚠️ All retries exhausted. Is the backend server running?");
          }
        }
      }
    }
  );
}

/**
 * Monitor for video ID changes
 */
function monitorVideoId() {
  const videoId = getVideoId();

  // Only process if we have a valid video ID and it's different from the last one
  if (videoId && isValidVideoId(videoId) && videoId !== lastVideoId) {
    // Clear any pending send timeout
    if (sendTimeout) {
      clearTimeout(sendTimeout);
    }

    // Update last video ID
    lastVideoId = videoId;

    // Delay sending to avoid rapid navigation changes
    sendTimeout = setTimeout(() => {
      sendVideoId(videoId);
    }, SEND_DELAY);
  }
}

/**
 * Initialize monitoring
 */
function init() {
  console.log("🚀 YouTube Video ID Detector initialized");

  // Initial check
  monitorVideoId();

  // Set up periodic monitoring
  setInterval(monitorVideoId, CHECK_INTERVAL);

  // Listen for navigation events (YouTube uses SPA navigation)
  let lastUrl = location.href;
  new MutationObserver(() => {
    const url = location.href;
    if (url !== lastUrl) {
      lastUrl = url;
      console.log("🔄 Navigation detected, checking for new video...");
      monitorVideoId();
    }
  }).observe(document, { subtree: true, childList: true });
}

// Listen for manual sync request
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "getVideoId") {
    const videoId = getVideoId();
    console.log("📥 Manual sync request received. Found ID:", videoId);
    sendResponse({ videoId: videoId });
  }
});

// Relaxed ID validation
function isValidVideoId(videoId) {
  if (!videoId) return false;
  // Allow 10-12 chars just in case (standard is 11)
  const videoIdPattern = /^[a-zA-Z0-9_-]{10,12}$/;
  return videoIdPattern.test(videoId);
}

// Start monitoring when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
