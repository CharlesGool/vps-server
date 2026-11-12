// Files page: upload with progress, delete confirmation, and live fetch progress.
(() => {
  const form = document.querySelector('.files-upload');
  if (form) {
    const input = form.querySelector('input[type=file]');
    const bar = form.querySelector('progress');
    const output = form.querySelector('output');
    const button = form.querySelector('button');
    const name = form.querySelector('.files-pick-name');
    input.addEventListener('change', () => {
      const file = input.files[0];
      name.textContent = file ? file.name : name.dataset.empty;
      name.classList.toggle('is-set', Boolean(file));
      output.textContent = '';
    });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const file = input.files[0];
      if (!file) {
        input.click();
        return;
      }
      if (file.size > Number(form.dataset.room)) {
        output.textContent = form.dataset.tooBig;
        return;
      }
      const request = new XMLHttpRequest();
      const query = new URLSearchParams({ csrf: form.dataset.csrf, name: file.name });
      request.open('POST', '/files/upload?' + query.toString());
      request.setRequestHeader('Content-Type', 'application/octet-stream');
      request.upload.addEventListener('progress', (progress) => {
        if (!progress.lengthComputable) return;
        const percent = Math.floor((progress.loaded * 100) / progress.total);
        bar.value = percent;
        output.textContent = percent + '%';
      });
      request.addEventListener('load', () => {
        let reply = {};
        try { reply = JSON.parse(request.responseText); } catch (error) { reply = {}; }
        if (request.status === 200 && reply.ok) {
          window.location.assign('/files?msg=files_uploaded');
        } else if (reply.error) {
          window.location.assign('/files?error=' + encodeURIComponent(reply.error));
        } else {
          finish(form.dataset.failed);
        }
      });
      request.addEventListener('error', () => finish(form.dataset.failed));
      button.disabled = true;
      input.disabled = true;
      bar.hidden = false;
      bar.value = 0;
      output.textContent = '0%';
      request.send(file);
    });
    const finish = (message) => {
      button.disabled = false;
      input.disabled = false;
      bar.hidden = true;
      output.textContent = message;
    };
  }

  document.querySelectorAll('form.files-delete[data-confirm]').forEach((target) => {
    target.addEventListener('submit', async (event) => {
      if (target.dataset.confirmed === 'true') return;
      event.preventDefault();
      const button = target.querySelector('button');
      if (await window.vpsConfirm(target.dataset.confirm, button?.textContent.trim())) {
        target.dataset.confirmed = 'true';
        target.requestSubmit();
      }
    });
  });

  // While a fetch runs, refresh its byte count; reload once it finishes.
  const running = document.querySelectorAll('[data-job][data-state=running]');
  if (!running.length) return;
  const size = (bytes) => {
    const units = [['GiB', 1073741824], ['MiB', 1048576], ['KiB', 1024]];
    for (const [unit, step] of units) if (bytes >= step) return (bytes / step).toFixed(1) + ' ' + unit;
    return bytes + ' B';
  };
  const poll = async () => {
    try {
      const reply = await fetch('/files/jobs', { cache: 'no-store' });
      const data = await reply.json();
      let finished = false;
      for (const job of data.jobs) {
        const row = document.querySelector(`[data-job="${job.id}"][data-state=running]`);
        if (!row) continue;
        if (job.state !== 'running') { finished = true; continue; }
        const detail = row.querySelector('.files-job-detail');
        if (detail) detail.textContent = job.total ? `${size(job.bytes)} / ${size(job.total)}` : size(job.bytes);
        const bar = row.querySelector('.files-job-meter > span');
        if (bar && job.total) bar.style.width = Math.min(100, Math.round((job.bytes * 100) / job.total)) + '%';
      }
      if (finished) { window.location.assign('/files'); return; }
    } catch (error) { /* try again on the next tick */ }
    window.setTimeout(poll, 2000);
  };
  window.setTimeout(poll, 2000);
})();
