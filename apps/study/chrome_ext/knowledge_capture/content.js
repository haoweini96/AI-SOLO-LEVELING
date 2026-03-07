// =============================================================================
// Mega Knowledge Capture — Content Script for claude.ai
// =============================================================================

(function () {
  'use strict';

  // Guard: only run on claude.ai chat pages
  if (!window.location.hostname.includes('claude.ai')) return;

  // Prevent double injection
  if (document.getElementById('mega-capture-btn')) return;

  // ---------------------------------------------------------------------------
  // Config
  // ---------------------------------------------------------------------------

  async function getConfig() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, (config) => {
        resolve(config || { apiUrl: 'http://localhost:8081' });
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Conversation extraction
  // ---------------------------------------------------------------------------

  function extractChatId() {
    const match = window.location.pathname.match(/\/chat\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : null;
  }

  function extractChatTitle() {
    // Method 1: page title (Claude uses "Chat Title - Claude")
    const title = document.title.replace(/\s*[-–]\s*Claude\s*$/, '').trim();
    if (title && title !== 'Claude') return title;

    // Method 2: sidebar active item
    const activeItem = document.querySelector('[data-testid="chat-menu-trigger"][aria-current="page"]');
    if (activeItem) return activeItem.textContent.trim();

    // Method 3: first user message from actual DOM
    const firstUser = document.querySelector('[data-testid="user-message"]');
    if (firstUser) {
      const text = firstUser.innerText.trim();
      return text.length > 60 ? text.slice(0, 57) + '...' : text;
    }

    return 'Untitled Chat';
  }

  function extractConversation() {
    const messages = [];

    // Strategy: try multiple selector patterns for claude.ai DOM
    // The DOM structure may change, so we try several approaches

    // Approach 1 (primary): actual claude.ai selectors as of 2026-03
    // User messages: div[data-testid="user-message"]
    // Assistant messages: div.font-claude-response
    const userMsgs = document.querySelectorAll('[data-testid="user-message"]');
    const assistantMsgs = document.querySelectorAll('div.font-claude-response');

    if (userMsgs.length || assistantMsgs.length) {
      const allTurns = [];
      userMsgs.forEach((el) => {
        allTurns.push({ role: 'user', el, text: el.innerText.trim() });
      });
      assistantMsgs.forEach((el) => {
        allTurns.push({ role: 'assistant', el, text: extractText(el) });
      });

      // Sort by DOM order
      allTurns.sort((a, b) => {
        const pos = a.el.compareDocumentPosition(b.el);
        return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });

      allTurns.forEach((t) => {
        if (t.text.trim()) messages.push({ role: t.role, content: t.text.trim() });
      });
    }

    // Approach 2: legacy data-testid selectors (older claude.ai versions)
    if (!messages.length) {
      const humanTurns = document.querySelectorAll('[data-testid="user-human-turn-container"]');
      const assistantTurns = document.querySelectorAll('[data-testid="assistant-turn-container"]');

      if (humanTurns.length || assistantTurns.length) {
        const allTurns = [];
        humanTurns.forEach((el) => {
          allTurns.push({ role: 'user', el, text: extractText(el) });
        });
        assistantTurns.forEach((el) => {
          allTurns.push({ role: 'assistant', el, text: extractText(el) });
        });

        allTurns.sort((a, b) => {
          const pos = a.el.compareDocumentPosition(b.el);
          return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
        });

        allTurns.forEach((t) => {
          if (t.text.trim()) messages.push({ role: t.role, content: t.text.trim() });
        });
      }
    }

    // Approach 3: data-role attributes
    if (!messages.length) {
      const roleEls = document.querySelectorAll('[data-role="user"], [data-role="assistant"]');
      roleEls.forEach((el) => {
        const role = el.getAttribute('data-role');
        const text = extractText(el);
        if (text.trim()) messages.push({ role, content: text.trim() });
      });
    }

    // Approach 4: generic fallback — render-count containers
    if (!messages.length) {
      const containers = document.querySelectorAll('[data-test-render-count]');
      if (containers.length) {
        containers.forEach((container) => {
          const userEl = container.querySelector('[data-testid="user-message"]');
          const asstEl = container.querySelector('div.font-claude-response');
          if (userEl) messages.push({ role: 'user', content: userEl.innerText.trim() });
          if (asstEl) messages.push({ role: 'assistant', content: extractText(asstEl) });
        });
      }
    }

    return {
      messages,
      chatId: extractChatId(),
      title: extractChatTitle(),
      url: window.location.href,
    };
  }

  function extractText(el) {
    // Clone to avoid modifying live DOM
    const clone = el.cloneNode(true);

    // Preserve code blocks
    clone.querySelectorAll('pre, code').forEach((code) => {
      code.textContent = '\n```\n' + code.textContent + '\n```\n';
    });

    // Preserve line breaks
    clone.querySelectorAll('br').forEach((br) => br.replaceWith('\n'));
    clone.querySelectorAll('p, div, li, h1, h2, h3, h4, h5, h6').forEach((block) => {
      block.prepend(document.createTextNode('\n'));
    });

    return clone.textContent.replace(/\n{3,}/g, '\n\n').trim();
  }

  // ---------------------------------------------------------------------------
  // Toast notification
  // ---------------------------------------------------------------------------

  function showToast(message, type) {
    const existing = document.getElementById('mega-capture-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'mega-capture-toast';
    toast.className = 'mega-capture-toast mega-capture-toast--' + type;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('mega-capture-toast--visible'));
    setTimeout(() => {
      toast.classList.remove('mega-capture-toast--visible');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ---------------------------------------------------------------------------
  // Preview panel
  // ---------------------------------------------------------------------------

  function showPreviewPanel(conversation) {
    // Remove existing panel
    const existing = document.getElementById('mega-capture-panel');
    if (existing) existing.remove();

    const userCount = conversation.messages.filter((m) => m.role === 'user').length;
    const asstCount = conversation.messages.filter((m) => m.role === 'assistant').length;

    const panel = document.createElement('div');
    panel.id = 'mega-capture-panel';
    panel.innerHTML = `
      <div class="mega-capture-panel-header">
        <span class="mega-capture-panel-title">Capture to Knowledge Tree</span>
        <button class="mega-capture-panel-close" id="mega-capture-close">&times;</button>
      </div>
      <div class="mega-capture-panel-body">
        <div class="mega-capture-info-row">
          <span class="mega-capture-info-label">Chat</span>
          <span class="mega-capture-info-value">${escapeHtml(conversation.title)}</span>
        </div>
        <div class="mega-capture-info-row">
          <span class="mega-capture-info-label">Messages</span>
          <span class="mega-capture-info-value">${conversation.messages.length} (${userCount} user, ${asstCount} assistant)</span>
        </div>
        <div class="mega-capture-field">
          <label class="mega-capture-field-label">Additional notes (optional)</label>
          <textarea class="mega-capture-textarea" id="mega-capture-notes"
            placeholder="Focus on..., skip the code parts..., etc."></textarea>
        </div>
      </div>
      <div class="mega-capture-panel-footer">
        <button class="mega-capture-btn-cancel" id="mega-capture-cancel">Cancel</button>
        <button class="mega-capture-btn-send" id="mega-capture-send">Capture</button>
      </div>
    `;
    document.body.appendChild(panel);
    requestAnimationFrame(() => panel.classList.add('mega-capture-panel--visible'));

    // Event handlers
    document.getElementById('mega-capture-close').addEventListener('click', closePanel);
    document.getElementById('mega-capture-cancel').addEventListener('click', closePanel);
    document.getElementById('mega-capture-send').addEventListener('click', async () => {
      const notes = document.getElementById('mega-capture-notes').value.trim();
      conversation.userNotes = notes;
      const sendBtn = document.getElementById('mega-capture-send');
      sendBtn.textContent = 'Capturing...';
      sendBtn.disabled = true;
      await sendToMega(conversation);
      closePanel();
    });
  }

  function closePanel() {
    const panel = document.getElementById('mega-capture-panel');
    if (panel) {
      panel.classList.remove('mega-capture-panel--visible');
      setTimeout(() => panel.remove(), 300);
    }
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  // ---------------------------------------------------------------------------
  // Send to Mega API
  // ---------------------------------------------------------------------------

  async function sendToMega(conversationData) {
    const config = await getConfig();
    const apiUrl = config.apiUrl || 'http://localhost:8081';

    try {
      const response = await fetch(`${apiUrl}/api/knowledge-tree/capture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation: conversationData.messages,
          chat_id: conversationData.chatId,
          chat_title: conversationData.title,
          chat_url: conversationData.url,
          user_notes: conversationData.userNotes || '',
        }),
      });

      if (!response.ok) throw new Error(`API error: ${response.status}`);

      const result = await response.json();
      if (result.ok !== false && result.nodes_created !== undefined) {
        showToast(`Captured ${result.nodes_created} knowledge node(s)`, 'success');
      } else {
        showToast(result.error || 'Unknown error', 'error');
      }
    } catch (err) {
      showToast(`Failed: ${err.message}`, 'error');
      console.error('Mega capture error:', err);
    }
  }

  // ---------------------------------------------------------------------------
  // Inject floating button
  // ---------------------------------------------------------------------------

  function injectCaptureUI() {
    const btn = document.createElement('div');
    btn.id = 'mega-capture-btn';
    btn.title = 'Capture to Knowledge Tree';
    btn.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4"/><path d="m4.93 4.93 2.83 2.83m8.48 8.48 2.83 2.83M4.93 19.07l2.83-2.83m8.48-8.48 2.83-2.83"/></svg>`;
    document.body.appendChild(btn);

    btn.addEventListener('click', () => {
      const conversation = extractConversation();
      if (!conversation.messages.length) {
        showToast('No conversation found on this page', 'error');
        return;
      }
      showPreviewPanel(conversation);
    });
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  // Wait for page to be ready, then inject
  if (document.readyState === 'complete') {
    injectCaptureUI();
  } else {
    window.addEventListener('load', injectCaptureUI);
  }
})();
