// Lessons and trials: the lesson text, a step-through visualization, the puzzle-mode trial, and the
// code-mode editor. Also the frame stepper the sandbox reuses.
import type { QuickJSWASMModule } from "quickjs-emscripten-core";
import type { PlayerCode } from "../core/sandbox";
import { grade } from "../core/sandbox";
import type { Concept, Frame, Puzzle } from "../core/types";

export function el<K extends keyof HTMLElementTagNameMap>(
	tag: K,
	props: Record<string, unknown> = {},
	...kids: (Node | string)[]
): HTMLElementTagNameMap[K] {
	const e = Object.assign(document.createElement(tag), props);
	e.append(...kids);
	return e;
}

/** A frame-by-frame player: caption, drawing, data structures, and step, play, and speed controls. */
export function stepper(frames: Frame[]): { node: HTMLElement; stop(): void } {
	let at = 0;
	let timer: number | undefined;
	const caption = el("p", { className: "caption" });
	const pre = el("pre", { className: "frame" });
	const data = el("ul", { className: "data" });
	const count = el("span", { className: "hint" });
	const play = el("button", { type: "button", textContent: "Play" });
	const speed = el("input", {
		type: "range",
		min: "1",
		max: "20",
		value: "4",
		title: "Speed (frames per second)",
	});
	speed.setAttribute("aria-label", "Speed, frames per second");
	const show = () => {
		const f = frames[at];
		if (!f) return;
		caption.textContent = f.caption;
		pre.textContent = f.lines.join("\n");
		data.replaceChildren(...f.data.map((d) => el("li", { textContent: d })));
		count.textContent = `${at + 1} / ${frames.length}`;
	};
	const go = (i: number) => {
		at = Math.max(0, Math.min(frames.length - 1, i));
		show();
	};
	const stop = () => {
		if (timer !== undefined) window.clearInterval(timer);
		timer = undefined;
		play.textContent = "Play";
	};
	const start = () => {
		stop();
		if (at >= frames.length - 1) go(0);
		play.textContent = "Pause";
		timer = window.setInterval(() => {
			if (at >= frames.length - 1) stop();
			else go(at + 1);
		}, 1000 / Number(speed.value));
	};
	play.addEventListener("click", () =>
		timer === undefined ? start() : stop(),
	);
	speed.addEventListener("input", () => {
		if (timer !== undefined) start();
	});
	const button = (text: string, label: string, fn: () => void) => {
		const b = el("button", { type: "button", textContent: text });
		b.setAttribute("aria-label", label);
		b.addEventListener("click", () => {
			stop();
			fn();
		});
		return b;
	};
	const controls = el(
		"div",
		{ className: "controls" },
		button("⏮", "First step", () => go(0)),
		button("◀", "Previous step", () => go(at - 1)),
		play,
		button("▶", "Next step", () => go(at + 1)),
		button("⏭", "Last step", () => go(frames.length - 1)),
		speed,
		count,
	);
	const node = el("div", {}, controls, caption, pre, data);
	node.addEventListener("keydown", (e) => {
		if (e.target instanceof HTMLInputElement) return;
		if (e.key === "ArrowRight") go(at + 1);
		else if (e.key === "ArrowLeft") go(at - 1);
		else return;
		e.preventDefault();
	});
	show();
	return { node, stop };
}

