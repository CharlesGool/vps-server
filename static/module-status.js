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
      const oldLog = document.querySelector('.module-log pre');
      const newLog = next.querySelector('.module-log pre');
      if (oldLog && newLog) {
        const follow = oldLog.scrollTop + oldLog.clientHeight >= oldLog.scrollHeight - 24;
        oldLog.textContent = newLog.textContent;
        if (follow) oldLog.scrollTop = oldLog.scrollHeight;
      }
      const oldNotice = document.querySelector('.module-notice');
      const newNotice = next.querySelector('.module-notice');
      if (oldNotice && newNotice) oldNotice.textContent = newNotice.textContent;
      if (!next.querySelector('script[src="/static/module-status.js"]')) {
        location.reload();
        return;
      }
    } catch (_) { /* Keep the current log visible and retry. */ }
    setTimeout(refresh, 1500);
  };
  setTimeout(refresh, 1500);
})();
