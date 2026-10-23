// The alias method (Vose's version): after O(n) setup, draw from any weighted list in O(1) with one
// random column and one coin flip. Each column holds part of one outcome and tops up with an "alias".

export interface AliasTable {
	prob: number[]; // chance of keeping the column's own outcome
	alias: number[]; // the outcome that fills the rest of the column
}

/** Build the table, pairing small and large columns in order (first small with first large). */
export function buildAlias(weights: number[]): AliasTable {
	const n = weights.length;
	const total = weights.reduce((a, b) => a + b, 0);
	if (!n || total <= 0) throw new Error("weights must be positive");
	const p = weights.map((w) => (w * n) / total);
	const prob = Array<number>(n).fill(1);
	const alias = Array.from({ length: n }, (_, i) => i);
	const small = p.flatMap((v, i) => (v < 1 ? [i] : []));
	const large = p.flatMap((v, i) => (v >= 1 ? [i] : []));
	while (small.length && large.length) {
		const s = small.shift() as number;
		const l = large.shift() as number;
		prob[s] = p[s] as number;
		alias[s] = l;
		p[l] = (p[l] as number) + (p[s] as number) - 1;
		if ((p[l] as number) < 1 - 1e-12) small.push(l);
		else large.unshift(l);
	}
	return { prob, alias };
}

/** Draw an outcome from two uniform numbers in [0, 1): one picks the column, the other flips its coin. */
export function sampleAlias(t: AliasTable, u1: number, u2: number): number {
	const col = Math.min(t.prob.length - 1, Math.floor(u1 * t.prob.length));
	return u2 < (t.prob[col] as number) ? col : (t.alias[col] as number);
}
