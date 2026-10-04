(() => {
  const refresh = async () => {
    if (document.visibilityState !== 'visible') {
      setTimeout(refresh, 1500);
      return;
    }
    try {
      const response = await fetch(location.href, { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error('status unavailable');
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
    } catch (_) { /* Keep the current log visible and retry. */ }
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
})();
