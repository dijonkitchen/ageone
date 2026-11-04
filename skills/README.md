# Skills

Shared agent skills live here, one folder per skill: `skills/<name>/` with a `SKILL.md` and any code it needs ([Projects in ageone](../docs/decisions/2026-09-30-projects-in-ageone.md)).
A skill here is for more than one project; a skill only one project uses stays in that project's folder.

A skill with code gets a `Makefile` whose `make check` CI runs whenever its folder changes, like a project's ([projects/README.md](../projects/README.md#ci)).
