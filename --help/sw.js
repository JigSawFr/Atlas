// The explorer's service worker (served from the site's root, as build_site copies it there: a worker can only
// act for the folder it is served from). It makes what the visitor has seen open without a network: the explorer
// page, its script and styles, and the data files it read (x/…), kept in this browser only. The network is asked
// first, so nothing is ever older than the site; the copy answers only when the network does not.
const CACHE = "atlas-explorer-1";       // a new number drops the old copies (activate)
const KEEP = 400;                       // files kept, the oldest dropped first

const wanted = (url) => /\/(x|assets)\//.test(url.pathname) || /\/explore\/(index\.html)?$/.test(url.pathname);

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((names) => Promise.all(names.filter((n) => n.startsWith("atlas-explorer-") && n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

async function keep(request, response) {
  const cache = await caches.open(CACHE);
  await cache.put(request, response);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - KEEP)).map((k) => cache.delete(k)));
}

self.addEventListener("fetch", (event) => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || !wanted(url)) return;
  event.respondWith(fetch(request).then((response) => {
    if (response.status === 200) event.waitUntil(keep(request, response.clone()));
    return response;
  }).catch(() => caches.match(request).then((hit) => hit || Response.error())));
});
