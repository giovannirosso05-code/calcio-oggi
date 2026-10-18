// Service worker minimo: prima la rete (dati sempre freschi), se manca la rete usa l'ultima copia salvata.
const NOME = "calcio-oggi-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(caches.keys().then((k) => Promise.all(k.filter((x) => x !== NOME).map((x) => caches.delete(x)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.method !== "GET" || new URL(r.url).origin !== location.origin) return;   // le richieste a ESPN restano fuori
  e.respondWith(fetch(r).then((ris) => { const copia = ris.clone(); caches.open(NOME).then((c) => c.put(r, copia)); return ris; }).catch(() => caches.match(r).then((c) => c || caches.match("index.html"))));
});
