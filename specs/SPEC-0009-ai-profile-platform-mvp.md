# SPEC-0009: AI Profile Platform MVP

## Repo

[dijonkitchen/exp](https://github.com/dijonkitchen/exp), a scaffolded Django app (`aiprofile`) with a C4 container diagram: workers sign in with GitHub, and an LLM proposes profile patches from a verified evidence log.
See [Project Repos](../docs/decisions/2026-09-30-project-repos.md).

## Functional requirements

Take the scaffold to a working end-to-end loop for one worker.

- Sign in with GitHub OAuth (django-allauth) creates the user and an empty, hidden profile.
- The worker triggers a refresh; a Celery task ingests public GitHub data (repos, languages, contributions) into `EvidenceItem`s, deduplicated by source and key.
- The synthesizer proposes a `ProfilePatchSchema` in which every claim cites the evidence keys behind it; a claim without evidence is rejected before it is shown.
- The worker sees each patch on the dashboard with its cited evidence, and accepts or rejects it; only accepted patches change the profile.
- The worker sets visibility: hidden, searchable, or public; a public profile has its own page.
- The synthesizer's model is chosen by `provider/model` ID through the model roles from [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md) instead of a hard-coded setting.

Recruiter search, LinkedIn ingestion, and embeddings-based matching are out of scope for this spec.

## Non-functional requirements

- Honest: no claim reaches a profile without cited evidence and the worker's acceptance.
- Private: profiles start hidden; only public GitHub data is ingested; secrets live in `.env`, never in the repo.
- Reproducible: one documented command starts Postgres (with pgvector), Redis, the web app, and the worker locally.
- Tested: the ingestor, the citation check, and the accept flow have tests that run without network or model calls.

## Definition of done

1. A new user signs in with GitHub, triggers a refresh, and accepts a patch that appears on their public page.
2. A patch whose claim cites no evidence is rejected in tests.
3. The README documents setup and the local run command, and CI runs the tests and migrations check.
4. An ADR in the repo records the stack and the evidence-citation rule.
