// Scout to Giglz - Content Script
// This script runs on every page and responds to messages from the popup.

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPageContent') {
    sendResponse({
      url: window.location.href,
      title: document.title,
      text: document.body.innerText.slice(0, 8000), // Must match server MAX_EXTRACTION_TEXT_LENGTH
    });
  }
  return true; // Keep channel open for async response
});
