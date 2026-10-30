// The project page's files: one made longer ago than its rhythm allows
// (data-age, in days: 2 for a daily file, 9 for a weekly one) is marked
// late. The site is built again after each run, so this only shows when the
// runs stop.
(function () {
  const today = Date.now();
  for (const t of document.querySelectorAll("time[data-age]")) {
    const made = Date.parse(t.getAttribute("datetime") + "T00:00:00Z");
    if (!Number.isNaN(made) && (today - made) / 86400000 > Number(t.dataset.age)) {
      t.classList.add("late");
      const tag = document.createElement("span");
      tag.className = "late-tag";
      tag.textContent = t.dataset.late;
      t.after(tag);
    }
  }
})();
