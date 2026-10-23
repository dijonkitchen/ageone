# Sonal

Paste a YouTube video URL; get the comments' sentiment split, main themes with example comments, and a short summary citing comments.

```sh
export YOUTUBE_API_KEY=...      # YouTube Data API v3
export OPENROUTER_API_KEY=...
bun run src/cli.ts --serve      # http://localhost:3000
bun run src/cli.ts <url>        # the analysis as JSON
bun run src/eval.ts --append    # classifier accuracy vs the old word list
```

Results are cached per video in `.cache/`.
See the [stack decision](docs/decisions/2026-10-23-sonal-stack.md).
