(() => {
  const button = document.querySelector('.tailscale-web-open');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const query = new URLSearchParams({ id: 'tailscale-tailscale_ipv4', field: 'address' });
      const response = await fetch(`/tailscale/private-value?${query}`, {
        credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }
      });
      if (!response.ok) throw new Error('Tailscale address unavailable');
      const { value } = await response.json();
      const parts = typeof value === 'string' && /^\d+\.\d+\.\d+\.\d+$/.test(value)
        ? value.split('.').map(Number) : [];
      if (parts.length !== 4 || parts[0] !== 100 || parts[1] < 64 || parts[1] > 127 ||
          parts.slice(2).some(part => part < 0 || part > 255)) {
        throw new Error('Invalid Tailscale address');
      }
      window.location.assign(`http://${value}:5252/`);
    } catch (_) {
      const status = document.querySelector('.tailscale-web-status');
      if (status) { status.textContent = button.dataset.error; status.hidden = false; }
      button.disabled = false;
    }
  });
})();
