// The drawings: every structure's shape in each view, made in code for this project.
// Shapes are authored for the body's right side in front coordinates (right is negative x) and mirrored
// for the left; the back view is the front coordinates mirrored, so the body's right shows on the right.
// The side view shows the body's right side, facing right (anterior is positive x).
import { drawnId, SEGMENTS, type Side, type View } from "./data";
import {
	band,
	ellipse,
	join,
	longBone,
	mirrorPath,
	type Point,
	smooth,
} from "./geometry";

export interface Drawn {
	id: string | null; // null for decoration (eye sockets, the ear canal), which is not a structure
	layer: "skeleton" | "muscles" | "organs" | "skin";
	d: string;
	evenOdd?: boolean;
}

type Layer = Drawn["layer"];
const ord = [
	"First",
	"Second",
	"Third",
	"Fourth",
	"Fifth",
	"Sixth",
	"Seventh",
	"Eighth",
	"Ninth",
	"Tenth",
	"Eleventh",
	"Twelfth",
];
const cervical = (i: number) =>
	i === 0 ? "Atlas" : i === 1 ? "Axis" : `${ord[i]} cervical vertebra`;

/** Collects shapes for one view. */
class Canvas {
	items: Drawn[] = [];
	constructor(readonly mirrorLeft: boolean) {}
	mid(layer: Layer, name: string, d: string, evenOdd = false) {
		this.items.push({ id: drawnId(name, null), layer, d, evenOdd });
	}
	/** A paired structure: the right side as drawn, and the left mirrored (front and back views only). */
	pair(layer: Layer, name: string, d: string, evenOdd = false) {
		this.items.push({ id: drawnId(name, "right"), layer, d, evenOdd });
		if (this.mirrorLeft)
			this.items.push({
				id: drawnId(name, "left"),
				layer,
				d: mirrorPath(d),
				evenOdd,
			});
	}
	one(layer: Layer, name: string, side: Side, d: string) {
		this.items.push({ id: drawnId(name, side), layer, d });
	}
	decor(layer: Layer, d: string) {
		this.items.push({ id: null, layer, d });
	}
}

const mirrorAll = (items: Drawn[]): Drawn[] =>
	items.map((i) => ({ ...i, d: mirrorPath(i.d) }));

// ---------------------------------------------------------------------------------------------
// Skeleton, front and back (front coordinates)

function vertebraLevels() {
	const out: { name: string; y: number; h: number; w: number }[] = [];
	out.push({ name: cervical(0), y: 20.4, h: 0.9, w: 5 });
	out.push({ name: cervical(1), y: 21.7, h: 1.1, w: 3.4 });
	for (let i = 2; i < 7; i++)
		out.push({
			name: cervical(i),
			y: 23 + (i - 2) * 1.1,
			h: 0.9,
			w: 2.6 + i * 0.1,
		});
	for (let i = 0; i < 12; i++)
		out.push({
			name: `${ord[i]} thoracic vertebra`,
			y: 28.6 + i * 2.55,
			h: 2.1,
			w: 3 + i * 0.12,
		});
	for (let i = 0; i < 5; i++)
		out.push({
			name: `${ord[i]} lumbar vertebra`,
			y: 59.5 + i * 3.9,
			h: 3.3,
			w: 4.8 + i * 0.2,
		});
	return out;
}

const RIB_HALF_WIDTH = [
	6.5, 9, 10.5, 11.5, 12.3, 12.9, 13.3, 13.5, 13.4, 13, 11.5, 9.5,
];
const RIB_FRONT_END: Point[] = [
	[-1.8, 30],
	[-1.9, 32.5],
	[-2, 35.5],
	[-2.1, 38.5],
	[-2.2, 41.5],
	[-2.3, 44],
	[-2.4, 46.5],
	[-5.5, 50.5],
	[-8.5, 53.5],
	[-11, 56.5],
	[-13, 60.5],
	[-11, 62.5],
];
const ribLevel = (i: number) => 28.6 + i * 2.55;

function ribFront(i: number): string {
	const yv = ribLevel(i);
	const w = RIB_HALF_WIDTH[i] as number;
	const end = RIB_FRONT_END[i] as Point;
	const line: Point[] =
		i < 10
			? [
					[-1.6, yv],
					[-w * 0.6, yv - 0.3],
					[-w, yv + (end[1] - yv) * 0.35 + 1.2],
					[-w * 0.85, yv + (end[1] - yv) * 0.75 + 1.4],
					end,
				]
			: [[-1.6, yv], [-w * 0.6, yv + 0.2], [-w, yv + 2.5], end];
	return band(line, [1.2, 1.1, 1.0, 0.9, 0.8]);
}

function ribBack(i: number): string {
	const yv = ribLevel(i);
	const w = RIB_HALF_WIDTH[i] as number;
	const drop = i < 10 ? 6.5 : 4;
	return band(
		[
			[-1.6, yv],
			[-w * 0.55, yv + 0.6],
			[-w, yv + drop * 0.55],
			[-w * 0.97, yv + drop],
		],
		[1.2, 1.1, 1, 0.9],
	);
}

function vertebraFront(c: Canvas, back: boolean) {
	for (const v of vertebraLevels()) {
		const body = smooth([
			[-v.w / 2, v.y - v.h / 2],
			[v.w / 2, v.y - v.h / 2],
			[v.w / 2 + 0.2, v.y],
			[v.w / 2, v.y + v.h / 2],
			[-v.w / 2, v.y + v.h / 2],
			[-v.w / 2 - 0.2, v.y],
		]);
		const spine = smooth([
			[0, v.y - v.h * 0.45],
			[v.h * 0.35, v.y],
			[0, v.y + v.h * 0.6],
			[-v.h * 0.35, v.y],
		]);
		c.mid("skeleton", v.name, back ? join(body, spine) : body);
	}
	c.mid(
		"skeleton",
		"Sacrum",
		smooth([
			[-5, 78.4],
			[5, 78.4],
			[3.6, 84],
			[1.2, 90.4],
			[-1.2, 90.4],
			[-3.6, 84],
		]),
	);
	c.mid(
		"skeleton",
		"Coccyx",
		smooth([
			[-1.1, 90.9],
			[1.1, 90.9],
			[0.4, 93.3],
			[-0.4, 93.3],
		]),
	);
}

const SCAPULA_FRONT: Point[] = [
	[-16.8, 30.3],
	[-15.5, 31.5],
	[-11, 31.2],
	[-9.2, 32],
	[-10.2, 40],
	[-11.8, 47],
	[-13.5, 44],
	[-15.8, 36.8],
	[-17, 33.6],
	[-17.2, 31.3],
];
const SCAPULA_BACK: Point[] = [
	[-16.8, 30.3],
	[-13, 30.6],
	[-9, 31],
	[-5.2, 32.6],
	[-6, 40],
	[-11, 47.5],
	[-12.5, 46],
	[-15.5, 38],
	[-16.5, 34],
	[-17.4, 31.5],
];

