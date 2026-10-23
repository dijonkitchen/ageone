"""Pull public GitHub data into evidence items. Only public endpoints, no token."""

from collections.abc import Callable
from typing import Any

import requests

from .models import Evidence

API = "https://api.github.com"
Fetch = Callable[[str], Any]


def fetch_json(url: str) -> Any:
    response = requests.get(
        url, headers={"Accept": "application/vnd.github+json"}, timeout=20
    )
    response.raise_for_status()
    return response.json()


def evidence_items(login: str, fetch: Fetch = fetch_json) -> list[dict[str, str]]:
    """Repos, languages, and recent public contributions as (source, key, text, url) items."""
    repos = fetch(f"{API}/users/{login}/repos?per_page=100&type=owner")
    items: list[dict[str, str]] = []
    languages: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        language = repo.get("language") or ""
        if language:
            languages[language] = languages.get(language, 0) + 1
        description = repo.get("description") or "no description"
        items.append(
            {
                "source": "github-repo",
                "key": repo["full_name"],
                "text": f"Owns the public repository {repo['full_name']} ({language or 'no language'}): {description}",
                "url": repo["html_url"],
            }
        )
    for language, count in sorted(languages.items()):
        items.append(
            {
                "source": "github-language",
                "key": language,
                "text": f"Uses {language} in {count} public repositories",
                "url": f"https://github.com/{login}?tab=repositories&language={language}",
            }
        )
    events = fetch(f"{API}/users/{login}/events/public?per_page=100")
    pushes: dict[str, int] = {}
    for event in events:
        if event.get("type") == "PushEvent":
            name = event["repo"]["name"]
            pushes[name] = pushes.get(name, 0) + len(
                event.get("payload", {}).get("commits", [])
            )
    for name, commits in sorted(pushes.items()):
        items.append(
            {
                "source": "github-contribution",
                "key": name,
                "text": f"Pushed {commits} recent commits to {name}",
                "url": f"https://github.com/{name}",
            }
        )
    return items


def ingest(user: Any, login: str, fetch: Fetch = fetch_json) -> int:
    """Store new evidence; an item already stored for the same source and key is updated, not duplicated."""
    for item in evidence_items(login, fetch):
        Evidence.objects.update_or_create(
            user=user,
            source=item["source"],
            key=item["key"],
            defaults={"text": item["text"], "url": item["url"]},
        )
    return Evidence.objects.filter(user=user).count()
