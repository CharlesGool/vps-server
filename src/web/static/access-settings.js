(() => {
  const form = document.querySelector('.access-ip-form');
  if (!form) return;
  const input = form.querySelector('input[name="ip"]');
  const button = form.querySelector('button[type="submit"]');
  const update = () => { button.disabled = input.value.trim().length === 0; };
  input.addEventListener('input', update);
  update();
})();