function hand(c: Canvas) {
	c.pair(
		"skeleton",
		"Carpal bone",
		smooth([
			[-25.6, 85.6],
			[-22.4, 85.4],
			[-21.9, 87.6],
			[-22.4, 89],
			[-26, 89.3],
			[-26.6, 87.4],
		]),
	);
	const meta: string[] = [
		longBone([-26.4, 88.8], [-28.2, 92.6], 0.7, 0.6, 0.6),
	];
	const phal: string[] = [
		longBone([-28.4, 93.2], [-29, 95.8], 0.6, 0.5, 0.5),
		longBone([-29.1, 96.2], [-29.6, 98.4], 0.5, 0.45, 0.4),
	];
	const tips = [103, 104, 103.3, 101.5];
	for (let j = 0; j < 4; j++) {
		const base: Point = [-25.4 + j * 0.95, 89.4];
		const head: Point = [-26.2 + j * 1.25, 95.4];
		meta.push(longBone(base, head, 0.6, 0.55, 0.55));
		const tip = tips[j] as number;
		const len = tip - 95.8;
		const x = head[0] - (1.5 - j) * 0.15;
		const cuts = [0, 0.45, 0.75, 1].map((k) => 95.8 + len * k);
		for (let k = 0; k < 3; k++)
			phal.push(
				longBone(
					[x, (cuts[k] as number) + 0.15],
					[x - (1.5 - j) * 0.05, (cuts[k + 1] as number) - 0.15],
					0.5,
					0.45,
					0.4,
				),
			);
	}
	c.pair("skeleton", "Metacarpal bone", join(...meta));
	c.pair("skeleton", "Phalanx of finger", join(...phal));
}

function footFront(c: Canvas) {
	c.pair(
		"skeleton",
		"Tarsal bone",
		smooth([
			[-9.6, 166.6],
			[-5.4, 166.4],
			[-5, 169.5],
			[-6.4, 171.2],
			[-10.6, 171.3],
			[-10.8, 169],
		]),
	);
	const meta: string[] = [];
	const phal: string[] = [];
	for (let j = 0; j < 5; j++) {
		const x = -5.6 - j * 1.2;
		meta.push(
			longBone([x + 0.3, 170.6], [x, 173.8], j === 0 ? 1 : 0.6, 0.55, 0.55),
		);
		phal.push(
			longBone(
				[x, 174.2],
				[x - 0.05, 176.2 - j * 0.25],
				j === 0 ? 0.9 : 0.55,
				0.5,
				0.45,
			),
		);
	}
	c.pair("skeleton", "Metatarsal bone", join(...meta));
	c.pair("skeleton", "Phalanx of toe", join(...phal));
}

const HIP_FRONT: Point[] = [
	[-1.3, 90.3],
	[-2.4, 88.3],
	[-5.5, 87.6],
	[-7, 85.6],
	[-6.6, 80],
	[-4.6, 79.2],
	[-5.5, 75.5],
	[-9, 72.5],
	[-13.2, 72.8],
	[-15, 75],
	[-14, 78],
	[-12.4, 80],
	[-11.8, 84.5],
	[-12, 88],
	[-11.6, 91.5],
	[-10, 94.6],
	[-7.5, 96.5],
	[-4.5, 95.3],
	[-2.2, 93.2],
];

function limbsFront(c: Canvas) {
	c.pair(
		"skeleton",
		"Humerus",
		longBone([-17, 32.5], [-20.5, 60], 1.9, 2.5, 2.2),
	);
	c.pair(
		"skeleton",
		"Ulna",
		longBone([-19.7, 60.5], [-22.6, 84.8], 1.1, 1.5, 0.8),
	);
	c.pair(
		"skeleton",
		"Radius",
		longBone([-21.6, 61], [-25.4, 84.6], 1.1, 1.0, 1.7),
	);
	hand(c);
	c.pair(
		"skeleton",
		"Femur",
		join(
			ellipse([-9, 89], 2, 2),
			band(
				[
					[-9.4, 89.5],
					[-12.4, 91.2],
				],
				2.2,
			),
			longBone([-12.4, 91.6], [-8.6, 129.5], 2.4, 2.2, 3),
		),
	);
	c.pair(
		"skeleton",
		"Tibia",
		longBone([-8, 131.4], [-7.2, 166], 2.3, 3.2, 1.9),
	);
	c.pair(
		"skeleton",
		"Fibula",
		longBone([-11.4, 132.4], [-10.4, 167], 0.8, 1, 1),
	);
}

function skullFront(c: Canvas) {
	c.mid(
		"skeleton",
		"Frontal bone",
		smooth([
			[-7.6, 6],
			[-6.5, 2],
			[-3.5, 0.1],
			[0, -0.3],
			[3.5, 0.1],
			[6.5, 2],
			[7.6, 6],
			[7, 9.8],
			[4, 9.4],
			[1.2, 10.2],
			[0, 11],
			[-1.2, 10.2],
			[-4, 9.4],
			[-7, 9.8],
		]),
	);
	c.pair(
		"skeleton",
		"Parietal bone",
		smooth([
			[-7.4, 5.2],
			[-8.3, 4.8],
			[-8.7, 8],
			[-8.3, 10.1],
			[-7.5, 9.8],
			[-7.7, 7.5],
		]),
	);
	c.pair(
		"skeleton",
		"Temporal bone",
		smooth([
			[-8.3, 10.3],
			[-8.7, 12.4],
			[-8.2, 15.5],
			[-7.2, 15.3],
			[-7.2, 12.4],
			[-7.5, 10.3],
		]),
	);
	const wing = smooth([
		[-7.4, 10],
		[-6.7, 10.1],
		[-6.8, 12],
		[-7.3, 12.1],
	]);
	c.mid("skeleton", "Sphenoid bone", join(wing, mirrorPath(wing)));
	c.pair(
		"skeleton",
		"Zygomatic bone",
		smooth([
			[-6.7, 10.5],
			[-5, 11.6],
			[-4.6, 13.4],
			[-6, 14.3],
			[-7.6, 13.8],
			[-7.2, 12.2],
		]),
	);
	c.pair(
		"skeleton",
		"Maxilla",
		smooth([
			[-0.1, 13.8],
			[-1.5, 13.4],
			[-2.4, 14.8],
			[-4.5, 13.7],
			[-5.8, 14.6],
			[-5.6, 16.5],
			[-4, 17.8],
			[-0.1, 18.2],
		]),
	);
	c.pair(
		"skeleton",
		"Nasal bone",
		smooth([
			[-0.1, 10.9],
			[-1, 10.7],
			[-1.3, 13.2],
			[-0.1, 13.6],
		]),
	);
	c.mid(
		"skeleton",
		"Mandible",
		smooth([
			[-6.3, 15.4],
			[-5.8, 19.5],
			[-3.5, 21.6],
			[0, 22.3],
			[3.5, 21.6],
			[5.8, 19.5],
			[6.3, 15.4],
			[5.4, 15.8],
			[4.8, 19],
			[3, 20.4],
			[0, 20.9],
			[-3, 20.4],
			[-4.8, 19],
			[-5.4, 15.8],
		]),
	);
	c.decor(
		"skeleton",
		join(ellipse([-3.3, 10.9], 2, 1.7), ellipse([3.3, 10.9], 2, 1.7)),
	);
	c.decor(
		"skeleton",
		smooth([
			[0, 13.4],
			[0.9, 14.6],
			[0.6, 15.8],
			[-0.6, 15.8],
			[-0.9, 14.6],
		]),
	);
}

