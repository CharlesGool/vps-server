(() => {
  const serverAddress = document.querySelector('[data-load-address]');
  if (serverAddress) {
    const details = serverAddress.closest('details');
    details.addEventListener('toggle', async () => {
      const port = details.querySelector('[data-load-port]');
      const token = details.querySelector('[data-load-token]');
      if (!details.open) {
        serverAddress.value = '';
        if (port) port.value = '';
        if (token) token.value = '';
        return;
      }
      try {
        const fields = ['server', 'port', 'token'];
        const values = await Promise.all(fields.map(async (field) => {
          const response = await fetch(`/frp/client/value?name=${encodeURIComponent(serverAddress.dataset.loadAddress)}&field=${field}`,
            { credentials: 'same-origin', cache: 'no-store' });
          if (!response.ok) throw new Error('value unavailable');
          return (await response.json()).value;
        }));
        if (details.open) {
          serverAddress.value = values[0];
          port.value = values[1];
          token.value = values[2];
        }
      } catch (_) {
        serverAddress.value = '';
        if (port) port.value = '';
        if (token) token.value = '';
      }
    });
  }

  document.querySelectorAll('.frp-fact-reveal').forEach((control) => {
    control.addEventListener('click', async () => {
      const display = control.querySelector('code');
      if (control.getAttribute('aria-pressed') === 'true') {
        display.textContent = control.dataset.masked;
        control.setAttribute('aria-pressed', 'false');
        control.setAttribute('aria-label', `${control.dataset.show} ${control.dataset.label}`);
        return;
      }
      control.disabled = true;
      try {
        const query = new URLSearchParams({ name: control.dataset.name, field: control.dataset.field });
        const response = await fetch(`/frp/client/value?${query}`, { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) throw new Error('value unavailable');
        display.textContent = (await response.json()).value;
        control.setAttribute('aria-pressed', 'true');
        control.setAttribute('aria-label', `${control.dataset.hide} ${control.dataset.label}`);
      } catch (_) { display.textContent = control.dataset.masked; }
      finally { control.disabled = false; }
    });
  });

  document.querySelectorAll('.frp-test-connection').forEach((control) => {
    control.addEventListener('click', async () => {
      const state = control.closest('.frp-target-card').querySelector('[data-frpc-state]');
      control.disabled = true;
      state.textContent = control.dataset.testing;
      state.classList.remove('is-open', 'is-closed');
      try {
        const body = new URLSearchParams({ name: control.dataset.name, csrf: control.dataset.csrf });
        const response = await fetch('/frp/client/test', {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body
        });
        if (!response.ok) throw new Error('test unavailable');
        const { connected } = await response.json();
        state.textContent = connected ? control.dataset.connected : control.dataset.disconnected;
        state.classList.add(connected ? 'is-open' : 'is-closed');
      } catch (_) {
        state.textContent = control.dataset.failed;
        state.classList.add('is-closed');
      } finally { control.disabled = false; }
    });
  });

  document.querySelectorAll('.frp-delete-form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-dialog-open]');
    if (opener) {
      const dialog = document.getElementById(opener.dataset.dialogOpen);
      if (dialog) {
        dialog.showModal();
        dialog.querySelector('[data-dialog-close]')?.focus();
      }
    }
    const closer = event.target.closest('[data-dialog-close]');
    if (closer) closer.closest('dialog')?.close();
  });

  document.querySelectorAll('.frp-info-wrap').forEach((wrap) => {
    const trigger = wrap.querySelector('.frp-info-trigger');
    const close = () => {
      wrap.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
    };
    trigger.addEventListener('click', () => {
      const open = !wrap.classList.contains('is-open');
      wrap.classList.toggle('is-open', open);
      wrap.classList.toggle('is-dismissed', !open);
      trigger.setAttribute('aria-expanded', String(open));
      if (!open) trigger.blur();
    });
    wrap.addEventListener('pointerleave', () => wrap.classList.remove('is-dismissed'));
    trigger.addEventListener('focus', () => wrap.classList.remove('is-dismissed'));
    document.addEventListener('pointerdown', (event) => { if (!wrap.contains(event.target)) close(); });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && wrap.matches(':hover, :focus-within, .is-open')) {
        event.preventDefault();
        close();
        trigger.blur();
      }
    });
  });

  window.addEventListener('pagehide', () => {
    if (serverAddress) serverAddress.value = '';
    document.querySelectorAll('.frp-fact-reveal').forEach((control) => {
      control.querySelector('code').textContent = control.dataset.masked;
      control.setAttribute('aria-pressed', 'false');
      control.setAttribute('aria-label', `${control.dataset.show} ${control.dataset.label}`);
    });
    if (serverAddress) {
      const details = serverAddress.closest('details');
      serverAddress.value = '';
      details.querySelector('[data-load-port]').value = '';
      details.querySelector('[data-load-token]').value = '';
    }
  });
})();
