(() => {
  const button = document.querySelector('.lucky-open');
  if (!button) return;
  const card = button.closest('.lucky-page');
  const addressLabel = card.querySelector('.lucky-address');
  const stateLabel = card.querySelector('.lucky-state');
  const errorLabel = card.querySelector('.lucky-open-status');
  // Lucky is shown through the console at /lucky/; its own port stays closed.
  const adminUrl = new URL('/lucky/', window.location.href).href;
  addressLabel.textContent = adminUrl;
  let leaving = false;

  const refresh = async () => {
    const response = await fetch('/lucky-status', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error('Lucky status unavailable');
    const data = await response.json();
    stateLabel.textContent = data.running ? card.dataset.active : card.dataset.stopped;
    button.disabled = !data.running;
    errorLabel.hidden = true;
    return data.running;
  };
  const poll = async () => {
    if (leaving || document.hidden) return;
    try { await refresh(); }
    catch (_) { button.disabled = true; }
  };
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      if (!await refresh()) throw new Error('Lucky unavailable');
      leaving = true;
      window.location.assign(adminUrl);
    } catch (_) {
      errorLabel.textContent = button.dataset.error;
      errorLabel.hidden = false;
    }
  });
  window.addEventListener('pagehide', () => { leaving = true; });
  document.addEventListener('visibilitychange', poll);
  poll();
  setInterval(poll, 5000);
})();