function skullBack(c: Canvas) {
	c.pair(
		"skeleton",
		"Parietal bone",
		smooth([
			[0, -0.3],
			[-4, 0.2],
			[-7.2, 3],
			[-8.4, 7.5],
			[-7.4, 10],
			[-4, 11],
			[-0.1, 12.5],
		]),
	);
	c.mid(
		"skeleton",
		"Occipital bone",
		smooth([
			[-7.4, 10.2],
			[-4, 11.2],
			[0, 12.7],
			[4, 11.2],
			[7.4, 10.2],
			[7.4, 13.5],
			[5, 16.5],
			[0, 18],
			[-5, 16.5],
			[-7.4, 13.5],
		]),
	);
	c.pair(
		"skeleton",
		"Temporal bone",
		smooth([
			[-8.4, 8.2],
			[-8.7, 12],
			[-7.8, 15.4],
			[-7.3, 13],
			[-7.6, 10.3],
		]),
	);
	const ramus = smooth([
		[-6.3, 15.6],
		[-6, 20],
		[-4.5, 21.6],
		[-5.1, 18],
		[-5.6, 15.9],
	]);
	c.mid("skeleton", "Mandible", join(ramus, mirrorPath(ramus)));
}

function skeletonFrontBack(c: Canvas, back: boolean) {
	// Draw order within the layer; the SVG builder then nests shapes by skeleton segment.
	if (back) skullBack(c);
	else skullFront(c);
	c.mid(
		"skeleton",
		"Hyoid bone",
		band(
			[
				[-2.2, 23.1],
				[-1, 23.8],
				[1, 23.8],
				[2.2, 23.1],
			],
			0.6,
		),
	);
	vertebraFront(c, back);
	c.pair("skeleton", "Scapula", smooth(back ? SCAPULA_BACK : SCAPULA_FRONT));
	for (let i = 0; i < 12; i++)
		c.pair("skeleton", `${ord[i]} rib`, back ? ribBack(i) : ribFront(i));
	if (!back)
		c.mid(
			"skeleton",
			"Sternum",
			smooth([
				[-2.2, 28.9],
				[2.2, 28.9],
				[1.6, 31.4],
				[1.6, 44],
				[0.9, 46.3],
				[0.4, 48.2],
				[-0.4, 48.2],
				[-0.9, 46.3],
				[-1.6, 44],
				[-1.6, 31.4],
			]),
		);
	c.pair(
		"skeleton",
		"Clavicle",
		band(
			[
				[-2.2, 28.6],
				[-6, 28.2],
				[-10, 29.4],
				[-13.5, 29.3],
				[-16.3, 29.2],
			],
			[1.4, 1.1, 1, 1, 1.3],
		),
	);
	c.pair(
		"skeleton",
		"Hip bone",
		join(smooth(HIP_FRONT), ellipse([-6.2, 92], 1.7, 1.5)),
		true,
	);
	limbsFront(c);
	if (!back) {
		c.pair("skeleton", "Patella", ellipse([-8.5, 127.5], 1.9, 2.4));
		footFront(c);
	} else
		c.pair(
			"skeleton",
			"Tarsal bone",
			smooth([
				[-9.4, 166.2],
				[-5.6, 166.2],
				[-5.2, 170],
				[-6.4, 173.2],
				[-8.6, 173.4],
				[-9.8, 170],
			]),
		);
}

// ---------------------------------------------------------------------------------------------
// Skeleton, side (right lateral; anterior is +x)

const SPINE: Point[] = [
	[-1, 20],
	[-2.5, 24],
	[-4, 28],
	[-6.5, 36],
	[-7.5, 43],
	[-6.8, 50],
	[-5, 58],
	[-3, 64],
	[-2.2, 69],
	[-2.8, 74],
	[-3.8, 78],
];
function spineX(y: number): number {
	for (let i = 0; i < SPINE.length - 1; i++) {
		const [x0, y0] = SPINE[i] as Point;
		const [x1, y1] = SPINE[i + 1] as Point;
		if (y <= y1) return x0 + ((x1 - x0) * (y - y0)) / (y1 - y0);
	}
	return (SPINE[SPINE.length - 1] as Point)[0];
}

