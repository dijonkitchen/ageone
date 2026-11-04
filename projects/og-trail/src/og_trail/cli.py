"""Terminal frontend. Renders a View as text and reads one line per input."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from .content import PROFESSIONS
from .engine import Game, InvalidInput
from .landmarks import LANDMARKS
from .state import View

Reader = Callable[[str], str]
Writer = Callable[[str], None]

BAR_WIDTH = 40
QUIT_WORDS = {"quit", "exit", "q"}


def progress_bar(miles: int, total: int) -> str:
    cells = [" "] * BAR_WIDTH
    for lm in LANDMARKS[1:-1]:
        cells[min(BAR_WIDTH - 1, lm.miles * BAR_WIDTH // total)] = "|"
    pos = min(BAR_WIDTH - 1, miles * BAR_WIDTH // total)
    for i in range(pos):
        if cells[i] == " ":
            cells[i] = "="
    cells[pos] = ">"
    return f"[{''.join(cells)}] {miles}/{total} mi"


def render(view: View, fresh_log: list[str]) -> str:
    st = view.status
    lines = ["", "=" * 60, f"  {view.title}", "=" * 60]
    if st and view.phase not in {"setup_name", "setup_profession", "setup_party"}:
        party = "  ".join(f"{p['name']}:{p['status']}" for p in st["party"])
        lines += [
            progress_bar(st["miles"], st["miles_total"]),
            f"Week {st['week']}  ${st['money']:,}  hustle:{st['hustle']}  budget:{st['budget']}",
            f"Next: {st['next_landmark']['name']} ({st['next_landmark']['miles']} mi)",
            party,
            "-" * 60,
        ]
    for entry in fresh_log:
        lines.append(f"  * {entry}")
    if fresh_log:
        lines.append("")
    lines.append(view.text)
    if view.input_type == "choice":
        lines.append("")
        lines += [f"  {i}) {c.label}" for i, c in enumerate(view.choices, 1)]
    return "\n".join(lines)


def _resolve(view: View, raw: str) -> str:
    raw = raw.strip()
    if view.input_type == "choice" and raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(view.choices):
            return view.choices[index].id
    return raw


def play(
    game: Game,
    read: Reader | None = None,
    write: Writer = print,
    save_path: Path | None = None,
) -> Game:
    read = read or input
    shown = len(game.state.log)
    while True:
        view = game.view()
        write(render(view, view.log[shown:]))
        shown = len(view.log)
        if view.input_type == "none":
            write("\nThanks for playing.")
            return game
        prompt = {"choice": "> ", "text": "> ", "number": "# "}[view.input_type]
        try:
            raw = read(prompt)
        except (EOFError, KeyboardInterrupt):
            write("\nSee you later.")
            return game
        if raw.strip().lower() in QUIT_WORDS:
            write("\nSee you later.")
            return game
        try:
            game.submit(_resolve(view, raw))
        except InvalidInput as exc:
            write(f"  ! {exc}")
            continue
        if save_path is not None:
            save_path.write_text(json.dumps(game.to_dict()))


def load_or_new(save_path: Path | None, seed: int | None) -> Game:
    if save_path is not None and save_path.exists():
        return Game.from_dict(json.loads(save_path.read_text()))
    return Game(seed=seed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="og-trail",
        description="The Oregon Trail, but for modern life. Runs in the terminal by default.",
    )
    parser.add_argument("--seed", type=int, default=None, help="seed for a reproducible run")
    parser.add_argument("--save", type=Path, default=None, help="autosave file; resumes if present")
    sub = parser.add_subparsers(dest="command")
    web_parser = sub.add_parser("web", help="serve the browser GUI instead")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8000)
    web_parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    batch = sub.add_parser("batch", help="play seeded games headless; one NDJSON line per game")
    batch.add_argument("--player", choices=["random", "rules", "llm"], default="rules")
    batch.add_argument("--games", type=int, default=20, help="seeded games per profession")
    batch.add_argument("--first-seed", type=int, default=0)
    batch.add_argument(
        "--profession",
        choices=["all", *(p.id for p in PROFESSIONS)],
        default="all",
    )
    batch.add_argument("--role", default="cheap", help="model role for the llm player")
    batch.add_argument("--out", type=Path, default=None, help="append here instead of stdout")
    return parser


def batch(args: argparse.Namespace, write: Writer = print) -> None:
    from .players import make_player, play_game

    professions = [p.id for p in PROFESSIONS] if args.profession == "all" else [args.profession]
    out = args.out.open("a") if args.out else None
    try:
        for profession in professions:
            for seed in range(args.first_seed, args.first_seed + args.games):
                player = make_player(args.player, seed=seed, role=args.role)
                record = play_game(player, seed, profession)
                if args.player == "llm":
                    record["model"] = getattr(player, "model", None)
                line = json.dumps(record)
                if out:
                    out.write(line + "\n")
                    out.flush()
                else:
                    write(line)
    finally:
        if out:
            out.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "web":
        from . import web

        web.serve(args.host, args.port, open_browser=not args.no_browser)
        return 0
    if args.command == "batch":
        batch(args)
        return 0
    game = load_or_new(args.save, args.seed)
    play(game, save_path=args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
