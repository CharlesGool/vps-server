// Backup and Tasks pages: confirmation dialogs, backup upload, schedule presets.
(() => {
  document.querySelectorAll('form.backup-confirm[data-confirm]').forEach((form) => {
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

  // Task form: show only the fields of the chosen way to schedule.
  const mode = document.getElementById('task-mode');
  if (mode) {
    const show = () => {
      document.querySelectorAll('.sched-mode').forEach((group) => {
        group.hidden = group.dataset.mode !== mode.value;
      });
    };
    mode.addEventListener('change', show);
    show();
  }

  const upload = document.querySelector('form.backup-upload');
  if (upload) {
    const input = upload.querySelector('input[type=file]');
    const output = upload.querySelector('output');
    const button = upload.querySelector('button');
    upload.addEventListener('submit', (event) => {
      event.preventDefault();
      const file = input.files[0];
      if (!file) return;
      if (file.size > Number(upload.dataset.max)) {
        output.textContent = upload.dataset.tooBig;
        return;
      }
      const request = new XMLHttpRequest();
      request.open('POST', '/backup/upload?csrf=' + encodeURIComponent(upload.dataset.csrf));
      request.setRequestHeader('Content-Type', 'application/octet-stream');
      request.upload.addEventListener('progress', (progress) => {
        if (progress.lengthComputable) output.textContent = Math.round(progress.loaded * 100 / progress.total) + '%';
      });
      request.addEventListener('load', () => {
        let reply = {};
        try { reply = JSON.parse(request.responseText); } catch (error) { reply = {}; }
        if (request.status === 200 && reply.ok) {
          // Straight on to the restore page: it shows what the file holds and asks for the key there.
          window.location.assign(reply.name ? '/backup/restore?name=' + encodeURIComponent(reply.name) : '/backup?msg=uploaded');
        } else {
          window.location.assign('/backup?error=' + (reply.error === 'invalid' ? 'invalid' : 'failed'));
        }
      });
      request.addEventListener('error', () => {
        output.textContent = upload.dataset.failed;
        button.disabled = false;
        input.disabled = false;
      });
      button.disabled = true;
      input.disabled = true;
      request.send(file);
    });
  }
})();
