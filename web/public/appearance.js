// 挂载前应用已保存的外观, 避免闪烁; 键名与 src/lib/appearance.ts 一致.
// 单独成文件: 控制台的 CSP 只允许本站脚本, 不允许内联脚本.
try {
  var mode = localStorage.getItem('ui.mode') || localStorage.getItem('vps-server-mode') || 'system'
  var dark = mode === 'dark' || (mode === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.dataset.theme = localStorage.getItem('ui.theme') || localStorage.getItem('vps-server-theme') || 'slate-blue'
} catch (e) {}