function skeletonSide(c: Canvas) {
	const S = (name: string, pts: Point[]) =>
		c.mid("skeleton", name, smooth(pts));
	const R = (name: string, d: string) => c.one("skeleton", name, "right", d);
	// Skull
	S("Frontal bone", [
		[9, 6],
		[7.5, 2],
		[3.5, -0.3],
		[0, -0.8],
		[-0.8, 2],
		[1, 6],
		[2.5, 9.5],
		[5.8, 10],
		[8.8, 10.3],
	]);
	R(
		"Parietal bone",
		smooth([
			[0, -0.8],
			[-4.5, -0.2],
			[-8, 2.5],
			[-9.6, 6.5],
			[-5.5, 8.6],
			[-1, 8.8],
			[1, 6],
			[-0.8, 2],
		]),
	);
	S("Occipital bone", [
		[-9.6, 6.6],
		[-10.2, 10],
		[-9, 14.5],
		[-6.8, 17.5],
		[-5, 16],
		[-5.5, 12],
		[-5.5, 8.7],
	]);
	R(
		"Temporal bone",
		smooth([
			[-5.4, 8.8],
			[-1, 8.9],
			[2.2, 9.7],
			[2.4, 12.5],
			[1, 13.8],
			[-1.6, 15.6],
			[-4.8, 16.2],
			[-5.4, 12],
		]),
	);
	S("Sphenoid bone", [
		[2.5, 9.7],
		[4.4, 9.9],
		[4.6, 12.5],
		[2.6, 12.5],
	]);
	R(
		"Zygomatic bone",
		smooth([
			[4.7, 10.2],
			[6.6, 10.8],
			[7, 13.2],
			[5, 14.2],
			[2.2, 13.9],
			[2.6, 12.8],
			[4.7, 12.6],
		]),
	);
	R(
		"Nasal bone",
		smooth([
			[8.8, 10.3],
			[10.2, 12.6],
			[9.5, 13.1],
			[8.6, 11],
		]),
	);
	R(
		"Maxilla",
		smooth([
			[7.1, 13.3],
			[8.6, 11.2],
			[9.5, 13.2],
			[10, 15],
			[9.6, 17.2],
			[6, 17.4],
			[4.8, 15.4],
			[5.1, 14.3],
		]),
	);
	S("Mandible", [
		[9.4, 17.6],
		[9.6, 20.4],
		[8, 21.8],
		[3.5, 21],
		[1.3, 20.4],
		[0.6, 17],
		[0.2, 13.6],
		[1.3, 13.4],
		[1.8, 16.2],
		[3, 18.2],
		[6.2, 18],
	]);
	c.decor(
		"skeleton",
		join(ellipse([7.6, 11.4], 1.2, 1.4), ellipse([-1.8, 13.6], 0.6, 0.6)),
	);
	c.mid(
		"skeleton",
		"Hyoid bone",
		band(
			[
				[3.2, 22.6],
				[4.6, 23.2],
			],
			0.6,
		),
	);
	// Vertebral column: bodies to the front, spinous processes to the back.
	for (const v of vertebraLevels()) {
		const x = spineX(v.y);
		const w = v.w * 0.75;
		const bodyD = smooth([
			[x + 0.4, v.y - v.h / 2],
			[x + 0.4 + w, v.y - v.h / 2],
			[x + 0.6 + w, v.y + v.h / 2],
			[x + 0.4, v.y + v.h / 2],
		]);
		const spinous = smooth([
			[x + 0.5, v.y - v.h * 0.35],
			[x - 1.8 - v.h * 0.3, v.y + v.h * 0.15],
			[x - 2 - v.h * 0.3, v.y + v.h * 0.6],
			[x + 0.5, v.y + v.h * 0.35],
		]);
		c.mid("skeleton", v.name, join(bodyD, spinous));
	}
	S("Sacrum", [
		[-4, 78.5],
		[-1.5, 79],
		[-2.5, 84],
		[-5.5, 89.5],
		[-7.5, 90],
		[-7, 85],
		[-5.8, 80],
	]);
	S("Coccyx", [
		[-7.5, 90.3],
		[-6.4, 90.6],
		[-7.2, 93],
		[-8, 92.6],
	]);
	// Scapula behind the ribs, then ribs, sternum, clavicle.
	R(
		"Scapula",
		smooth([
			[-3.5, 29.6],
			[-1.2, 30.2],
			[-2.2, 33.2],
			[-5.2, 47],
			[-6.6, 46.6],
			[-7, 36],
			[-6.4, 31.4],
		]),
	);
	for (let i = 0; i < 12; i++) {
		const yv = ribLevel(i);
		const x0 = spineX(yv) + 0.5;
		const front =
			i < 7 ? (RIB_FRONT_END[i] as Point)[1] : yv + 9 - (i - 7) * 1.5;
		const reach =
			i < 7 ? 8.6 - i * 0.1 : i < 10 ? 6 - (i - 7) * 2 : -1 - (i - 10) * 2;
		const line: Point[] = [
			[x0, yv],
			[x0 + (reach - x0) * 0.35, yv + (front - yv) * 0.3 + 1],
			[x0 + (reach - x0) * 0.75, yv + (front - yv) * 0.75 + 1],
			[reach, front],
		];
		R(`${ord[i]} rib`, band(line, [1.1, 1, 0.9, 0.8]));
	}
	S("Sternum", [
		[6.8, 28.8],
		[8.6, 29.2],
		[9.4, 38],
		[9.4, 46],
		[8.6, 48.4],
		[8.2, 46],
		[7.8, 38],
	]);
	R(
		"Clavicle",
		band(
			[
				[6.4, 29],
				[3, 29.2],
				[0, 29.6],
				[-2.6, 29.8],
			],
			[1.3, 1.1, 1.1, 1.3],
		),
	);
	// Arm
	R("Humerus", longBone([-1.5, 32.5], [-3, 60], 1.9, 2.4, 1.7));
	R("Ulna", longBone([-3.8, 59.6], [-0.6, 84.6], 1.1, 1.5, 0.8));
	R("Radius", longBone([-2.2, 60.5], [0.8, 84.8], 1.1, 1, 1.4));
	R(
		"Carpal bone",
		smooth([
			[-1.2, 85.5],
			[1.8, 85.3],
			[2.2, 88.6],
			[-1, 89.2],
		]),
	);
	R(
		"Metacarpal bone",
		join(
			longBone([-0.4, 89.4], [0.2, 95.4], 1.6, 1, 0.9),
			longBone([1.9, 88.6], [3.3, 92.4], 0.7, 0.6, 0.6),
		),
	);
	R(
		"Phalanx of finger",
		join(
			longBone([0.2, 95.9], [0.5, 99.4], 1.3, 0.8, 0.7),
			longBone([0.5, 99.7], [0.8, 103.6], 1.1, 0.7, 0.5),
			longBone([3.4, 92.8], [3.8, 95.6], 0.6, 0.5, 0.5),
			longBone([3.85, 95.9], [4, 98], 0.5, 0.45, 0.4),
		),
	);
	// Pelvis and leg
	c.items.push({
		id: drawnId("Hip bone", "right"),
		layer: "skeleton",
		evenOdd: true,
		d: join(
			smooth([
				[-7, 73],
				[-2, 71.8],
				[3.6, 73.6],
				[5, 76.6],
				[3.6, 79],
				[4.3, 81.5],
				[3, 85.6],
				[3.8, 88],
				[5, 92.6],
				[4, 94.6],
				[0.5, 94],
				[-2, 97],
				[-4.4, 96.2],
				[-3.4, 92],
				[-2.2, 88],
				[-4.6, 84.6],
				[-7.4, 80.4],
				[-8, 76],
			]),
			ellipse([1.8, 92.6], 1.4, 1),
		),
	});
	R(
		"Femur",
		join(
			ellipse([1, 89], 2, 2),
			longBone([0.4, 90.6], [2, 129.5], 2.5, 2.4, 2.8),
		),
	);
	R(
		"Patella",
		smooth([
			[4.4, 125.4],
			[5.6, 126],
			[5.8, 129.6],
			[4.8, 130.4],
			[4, 128],
		]),
	);
	R("Fibula", longBone([-0.6, 132.6], [-2, 167.4], 0.8, 0.9, 1));
	R("Tibia", longBone([2.4, 131.5], [-0.2, 166], 2.3, 3, 1.8));
	R(
		"Tarsal bone",
		smooth([
			[-1.8, 166.2],
			[1, 166],
			[2.2, 167.8],
			[5.4, 168.6],
			[6.2, 170.4],
			[4, 172.4],
			[-1.2, 172.6],
			[-4.8, 172.8],
			[-5.6, 170.8],
			[-4.4, 168.4],
		]),
	);
	R(
		"Metatarsal bone",
		band(
			[
				[6, 169.8],
				[10, 171.6],
				[13.5, 173.4],
			],
			[1.8, 1.5, 1.3],
		),
	);
	R(
		"Phalanx of toe",
		band(
			[
				[13.8, 173.6],
				[16.4, 174.4],
				[18.6, 175],
			],
			[1.3, 1.1, 0.9],
		),
	);
}

