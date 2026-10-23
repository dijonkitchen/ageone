# Decision Record 2026-10-23: aiprofile Stack

## Status timeline

2026-10-23: Proposed by Claude, implementing [SPEC-2026-09-30-aiprofile-mvp](../../specs/SPEC-2026-09-30-aiprofile-mvp.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-aiprofile-mvp.md): GitHub sign-in, evidence ingest from public GitHub data, a synthesizer whose every claim cites evidence, accept or reject by the worker, and a public page.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
One command runs the app, its database, and its job worker.
Tests need no network and no model.

### Nice to haves

#### Functional

Other evidence sources are one more function that returns evidence items.

#### Non-functional

Moves to Postgres by changing `DATABASES` only.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Recruiter search, LinkedIn, and embedding matching (later specs); a front-end build.

#### Non-functional

Celery, Redis, and Postgres before a second worker or a second user needs them.

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo's stack (Django, allauth, htmx, Celery, Redis, Postgres with pgvector, Pydantic AI) holds in part:

- **Keeps** Django and django-allauth: sessions, CSRF, admin-grade ORM, and the GitHub OAuth flow are solved problems, and allauth creates the user on first sign-in, which the signal in `signals.py` turns into an empty, hidden profile.
- **Drops** Celery and Redis for a `Job` table drained by `manage.py runworker`: one process, no broker, and the queue is inspectable in the same database. Revisit at a second worker.
- **Drops** Postgres and pgvector for SQLite, since no embeddings exist until the recruiter-matching spec; the ORM keeps the move cheap.
- **Drops** htmx and Pydantic AI: server-rendered forms are enough for accept, reject, and refresh, and the model call is one HTTP request whose reply is checked by plain code.
- **Model**: `synth.py` reads the `default` role from the root [`harness/models.json`](../../../../harness/models.json) and calls OpenRouter with its routing settings; no model ID is in code.
- **Honesty rule**: `synth.parse_claims` drops any claim that is malformed, over 300 characters, or cites no evidence or an id that is not in this user's evidence. Only a pending patch the worker accepts shows on the profile. A worker can decide only on their own patches.
- **Untrusted evidence**: repo descriptions are written by anyone. The model call has no tools, evidence is length-capped and fenced as data, and the reply is accepted only as the narrow claims shape. The shared [prompt injection skill](../../../../specs/SPEC-2026-09-30-prompt-injection-skill.md) is not on `main` yet, so this applies its approach by hand and should switch to the library when it lands. A hostile description can still skew a claim's wording; the worker reads every claim and its evidence before accepting.

### High-level C4(context/container/component/code) diagram

```text
worker ─> Django (urls, views) ─> SQLite: Profile, Evidence, Patch, Claim, Job
GitHub ─> allauth sign-in ─> User ─(signal)─> hidden Profile
runworker ─> jobs.run_job ─> github.ingest ─> GitHub public REST API
                          └─> synth.synthesize ─> OpenRouter ─> parse_claims (drops uncited) ─> pending Patch
```

### Choices and Tradeoffs/Risks

- Evidence cited by any earlier patch, accepted or rejected, is not offered again, so a rejection is final until the evidence changes.
- Only the first 100 repos and 100 public events are read: enough for a profile, not a full history.
- Forks are skipped, since they are not the worker's work.
- `searchable` is stored but does nothing until recruiter search exists.

### Dependencies

Django, django-allauth, requests; Ruff, mypy, django-stubs, pytest, and pytest-django for development.

### Interfaces

- `make run` migrates, starts the worker, and serves on `localhost:8000`.
- `uv run python manage.py runworker [--once]` drains the queue.
- Environment: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (a GitHub OAuth app whose callback is `/accounts/github/login/callback/`), `OPENROUTER_API_KEY`, `AIPROFILE_SECRET_KEY` and `AIPROFILE_DEBUG=0` outside development, optional `AIPROFILE_DB`, `AIPROFILE_MODELS`.
- Eval: [`evals/cases/aiprofile-synthesize`](../../../../evals/cases/aiprofile-synthesize/case.json) sends the app's own prompt on fixed evidence through the harness runner; a test keeps the two identical.

## Key Results and retrospective feedback
