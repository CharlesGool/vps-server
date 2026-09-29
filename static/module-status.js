(() => {
  const refresh = () => {
    if (document.visibilityState === 'visible') location.reload();
    else document.addEventListener('visibilitychange', refresh, { once: true });
  };
  setTimeout(refresh, 2500);
})();
