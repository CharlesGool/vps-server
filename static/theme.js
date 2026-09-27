(function () {
  "use strict";
  var choices = ["slate-blue", "sage", "teal", "plum"];
  var storageKey = "vps-server-theme";
  function selected() {
    try {
      var saved = localStorage.getItem(storageKey);
      return choices.indexOf(saved) >= 0 ? saved : "slate-blue";
    } catch (_) {
      return "slate-blue";
    }
  }
  function apply(value) {
    document.documentElement.dataset.theme = value;
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === value));
    });
  }
  function ready() {
    apply(selected());
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.dataset.themeChoice;
        if (choices.indexOf(value) < 0) return;
        try { localStorage.setItem(storageKey, value); } catch (_) {}
        apply(value);
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
