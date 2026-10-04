(() => {
  const button = document.querySelector('.lucky-open');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const response = await fetch('/proxy/private-value?id=lucky&field=port', {
        credentials: 'same-origin', cache: 'no-store'
      });
      if (!response.ok) throw new Error('Lucky port unavailable');
      const port = Number((await response.json()).value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid Lucky port');
      const address = button.dataset.public === 'true' ? window.location.hostname : '127.0.0.1';
      const host = address.includes(':') && !address.startsWith('[') ? `[${address}]` : address;
      window.location.assign(`http://${host}:${port}/`);
    } catch (_) {
      const status = button.closest('.card').querySelector('.lucky-open-status');
      status.textContent = button.dataset.error;
      status.hidden = false;
      button.disabled = false;
    }
  });
})();
