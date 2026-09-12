// Copy-to-clipboard for the anytls node page.
//
// navigator.clipboard only exists in a secure context. The console defaults to
// plain HTTP on a LAN address (see DECISIONS.md, 2026-08-25), which is not one
// — so on the setup this project actually ships, the modern API is undefined
// and the deprecated execCommand path is the one that runs. Treat the
// fallback as the primary, not as legacy tidying.
(function () {
  "use strict";

  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    // Off-screen rather than display:none — a hidden element cannot be
    // selected, and without a selection execCommand copies nothing.
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, area.value.length);  // iOS needs the explicit range
    var ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(area);
    return ok;
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return legacyCopy(text); }
      );
    }
    return Promise.resolve(legacyCopy(text));
  }

  function flash(button, ok) {
    var original = button.dataset.original || button.textContent;
    button.dataset.original = original;
    // On failure say nothing reassuring: a button that always reports success
    // is worse than one that reports nothing, because the operator walks away
    // believing they have the value when they do not.
    button.textContent = ok ? button.dataset.copied : "✕";
    button.classList.toggle("copied", ok);
    window.setTimeout(function () {
      button.textContent = original;
      button.classList.remove("copied");
    }, 1500);
  }

  document.querySelectorAll(".copybtn").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.getElementById(button.dataset.copy);
      if (!target) {
        flash(button, false);
        return;
      }
      copy(target.textContent).then(function (ok) {
        flash(button, ok);
      });
    });
  });
})();
