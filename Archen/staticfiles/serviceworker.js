// PATH: /Archen/static/serviceworker.js
/* Safe, minimal service worker for django-pwa
 * - Never intercept POST/PUT/DELETE
 * - Don't handle HTML navigations aggressively
 * - Make install robust even if some assets 404
 */

// Bump version to invalidate old caches after policy and feature changes
// Bump when static pipeline/CSP changes to force clients to refetch assets
// v15: invalidate static cache after sort.js numeric sorting update
const CACHE_NAME = 'archen-static-v15';
const PAGE_CACHE_NAME = 'archen-pages-v5';

// App routes allowed for page caching and request queueing (same-origin)
const ROUTE_ALLOWLIST = [
  '/',
  '/dashboard',
  '/orders',
  '/inventory',
  '/production_line',
  '/jobs',
  '/reports',
  '/maintenance',
  '/users',
];

function isAllowedPath(pathname) {
  return ROUTE_ALLOWLIST.some(prefix => pathname === prefix || pathname.startsWith(prefix + '/') || (prefix === '/' && pathname === '/'));
}

// Precache only stable, existing assets and the offline page
// Note: '/offline/' is served by django-pwa using the offline.html template.
const PRECACHE_URLS = [
  // Core app shell
  '/offline/',
  '/manifest.json',
  '/static/css/app.min.css',
  '/static/js/jquery.min.js',
  // UI assets
  '/static/icons/archen_pattern.png',
  // Persian datepicker (orders/create) — ensure offline calendar works
  '/static/orders/js/persian-date.min.js',
  '/static/orders/js/persian-datepicker.min.js',
  '/static/orders/css/persian-datepicker.min.css',
  // jQuery UI used by some widgets
  '/static/js/jquery-ui.min.js',
  // Charts
  '/static/js/chart.lite.v2.js',
];

// Allowlist of external CDNs we intentionally cache for offline usage
// This keeps Tailwind CDN available after first online visit.
const CDN_ALLOWLIST = [
  // No external CSS in production; keep jQuery CDN as optional future use
  'https://code.jquery.com',
];

// Install: try to cache known URLs, but don't fail the install if any 404
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      try {
        await cache.addAll(PRECACHE_URLS);
      } catch (e) {
        // Ignore errors during install precache
      }
      self.skipWaiting();
    })()
  );
});

// Activate: cleanup old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME && key !== PAGE_CACHE_NAME) return caches.delete(key);
        })
      );
      self.clients.claim();
    })()
  );
});

// Fetch: network-first for HTML navigations to avoid stale pages after POST
// Cache-first only for static assets and allowed CDNs
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const isSameOrigin = url.origin === self.location.origin;
  const accept = req.headers.get('accept') || '';
  const isHTML = accept.includes('text/html') || req.mode === 'navigate';
  const isStatic = url.pathname.startsWith('/static/') || url.pathname.endsWith('/manifest.json');
  const isAllowedCDN = CDN_ALLOWLIST.some(prefix => req.url.startsWith(prefix));

  // Navigations: network-first → cache fallback (prevents stale after POST/PUT)
  if (isHTML) {
    event.respondWith((async () => {
      const pageCache = await caches.open(PAGE_CACHE_NAME);
      const allowCache = isSameOrigin && isAllowedPath(url.pathname);
      try {
        const fresh = await fetch(req, { cache: 'no-store' });
        if (allowCache && fresh && fresh.ok && fresh.type === 'basic') {
          pageCache.put(req, fresh.clone());
        }
        return fresh;
      } catch (e) {
        if (allowCache) {
          const cached = await pageCache.match(req, { ignoreVary: true });
          if (cached) return cached;
        }
        const staticCache = await caches.open(CACHE_NAME);
        const offline = await staticCache.match('/offline/');
        if (offline) return offline;
        throw e;
      }
    })());
    return;
  }

  // Network-first for frequently-changing chart assets (same origin only)
  if (isSameOrigin && (url.pathname.includes('/static/accounting/') || url.pathname.includes('/static/js/chart.lite'))) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      try {
        const fresh = await fetch(req, { cache: 'no-store' });
        if (fresh && fresh.ok) { cache.put(req, fresh.clone()); }
        return fresh;
      } catch (e) {
        const cached = await cache.match(req);
        if (cached) return cached;
        throw e;
      }
    })());
    return;
  }

  // Cache-first for local static files and allowed CDN assets
  if (isStatic || isAllowedCDN) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(req, { ignoreVary: true });
      if (cached) return cached;
      const fresh = await fetch(req);
      if (fresh && (fresh.ok || fresh.type === 'opaque')) {
        // Store opaque responses too (e.g., no-cors from CDNs)
        cache.put(req, fresh.clone());
      }
      return fresh;
    })());
  }
});

// -------------------------------
// Offline POST queue (Background Sync)
// -------------------------------
// Minimal IndexedDB helpers
const DB_NAME = 'archen-sync-db';
const DB_STORE = 'queue';

function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(DB_STORE)) db.createObjectStore(DB_STORE, { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function queuePut(entry) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite');
    tx.objectStore(DB_STORE).add(entry);
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error);
  });
}

async function queueAll() {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readonly');
    const req = tx.objectStore(DB_STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function queueDelete(id) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite');
    tx.objectStore(DB_STORE).delete(id);
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => reject(tx.error);
  });
}

// Intercept POST/PUT/DELETE for allowed routes to queue when offline
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (!['POST', 'PUT', 'DELETE'].includes(req.method)) return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (!isAllowedPath(url.pathname)) return;

  event.respondWith((async () => {
    try {
      // Try online first
      return await fetch(req);
    } catch (e) {
      // On failure, queue the request body and metadata for later sync
      try {
        const headers = {};
        req.headers.forEach((v, k) => { headers[k] = v; });
        const body = await req.clone().arrayBuffer();
        await queuePut({
          url: req.url,
          method: req.method,
          headers,
          body: body ? Array.from(new Uint8Array(body)) : null,
          ts: Date.now(),
        });
        // Register a background sync if supported
        if ('sync' in self.registration) {
          try { await self.registration.sync.register('archen-sync'); } catch (_) {}
        }
      } catch (_) {}
      // Inform the client that the request is queued
      return new Response('<html lang="fa" dir="rtl"><body style="font-family:sans-serif;padding:1rem"><h1>درخواست شما در صف همگام‌سازی قرار گرفت</h1><p>به محض اتصال اینترنت، عملیات ارسال می‌شود.</p></body></html>', {
        status: 202,
        headers: { 'Content-Type': 'text/html; charset=utf-8' }
      });
    }
  })());
});

async function flushQueue() {
  const entries = await queueAll();
  for (const entry of entries) {
    try {
      const body = entry.body ? new Uint8Array(entry.body) : undefined;
      const res = await fetch(entry.url, {
        method: entry.method,
        headers: entry.headers || {},
        body,
        credentials: 'include',
      });
      if (res && res.ok) await queueDelete(entry.id);
    } catch (_) { /* keep in queue */ }
  }
  // Notify clients (best-effort)
  try {
    const allClients = await self.clients.matchAll({ includeUncontrolled: true });
    allClients.forEach(c => c.postMessage({ type: 'sync-complete' }));
  } catch (_) {}
}

self.addEventListener('sync', (event) => {
  if (event.tag === 'archen-sync') {
    event.waitUntil(flushQueue());
  }
});

self.addEventListener('message', (event) => {
  if (event && event.data && event.data.type === 'sync-queue') {
    event.waitUntil(flushQueue());
  }
});
