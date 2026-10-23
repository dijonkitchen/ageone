// Offline and safe updates. Every file of one version is cached together under that version's name, and served
// only from there, so a page never mixes files from two versions. A new version installs in the background and
// waits; the page activates it on the next launch, before showing anything (see app.ts).
const CACHE = "simplefit-__VERSION__";
const FILES = [
	"./",
	"index.html",
	"app.js",
	"styles.css",
	"manifest.webmanifest",
	"icon.svg",
	"icon-180.png",
	"icon-512.png",
];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) =>
				cache.addAll(FILES.map((f) => new Request(f, { cache: "reload" }))),
			),
	);
});

self.addEventListener("message", (event) => {
	if (event.data === "activate") self.skipWaiting();
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((k) => k.startsWith("simplefit-") && k !== CACHE)
						.map((k) => caches.delete(k)),
				),
			)
			.then(() => self.clients.claim()),
	);
});

self.addEventListener("fetch", (event) => {
	const request = event.request;
	if (
		request.method !== "GET" ||
		new URL(request.url).origin !== self.location.origin
	)
		return;
	event.respondWith(
		caches.open(CACHE).then(async (cache) => {
			const hit = await cache.match(
				request.mode === "navigate" ? "index.html" : request,
				{ ignoreSearch: true },
			);
			return hit ?? fetch(request);
		}),
	);
});