// ---------------------------------------------------------------------------------------------
// Muscles

function musclesFront(c: Canvas) {
	const P = (name: string, pts: Point[]) =>
		c.pair("muscles", name, smooth(pts));
	P("Temporalis", [
		[-7.5, 5.5],
		[-8.4, 6.5],
		[-8.5, 10],
		[-7.8, 12.8],
		[-7.4, 9],
	]);
	P("Masseter", [
		[-6, 14.8],
		[-7.1, 14.4],
		[-7.3, 18.6],
		[-6.1, 20.6],
		[-5.2, 19.2],
	]);
	c.pair(
		"muscles",
		"Sternocleidomastoid",
		band(
			[
				[-6.4, 16.2],
				[-5.4, 21],
				[-3.6, 25.5],
				[-2, 28.8],
			],
			[1.4, 1.8, 1.6, 1.2],
		),
	);
	P("Trapezius", [
		[-4.6, 21.4],
		[-5.6, 25],
		[-15, 28.6],
		[-13.2, 29.6],
		[-4.2, 27.4],
	]);
	P("Pectoralis major", [
		[-2.2, 29.6],
		[-14, 30],
		[-17, 35],
		[-15.6, 37.2],
		[-11, 41],
		[-6, 42.6],
		[-2.6, 42],
	]);
	P("Serratus anterior", [
		[-12.6, 40.2],
		[-14.4, 39],
		[-15, 45],
		[-13.8, 52],
		[-12, 52],
		[-12.6, 46],
	]);
	P("Rectus abdominis", [
		[-0.5, 45],
		[-6, 45.2],
		[-6.5, 55],
		[-5, 72],
		[-3, 86],
		[-0.5, 87],
	]);
	P("External oblique", [
		[-6.6, 47],
		[-13.4, 47],
		[-14.4, 58],
		[-13.5, 72],
		[-10, 78],
		[-6.2, 74],
		[-6.6, 60],
	]);
	P("Deltoid", [
		[-14, 29],
		[-18.5, 29.5],
		[-21, 34],
		[-20.5, 42],
		[-19.5, 45],
		[-17.5, 40],
		[-15.5, 34],
	]);
	P("Brachialis", [
		[-21.2, 47.5],
		[-22, 52],
		[-21.2, 59],
		[-20.1, 57.6],
	]);
	P("Biceps brachii", [
		[-17.8, 37],
		[-19.8, 37],
		[-21, 47],
		[-20.6, 56],
		[-20, 60],
		[-19, 56],
		[-18.2, 47],
	]);
	P("Brachioradialis", [
		[-21.6, 52],
		[-22.8, 55],
		[-24, 65],
		[-25.5, 82],
		[-24.6, 82],
		[-22.2, 68],
		[-21, 60],
	]);
	P("Flexor carpi radialis", [
		[-21.2, 61],
		[-22.2, 62.6],
		[-24.2, 82],
		[-23.5, 82.4],
		[-21, 66],
	]);
	P("Flexor carpi ulnaris", [
		[-19.6, 60],
		[-20.6, 61],
		[-22.8, 84],
		[-22, 84],
		[-19.4, 66],
	]);
	P("Tensor fasciae latae", [
		[-13, 76],
		[-15, 78],
		[-15.2, 92],
		[-13.5, 95],
		[-12.5, 86],
	]);
	P("Adductor longus", [
		[-2.5, 91],
		[-5.5, 92],
		[-8.5, 110],
		[-7.6, 111],
		[-3.5, 95],
	]);
	c.pair(
		"muscles",
		"Gracilis",
		band(
			[
				[-1.8, 92],
				[-3.5, 108],
				[-5, 122],
				[-5.8, 129],
			],
			[1.6, 1.4, 1.1, 0.8],
		),
	);
	P("Vastus lateralis", [
		[-13.5, 95],
		[-15, 105],
		[-14, 120],
		[-11, 128],
		[-10, 125],
		[-12.5, 112],
	]);
	P("Vastus medialis", [
		[-7.5, 110],
		[-6, 118],
		[-6.2, 126],
		[-7.5, 128],
		[-9, 124],
		[-8.6, 116],
	]);
	P("Rectus femoris", [
		[-11, 92],
		[-13, 98],
		[-12.5, 115],
		[-9.5, 124],
		[-8, 123],
		[-9, 108],
		[-9.5, 98],
	]);
	c.pair(
		"muscles",
		"Sartorius",
		band(
			[
				[-12.6, 77],
				[-11, 90],
				[-8, 105],
				[-6, 120],
				[-6.2, 129],
			],
			[1.4, 1.6, 1.6, 1.4, 1.1],
		),
	);
	P("Gastrocnemius", [
		[-5.8, 134],
		[-5, 140],
		[-5.3, 150],
		[-6.2, 152],
		[-6.6, 140],
	]);
	P("Soleus", [
		[-5.8, 150],
		[-5.6, 158],
		[-6.4, 162],
		[-6.6, 152],
	]);
	P("Tibialis anterior", [
		[-9.5, 133],
		[-10.5, 137],
		[-9.6, 158],
		[-8.6, 165],
		[-8.6, 160],
		[-9, 140],
	]);
	P("Fibularis longus", [
		[-11, 134],
		[-11.8, 137],
		[-11.2, 155],
		[-10.5, 155],
		[-10.4, 140],
	]);
}

