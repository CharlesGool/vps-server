(() => {
  const root = document.documentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const visible = () => [...document.querySelectorAll('body *')].filter(element =>
    element instanceof HTMLElement && element.getClientRects().length &&
    getComputedStyle(element).visibility !== 'hidden');
  const origin = () => {
    const frameWidth = outerWidth - innerWidth;
    const frame = frameWidth >= 0 && frameWidth <= 80 ? frameWidth / 2 : 0;
    return { x: screenX + frame, y: screenY + Math.max(0, outerHeight - innerHeight - frame) };
  };
  const capture = () => {
    const point = origin();
    return new Map(visible().map(element => {
      const rect = element.getBoundingClientRect();
      return [element, { x: rect.left + point.x, y: rect.top + point.y }];
    }));
  };
  const offset = element => {
    let x = 0, y = 0;
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      const matrix = new DOMMatrixReadOnly(getComputedStyle(node).transform);
      x += matrix.m41;
      y += matrix.m42;
    }
    return { x, y };
  };
  const animations = new Set();
  const frozenStyles = new Map();
  const clearElementMotion = () => {
    for (const animation of animations) animation.cancel();
    animations.clear();
    for (const [element, transform] of frozenStyles) element.style.transform = transform;
    frozenStyles.clear();
  };
  const move = (before, after, animate) => {
    const deltas = new Map();
    for (const [element, next] of after) {
      const previous = before.get(element);
      if (previous) deltas.set(element, { x: previous.x - next.x, y: previous.y - next.y });
    }
    for (const [element, delta] of deltas) {
      let parent = element.parentElement;
      while (parent && !deltas.has(parent)) parent = parent.parentElement;
      const inherited = deltas.get(parent) || { x: 0, y: 0 };
      const dx = delta.x - inherited.x;
      const dy = delta.y - inherited.y;
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) continue;
      const base = getComputedStyle(element).transform;
      const from = `translate(${dx}px, ${dy}px)${base === 'none' ? '' : ` ${base}`}`;
      if (animate) {
        const animation = element.animate([{ transform: from }, { transform: base }], {
          duration: 620, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'backwards'
        });
        animations.add(animation);
        animation.finished.catch(() => {}).finally(() => animations.delete(animation));
      } else {
        frozenStyles.set(element, element.style.transform);
        element.style.transform = from;
      }
    }
  };
  let previousLayout;
  let previousWidth = innerWidth;
  let previousHeight = innerHeight;
  let previousOrigin = origin();
  let frozen = null;
  let frame = 0, settleTimer = 0, clipTimer = 0;
  const unfreeze = keepClip => {
    document.body.style.width = '';
    document.body.style.transform = '';
    root.style.removeProperty('--frozen-viewport-height');
    if (!keepClip) root.classList.remove('layout-resizing');
    clearElementMotion();
    frozen = null;
  };
  const updateBaseline = () => {
    previousLayout = capture();
    previousWidth = innerWidth;
    previousHeight = innerHeight;
    previousOrigin = origin();
  };
  const settle = () => {
    clearTimeout(settleTimer);
    if (!frozen) return;
    const before = capture();
    unfreeze(true);
    const after = capture();
    if (!reduced.matches) move(before, after, true);
    updateBaseline();
    clearTimeout(clipTimer);
    clipTimer = setTimeout(() => root.classList.remove('layout-resizing'), 660);
  };
  window.__settleLayoutMotion = settle;
  document.addEventListener('DOMContentLoaded', () => {
    updateBaseline();
    window.addEventListener('resize', () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (matchMedia('(pointer: coarse)').matches && innerWidth === previousWidth && !frozen) {
          updateBaseline();
          return;
        }
        if (reduced.matches) {
          unfreeze(false);
          updateBaseline();
          return;
        }
        if (!frozen) {
          clearTimeout(clipTimer);
          const before = new Map([...previousLayout].map(([element, point]) => {
            const current = offset(element);
            return [element, { x: point.x + current.x, y: point.y + current.y }];
          }));
          clearElementMotion();
          frozen = { width: previousWidth, position: previousOrigin, scrollY };
          document.body.style.width = `${previousWidth}px`;
          root.style.setProperty('--frozen-viewport-height', `${previousHeight}px`);
          root.classList.add('layout-resizing');
          const now = origin();
          document.body.style.transform = `translate(${previousOrigin.x - now.x}px, ${previousOrigin.y - now.y}px)`;
          move(before, capture(), false);
        }
        const now = origin();
        document.body.style.transform = `translate(${frozen.position.x - now.x}px, ${frozen.position.y - now.y + scrollY - frozen.scrollY}px)`;
        clearTimeout(settleTimer);
        settleTimer = setTimeout(settle, 180);
      });
    });
    window.addEventListener('hashchange', () => requestAnimationFrame(() => {
      clearTimeout(settleTimer);
      clearTimeout(clipTimer);
      unfreeze(false);
      updateBaseline();
    }));
  });
})();
