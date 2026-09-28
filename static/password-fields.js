(() => {
  document.querySelectorAll('.password-field').forEach((field) => {
    const input = field.querySelector('input[type="password"]');
    const toggle = field.querySelector('.password-toggle');
    if (!input || !toggle) return;

    toggle.addEventListener('click', () => {
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      toggle.textContent = visible ? toggle.dataset.hideLabel : toggle.dataset.showLabel;
      toggle.setAttribute('aria-label', visible ? toggle.dataset.hideAccessible : toggle.dataset.showAccessible);
      toggle.setAttribute('aria-pressed', String(visible));
    });
  });
})();
