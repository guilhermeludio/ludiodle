/* Service worker: deixa o jogo funcionar offline depois da primeira visita (https/localhost). */
const CACHE = "hihihiacerto-v10";
const CORE = ["./", "index.html", "data/modes.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(req, { ignoreSearch: true });
    const net = fetch(req).then(r => { if (r && r.ok) c.put(req, r.clone()); return r; }).catch(() => null);
    return hit || (await net) || new Response("offline", { status: 503 });
  }));
});
self.addEventListener("message", e => {
  if (e.data && e.data.type === "precache") {
    e.waitUntil(caches.open(CACHE).then(c => Promise.all(e.data.urls.map(u => c.match(u).then(h => h || c.add(u).catch(() => {}))))));
  }
});
