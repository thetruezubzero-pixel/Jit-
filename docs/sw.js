// Service worker for the Jit phone site.
//
// The single biggest latency cost on this site is Pyodide's runtime: ~14MB
// of wasm + stdlib, re-downloaded from scratch on every visit without this.
// Strategy:
//   - vendor/pyodide/* is pinned to an exact version (see CACHE_VERSION) and
//     never changes without a deploy, so it's cache-first, effectively
//     permanent until the version bumps.
//   - Everything else (app shell, jit engine source) is stale-while-revalidate:
//     serve instantly from cache, then refetch in the background so the next
//     visit picks up whatever changed on the last deploy.

// Bump this on every deploy that changes app-shell files (styles.css,
// app.js, index.html, bridge.py). Without a version bump, "activate"'s
// cache cleanup has nothing to clean up and a returning visitor can stay
// stuck on stale assets far longer than intended — this is what caused a
// shipped CSS fix to not actually show up on a real device.
const CACHE_VERSION = "v11";
const CACHE_NAME = `jit-${CACHE_VERSION}`;

const PRECACHE_URLS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./py/bridge.py",
  "./manifest.json",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./terms.html",
  "./privacy.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function isImmutableVendorAsset(url) {
  return url.pathname.includes("/vendor/pyodide/");
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (isImmutableVendorAsset(url)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      })
    );
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request);
      // "reload" bypasses the browser's own HTTP cache, not just this
      // Cache API layer — otherwise "revalidate" can silently hand back the
      // same stale bytes the HTTP cache already had, defeating the point.
      const networkFetch = fetch(request, { cache: "reload" })
        .then((response) => {
          if (response.ok) cache.put(request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