/** The puzzle-mode trial: one step at a time, checked against the reference's answer. */
function puzzleView(
	concept: Concept,
	onPass: (() => void) | null,
): HTMLElement {
	const box = el("div");
	const run = (seed: number) => {
		const p: Puzzle = concept.puzzle(seed);
		let i = 0;
		let mistakes = 0;
		const next = () => {
			const step = p.steps[i];
			if (!step) {
				const passed = mistakes <= p.slack;
				const again = el("button", {
					type: "button",
					textContent: "Try a new puzzle",
				});
				again.addEventListener("click", () => run(seed + 1));
				box.replaceChildren(
					el("p", {
						className: `verdict ${passed ? "right" : "wrong"}`,
						textContent: passed
							? `Passed, with ${mistakes} mistake${mistakes === 1 ? "" : "s"}.`
							: `${mistakes} mistakes: up to ${p.slack} are allowed. Try a fresh puzzle.`,
					}),
					again,
				);
				if (passed) onPass?.();
				if (passed && !onPass)
					box.append(
						el("p", {
							className: "hint",
							textContent:
								"Practice only: learn it at a shrine with its codex page.",
						}),
					);
				return;
			}
			const verdict = el("p", { className: "verdict", role: "status" });
			const choices = el("div", { className: "choices" });
			let wrongHere = false;
			step.choices.forEach((c, k) => {
				const b = el("button", {
					type: "button",
					textContent: `${k + 1}. ${c}`,
				});
				b.addEventListener("click", () => {
					if (k === step.answer) {
						b.dataset.state = "right";
						verdict.className = "verdict right";
						verdict.textContent = `Right. ${step.explain}`;
						for (const x of choices.querySelectorAll("button"))
							x.disabled = true;
						const on = el("button", {
							type: "button",
							textContent: i + 1 < p.steps.length ? "Next step" : "Finish",
						});
						on.addEventListener("click", () => {
							i++;
							next();
						});
						box.append(on);
						on.focus();
					} else if (!b.dataset.state) {
						b.dataset.state = "wrong";
						if (!wrongHere) mistakes++;
						wrongHere = true;
						verdict.className = "verdict wrong";
						verdict.textContent = `Not that one. ${step.explain}`;
					}
				});
				choices.append(b);
			});
			box.replaceChildren(
				el("p", {
					className: "hint",
					textContent: `Step ${i + 1} of ${p.steps.length} · mistakes ${mistakes} (up to ${p.slack} allowed)`,
				}),
				el("p", { textContent: step.prompt }),
				...(step.lines
					? [
							el("pre", {
								className: "frame",
								textContent: step.lines.join("\n"),
							}),
						]
					: []),
				choices,
				verdict,
			);
			choices.querySelector("button")?.focus();
		};
		box.replaceChildren(
			el("p", { textContent: p.intro }),
			el("p", {
				className: "hint",
				textContent:
					"Pick an answer with the mouse or the number keys. The game checks each step against the reference implementation.",
			}),
		);
		const begin = el("button", {
			type: "button",
			textContent: "Start the trial",
		});
		begin.addEventListener("click", next);
		box.append(begin);
	};
	box.addEventListener("keydown", (e) => {
		const n = Number(e.key);
		if (!(n >= 1 && n <= 9) || e.target instanceof HTMLTextAreaElement) return;
		const b = box.querySelectorAll<HTMLButtonElement>(".choices button")[n - 1];
		if (b && !b.disabled) {
			e.preventDefault();
			b.click();
		}
	});
	run(Math.floor(Math.random() * 1e9));
	return box;
}

export interface CodeHooks {
	qjs: QuickJSWASMModule | null;
	saved: string | undefined;
	/** Called with the passing source and its loaded code. */
	passed(source: string, code: PlayerCode): void;
}

