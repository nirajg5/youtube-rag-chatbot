const backendStatus = document.getElementById('backend-status');
const backendText = document.getElementById('backend-text');
const videoIdElement = document.getElementById('video-id');
const openButton = document.getElementById('open-chatbot');

// Check backend status
async function checkBackend() {
    try {
        const response = await fetch('http://127.0.0.1:5000/health');
        if (response.ok) {
            const data = await response.json();
            backendStatus.classList.add('active');
            backendStatus.classList.remove('inactive');
            backendText.textContent = 'Connected';

            if (data.video_loaded) {
                videoIdElement.innerHTML = `<span class="video-id">${data.video_id || 'Unknown'}</span>`;
            } else {
                videoIdElement.textContent = 'None';
            }
        } else {
            throw new Error('Backend not responding');
        }
    } catch (error) {
        backendStatus.classList.add('inactive');
        backendStatus.classList.remove('active');
        backendText.textContent = 'Offline: ' + error.message;
        videoIdElement.textContent = 'N/A';
    }
}

const syncButton = document.getElementById('sync-video');

// Open chatbot in new tab
openButton.addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://127.0.0.1:5000' });
});

// Manual Sync
syncButton.addEventListener('click', async () => {
    syncButton.textContent = '⏳ Syncing...';
    syncButton.disabled = true;

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab");

        // Request ID from content script
        chrome.tabs.sendMessage(tab.id, { action: "getVideoId" }, async (response) => {
            if (chrome.runtime.lastError) {
                backendText.textContent = 'Error: Refresh Page';
                syncButton.textContent = '❌ Failed';
                setTimeout(() => {
                    syncButton.textContent = '🔄 Sync Video ID';
                    syncButton.disabled = false;
                }, 2000);
                return;
            }

            if (response && response.videoId) {
                // Send to backend
                try {
                    const res = await fetch('http://127.0.0.1:5000/video-id', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ video_id: response.videoId })
                    });

                    if (res.ok) {
                        syncButton.textContent = '✅ Synced!';
                        checkBackend(); // Refresh UI
                    } else {
                        throw new Error('Backend rejected ID');
                    }
                } catch (e) {
                    backendText.textContent = 'Backend Error';
                    syncButton.textContent = '❌ API Fail';
                }
            } else {
                backendText.textContent = 'No Video Found';
                syncButton.textContent = '❌ No ID';
            }

            setTimeout(() => {
                syncButton.textContent = '🔄 Sync Video ID';
                syncButton.disabled = false;
            }, 2000);
        });
    } catch (error) {
        backendText.textContent = 'Sync Error';
        syncButton.textContent = '❌ Error';
        setTimeout(() => {
            syncButton.textContent = '🔄 Sync Video ID';
            syncButton.disabled = false;
        }, 2000);
    }
});

// Initial check
checkBackend();

// Check every 3 seconds
setInterval(checkBackend, 3000);
