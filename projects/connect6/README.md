# Connect6

Six in a row wins. Black opens with one stone; every turn after places two.
Restarted from [dijonkitchen/connect](https://github.com/dijonkitchen/connect) per [SPEC-2026-09-30-connect6-rebuild](specs/SPEC-2026-09-30-connect6-rebuild.md).

## Play

```sh
bun run dev     # http://localhost:3000; pick Human or any player for each side
bun run build   # static bundle in dist/ (no LLM player without the server)
```

The LLM player in the browser sends its turns to the local server's `/api/chat`, which uses the `cheap` role and `OPENROUTER_API_KEY` from the server's environment, so the key never reaches the page.
Without a key, the LLM side forfeits on its first turn.

## Players

- **random**: any empty points.
- **heuristic**: wins with one stone if it can, blocks a five, else takes the best line-potential cells.
- **mcts**: Monte Carlo tree search over whole turns (both stones as one move), with tactics from window counts: take a win this turn, block every window the opponent could fill next turn, then search the best pairs near the stones.
- **llm**: asks the model for a role in the root [`harness/models.json`](../../harness/models.json) (default `cheap`) through OpenRouter. A bad reply is shown back with the reason, up to three replies a turn, then the player forfeits.

## Tournament

```sh
bun run tournament --players mcts,heuristic --games 100 --seed 1
OPENROUTER_API_KEY=... bun run tournament --players llm,heuristic --games 4 --role cheap
```

Every pair of players meets over `--games` seeded games, swapping colours each game, and each game is one NDJSON line: `seed`, `black`, `white`, `winner` (`black`, `white`, or `draw`), `winnerPlayer`, `reason` (`six`, `draw`, or `forfeit`), `moves`, `ms`, `tokens` and `cost` per side, and `model` when an LLM plays.
With an LLM player it first prints the estimated cost from OpenRouter's price list.

[`results/2026-10-04-mcts-vs-heuristic.ndjson`](results/2026-10-04-mcts-vs-heuristic.ndjson): MCTS (300 playouts a turn) won 100 of 100 games against the heuristic player, 50 as each colour.