function musclesBack(c: Canvas) {
	const P = (name: string, pts: Point[]) =>
		c.pair("muscles", name, smooth(pts));
	P("Sternocleidomastoid", [
		[-5, 17],
		[-6.5, 18],
		[-6.4, 23],
		[-5.4, 22],
	]);
	P("External oblique", [
		[-13, 60],
		[-14.5, 62],
		[-14, 73],
		[-12.5, 75],
		[-12.8, 66],
	]);
	P("Latissimus dorsi", [
		[-0.2, 44],
		[-4, 42],
		[-12.5, 47],
		[-17, 42],
		[-16, 46],
		[-14.5, 55],
		[-13.5, 70],
		[-8, 75],
		[-2, 74],
		[-0.2, 60],
	]);
	P("Teres major", [
		[-11, 44],
		[-15.5, 40],
		[-17, 41.5],
		[-12.5, 47],
	]);
	P("Infraspinatus", [
		[-6, 37],
		[-14, 36],
		[-15.5, 38],
		[-11, 44],
		[-7, 41],
	]);
	P("Trapezius", [
		[-0.2, 18],
		[-3, 21],
		[-6, 25],
		[-15, 28.6],
		[-14, 31],
		[-8, 33],
		[-4, 40],
		[-0.2, 57],
	]);
	P("Deltoid", [
		[-14, 29],
		[-18.5, 29.5],
		[-21, 34],
		[-20.5, 42],
		[-19.5, 45],
		[-17.5, 40],
		[-15.5, 34],
	]);
	P("Triceps brachii", [
		[-17.5, 36],
		[-21, 37],
		[-21.5, 50],
		[-20.5, 59],
		[-18.7, 58],
		[-17.8, 48],
	]);
	P("Brachioradialis", [
		[-21.3, 54],
		[-22.8, 57],
		[-24, 70],
		[-23, 70],
		[-21.5, 62],
	]);
	P("Extensor carpi radialis longus", [
		[-22, 58],
		[-23.2, 61],
		[-24.8, 80],
		[-24, 80],
		[-22.3, 66],
	]);
	P("Extensor digitorum", [
		[-21, 61],
		[-22.2, 63],
		[-23.8, 84],
		[-23, 84],
		[-20.8, 68],
	]);
	P("Flexor carpi ulnaris", [
		[-19.8, 61],
		[-20.6, 62],
		[-22.6, 84],
		[-21.9, 84],
		[-19.6, 68],
	]);
	P("Gluteus medius", [
		[-4, 77],
		[-13.5, 73],
		[-15, 79],
		[-13, 86],
		[-8, 83],
	]);
	P("Gluteus maximus", [
		[-1, 81],
		[-8, 79],
		[-13.5, 86],
		[-14, 95],
		[-11, 100],
		[-5, 99],
		[-1, 95],
	]);
	c.pair(
		"muscles",
		"Gracilis",
		band(
			[
				[-2.5, 98],
				[-3.8, 110],
				[-5.2, 122],
				[-5.8, 129],
			],
			[1.4, 1.3, 1.1, 0.8],
		),
	);
	P("Semitendinosus", [
		[-6, 99],
		[-9.5, 101],
		[-9, 118],
		[-6.5, 129],
		[-5.3, 127],
		[-6.5, 112],
	]);
	P("Biceps femoris", [
		[-11.5, 100],
		[-13.5, 104],
		[-12.5, 120],
		[-11, 130],
		[-10, 129],
		[-10.5, 112],
	]);
	P("Soleus", [
		[-11, 146],
		[-11.6, 152],
		[-9.5, 162],
		[-7.8, 163],
		[-5.5, 156],
		[-5, 148],
	]);
	P("Gastrocnemius", [
		[-5.5, 128],
		[-8.5, 129],
		[-12, 136],
		[-11.5, 148],
		[-9, 153],
		[-7, 153],
		[-5, 146],
		[-4.8, 136],
	]);
}

function musclesSide(c: Canvas) {
	const R = (name: string, pts: Point[]) =>
		c.one("muscles", name, "right", smooth(pts));
	R("Temporalis", [
		[4, 4],
		[-4, 3],
		[-6, 8],
		[-3, 12],
		[2.5, 13],
		[5, 10],
	]);
	R("Masseter", [
		[2, 14],
		[5.5, 14],
		[6, 19.5],
		[3, 20.5],
		[1.5, 18],
	]);
	c.one(
		"muscles",
		"Sternocleidomastoid",
		"right",
		band(
			[
				[-3, 15],
				[0, 20],
				[3.5, 25.5],
				[6.5, 29],
			],
			[1.6, 2, 1.8, 1.2],
		),
	);
	R("Trapezius", [
		[-4, 18],
		[-6, 22],
		[-7, 30],
		[-4, 31],
		[-2, 28],
		[-1, 25],
	]);
	R("Latissimus dorsi", [
		[-7, 44],
		[-4, 42],
		[-1, 50],
		[-3, 62],
		[-7, 72],
		[-8.5, 60],
	]);
	R("Serratus anterior", [
		[-3, 40],
		[2, 38],
		[5, 44],
		[3, 51],
		[-2, 50],
	]);
	R("External oblique", [
		[2, 48],
		[7, 48],
		[8, 62],
		[5.5, 76],
		[-3, 74],
		[-6, 66],
		[-2, 56],
	]);
	R("Rectus abdominis", [
		[7.5, 46],
		[9, 48],
		[9.5, 60],
		[8, 78],
		[6, 86],
		[5.5, 82],
		[7, 62],
	]);
	R("Pectoralis major", [
		[5, 30],
		[8.5, 32],
		[8.5, 38],
		[5, 41],
		[2.5, 36],
	]);
	R("Deltoid", [
		[-5, 30],
		[2, 29],
		[3.5, 33],
		[1, 43],
		[-1, 44],
		[-4.5, 38],
	]);
	R("Triceps brachii", [
		[-3.5, 36],
		[-1.5, 38],
		[-2, 55],
		[-4, 62],
		[-5.2, 58],
		[-4.8, 44],
	]);
	R("Biceps brachii", [
		[0, 38],
		[2, 40],
		[1.5, 53],
		[0, 60],
		[-1, 56],
		[-0.5, 44],
	]);
	R("Brachialis", [
		[-0.5, 50],
		[1, 53],
		[0, 60],
		[-1.5, 58],
	]);
	R("Extensor carpi radialis longus", [
		[-1.5, 58],
		[-0.2, 62],
		[0.3, 80],
		[-0.4, 80],
		[-1.8, 66],
	]);
	R("Brachioradialis", [
		[0, 52],
		[1.8, 58],
		[2.2, 70],
		[1.3, 84],
		[0.2, 84],
		[0.3, 68],
		[-0.8, 60],
	]);
	R("Gluteus medius", [
		[-6, 74],
		[2, 72],
		[4, 76],
		[0, 84],
		[-5, 83],
	]);
	R("Gluteus maximus", [
		[-7, 80],
		[-2, 82],
		[-1, 92],
		[-4, 100],
		[-8, 97],
		[-9, 88],
	]);
	R("Tensor fasciae latae", [
		[2.5, 76],
		[5, 78],
		[4.5, 90],
		[2.5, 94],
		[1, 86],
	]);
	R("Vastus lateralis", [
		[0.5, 95],
		[3.5, 97],
		[4, 112],
		[3, 127],
		[0, 128],
		[-2, 115],
		[-1, 103],
	]);
	R("Biceps femoris", [
		[-4, 100],
		[-1.5, 101],
		[-1.5, 118],
		[-1, 131],
		[-2.5, 131],
		[-4.5, 118],
	]);
	R("Rectus femoris", [
		[4, 92],
		[6.5, 100],
		[6, 118],
		[4.5, 126],
		[3, 124],
		[3.5, 108],
	]);
	c.one(
		"muscles",
		"Sartorius",
		"right",
		band(
			[
				[5, 77],
				[4, 95],
				[1, 115],
				[-1, 129],
			],
			[1.3, 1.5, 1.4, 1.1],
		),
	);
	R("Soleus", [
		[-3.5, 146],
		[-1, 148],
		[-1, 160],
		[-2, 165],
		[-3.4, 160],
	]);
	R("Gastrocnemius", [
		[-1, 130],
		[1, 133],
		[0, 148],
		[-1.5, 155],
		[-3.8, 148],
		[-4.2, 138],
		[-2.5, 132],
	]);
	R("Fibularis longus", [
		[1.2, 135],
		[2.6, 137],
		[1, 158],
		[-0.5, 164],
		[-0.8, 158],
		[0.2, 142],
	]);
	R("Tibialis anterior", [
		[3.5, 133],
		[5, 136],
		[3.5, 158],
		[2, 165],
		[1.6, 160],
		[2.8, 140],
	]);
}

