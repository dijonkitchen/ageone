// Offline app shell: the build replaces __VERSION__ with a hash of the files, so a new build replaces the cache.
// Notes live in the browser's private file system, so they are read offline from there.
const CACHE = "needle-__VERSION__";
const SHELL = [
	"./",
	"index.html",
	"app.js",
	"styles.css",
	"manifest.webmanifest",
	"icon.svg",
];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(SHELL))
			.then(() => self.skipWaiting()),
	);
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((k) => k.startsWith("needle-") && k !== CACHE)
						.map((k) => caches.delete(k)),
				),
			)
			.then(() => self.clients.claim()),
	);
});

self.addEventListener("fetch", (event) => {
	const url = new URL(event.request.url);
	// Only the app's own files; searches and model calls go straight to the network.
	if (event.request.method !== "GET" || url.origin !== self.location.origin)
		return;
	event.respondWith(
		caches.match(event.request).then((hit) => hit ?? fetch(event.request)),
	);
});
