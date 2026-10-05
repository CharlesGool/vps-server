(() => {
  document.querySelector('.tailscale-logout')?.addEventListener('submit', event => {
    if (!window.confirm(event.currentTarget.dataset.confirm)) event.preventDefault();
  });
  document.querySelectorAll('[data-tailscale-single]').forEach(select => {
    select.addEventListener('change', () => {
      select.closest('form').querySelector(`[name="${select.dataset.tailscaleSingle}_clear"]`).value = select.value ? '0' : '1';
    });
  });
  const button = document.querySelector('.tailscale-web-open');
  document.addEventListener('click', (event) => {
    const route = event.target.closest('[data-route-choice]');
    const exit = event.target.closest('[data-exit-choice]');
    if (!route && !exit) return;
    const kind = route ? 'routes' : 'exit';
    const field = document.querySelector(`[name="${kind}_value"]`);
    if (!field) return;
    const value = route ? route.dataset.routeChoice : exit.dataset.exitChoice;
    const existing = route ? field.value.split(',').map(item => item.trim()).filter(Boolean) : [];
    field.value = route ? [...new Set([...existing, value])].join(', ') : value;
    const clear = document.querySelector(`[name="${kind}_clear"]`);
    if (clear) clear.checked = false;
    field.focus();
  });
  button?.addEventListener('click', async () => {
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
