// A restored page may outlive its server-side login session in the back/forward cache.
// Hide it before caching and require a fresh server request on restoration.
(() => {
  if (performance.getEntriesByType('navigation')[0]?.type === 'back_forward') {
    document.documentElement.style.visibility = 'hidden';
    location.replace(location.href);
  }
  window.addEventListener('pagehide', () => {
    document.documentElement.style.visibility = 'hidden';
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) location.reload();
  });
})();
