// boreale-site (README.md): the header's two menus, loaded by each of
// Boréale's sites beside its own site.js. Without popovers (an old browser),
// the name still leads home and the languages stay a list.

// Boréale's site switcher: the menu of Boréale's sites opens under the name
// beside its button, wherever the header is.
(function () {
  const menu = document.getElementById("sites");
  const anchor = menu && menu.closest(".switcher");
  if (!anchor || !menu.showPopover) return;
  menu.addEventListener("beforetoggle", (event) => {
    if (event.newState !== "open") return;
    const box = anchor.getBoundingClientRect();
    const screen = document.documentElement.clientWidth;
    const width = Math.min(400, screen - 24); // boreale.css's width
    menu.style.top = `${box.bottom + window.scrollY + 6}px`;
    menu.style.left = `${Math.max(12, Math.min(box.left, screen - width - 12)) + window.scrollX}px`;
  });
})();

// The header's languages: their menu opens under its button, its right edge
// on the button's where the screen has room, the language in use in view.
(function () {
  const menu = document.getElementById("languages");
  const button = document.querySelector(".lang-button");
  if (!menu || !button || !menu.showPopover) return;
  menu.addEventListener("beforetoggle", (event) => {
    if (event.newState !== "open") return;
    const box = button.getBoundingClientRect();
    const screen = document.documentElement.clientWidth;
    menu.style.top = `${box.bottom + window.scrollY + 6}px`;
    const width = Math.min(460, screen - 24); // boreale.css's width
    menu.style.left = `${Math.max(12, Math.min(box.right - width, screen - width - 12)) + window.scrollX}px`;
    requestAnimationFrame(() => menu.querySelector("[aria-current]")?.scrollIntoView({ block: "nearest" }));
  });
})();
