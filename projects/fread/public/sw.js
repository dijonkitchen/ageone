// Offline app shell: the build replaces __VERSION__ with a hash of the files, so a new build replaces the cache.
// Feeds are fetched by the page and their articles kept in IndexedDB, so they are read offline from there.
const CACHE = "fread-__VERSION__";
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
						.filter((k) => k.startsWith("fread-") && k !== CACHE)
						.map((k) => caches.delete(k)),
				),
			)
			.then(() => self.clients.claim()),
	);
});

self.addEventListener("fetch", (event) => {
	const url = new URL(event.request.url);
	// Only the app's own files; feeds and images go straight to the network.
	if (event.request.method !== "GET" || url.origin !== self.location.origin)
		return;
	event.respondWith(
		caches
			.match(event.request, { ignoreSearch: true })
			.then((hit) => hit ?? fetch(event.request)),
	);
});
