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
})();