// ---------------------------------------------------------------------------------------------
// Organs (asymmetric, so drawn per side in front coordinates)

function organsFront(c: Canvas) {
	const M = (name: string, pts: Point[]) => c.mid("organs", name, smooth(pts));
	c.mid("organs", "Brain", ellipse([0, 8.5], 7, 7.3));
	M("Thyroid gland", [
		[-2.2, 23.5],
		[-0.8, 24.6],
		[0, 24.4],
		[0.8, 24.6],
		[2.2, 23.5],
		[2.4, 25.8],
		[0.8, 26],
		[0, 25.6],
		[-0.8, 26],
		[-2.4, 25.8],
	]);
	c.mid(
		"organs",
		"Trachea",
		join(
			band(
				[
					[0, 22],
					[0, 29],
					[0, 36],
				],
				1.6,
			),
			band(
				[
					[0, 35.4],
					[-2, 37],
					[-3.6, 38.6],
				],
				1.1,
			),
			band(
				[
					[0, 35.4],
					[2, 37],
					[3.6, 38.6],
				],
				1.1,
			),
		),
	);
	M("Right lung", [
		[-2, 31],
		[-6, 30],
		[-11, 34],
		[-13, 44],
		[-13.5, 52],
		[-9, 51],
		[-4, 50],
		[-2.5, 44],
	]);
	M("Left lung", [
		[2, 31],
		[6, 30],
		[11, 34],
		[13, 44],
		[13.5, 53],
		[9, 52],
		[6, 48],
		[3, 44],
		[5, 41],
		[3, 38],
	]);
	M("Heart", [
		[-3, 39],
		[1, 37],
		[5, 40],
		[6.5, 45],
		[3, 49],
		[-1, 48],
		[-3.5, 45],
	]);
	M("Liver", [
		[-13, 50],
		[-6, 48],
		[2, 49],
		[6, 51],
		[4, 54],
		[-4, 57],
		[-12, 60],
		[-14, 55],
	]);
	M("Stomach", [
		[2, 52],
		[5, 50],
		[9, 52],
		[11, 56],
		[9, 62],
		[5, 64],
		[2, 62],
		[4, 58],
		[3, 55],
	]);
	M("Gallbladder", [
		[-6, 57],
		[-4.8, 56.8],
		[-4.6, 60],
		[-5.8, 60.5],
	]);
	M("Pancreas", [
		[-4, 60],
		[2, 59.5],
		[8, 58],
		[10, 58.5],
		[8, 60.5],
		[2, 61.5],
		[-3, 63],
		[-4.5, 62],
	]);
	c.mid(
		"organs",
		"Large intestine",
		band(
			[
				[-9.6, 80],
				[-11, 72],
				[-11, 64],
				[-8, 62.4],
				[0, 63],
				[8, 62],
				[11, 64],
				[11.4, 72],
				[10.6, 80],
				[6, 84],
				[2, 86],
			],
			2.4,
			0.9,
		),
	);
	M("Small intestine", [
		[-8, 66],
		[0, 65],
		[8, 66],
		[9, 74],
		[6, 82],
		[-1, 84],
		[-7, 81],
		[-9, 74],
	]);
	M("Urinary bladder", [
		[-3.5, 86],
		[3.5, 86],
		[4, 89.5],
		[0, 91],
		[-4, 89.5],
	]);
}

function organsBack(c: Canvas) {
	// Front coordinates (the view is mirrored afterwards), so the body's right is still negative x.
	const M = (name: string, pts: Point[]) => c.mid("organs", name, smooth(pts));
	c.mid("organs", "Brain", ellipse([0, 8.5], 7, 7.3));
	M("Right lung", [
		[-2, 31],
		[-6, 30],
		[-11, 34],
		[-13, 44],
		[-13.5, 54],
		[-9, 55],
		[-3, 52],
		[-2, 44],
	]);
	M("Left lung", [
		[2, 31],
		[6, 30],
		[11, 34],
		[13, 44],
		[13.5, 55],
		[9, 56],
		[3, 53],
		[2, 44],
	]);
	M("Liver", [
		[-13, 55],
		[-6, 54],
		[-2, 56],
		[-6, 60],
		[-12, 61],
		[-14, 58],
	]);
	M("Spleen", [
		[9, 55],
		[12, 56],
		[12.5, 61],
		[10.5, 63],
		[8.8, 59],
	]);
	M("Right kidney", [
		[-4, 60],
		[-7, 59.6],
		[-8, 64],
		[-7, 69],
		[-4.4, 69],
		[-4.8, 66],
		[-4, 64.5],
	]);
	M("Left kidney", [
		[4, 58],
		[7, 57.6],
		[8, 62],
		[7, 67],
		[4.4, 67],
		[4.8, 64],
		[4, 62.5],
	]);
	c.mid(
		"organs",
		"Large intestine",
		band(
			[
				[-10, 80],
				[-11, 70],
				[-10.5, 64],
				[-9, 63],
				[9, 63],
				[11, 65],
				[11.4, 72],
				[10.6, 80],
			],
			2.2,
			0.9,
		),
	);
}

