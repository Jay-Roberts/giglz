// Scout to Giglz - Popup Script

const DEFAULT_API_URL = 'http://localhost:5001';
// Note: MAX_TEXT_LENGTH (8000) must match server's MAX_EXTRACTION_TEXT_LENGTH

// DOM elements
const statusIdle = document.getElementById('status-idle');
const statusLoading = document.getElementById('status-loading');
const statusSuccess = document.getElementById('status-success');
const statusError = document.getElementById('status-error');
const scoutBtn = document.getElementById('scout-btn');
const retryBtn = document.getElementById('retry-btn');
const apiUrlInput = document.getElementById('api-url');
const saveSettingsBtn = document.getElementById('save-settings');

// Show a specific status, hide others
function showStatus(status) {
  statusIdle.classList.add('hidden');
  statusLoading.classList.add('hidden');
  statusSuccess.classList.add('hidden');
  statusError.classList.add('hidden');
  status.classList.remove('hidden');
}

// Get API URL from storage
async function getApiUrl() {
  const result = await chrome.storage.sync.get(['apiUrl']);
  return result.apiUrl || DEFAULT_API_URL;
}

// Save API URL to storage
async function saveApiUrl(url) {
  await chrome.storage.sync.set({ apiUrl: url });
}

// Get page content from content script
async function getPageContent() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  // Inject content script if needed and get page content
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => ({
      url: window.location.href,
      title: document.title,
      text: document.body.innerText.slice(0, 8000), // MAX_TEXT_LENGTH - must match server
    }),
  });

  return results[0].result;
}

// Scout the current page
async function scout() {
  showStatus(statusLoading);

  try {
    const apiUrl = await getApiUrl();
    const pageContent = await getPageContent();

    const response = await fetch(`${apiUrl}/api/scout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Send session cookies
      body: JSON.stringify(pageContent),
    });

    const data = await response.json();

    if (data.success) {
      // Show success
      document.getElementById('artists').textContent = data.show.artists.join(', ');
      document.getElementById('venue-date').textContent = `${data.show.venue} // ${data.show.date}`;
      document.getElementById('track-count').textContent = data.track_count;
      document.getElementById('view-link').href = `${apiUrl}/shows`;
      showStatus(statusSuccess);
    } else {
      // Show error
      document.getElementById('error-message').textContent = data.error || 'Unknown error';
      showStatus(statusError);
    }
  } catch (err) {
    console.error('Scout error:', err);
    document.getElementById('error-message').textContent =
      err.message || 'Failed to connect to Giglz';
    showStatus(statusError);
  }
}

// Initialize
async function init() {
  // Load saved API URL
  const apiUrl = await getApiUrl();
  apiUrlInput.value = apiUrl;

  // Event listeners
  scoutBtn.addEventListener('click', scout);
  retryBtn.addEventListener('click', () => {
    showStatus(statusIdle);
  });

  saveSettingsBtn.addEventListener('click', async () => {
    const url = apiUrlInput.value.trim() || DEFAULT_API_URL;
    await saveApiUrl(url);
    apiUrlInput.value = url;
    saveSettingsBtn.textContent = 'Saved!';
    setTimeout(() => {
      saveSettingsBtn.textContent = 'Save';
    }, 1500);
  });
}

init();
