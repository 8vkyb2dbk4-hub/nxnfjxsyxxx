const CACHE="ai-brief-v9-panels-4";
const FILES=["./", "./index.html", "./styles.css", "./app.js", "./translation.js", "./data/today.json", "./sync.js", "./sync-core.js", "./manifest.webmanifest", "./assets/icon-192.png", "./assets/icon-512.png", "./config/learning.json", "./config/preferences.json", "./config/quality.json", "./config/runtime.json", "./config/sources.json", "./config/sync.example.json", "./config/sync.json", "./config/trends.json", "./data/events.ics", "./data/health.json", "./data/latest.json", "./data/latest.md", "./data/latest_10min.json", "./data/latest_5min.json", "./data/seen_items.json", "./data/signals.json", "./data/source_health.json", "./data/weekly.json", "./data/archive/2026-10-02.json", "./data/archive/index.json", "./editions/2026-10-02.html"];
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES))));
self.addEventListener("activate",e=>e.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("ai-brief-")&&k!==CACHE).map(k=>caches.delete(k))))])));
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=="GET"||u.origin!==self.location.origin||!u.pathname.startsWith(new URL(self.registration.scope).pathname)) return;
  e.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{const r=await fetch(e.request);if(r.ok) await cache.put(e.request,r.clone());else if(r.status>=500){const saved=await cache.match(e.request);if(saved)return saved}return r}
    catch(error){return (await cache.match(e.request))||new Response("离线内容尚未缓存",{status:503})}
  })());
});

