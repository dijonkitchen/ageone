# SPEC-0010: AI Profile Platform MVP

Restarts [dijonkitchen/exp](https://github.com/dijonkitchen/exp) in this folder, `projects/aiprofile/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/aiprofile/docs/decisions/`.

An AI-maintained work profile: a worker signs in with GitHub, and an LLM proposes profile changes from a log of verified evidence, each citing its sources.

## Functional requirements

- Sign in with GitHub creates the user and an empty, hidden profile.
- The worker triggers a refresh; a background job pulls public GitHub data (repos, languages, contributions) into evidence items, deduplicated by source and key.
- A synthesizer proposes patches in which every claim cites the evidence behind it; a claim without evidence is dropped before it's shown.
  It picks its model by role through the model roles config from [SPEC-0002](../../../specs/SPEC-0002-vendor-neutral-ai-harness.md), never a model ID in code.
  Evidence text is untrusted and handled with [`skills/prompt-injection-prevention`](../../../specs/SPEC-0016-prompt-injection-skill.md).
- The worker sees each patch with its evidence and accepts or rejects it; only accepted patches change the profile.
- Visibility: hidden, searchable, or public; a public profile has its own page.

Recruiter search, other sources such as LinkedIn, and embedding-based matching are later specs.

## Non-functional requirements

- Honest: no claim reaches a profile without cited evidence and the worker's acceptance.
- Private: profiles start hidden; only public GitHub data is read; secrets stay out of the repo.
- One documented command runs the app, its database, and its job worker locally.
- Tests of ingest, the citation check, and the accept flow run without network or model calls.

## Definition of done

1. The first decision record in `projects/aiprofile/docs/decisions/` chooses the stack (old: Django, allauth, htmx, Celery, Redis, Postgres with pgvector, Pydantic AI).
2. `projects/aiprofile/` is set up by `make`, and its CI job passes on `main`.
3. A new user signs in with GitHub, triggers a refresh, and accepts a patch that appears on their public page.
4. A patch claim with no cited evidence is dropped, shown by a test.
5. An eval of the synthesizer on fixed evidence runs through the SPEC-0002 runner.
