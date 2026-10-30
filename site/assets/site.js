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

// Boréale's site switcher: the menu of Boréale's sites opens under the name
// beside its button, wherever the header is. The same block in boreale.dev's,
// PlayGuard's, PlayShelf's and Aurore's site.js; boreale's is the reference.
// Without popovers (an old browser), the name still leads home.
(function () {
  const menu = document.getElementById("sites");
  const anchor = menu && menu.closest(".switcher");
  if (!anchor || !menu.showPopover) return;
  menu.addEventListener("beforetoggle", (event) => {
    if (event.newState !== "open") return;
    const box = anchor.getBoundingClientRect();
    const screen = document.documentElement.clientWidth;
    const width = Math.min(400, screen - 24); // site.css's width
    menu.style.top = `${box.bottom + window.scrollY + 6}px`;
    menu.style.left = `${Math.max(12, Math.min(box.left, screen - width - 12)) + window.scrollX}px`;
  });
})();
