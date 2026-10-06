(() => {
  document.querySelectorAll('.log-clear-form').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      if (form.dataset.confirmed === 'true') {
        delete form.dataset.confirmed;
        return;
      }
      event.preventDefault();
      const button = event.submitter || form.querySelector('button[type="submit"]');
      if (await window.vpsConfirm(form.dataset.confirm, button?.textContent.trim())) {
        form.dataset.confirmed = 'true';
        form.requestSubmit(event.submitter || undefined);
      }
    });
  });
})();
