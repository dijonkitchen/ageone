// Sound effects synthesized with Web Audio: short oscillator sweeps and filtered noise bursts, no sound files.
// The context starts on the first key, touch, or click, as browsers require.

import type { EventType } from "./sim";

interface Voice {
	wave: OscillatorType | "noise";
	from: number; // Hz
	to: number;
	length: number; // seconds
	volume: number;
}

export const SOUNDS: Record<EventType | "select", Voice[]> = {
	hit: [
		{ wave: "noise", from: 1800, to: 400, length: 0.12, volume: 0.5 },
		{ wave: "square", from: 160, to: 60, length: 0.1, volume: 0.25 },
	],
	block: [{ wave: "triangle", from: 900, to: 700, length: 0.06, volume: 0.25 }],
	whoosh: [{ wave: "noise", from: 600, to: 2400, length: 0.08, volume: 0.12 }],
	special: [
		{ wave: "sawtooth", from: 220, to: 880, length: 0.25, volume: 0.18 },
		{ wave: "sine", from: 440, to: 1320, length: 0.25, volume: 0.15 },
	],
	ko: [
		{ wave: "square", from: 400, to: 40, length: 0.7, volume: 0.25 },
		{ wave: "noise", from: 1200, to: 100, length: 0.5, volume: 0.3 },
	],
	round: [
		{ wave: "square", from: 523, to: 523, length: 0.12, volume: 0.15 },
		{ wave: "square", from: 784, to: 784, length: 0.24, volume: 0.12 },
	],
	select: [{ wave: "square", from: 660, to: 990, length: 0.06, volume: 0.12 }],
};

export class Sfx {
	private ctx: AudioContext | null = null;
	private noise: AudioBuffer | null = null;
	muted = false;

	/** Call from a user gesture. */
	start(): void {
		if (this.ctx || typeof AudioContext === "undefined") return;
		this.ctx = new AudioContext();
		const length = this.ctx.sampleRate;
		this.noise = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
		const data = this.noise.getChannelData(0);
		let seed = 1;
		for (let i = 0; i < length; i++) {
			seed = (seed * 16807) % 2147483647;
			data[i] = (seed / 2147483647) * 2 - 1;
		}
	}

	play(name: keyof typeof SOUNDS): void {
		const ctx = this.ctx;
		if (!ctx || this.muted) return;
		const now = ctx.currentTime;
		for (const v of SOUNDS[name]) {
			const gain = ctx.createGain();
			gain.gain.setValueAtTime(v.volume, now);
			gain.gain.exponentialRampToValueAtTime(0.001, now + v.length);
			gain.connect(ctx.destination);
			if (v.wave === "noise") {
				const src = ctx.createBufferSource();
				src.buffer = this.noise;
				const filter = ctx.createBiquadFilter();
				filter.type = "bandpass";
				filter.frequency.setValueAtTime(v.from, now);
				filter.frequency.exponentialRampToValueAtTime(v.to, now + v.length);
				src.connect(filter).connect(gain);
				src.start(now, Math.random() * 0.5, v.length);
			} else {
				const osc = ctx.createOscillator();
				osc.type = v.wave;
				osc.frequency.setValueAtTime(v.from, now);
				osc.frequency.exponentialRampToValueAtTime(v.to, now + v.length);
				osc.connect(gain);
				osc.start(now);
				osc.stop(now + v.length);
			}
		}
	}
}
