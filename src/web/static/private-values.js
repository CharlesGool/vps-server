(() => {
  const masked = '••••••';
  let leaving = false;
  const flash = (button, message) => {
    const original = button.textContent;
    button.textContent = message;
    setTimeout(() => { if (button.isConnected && button.textContent === message) button.textContent = original; }, 1800);
  };
  const fetchValue = async (id, field, endpoint = '/proxy/private-value') => {
    const query = new URLSearchParams(endpoint === "/frp/client/value" ? { name: id, field } : { id, field });
    const response = await fetch(`${endpoint}?${query}`, {
      credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }
    });
    if (!response.ok) throw new Error(`Reveal failed: ${response.status}`);
    return (await response.json()).value;
  };

  const syncForwarding = (container, value = masked) => {
    if (container.dataset.privateUrl !== '/frp/client/value' || container.dataset.privateField !== 'server') return;
    const address = value !== masked && value.includes(':') ? `[${value}]` : value;
    container.closest('.frp-target-card')?.querySelectorAll('[data-frpc-forward-server]')
      .forEach(display => { display.textContent = address; });
  };

  document.addEventListener('click', async (event) => {
    const reveal = event.target.closest('.private-reveal');
    if (reveal) {
      const container = reveal.closest('.private-value');
      const display = container.querySelector('[data-private-text]');
      if (reveal.getAttribute('aria-pressed') === 'true') {
        display.textContent = masked;
        syncForwarding(container);
        reveal.setAttribute('aria-pressed', 'false');
        reveal.textContent = container.dataset.show;
        return;
      }
      reveal.disabled = true;
      try {
        const value = await fetchValue(container.dataset.privateId, container.dataset.privateField, container.dataset.privateUrl);
        if (!leaving && container.isConnected) {
          display.textContent = value;
          syncForwarding(container, value);
          reveal.setAttribute('aria-pressed', 'true');
          reveal.textContent = container.dataset.hide;
        }
      } catch (_) {
        display.textContent = masked;
        syncForwarding(container);
        flash(reveal, container.dataset.error);
      }
      finally { reveal.disabled = false; }
      return;
    }
    const copy = event.target.closest('.private-copy, .private-share-copy');
    if (copy) {
      const container = copy.closest('.private-value');
      const share = copy.closest('[data-share-id]');
      try {
        const value = await fetchValue(container?.dataset.privateId || share.dataset.shareId,
          container?.dataset.privateField || 'share', container?.dataset.privateUrl);
        flash(copy, (await window.copyPrivateText(value)) ? copy.dataset.copied : copy.dataset.error);
      } catch (_) { flash(copy, copy.dataset.error); }
      return;
    }
    const importButton = event.target.closest('.private-share-import');
    if (importButton) {
      try {
        const url = await fetchValue(importButton.closest('[data-share-id]').dataset.shareId, 'share');
        window.location.href = `clash://install-config?url=${encodeURIComponent(url)}`;
      } catch (_) { flash(importButton, importButton.dataset.error); }
    }
  });

  document.querySelectorAll('[data-share-id] .private-share-qr').forEach((button) => {
    const share = button.closest('[data-share-id]');
    const dialog = share.querySelector('.node-qr-dialog');
    const target = dialog.querySelector('[data-private-qr]');
    dialog.addEventListener('close', () => target.replaceChildren());
    dialog.querySelector('[data-qr-close]').addEventListener('click', () => dialog.close());
    button.addEventListener('click', async () => {
      target.replaceChildren();
      dialog.showModal();
      try {
        const url = await fetchValue(share.dataset.shareId, 'share');
        if (dialog.open) window.renderPrivateQr(target, `clash://install-config?url=${encodeURIComponent(url)}`);
      } catch (_) { target.textContent = target.dataset.error; }
    });
  });
  window.addEventListener('pagehide', () => {
    leaving = true;
    document.querySelectorAll('.private-value').forEach((container) => {
      container.querySelector('[data-private-text]').textContent = masked;
      syncForwarding(container);
      const reveal = container.querySelector('.private-reveal');
      reveal.setAttribute('aria-pressed', 'false');
      reveal.textContent = container.dataset.show;
    });
    document.querySelectorAll('[data-private-qr]').forEach((target) => target.replaceChildren());
  });
  window.addEventListener('pageshow', () => { leaving = false; });
})();
