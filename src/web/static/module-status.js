(() => {
  const pollUrl = location.href;
  const cleanUrl = new URL(location.href);
  cleanUrl.searchParams.delete('operation');
  history.replaceState(history.state, '', cleanUrl);
  let leaving = false;
  let interrupted = false;
  const refresh = async () => {
    if (leaving) return;
    if (document.visibilityState !== 'visible') {
      setTimeout(refresh, 1500);
      return;
    }
    try {
      const response = await fetch(pollUrl, { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error('status unavailable');
      if (interrupted) {
        // The console was unreachable (a restart): reload so the final state is shown.
        location.reload();
        return;
      }
      const next = new DOMParser().parseFromString(await response.text(), 'text/html');
      const oldProgress = document.querySelector('.module-progress');
      const newProgress = next.querySelector('.module-progress');
      if (oldProgress && newProgress) {
        const oldLog = oldProgress.querySelector('pre');
        const newLog = newProgress.querySelector('pre');
        const follow = oldLog.scrollTop + oldLog.clientHeight >= oldLog.scrollHeight - 24;
        oldLog.textContent = newLog.textContent;
        oldProgress.dataset.lastOutput = newProgress.dataset.lastOutput;
        oldProgress.hidden = newProgress.hidden;
        if (follow) oldLog.scrollTop = oldLog.scrollHeight;
      }
      const oldNotice = document.querySelector('.module-notice');
      const newNotice = next.querySelector('.module-notice');
      if (oldNotice && newNotice) oldNotice.textContent = newNotice.textContent;
      const oldPage = document.querySelector('.module-page');
      const newPage = next.querySelector('.module-page');
      if ((oldPage && (!newPage || oldPage.dataset.busy !== newPage.dataset.busy)) ||
          (!oldPage && !next.querySelector('script[src="/static/module-status.js"]'))) {
        location.reload();
        return;
      }
      if (!next.querySelector('script[src="/static/module-status.js"]')) return;
    } catch (_) { interrupted = true; /* Keep the current log visible and retry. */ }
    setTimeout(refresh, 1500);
  };
  const hideStaleProgress = () => {
    const progress = document.querySelector('.module-progress');
    if (progress && Date.now() - Number(progress.dataset.lastOutput) >= 30000) progress.hidden = true;
    const notice = document.querySelector('.module-notice');
    if (notice && Number(notice.dataset.expiresAt) > 0 &&
        Date.now() >= Number(notice.dataset.expiresAt)) notice.hidden = true;
  };
  setInterval(hideStaleProgress, 1000);
  setTimeout(refresh, 1500);
  window.addEventListener('pagehide', () => {
    leaving = true;
    document.querySelector('.module-progress')?.setAttribute('hidden', '');
    document.querySelector('.module-notice')?.setAttribute('hidden', '');
  });
  window.addEventListener('pageshow', (event) => { if (event.persisted) location.reload(); });
})();
