// A binary min-heap in an array: the parent of index i is at (i - 1) >> 1, its children at 2i + 1 and
// 2i + 2, and no child is smaller than its parent, so the smallest entry is always at index 0.
// Entries are arrays of numbers compared in order ([time, seq, id] in the game). Self-contained functions
// that return new arrays, so they also run in the code-mode sandbox.

/** Push an entry; returns the new heap. */
export function heapPush(heap: number[][], entry: number[]): number[][] {
	const less = (a: number[], b: number[]) => {
		for (let k = 0; k < Math.max(a.length, b.length); k++) {
			const x = a[k] ?? 0;
			const y = b[k] ?? 0;
			if (x !== y) return x < y;
		}
		return false;
	};
	const h = [...heap, entry];
	let i = h.length - 1;
	while (i > 0) {
		const p = (i - 1) >> 1;
		if (!less(h[i] as number[], h[p] as number[])) break;
		[h[i], h[p]] = [h[p] as number[], h[i] as number[]];
		i = p;
	}
	return h;
}

/** Pop the smallest entry; returns [entry, new heap], or [null, []] when empty. */
export function heapPop(heap: number[][]): [number[] | null, number[][]] {
	const less = (a: number[], b: number[]) => {
		for (let k = 0; k < Math.max(a.length, b.length); k++) {
			const x = a[k] ?? 0;
			const y = b[k] ?? 0;
			if (x !== y) return x < y;
		}
		return false;
	};
	if (!heap.length) return [null, []];
	const h = [...heap];
	const top = h[0] as number[];
	const last = h.pop() as number[];
	if (h.length) {
		h[0] = last;
		let i = 0;
		for (;;) {
			const l = 2 * i + 1;
			const r = l + 1;
			let m = i;
			if (l < h.length && less(h[l] as number[], h[m] as number[])) m = l;
			if (r < h.length && less(h[r] as number[], h[m] as number[])) m = r;
			if (m === i) break;
			[h[i], h[m]] = [h[m] as number[], h[i] as number[]];
			i = m;
		}
	}
	return [top, h];
}

/** Whether an array satisfies the heap property. */
export function isHeap(h: number[][]): boolean {
	const cmp = (a: number[], b: number[]) => {
		for (let k = 0; k < Math.max(a.length, b.length); k++)
			if ((a[k] ?? 0) !== (b[k] ?? 0)) return (a[k] ?? 0) - (b[k] ?? 0);
		return 0;
	};
	return h.every((e, i) => i === 0 || cmp(h[(i - 1) >> 1] as number[], e) <= 0);
}

const lessThan = (a: number[], b: number[]) => {
	for (let k = 0; k < Math.max(a.length, b.length); k++)
		if ((a[k] ?? 0) !== (b[k] ?? 0)) return (a[k] ?? 0) < (b[k] ?? 0);
	return false;
};

/** The same push, changing the array in place (for Dijkstra's many pushes, where copying would cost O(n)). */
export function pushInPlace(h: number[][], entry: number[]) {
	h.push(entry);
	let i = h.length - 1;
	while (i > 0) {
		const p = (i - 1) >> 1;
		if (!lessThan(h[i] as number[], h[p] as number[])) break;
		[h[i], h[p]] = [h[p] as number[], h[i] as number[]];
		i = p;
	}
}

/** The same pop, in place; undefined when empty. */
export function popInPlace(h: number[][]): number[] | undefined {
	const top = h[0];
	const last = h.pop();
	if (h.length && last) {
		h[0] = last;
		let i = 0;
		for (;;) {
			const l = 2 * i + 1;
			const r = l + 1;
			let m = i;
			if (l < h.length && lessThan(h[l] as number[], h[m] as number[])) m = l;
			if (r < h.length && lessThan(h[r] as number[], h[m] as number[])) m = r;
			if (m === i) break;
			[h[i], h[m]] = [h[m] as number[], h[i] as number[]];
			i = m;
		}
	}
	return top;
}
