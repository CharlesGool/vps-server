(() => {
  const button = document.querySelector('.lucky-open');
  if (!button) return;
  const card = button.closest('.lucky-page');
  const addressLabel = card.querySelector('.lucky-address');
  const stateLabel = card.querySelector('.lucky-state');
  const errorLabel = card.querySelector('.lucky-open-status');
  const hostName = window.location.hostname;
  const host = hostName.includes(':') && !hostName.startsWith('[') ? `[${hostName}]` : hostName;
  let currentUrl = '';
  let leaving = false;

  const refresh = async () => {
    const response = await fetch('/lucky/status', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error('Lucky status unavailable');
    const data = await response.json();
    const port = Number(data.port);
    const scheme = data.scheme === 'https' ? 'https' : 'http';
    currentUrl = Number.isInteger(port) && port >= 1 && port <= 65535 ? `${scheme}://${host}:${port}/` : '';
    addressLabel.textContent = currentUrl || '—';
    stateLabel.textContent = data.running ? card.dataset.active : card.dataset.stopped;
    button.disabled = !data.running || !currentUrl;
    errorLabel.hidden = true;
  };
  const poll = async () => {
    if (leaving || document.hidden) return;
    try { await refresh(); }
    catch (_) { button.disabled = true; }
  };
  button.addEventListener('click', async () => {
    button.disabled = true;
    // Open the tab inside the click so the browser allows it, then point it at Lucky.
    const tab = window.open('', '_blank');
    try {
      await refresh();
      if (!currentUrl || button.disabled || !tab) throw new Error('Lucky unavailable');
      tab.opener = null;
      tab.location.href = currentUrl;
    } catch (_) {
      tab?.close();
      errorLabel.textContent = button.dataset.error;
      errorLabel.hidden = false;
    }
  });
  window.addEventListener('pagehide', () => { leaving = true; });
  document.addEventListener('visibilitychange', poll);
  poll();
  setInterval(poll, 5000);
})();
