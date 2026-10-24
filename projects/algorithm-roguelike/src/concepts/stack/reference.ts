// A stack: last in, first out. `push` adds to the top and `pop` takes from the top, both O(1) on the end
// of an array. A bounded stack drops its oldest entry when full, as the game's undo history does.

export class Stack<T> {
	private items: T[] = [];
	constructor(private readonly limit = Number.POSITIVE_INFINITY) {}
	push(item: T) {
		this.items.push(item);
		if (this.items.length > this.limit) this.items.shift();
	}
	pop(): T | undefined {
		return this.items.pop();
	}
	peek(): T | undefined {
		return this.items.at(-1);
	}
	get size() {
		return this.items.length;
	}
	toArray(): T[] {
		return [...this.items];
	}
}
