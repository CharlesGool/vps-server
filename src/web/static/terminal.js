(() => {
  const page = document.querySelector('.terminal-page');
  if (!page) return;
  const screen = page.querySelector('.terminal-screen');
  const status = page.querySelector('.terminal-status');
  if (!window.Terminal || !window.FitAddon?.FitAddon) {
    status.textContent = page.dataset.disconnected;
    return;
  }
  const terminalStyle = getComputedStyle(screen);
  const terminal = new window.Terminal({
    cursorBlink: true, convertEol: false, scrollback: 5000, fontSize: 12,
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
    theme: { background: terminalStyle.getPropertyValue('--terminal-bg').trim(),
      foreground: terminalStyle.getPropertyValue('--terminal-fg').trim(),
      cursor: terminalStyle.getPropertyValue('--terminal-fg').trim() }
  });
  const fit = new window.FitAddon.FitAddon();
  terminal.loadAddon(fit);
  terminal.open(screen);
  let socket = null;
  let leaving = false;
  const resize = () => {
    if (!screen.isConnected) return;
    fit.fit();
    if (socket?.readyState === WebSocket.OPEN &&
        terminal.cols >= 20 && terminal.cols <= 400 && terminal.rows >= 10 && terminal.rows <= 200) {
      socket.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }));
    }
  };
  const observer = new ResizeObserver(resize);
  observer.observe(screen);
  terminal.onData((data) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'input', data }));
  });
  const connect = () => {
    if (leaving) return;
    socket?.close();
    terminal.reset();
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const next = new WebSocket(`${protocol}//${location.host}/terminal/ws?token=${encodeURIComponent(page.dataset.token)}`);
    socket = next;
    next.binaryType = 'arraybuffer';
    status.textContent = '';
    next.onopen = () => { if (socket === next) { resize(); terminal.focus(); } };
    next.onmessage = (event) => {
      if (socket === next && event.data instanceof ArrayBuffer) terminal.write(new Uint8Array(event.data));
    };
    next.onclose = () => {
      if (socket !== next) return;
      if (!leaving) status.textContent = page.dataset.disconnected;
    };
    next.onerror = () => { if (socket === next) status.textContent = page.dataset.disconnected; };
  };
  window.addEventListener('pagehide', () => { leaving = true; observer.disconnect(); socket?.close(); terminal.dispose(); });
  connect();
})();
