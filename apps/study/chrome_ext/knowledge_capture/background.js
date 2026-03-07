// Service worker — handle message passing
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_CONFIG') {
    chrome.storage.local.get('megaConfig', (data) => {
      sendResponse(data.megaConfig || { apiUrl: 'http://localhost:8081' });
    });
    return true; // async sendResponse
  }
});
