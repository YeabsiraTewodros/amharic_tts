const CACHE_NAME = 'amharic-tts-v2';
const ASSETS = [
  '/ui',
  '/static/ui.html',
  '/static/ui.css',
  '/static/ui.js',
  '/static/ui1.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // API requests and HTML -> network-first
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    e.respondWith(fetch(req).catch(() => caches.match('/ui')));
    return;
  }

  // For same-origin images and audio, use cache-first then network
  if (url.origin === location.origin && (req.destination === 'image' || req.destination === 'audio')) {
    e.respondWith(caches.match(req).then(cached => cached || fetch(req).then(resp => { caches.open(CACHE_NAME).then(c => c.put(req, resp.clone())); return resp; })).catch(()=>caches.match('/ui')));
    return;
  }

  // Default: try cache, then network
  e.respondWith(caches.match(req).then(res => res || fetch(req)));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    ))
  );
});
