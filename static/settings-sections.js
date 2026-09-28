(() => {
  const nav = document.querySelector('.section-nav');
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.hash.slice(1)));
  if (sections.some(section => !section)) return;

  let pending = false;
  const update = () => {
    pending = false;
    let active = 0;
    let best = -1;
    sections.forEach((section, index) => {
      const bounds = section.getBoundingClientRect();
      const visible = Math.max(0, Math.min(bounds.bottom, innerHeight) - Math.max(bounds.top, 0));
      const score = visible / Math.max(1, Math.min(bounds.height, innerHeight));
      if (score > 0 && score >= best) { best = score; active = index; }
    });
    links.forEach((link, index) => {
      if (index === active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(update);
  };
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
  window.addEventListener('hashchange', () => setTimeout(schedule, 0));
  window.addEventListener('load', schedule);
  window.addEventListener('pageshow', schedule);
  nav.addEventListener('click', () => setTimeout(schedule, 80));
  schedule();
  setTimeout(schedule, 80);
})();
