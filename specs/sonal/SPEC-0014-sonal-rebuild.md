# SPEC-0014: Sonal Rebuild

Restarts [dijonkitchen/sonal](https://github.com/dijonkitchen/sonal) in `projects/sonal/`, per [Projects in ageone](../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `docs/decisions/sonal/`.

A tool that reads what people say about a link on social media and summarizes the reaction; the old repo got as far as fetching YouTube comments and scoring them with a word list.

## Functional requirements

- Paste a YouTube video URL; fetch its top-level comments through the YouTube Data API behind a source interface, so other platforms can be added later.
- Classify each comment's sentiment and themes with an LLM that picks its model by role through the model roles config from [SPEC-0002](../SPEC-0002-vendor-neutral-ai-harness.md), never a model ID in code, replacing the old word-list scoring; comments are untrusted and handled with [`skills/prompt-injection-prevention`](../SPEC-0016-prompt-injection-skill.md).
- A page showing the overall sentiment split, the main themes with example comments, and a short summary citing comments.
- Results are cached per video so a repeat visit doesn't refetch or reclassify.

## Non-functional requirements

- Tests use recorded API responses and a fake model; no network in tests.
- The API key lives in the environment, never the repo.
- Cheap: classification defaults to the `cheap` role, batched.

## Definition of done

1. The first decision record in `docs/decisions/sonal/` chooses the stack (old: Ruby on Rails, Hotwire, Faraday and the `yt` gem).
2. `projects/sonal/` is set up by `make`, and its CI job passes on `main`.
3. A real video URL produces the sentiment split, themes, and cited summary.
4. The classifier's accuracy on a small hand-labeled comment set beats the old word list, measured through the SPEC-0002 runner.
