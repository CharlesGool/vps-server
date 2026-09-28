(() => {
  const root = document.documentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const choiceKey = 'vps-server-page-motion';
  const pendingKey = 'vps-server-route-pending';
  const entryKey = key => `vps-server-route-${key}`;
  const read = key => { try { return sessionStorage.getItem(key); } catch (_) { return null; } };
  const write = (key, value) => { try { sessionStorage.setItem(key, value); } catch (_) {} };
  const parse = text => { try { return JSON.parse(text); } catch (_) { return null; } };
  const mobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const urlChoice = new URL(location.href).searchParams.get('page-motion');
  let saved = null;
  try { saved = localStorage.getItem(choiceKey); } catch (_) {}
  if (saved !== 'on' && saved !== 'off') {
    saved = document.cookie.match(/(?:^|;\s*)vps-server-page-motion=(on|off)(?:;|$)/)?.[1] || null;
  }
  let enabled = (urlChoice === 'on' || urlChoice === 'off' ? urlChoice === 'on' :
    saved === 'on' || saved === 'off' ? saved === 'on' : !mobile);
  root.dataset.pageMotion = enabled ? 'on' : 'off';
  let trigger = null;
  let pendingPress = 0;
  let activeTransition = null;

  const usable = () => enabled && !reduced.matches && 'onpageswap' in window &&
    'onpagereveal' in window;
  const links = () => [...document.querySelectorAll('a[href]')];
  const findByIndex = index => Number.isInteger(index) ? links()[index] : null;
  const findCard = path => [...document.querySelectorAll('a.tile')].find(link =>
    new URL(link.href).pathname === path);
  const findRecorded = (fromKey, path) => {
    try {
      for (let index = 0; index < sessionStorage.length; index++) {
        const key = sessionStorage.key(index);
        if (!key?.startsWith('vps-server-route-') || key === pendingKey) continue;
        const item = parse(sessionStorage.getItem(key));
        if (item?.fromKey === fromKey && item.targetPath === path) return item;
      }
    } catch (_) {}
    return null;
  };
  const setGeometry = bounds => {
    if (!bounds || bounds.width < 1 || bounds.height < 1) return false;
    root.style.setProperty('--route-x', `${bounds.left}px`);
    root.style.setProperty('--route-y', `${bounds.top}px`);
    root.style.setProperty('--route-scale-x', String(bounds.width / innerWidth));
    root.style.setProperty('--route-scale-y', String(bounds.height / innerHeight));
    root.style.setProperty('--route-cover-scale-x', String(innerWidth / bounds.width));
    root.style.setProperty('--route-cover-scale-y', String(innerHeight / bounds.height));
    return true;
  };
  const clearGeometry = () => {
    root.removeAttribute('data-route-motion');
    for (const key of ['--route-x', '--route-y', '--route-scale-x', '--route-scale-y',
      '--route-cover-scale-x', '--route-cover-scale-y']) root.style.removeProperty(key);
    document.querySelectorAll('[style*="view-transition-name: route-cover"]').forEach(node => {
      node.style.viewTransitionName = '';
    });
  };
  const setSwitch = () => {
    const control = document.querySelector('[data-page-motion-switch]');
    control?.setAttribute('aria-checked', String(enabled));
  };
  const saveChoice = choice => {
    try { localStorage.setItem(choiceKey, choice); } catch (_) {}
    try { document.cookie = `${choiceKey}=${choice}; Path=/; Max-Age=31536000; SameSite=Lax`; } catch (_) {}
    const url = new URL(location.href);
    url.searchParams.set('page-motion', choice);
    try { history.replaceState(history.state, '', url); } catch (_) {}
  };

  document.addEventListener('DOMContentLoaded', () => {
    setSwitch();
    document.querySelector('[data-page-motion-switch]')?.addEventListener('click', () => {
      enabled = !enabled;
      root.dataset.pageMotion = enabled ? 'on' : 'off';
      saveChoice(enabled ? 'on' : 'off');
      setSwitch();
      if (!enabled) {
        clearTimeout(pendingPress);
        trigger?.element?.classList.remove('route-press');
        trigger = null;
        activeTransition?.skipTransition();
        clearGeometry();
      }
    });
  });

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
        event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || link.target && link.target !== '_self' || link.hasAttribute('download')) return;
    const destination = new URL(link.href);
    if (destination.origin !== location.origin || destination.pathname === '/logout' ||
        destination.pathname === '/login' ||
        destination.pathname === location.pathname && destination.search === location.search) return;
    window.__settleLayoutMotion?.();
    if (!usable()) return;
    trigger?.element?.classList.remove('route-press');
    trigger = { element: link, index: links().indexOf(link),
      back: link.classList.contains('page-back'), destination };
    event.preventDefault();
    link.classList.add('route-press');
    clearTimeout(pendingPress);
    pendingPress = setTimeout(() => { pendingPress = 0; location.assign(destination.href); }, 70);
  }, true);

  window.addEventListener('pageswap', event => {
    window.__settleLayoutMotion?.();
    if (!event.viewTransition || !usable()) {
      event.viewTransition?.skipTransition();
      return;
    }
    const from = event.activation?.from;
    const to = event.activation?.entry;
    if (!from?.key || !to?.url || new URL(to.url).pathname === '/login') {
      event.viewTransition.skipTransition();
      return;
    }
    let motion;
    let recordNew = false;
    const oldPath = new URL(from.url).pathname;
    const newPath = new URL(to.url).pathname;
    if (trigger && trigger.destination.href === to.url) {
      motion = { mode: trigger.back ? 'return' : 'open', fromKey: from.key,
        fromPath: oldPath, targetPath: newPath,
        sourceIndex: trigger.index };
      recordNew = true;
    } else {
      const previous = parse(read(entryKey(from.key)));
      const next = parse(read(entryKey(to.key))) || findRecorded(from.key, newPath);
      if (previous?.fromKey === to.key || previous?.fromPath === newPath) {
        motion = { ...previous, mode: previous.mode === 'open' ? 'return' : 'open' };
      } else if (next?.fromKey === from.key) motion = next;
    }
    trigger?.element?.classList.remove('route-press');
    trigger = null;
    if (!motion) { write(pendingKey, JSON.stringify({ departKey: from.key, toPath: newPath, mode: 'slide' })); return; }
    const outgoing = motion.mode === 'open' ?
      (oldPath === motion.fromPath ? findByIndex(motion.sourceIndex) : findCard(motion.fromPath)) : null;
    const bounds = outgoing?.getBoundingClientRect();
    if (outgoing && bounds?.width && bounds?.height) outgoing.style.viewTransitionName = 'route-cover';
    write(pendingKey, JSON.stringify({ departKey: from.key, toPath: newPath, recordNew, ...motion,
      bounds: outgoing ? { left: bounds.left, top: bounds.top,
        width: bounds.width, height: bounds.height } : null }));
    event.viewTransition.finished.catch(() => {}).finally(() => {
      if (outgoing) outgoing.style.viewTransitionName = '';
    });
  });

  window.addEventListener('pagereveal', event => {
    if (!event.viewTransition || !usable()) {
      event.viewTransition?.skipTransition();
      return;
    }
    const pending = parse(read(pendingKey));
    const currentKey = window.navigation?.activation?.entry?.key;
    const departKey = window.navigation?.activation?.from?.key;
    if (!pending || pending.departKey !== departKey || pending.toPath !== location.pathname) {
      event.viewTransition.skipTransition();
      return;
    }
    try { sessionStorage.removeItem(pendingKey); } catch (_) {}
    if (pending.recordNew && currentKey) {
      const { mode, fromKey, fromPath, targetPath, sourceIndex } = pending;
      write(entryKey(currentKey), JSON.stringify({ mode, fromKey, fromPath, targetPath, sourceIndex }));
    }
    let bounds = pending.bounds;
    if (pending.mode === 'return') {
      const target = location.pathname === pending.fromPath ?
        findByIndex(pending.sourceIndex) : findCard(pending.fromPath);
      if (target) {
        const box = target.getBoundingClientRect();
        if (box.top < 0 || box.bottom > innerHeight) target.scrollIntoView({ block: 'center' });
        target.style.viewTransitionName = 'route-cover';
        bounds = target.getBoundingClientRect();
      }
    }
    root.dataset.routeMotion = setGeometry(bounds) ? pending.mode : 'slide';
    activeTransition = event.viewTransition;
    event.viewTransition.finished.catch(() => {}).finally(() => {
      if (activeTransition === event.viewTransition) activeTransition = null;
      clearGeometry();
    });
  });
})();
