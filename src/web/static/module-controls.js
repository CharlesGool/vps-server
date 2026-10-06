(() => {
  document.querySelectorAll('form[action="/settings/modules/action"]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      if (form.dataset.submitting === 'true') {
        event.preventDefault();
        return;
      }
      const button = event.submitter;
      if (button?.dataset.confirm && form.dataset.confirmed !== 'true') {
        event.preventDefault();
        if (await window.vpsConfirm(button.dataset.confirm, button.textContent.trim())) {
          form.dataset.confirmed = 'true';
          form.requestSubmit(button);
        }
        return;
      }
      delete form.dataset.confirmed;
      form.dataset.submitting = 'true';
      form.querySelectorAll('button[type="submit"]').forEach((submit) => {
        submit.disabled = true;
      });
    });
  });
})();
