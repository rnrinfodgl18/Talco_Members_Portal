const CACHE = "talco-shell-v5";
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(["/", "/manifest.webmanifest", "/pwa-icon.svg"])));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || new URL(event.request.url).pathname.startsWith("/api/")) return;
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return response;
  }).catch(() => caches.match(event.request).then(response => response || caches.match("/"))));
});
self.addEventListener("push", event => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || "TALCO", {
    body: data.body || "You have a new update", icon: "/pwa-icon.svg", badge: "/pwa-icon.svg",
    data: {url: data.url || "/"}, tag: data.notificationId ? "talco-" + data.notificationId : undefined
  }));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(clients.matchAll({type:"window",includeUncontrolled:true}).then(list => {
    const target = event.notification.data?.url || "/";
    for (const client of list) { if ("focus" in client) { client.navigate(target); return client.focus(); } }
    return clients.openWindow(target);
  }));
});