function organsSide(c: Canvas) {
	const M = (name: string, pts: Point[]) => c.mid("organs", name, smooth(pts));
	c.mid("organs", "Brain", ellipse([-0.5, 7.5], 8.6, 6.6));
	c.mid(
		"organs",
		"Esophagus",
		band(
			[
				[1.5, 22.5],
				[0, 32],
				[-0.8, 42],
				[0.5, 52],
			],
			1.2,
		),
	);
	c.mid(
		"organs",
		"Trachea",
		band(
			[
				[4.4, 22],
				[3.8, 29],
				[2.6, 36],
			],
			1.6,
		),
	);
	M("Thyroid gland", [
		[4.6, 23.6],
		[6, 24],
		[5.8, 26.2],
		[4.4, 25.8],
	]);
	M("Right lung", [
		[-6, 32],
		[2, 31],
		[7, 34],
		[7.5, 44],
		[6, 50],
		[0, 52],
		[-6, 54],
		[-7, 44],
	]);
	M("Heart", [
		[1, 38],
		[7, 38],
		[8, 44],
		[5, 49],
		[1, 46],
	]);
	M("Liver", [
		[-4, 52],
		[4, 50],
		[8, 53],
		[7, 58],
		[0, 60],
		[-5, 58],
	]);
	M("Gallbladder", [
		[5.6, 56.4],
		[7, 56.6],
		[7, 58.8],
		[5.8, 59],
	]);
	M("Right kidney", [
		[-2.5, 58.5],
		[-0.8, 60],
		[-1, 66],
		[-2.6, 68],
		[-4.4, 66],
		[-4.2, 60],
	]);
	c.mid(
		"organs",
		"Large intestine",
		band(
			[
				[3, 80],
				[1, 72],
				[2, 64],
				[6, 62.5],
			],
			2.4,
		),
	);
	M("Small intestine", [
		[-1, 64],
		[6, 64],
		[8, 74],
		[5, 82],
		[-1, 80],
	]);
	M("Urinary bladder", [
		[3, 86],
		[6, 86.2],
		[6.4, 90],
		[4, 91],
		[2.6, 89],
	]);
}

// ---------------------------------------------------------------------------------------------
// Skin: the body's outline

const SKIN_FRONT_RIGHT: Point[] = [
	[0, -0.9],
	[-4.5, 0.3],
	[-8, 3],
	[-9, 9],
	[-8.5, 15],
	[-7, 20],
	[-5.5, 23],
	[-5.5, 26],
	[-9, 28],
	[-15, 29.5],
	[-18.5, 31.5],
	[-20.5, 36],
	[-21.5, 45],
	[-22.5, 55],
	[-24, 63],
	[-26, 74],
	[-27.5, 84],
	[-29, 90],
	[-30.2, 97],
	[-29.2, 103.4],
	[-27.2, 105],
	[-25.4, 99],
	[-24.3, 92],
	[-22.5, 86],
	[-21, 72],
	[-19.6, 61],
	[-18.4, 52],
	[-17, 43],
	[-15.2, 40],
	[-14.5, 47],
	[-13.5, 58],
	[-14.5, 70],
	[-15.5, 80],
	[-15.5, 90],
	[-14.5, 100],
	[-13, 112],
	[-11.8, 125],
	[-11.5, 131],
	[-11.5, 140],
	[-10.6, 152],
	[-9.5, 163],
	[-10, 170],
	[-11, 173.5],
	[-9, 176.4],
	[-4.5, 176.4],
	[-4.5, 170],
	[-5, 163],
	[-4.6, 150],
	[-4.5, 135],
	[-4.8, 126],
	[-3.5, 112],
	[-2.2, 100],
	[-0.8, 94],
];

function skinFront(c: Canvas) {
	const left = SKIN_FRONT_RIGHT.slice(1)
		.reverse()
		.map(([x, y]) => [-x, y] as Point);
	c.mid("skin", "Skin", smooth([...SKIN_FRONT_RIGHT, [0, 93.4], ...left], 0.9));
}

function skinSide(c: Canvas) {
	const body: Point[] = [
		[-1, -0.9],
		[3, -0.6],
		[7, 1.5],
		[9.4, 6],
		[9.8, 9.5],
		[11, 12.8],
		[10, 14.6],
		[10.4, 16],
		[9.8, 17.6],
		[10, 20],
		[8.6, 22.4],
		[5.6, 23.3],
		[5.4, 26],
		[7.5, 29.5],
		[9.6, 33],
		[10.4, 38],
		[10.2, 43],
		[9.2, 47],
		[9.4, 52],
		[10.4, 60],
		[10.4, 68],
		[9.2, 76],
		[7.4, 82],
		[6.6, 88],
		[7.4, 95],
		[7.6, 108],
		[6.4, 120],
		[5.8, 127],
		[5.6, 131],
		[4.6, 138],
		[4, 150],
		[3.4, 160],
		[3, 166],
		[5, 169],
		[12, 172],
		[18, 173.6],
		[19.6, 175],
		[18.6, 176.4],
		[-4.6, 176.4],
		[-6, 174.6],
		[-5.2, 170],
		[-3.8, 166],
		[-3.4, 158],
		[-5, 146],
		[-5.6, 138],
		[-4, 131],
		[-4.8, 124],
		[-6, 110],
		[-7.4, 100],
		[-9.6, 94],
		[-10.4, 88],
		[-9.6, 82],
		[-7.6, 76],
		[-6.4, 70],
		[-7.6, 62],
		[-9.4, 52],
		[-10, 44],
		[-9.6, 36],
		[-8.4, 30],
		[-6.4, 26],
		[-5.8, 23],
		[-7.6, 20],
		[-9.6, 16],
		[-10.4, 10],
		[-8.6, 4],
		[-5, 0.2],
	];
	const arm: Point[] = [
		[-4.6, 30],
		[1.8, 30],
		[2.6, 40],
		[2.2, 52],
		[2, 60],
		[2.4, 72],
		[2.6, 84],
		[3.4, 88],
		[4.2, 95],
		[3.2, 103.6],
		[1.4, 104.6],
		[-0.8, 98],
		[-1.6, 90],
		[-2.2, 84],
		[-4, 72],
		[-5, 62],
		[-6, 50],
		[-6.2, 38],
	];
	c.mid("skin", "Skin", join(smooth(body, 0.9), smooth(arm, 0.9)));
}

// ---------------------------------------------------------------------------------------------

const cache = new Map<View, Drawn[]>();

/** Every shape in a view, in drawing order within each layer. */
export function drawings(view: View): Drawn[] {
	const hit = cache.get(view);
	if (hit) return hit;
	let items: Drawn[];
	if (view === "side") {
		const c = new Canvas(false);
		skeletonSide(c);
		musclesSide(c);
		organsSide(c);
		skinSide(c);
		items = c.items;
	} else {
		const back = view === "back";
		const c = new Canvas(true);
		skeletonFrontBack(c, back);
		if (back) musclesBack(c);
		else musclesFront(c);
		if (back) organsBack(c);
		else organsFront(c);
		skinFront(c);
		items = back ? mirrorAll(c.items) : c.items;
	}
	cache.set(view, items);
	return items;
}

/** Which skeleton segment a drawn bone belongs to. */
export const segmentOf = (() => {
	const map = new Map<string, string>();
	for (const s of SEGMENTS) for (const b of s.bones) map.set(b, s.id);
	return (id: string) => map.get(id) ?? null;
})();

/** Segments drawn behind their parent's bones in a view (the shoulder girdle behind the ribs in front). */
export function behindParent(segment: string, view: View): boolean {
	if (view === "side") return segment.startsWith("shoulder-girdle");
	if (view === "front")
		return segment.startsWith("shoulder-girdle") || segment.startsWith("thigh");
	return segment.startsWith("thigh");
}
