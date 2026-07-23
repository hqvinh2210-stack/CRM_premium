/* SoftPOS PWA service worker — cache shell for offline UI (GH Pages safe) */
const CACHE = 'pos-shell-v2'
const SCOPE = self.registration.scope // includes base path e.g. .../CRM_premium/

function asset(path) {
  return new URL(path.replace(/^\//, ''), SCOPE).href
}

const ASSETS = ['./', './index.html', './manifest.webmanifest', './favicon.svg'].map(asset)

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(ASSETS).catch(() => undefined))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  // never cache API (any host)
  if (url.pathname.includes('/api/')) return
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          const copy = res.clone()
          if (res.ok && url.origin === self.location.origin) {
            caches.open(CACHE).then((c) => c.put(req, copy))
          }
          return res
        })
        .catch(() => cached)
      return cached || network
    }),
  )
})
