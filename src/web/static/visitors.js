(function () {
  const table = document.getElementById("visitors");
  if (!table) return;
  const chips = document.querySelectorAll(".chip[data-filter]");
  const rows = table.querySelectorAll("tbody tr[data-scope]");

  function matches(row, filter) {
    if (filter === "all") return true;
    if (filter === "inbound") return row.getAttribute("data-dir") === "in";
    return row.getAttribute("data-scope") === filter;
  }

  function apply(filter) {
    rows.forEach((row) => {
      row.style.display = matches(row, filter) ? "" : "none";
    });
    chips.forEach((c) =>
      c.classList.toggle("active", c.getAttribute("data-filter") === filter)
    );
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => apply(chip.getAttribute("data-filter")));
  });

  const clearForm = document.getElementById("visitors-clear");
  clearForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = clearForm.querySelector('button[type="submit"]');
    if (!(await window.vpsConfirm(clearForm.dataset.confirm, button.textContent.trim()))) return;
    const status = document.getElementById("visitors-clear-status");
    button.disabled = true;
    status.textContent = clearForm.dataset.working;
    try {
      const response = await fetch(clearForm.action, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(new FormData(clearForm))
      });
      if (!response.ok) throw new Error("clear failed");
      const body = table.querySelector("tbody");
      const row = body.insertRow();
      const cell = row.insertCell();
      cell.colSpan = 7;
      cell.textContent = clearForm.dataset.empty;
      body.replaceChildren(row);
      document.getElementById("visitors-heading").textContent = clearForm.dataset.emptyHeading;
      status.textContent = clearForm.dataset.done;
    } catch (_) {
      status.textContent = clearForm.dataset.failed;
      button.disabled = false;
    }
  });
})();
