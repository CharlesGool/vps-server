(() => {
  const nav = document.querySelector('.section-nav');
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.hash.slice(1)));
  if (sections.some(section => !section)) return;

  let pending = false;
  let requested = links.findIndex(link => link.hash === location.hash);
  const update = () => {
    pending = false;
    const topnav = document.querySelector('.topnav');
    const sticky = topnav && getComputedStyle(topnav).position === 'sticky';
    const threshold = (sticky ? topnav.getBoundingClientRect().bottom : 0) + 32;
    let active = 0;
    sections.forEach((section, index) => {
      if (section.getBoundingClientRect().top <= threshold) active = index;
    });
    if (scrollY > 0 && innerHeight + scrollY >= document.documentElement.scrollHeight - 2) {
      active = sections.length - 1;
    }
    if (requested >= 0) active = requested;
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
  window.addEventListener('hashchange', () => {
    requested = links.findIndex(link => link.hash === location.hash);
    schedule();
  });
  const resumeTracking = () => { requested = -1; schedule(); };
  window.addEventListener('wheel', resumeTracking, { passive: true });
  window.addEventListener('touchstart', resumeTracking, { passive: true });
  window.addEventListener('keydown', event => {
    if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key) &&
        !event.target.closest('input, select, textarea, button')) resumeTracking();
  });
  document.addEventListener('pointerdown', event => {
    if (!event.target.closest('.section-nav')) resumeTracking();
  });
  window.addEventListener('load', schedule);
  window.addEventListener('pageshow', schedule);
  nav.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || !nav.contains(link)) return;
    requested = links.indexOf(link);
    schedule();
  });
  schedule();
  setTimeout(schedule, 80);
})();
