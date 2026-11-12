// Files page: upload with progress, delete confirmation, and live fetch progress.
(() => {
  const form = document.querySelector('.files-upload');
  if (form) {
    const input = form.querySelector('input[type=file]');
    const meter = form.querySelector('.files-upload-meter');
    const bar = meter.querySelector('span');
    const output = form.querySelector('output');
    const button = form.querySelector('button');
    const name = form.querySelector('.files-pick-name');
    input.addEventListener('change', () => {
      const file = input.files[0];
      name.textContent = file ? file.name : name.dataset.empty;
      name.classList.toggle('is-set', Boolean(file));
      say('');
    });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const file = input.files[0];
      if (!file) {
        input.click();
        return;
      }
      if (file.size > Number(form.dataset.room)) {
        say(form.dataset.tooBig, true);
        return;
      }
      const request = new XMLHttpRequest();
      const query = new URLSearchParams({ csrf: form.dataset.csrf, name: file.name });
      request.open('POST', '/files/upload?' + query.toString());
      request.setRequestHeader('Content-Type', 'application/octet-stream');
      request.upload.addEventListener('progress', (progress) => {
        if (!progress.lengthComputable) return;
        show(progress.loaded, progress.total);
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
      meter.hidden = false;
      show(0, file.size);
      request.send(file);
    });
    const size = (bytes) => {
      const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
      let value = bytes;
      let unit = 0;
      while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit += 1;
      }
      return (unit ? value.toFixed(1) : String(value)) + ' ' + units[unit];
    };
    // Progress sits in the row; a message (an error) hangs under it like the bar.
    function say(text, message) {
      output.textContent = text;
      output.classList.toggle('is-message', Boolean(message));
    }
    function show(loaded, total) {
      const percent = total ? Math.floor((loaded * 100) / total) : 0;
      bar.style.width = percent + '%';
      say(percent + '%');
      const detail = document.createElement('span');
      detail.className = 'files-upload-size';
      detail.textContent = ' · ' + size(loaded) + ' / ' + size(total);
      output.append(detail);
    }
    const finish = (message) => {
      button.disabled = false;
      input.disabled = false;
      meter.hidden = true;
      say(message, true);
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
