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

  // Schedule form (tasks and backup): show only the parts the chosen kind and frequency need.
  document.querySelectorAll('fieldset.sched-schedule').forEach((fieldset) => {
    const kind = fieldset.querySelector('.sched-kind-select');
    const mode = fieldset.querySelector('.sched-mode-select');
    if (!kind || !mode) return;
    const show = () => {
      const effective = kind.value === 'once' ? 'once' : mode.value;
      fieldset.querySelectorAll('.sched-mode').forEach((part) => {
        part.hidden = !part.dataset.modes.split(' ').includes(effective);
      });
    };
    kind.addEventListener('change', show);
    mode.addEventListener('change', show);
    show();
  });

  const upload = document.querySelector('form.backup-upload');
  if (upload) {
    const input = upload.querySelector('input[type=file]');
    const output = upload.querySelector('output');
    const button = upload.querySelector('button');
    const pickName = upload.querySelector('.files-pick-name');
    input.addEventListener('change', () => {
      const file = input.files[0];
      pickName.textContent = file ? file.name : pickName.dataset.empty;
      pickName.classList.toggle('is-set', Boolean(file));
    });
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
