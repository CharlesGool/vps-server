(() => {
  document.querySelectorAll('form[action="/settings/modules/action"]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.submitting === 'true') {
        event.preventDefault();
        return;
      }
      const button = event.submitter;
      if (button?.dataset.confirm && !window.confirm(button.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = 'true';
      form.querySelectorAll('button[type="submit"]').forEach((submit) => {
        submit.disabled = true;
      });
    });
  });
})();