/** The code-mode trial: write the function, run the suite in the sandbox. */
function codeView(
	concept: Concept,
	hooks: CodeHooks,
	onPass: (() => void) | null,
): HTMLElement {
	const trial = concept.code;
	if (!trial)
		return el("p", { textContent: "This concept has no code-mode trial yet." });
	if (!hooks.qjs)
		return el("p", {
			textContent: "The code sandbox is still loading; try again in a moment.",
		});
	const qjs = hooks.qjs;
	const editor = el("textarea", {
		value: hooks.saved ?? trial.starter,
		spellcheck: false,
	});
	editor.setAttribute("aria-label", `Your JavaScript for ${concept.name}`);
	editor.addEventListener("keydown", (e) => {
		if (e.key !== "Tab") return;
		e.preventDefault();
		editor.setRangeText(
			"  ",
			editor.selectionStart,
			editor.selectionEnd,
			"end",
		);
	});
	const results = el("ul", { className: "results" });
	const verdict = el("p", { className: "verdict", role: "status" });
	const runTests = el("button", {
		type: "button",
		textContent: "Run the tests",
	});
	runTests.addEventListener("click", () => {
		const g = grade(qjs, trial, editor.value);
		results.replaceChildren(
			...g.results.map((r) =>
				el("li", {
					className: r.error ? "no" : "ok",
					textContent: r.error ? `${r.name}: ${r.error}` : r.name,
				}),
			),
		);
		if (g.compileError) {
			verdict.className = "verdict wrong";
			verdict.textContent = `Your code didn't load: ${g.compileError}`;
		} else if (!g.passed || !g.code) {
			verdict.className = "verdict wrong";
			verdict.textContent = `${g.results.filter((r) => r.error).length} of ${g.results.length} tests failed.`;
		} else {
			verdict.className = "verdict right";
			verdict.textContent = `All ${g.results.length} tests pass in ${Math.round(g.ms)} ms. Your code now runs this part of the game; switch back to the reference in the codex any time.`;
			hooks.passed(editor.value, g.code);
			onPass?.();
		}
	});
	const reset = el("button", {
		type: "button",
		textContent: "Start over from the starter",
	});
	reset.addEventListener("click", () => {
		editor.value = trial.starter;
	});
	return el(
		"div",
		{},
		el("pre", { className: "frame", textContent: trial.docs }),
		el("p", {
			className: "hint",
			textContent:
				"Your code runs in a sandbox (QuickJS in WebAssembly): no network or storage, 250 ms per call, and a memory cap. If it ever fails in the game, the reference takes over and the run goes on.",
		}),
		editor,
		el("div", { className: "controls" }, runTests, reset),
		verdict,
		results,
	);
}

/** Fill the lesson dialog for a concept. `onPass` is null when this is review or practice only. */
export function lessonView(
	concept: Concept,
	code: CodeHooks,
	onPass: (() => void) | null,
): { node: HTMLElement; stop(): void } {
	const frames = stepper(
		concept.lesson.frames(Math.floor(Math.random() * 1e9)),
	);
	const lesson = el(
		"div",
		{},
		...concept.lesson.text.map((t) => el("p", { textContent: t })),
		el("h3", { textContent: "Step through it" }),
		frames.node,
		el(
			"p",
			{ className: "hint" },
			`Time ${concept.complexity.time}; space ${concept.complexity.space}. Read more: `,
			el("a", {
				href: concept.reading.url,
				textContent: concept.reading.title,
				target: "_blank",
				rel: "noopener",
			}),
		),
	);
	const body = el("div");
	const tabs = el("div", { className: "tabs", role: "group" });
	tabs.setAttribute("aria-label", "Lesson parts");
	const views: [string, () => HTMLElement][] = [
		["Lesson", () => lesson],
		["Trial: puzzle", () => puzzleView(concept, onPass)],
	];
	if (concept.code)
		views.push(["Trial: code", () => codeView(concept, code, onPass)]);
	const buttons = views.map(([name, make]) => {
		const b = el("button", { type: "button", textContent: name });
		b.addEventListener("click", () => {
			frames.stop();
			for (const x of buttons) x.setAttribute("aria-pressed", String(x === b));
			body.replaceChildren(make());
		});
		return b;
	});
	tabs.append(...buttons);
	buttons[0]?.setAttribute("aria-pressed", "true");
	body.append(lesson);
	for (const b of buttons.slice(1)) b.setAttribute("aria-pressed", "false");
	const intro = el("p", {
		className: "hint",
		textContent: onPass
			? `Unlocks: ${concept.unlocks} Pass either trial to learn it.`
			: `Unlocks: ${concept.unlocks}`,
	});
	return { node: el("div", {}, intro, tabs, body), stop: frames.stop };
}
