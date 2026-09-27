// Ticks the open iperf3 window's remaining time down every second, so the
// figure moves without a manual page reload — the previous version rendered
// the countdown once at page-load and never touched it again, which read as
// broken to an operator watching it.
(function () {
  "use strict";
  var stateEl = document.querySelector(".iperf-state[data-iperf-deadline]");
  if (!stateEl) return;
  var deadline = parseInt(stateEl.getAttribute("data-iperf-deadline"), 10);
  var minsEl = document.getElementById("iperf-mins");
  var secsEl = document.getElementById("iperf-secs");
  if (!deadline || !minsEl || !secsEl) return;

  function tick() {
    var remaining = deadline - Math.floor(Date.now() / 1000);
    if (remaining <= 0) {
      // The window has actually closed itself server-side by now — reload
      // to pick up the real (closed) state and the close button going away.
      window.location.reload();
      return;
    }
    minsEl.textContent = Math.floor(remaining / 60);
    secsEl.textContent = remaining % 60;
  }

  tick();
  setInterval(tick, 1000);
})();
