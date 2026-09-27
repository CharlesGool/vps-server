(() => {
  const form = document.querySelector('.login-form');
  if (!form) return;
  const input = form.querySelector('#login-password');
  const toggle = form.querySelector('.login-visibility');
  toggle.addEventListener('click', () => {
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    toggle.textContent = visible ? form.dataset.hideLabel : form.dataset.showLabel;
    toggle.setAttribute('aria-pressed', String(visible));
    input.focus();
  });
})();
