(function () {
  "use strict";
  var choices = ["slate-blue", "sage", "teal", "plum", "ocean", "olive", "terracotta", "indigo"];
  var storageKey = "vps-server-theme";
  var modeKey = "vps-server-mode";
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
  function selectedMode() {
    try { return localStorage.getItem(modeKey) === "dark" ? "dark" : "light"; }
    catch (_) { return "light"; }
  }
  function applyMode(value) {
    document.documentElement.classList.toggle("dark", value === "dark");
    document.querySelectorAll("[data-mode-choice]").forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.modeChoice === value));
    });
  }
  function ready() {
    apply(selected());
    applyMode(selectedMode());
    document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.dataset.themeChoice;
        if (choices.indexOf(value) < 0) return;
        try { localStorage.setItem(storageKey, value); } catch (_) {}
        apply(value);
      });
    });
    document.querySelectorAll("[data-mode-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        var value = button.dataset.modeChoice;
        if (value !== "light" && value !== "dark") return;
        try { localStorage.setItem(modeKey, value); } catch (_) {}
        applyMode(value);
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
