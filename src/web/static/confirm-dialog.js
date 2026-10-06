// Shared confirmation dialog: window.vpsConfirm(message, confirmLabel) resolves to true or false.
// Replaces window.confirm so every second confirmation uses the console's own dialog style.
(() => {
  const cancelLabel = document.currentScript?.dataset.cancel || 'Cancel';
  window.vpsConfirm = (message, confirmLabel) => new Promise((resolve) => {
    const dialog = document.createElement('dialog');
    dialog.className = 'node-confirm-dialog';
    const text = document.createElement('p');
    text.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'node-dialog-actions';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'node-dialog-cancel';
    cancel.textContent = cancelLabel;
    const accept = document.createElement('button');
    accept.type = 'button';
    accept.className = 'danger';
    accept.textContent = confirmLabel || 'OK';
    actions.append(cancel, accept);
    dialog.append(text, actions);
    let accepted = false;
    cancel.addEventListener('click', () => dialog.close());
    accept.addEventListener('click', () => { accepted = true; dialog.close(); });
    dialog.addEventListener('close', () => { dialog.remove(); resolve(accepted); });
    document.body.append(dialog);
    dialog.showModal();
    cancel.focus();
  });
})();
