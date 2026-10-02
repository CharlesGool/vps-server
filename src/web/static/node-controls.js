(() => {
  document.addEventListener('click', (event) => {
    const opener = event.target.closest('[data-dialog-open]');
    if (opener) {
      const dialog = document.getElementById(opener.dataset.dialogOpen);
      if (dialog) {
        dialog.showModal();
        if (dialog.classList.contains('node-access-dialog')) {
          dialog.querySelector('input:not([type="hidden"])')?.focus();
        } else {
          dialog.querySelector('[data-dialog-close]')?.focus();
        }
      }
      return;
    }
    const closer = event.target.closest('[data-dialog-close]');
    if (closer) closer.closest('dialog')?.close();
  });

  document.querySelectorAll('[data-node-edit-id]').forEach((details) => {
    details.addEventListener('toggle', async () => {
      const port = details.querySelector('[data-node-edit-port]');
      const credential = details.querySelector('[data-node-edit-credential]');
      if (!details.open) { port.value = ''; credential.value = ''; return; }
      try {
        const id = encodeURIComponent(details.dataset.nodeEditId);
        const values = await Promise.all(['port', 'credential'].map(async (field) => {
          const response = await fetch(`/proxy/private-value?id=${id}&field=${field}`,
            { credentials: 'same-origin', cache: 'no-store' });
          if (!response.ok) throw new Error('value unavailable');
          return (await response.json()).value;
        }));
        if (details.open) { port.value = values[0]; credential.value = values[1]; }
      } catch (_) { port.value = ''; credential.value = ''; }
    });
  });
  window.addEventListener('pagehide', () => {
    document.querySelectorAll('[data-node-edit-id]').forEach((details) => {
      details.querySelector('[data-node-edit-port]').value = '';
      details.querySelector('[data-node-edit-credential]').value = '';
    });
  });

  const createForm = document.querySelector('[data-node-create]');
  if (!createForm) return;
  const sniField = createForm.querySelector('[data-sni-field]');
  const sniInput = sniField.querySelector('input');
  const credentialHint = createForm.querySelector('[data-credential-hint]');
  const updateFields = () => {
    const protocol = createForm.querySelector('input[name="protocol"]:checked')?.value;
    sniField.hidden = protocol === 'shadowsocks';
    if (protocol !== 'shadowsocks' && !sniInput.value) sniInput.value = 'www.bing.com';
    credentialHint.textContent = protocol === 'shadowsocks' ? createForm.dataset.credentialSs :
      (protocol === 'vmess' || protocol === 'vless') ? createForm.dataset.credentialUuid :
        createForm.dataset.credentialPassword;
  };
  createForm.addEventListener('change', (event) => {
    if (event.target.name === 'protocol') updateFields();
  });
  updateFields();
})();
