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

// The language a visitor chose before boreale-site's lang.js, which keeps it
// as "boreale-lang": the old "atlas-lang" moved there once, then removed.
// To delete after 2027-01-31 (workbench plans/atlas/suivi.md).
(function () {
  try {
    const old = localStorage.getItem("atlas-lang");
    if (old === null) return;
    if (localStorage.getItem("boreale-lang") === null) localStorage.setItem("boreale-lang", old);
    localStorage.removeItem("atlas-lang");
  } catch (e) { /* storage refused: nothing kept */ }
})();
