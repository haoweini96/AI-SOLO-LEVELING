// Load saved config
chrome.storage.local.get('megaConfig', (data) => {
  if (data.megaConfig?.apiUrl) {
    document.getElementById('apiUrl').value = data.megaConfig.apiUrl;
  }
});

function showStatus(message, color) {
  const el = document.getElementById('status');
  el.textContent = message;
  el.style.color = color === 'green' ? '#6ee7b7' : '#fca5a5';
  el.style.display = 'block';
}

document.getElementById('save').addEventListener('click', () => {
  const apiUrl = document.getElementById('apiUrl').value.trim();
  chrome.storage.local.set({ megaConfig: { apiUrl } }, () => {
    showStatus('Saved', 'green');
    setTimeout(() => { document.getElementById('status').style.display = 'none'; }, 1500);
  });
});

document.getElementById('test').addEventListener('click', async () => {
  const apiUrl = document.getElementById('apiUrl').value.trim();
  showStatus('Testing...', 'green');
  try {
    const res = await fetch(`${apiUrl}/api/knowledge-tree/stats`);
    if (res.ok) {
      const data = await res.json();
      const nodes = data.stats?.total_nodes ?? '?';
      showStatus(`Connected — ${nodes} nodes`, 'green');
    } else {
      showStatus('API error: ' + res.status, 'red');
    }
  } catch (e) {
    showStatus('Cannot connect: ' + e.message, 'red');
  }
});
