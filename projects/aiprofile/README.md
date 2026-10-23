# aiprofile

Sign in with GitHub; the app pulls your public repos, languages, and recent commits as evidence, and a model proposes profile claims that each cite it.
You accept or reject each patch, and only accepted claims show on your profile, hidden by default and public on its own page when you choose.

```sh
export GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=...   # GitHub OAuth app, callback /accounts/github/login/callback/
export OPENROUTER_API_KEY=...
make run                                                # http://localhost:8000
```

See the [stack decision](docs/decisions/2026-10-23-aiprofile-stack.md).
