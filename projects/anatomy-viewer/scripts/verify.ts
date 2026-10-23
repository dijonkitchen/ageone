// Check the data file against its open sources over the network (not part of `make check`, which runs
// offline). Run with `bun run verify`. It checks:
// - every FMA id (and side id) against FMA 5.1 in the EBI Ontology Lookup Service: names must match
//   (failures), and Latin names and synonyms should be among FMA's (warnings);
// - each bone's joints against its FMA definition ("articulates with ...") where it has one (warnings);
// - each muscle's nerve against its Wikipedia infobox (warnings), as a cross-check from a second source.
import { STRUCTURES, type Structure } from "../src/data";

const UA = {
	"User-Agent":
		"ageone-anatomy-viewer/0.1 (data check; https://github.com/dijonkitchen/ageone)",
	Accept: "application/json",
};
const checked = { joints: 0, nerves: 0 };
const failures: string[] = [];
const warnings: string[] = [];

async function get(url: string): Promise<unknown> {
	for (let attempt = 0; ; attempt++) {
		const r = await fetch(url, { headers: UA });
		if (r.ok) return r.json();
		if (attempt >= 4 || (r.status !== 429 && r.status < 500))
			throw new Error(`${r.status} for ${url}`);
		await Bun.sleep(
			1000 * Math.max(Number(r.headers.get("retry-after")) || 0, 2 ** attempt),
		);
	}
}

/** Run `fn` over `items`, a few at a time. */
async function each<T>(items: T[], fn: (t: T) => Promise<void>, width = 6) {
	let i = 0;
	await Promise.all(
		Array.from({ length: width }, async () => {
			while (i < items.length) await fn(items[i++] as T);
		}),
	);
}

interface FmaTerm {
	label: string;
	annotation: Record<string, string[] | undefined>;
}

const fmaTerm = (id: string) => {
	const iri = `http://purl.org/sig/ont/fma/fma${id.replace("FMA:", "")}`;
	return get(
		`https://www.ebi.ac.uk/ols4/api/ontologies/fma/terms/${encodeURIComponent(encodeURIComponent(iri))}`,
	) as Promise<FmaTerm>;
};

const norm = (t: string) =>
	t
		.toLowerCase()
		.replace(/[^a-z0-9 ]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();
const byId = new Map(STRUCTURES.map((s) => [s.id, s]));

async function checkFma(s: Structure) {
	const t = await fmaTerm(s.id);
	if (norm(t.label) !== norm(s.name))
		failures.push(`${s.id}: FMA calls it "${t.label}", the data "${s.name}"`);
	const fmaNames = [
		...(t.annotation.synonym ?? []),
		...(t.annotation["non-English equivalent"] ?? []),
	].map(norm);
	if (s.latinSource !== "TA" && !fmaNames.includes(norm(s.latin)))
		warnings.push(`${s.name}: Latin "${s.latin}" is not among FMA's`);
	for (const syn of s.synonyms)
		if (!fmaNames.includes(norm(syn)))
			warnings.push(`${s.name}: synonym "${syn}" is not among FMA's`);
	if (s.sides)
		for (const side of ["right", "left"] as const) {
			const st = await fmaTerm(s.sides[side]);
			if (!norm(st.label).split(" ").includes(side))
				failures.push(
					`${s.sides[side]}: "${st.label}" is not the ${side} ${s.name}`,
				);
		}
	const definition = t.annotation.definition?.[0];
	if (s.system === "skeleton" && definition?.includes("articulates with")) {
		const text = norm(definition);
		for (const j of s.joints ?? []) {
			checked.joints++;
			const other = byId.get(j);
			const names = other ? [other.name, ...other.synonyms].map(norm) : [];
			// FMA writes "some hip bone"; match a name's first word, or its whole, singular or plural.
			if (
				!names.some(
					(n) =>
						text.includes(n) ||
						text.includes(n.replace(/ bone$/, "")) ||
						text.includes(n.split(" ")[0] ?? n),
				)
			)
				warnings.push(
					`${s.name}: joint with ${other?.name ?? j} is not in FMA's definition ("${definition}")`,
				);
		}
	}
}

interface WikiPages {
	query: {
		normalized?: { from: string; to: string }[];
		redirects?: { from: string; to: string }[];
		pages: {
			title: string;
			revisions?: { slots: { main: { content: string } } }[];
		}[];
	};
}

/** Every muscle's nerve against its Wikipedia infobox, in one request (the API takes 50 titles). */
async function checkWikipedia(muscles: Structure[]) {
	const titles = new Map(
		muscles.map((s) => [
			s.name.includes("muscle") ? s.name : `${s.name} muscle`,
			s,
		]),
	);
	const url = `https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&redirects=1&format=json&formatversion=2&titles=${encodeURIComponent([...titles.keys()].join("|"))}`;
	const { query } = (await get(url)) as WikiPages;
	const follow = (t: string) => {
		let at = t;
		for (const step of [
			...(query.normalized ?? []),
			...(query.redirects ?? []),
		])
			if (step.from === at) at = step.to;
		return at;
	};
	for (const [title, s] of titles) {
		const text = query.pages.find((p) => p.title === follow(title))
			?.revisions?.[0]?.slots.main.content;
		const nerve = text?.match(/\|\s*nerve\s*=([^\n]*)/i)?.[1];
		if (!text) warnings.push(`${s.name}: no Wikipedia article "${title}"`);
		else if (!nerve || !s.nerve)
			warnings.push(`${s.name}: no nerve in the Wikipedia infobox`);
		else {
			checked.nerves++;
			const skip = [
				"nerve",
				"nerves",
				"branch",
				"branches",
				"from",
				"spinal",
				"anterior",
				"posterior",
			];
			const words = norm(s.nerve)
				.split(" ")
				.filter((w) => w.length > 4 && !skip.includes(w));
			if (!words.some((w) => norm(nerve).includes(w)))
				warnings.push(
					`${s.name}: nerve "${s.nerve}" vs Wikipedia "${nerve.trim()}"`,
				);
		}
	}
}

await each(STRUCTURES, checkFma);
await checkWikipedia(STRUCTURES.filter((s) => s.system === "muscles"));

const ids = STRUCTURES.reduce((n, s) => n + (s.sides ? 3 : 1), 0);
console.log(
	`Checked ${ids} FMA ids for ${STRUCTURES.length} structures, and ${STRUCTURES.filter((s) => s.system === "muscles").length} muscles on Wikipedia: ${checked.joints} joints against FMA definitions, ${checked.nerves} nerves against infoboxes.`,
);
for (const w of warnings) console.log(`warning: ${w}`);
for (const f of failures) console.log(`FAIL: ${f}`);
console.log(`${failures.length} failures, ${warnings.length} warnings.`);
process.exit(failures.length ? 1 : 0);
