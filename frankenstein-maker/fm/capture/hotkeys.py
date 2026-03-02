"""Browser hotkey script injection."""
from __future__ import annotations

HOTKEY_SCRIPT = r'''
(() => {
  if (window.__fmHotkeysInstalled) return;
  window.__fmHotkeysInstalled = true;

  window.addEventListener('keydown', (event) => {
    const key = (event.key || '').toLowerCase();
    if (key === 'c' && !event.metaKey && !event.ctrlKey && !event.altKey) {
      if (window.fmCapture) {
        window.fmCapture({
          url: window.location.href,
          title: document.title || '',
          metrics_text: (document.body && document.body.innerText)
            ? document.body.innerText.slice(0, 2000)
            : ''
        });
      }
    }
    if (key === 'q' && !event.metaKey && !event.ctrlKey && !event.altKey) {
      if (window.fmStopCapture) {
        window.fmStopCapture({ reason: 'user_hotkey_q' });
      }
    }
  }, true);
})();
'''
