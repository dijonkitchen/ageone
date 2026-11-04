# Projects

Each project lives in its own folder here, `projects/<slug>/`, with its code, specs, and decision records ([Projects in ageone](../docs/decisions/2026-09-30-projects-in-ageone.md)).
Its specs are ranked with every other spec in [`specs/PRIORITIES.md`](../specs/PRIORITIES.md).

## Starting a project's code

From the repo root, run `make new PROJECT=<slug>` for TypeScript or plain JavaScript with Bun, or `make new PROJECT=<slug> STACK=python` for Python with uv.
It copies [`_template/`](_template/) into `projects/<slug>/` (keeping any specs already there), fills in the names, and locks the dependencies.
The new project gets an `AGENTS.md` with `CLAUDE.md` symlinked to it, `specs/`, a stack decision record stub in `docs/decisions/`, and a `Makefile` whose `make check` lints, checks formatting, typechecks, and runs the tests.

## CI

The [Projects workflow](../.github/workflows/projects.yml) runs `make check` in each project or `skills/` folder that a pull request changes, and in all of them on `main`; a folder without a `Makefile` (specs only) is skipped.
[`changed`](changed) decides which, and [`new`](new) is what `make new` runs.
See [Project template](../docs/decisions/2026-10-04-project-template.md).
