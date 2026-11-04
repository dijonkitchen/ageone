// A 3x5 pixel font for the HUD and menus, so the game draws all of its text itself (no font files).
// Each glyph is five rows of three bits, high bit on the left.

const GLYPHS: Record<string, string> = {
	A: "25755",
	B: "65656",
	C: "34443",
	D: "65556",
	E: "74647",
	F: "74644",
	G: "34553",
	H: "55755",
	I: "72227",
	J: "11152",
	K: "55655",
	L: "44447",
	M: "57755",
	N: "65555",
	O: "25552",
	P: "65644",
	Q: "25563",
	R: "65655",
	S: "34216",
	T: "72222",
	U: "55557",
	V: "55552",
	W: "55775",
	X: "55255",
	Y: "55222",
	Z: "71247",
	"0": "75557",
	"1": "26227",
	"2": "61247",
	"3": "61216",
	"4": "55711",
	"5": "74616",
	"6": "34757",
	"7": "71222",
	"8": "75757",
	"9": "75716",
	" ": "00000",
	"!": "22202",
	"?": "61202",
	".": "00002",
	":": "02020",
	"-": "00700",
	"/": "11244",
	">": "42124",
	"<": "12421",
	"'": "22000",
	";": "02024",
	",": "00024",
};

/** The glyph's five rows as 3-bit numbers; unknown characters draw as blanks. */
export function glyph(ch: string): number[] {
	return [...(GLYPHS[ch.toUpperCase()] ?? "00000")].map(Number);
}

/** Width in pixels of `text` at `scale`: 3 pixels per glyph plus 1 between. */
export const textWidth = (text: string, scale = 1): number =>
	Math.max(0, text.length * 4 - 1) * scale;

/** Calls `dot(x, y)` for each lit pixel of `text` at (x, y), one font pixel = `scale` screen pixels. */
export function eachDot(
	text: string,
	x: number,
	y: number,
	scale: number,
	dot: (x: number, y: number) => void,
): void {
	for (const [i, ch] of [...text].entries())
		for (const [row, bits] of glyph(ch).entries())
			for (let col = 0; col < 3; col++)
				if (bits & (4 >> col)) dot(x + (i * 4 + col) * scale, y + row * scale);
}
