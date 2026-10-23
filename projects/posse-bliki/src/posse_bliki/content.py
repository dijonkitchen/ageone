"""Load the vault and validate it against the content schema."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
KINDS = {"posts": "post", "notes": "note", "pages": "page"}
# Output paths (the URL policy): a page lives at the site root, the rest under their kind.
RESERVED = {"posts", "notes", "tags", "feed", "404", "robots", "sitemap", "index"}


class ContentError(Exception):
    """The vault breaks the content schema or the URL policy."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Author:
    name: str
    url: str = ""
    note: str = ""


@dataclass(frozen=True)
class Site:
    title: str
    description: str
    url: str  # absolute, no trailing slash, may carry a path prefix
    language: str
    author: Author
    webmention_endpoint: str = ""

    @property
    def base(self) -> str:
        """The path prefix every internal link starts with, '' at the domain root."""
        return urlparse(self.url).path.rstrip("/")


@dataclass
class Entry:
    kind: str  # post, note, or page
    slug: str
    title: str
    body: str
    source: Path
    published: datetime | None = None
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    summary: str = ""
    syndication: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        """The entry's URL path below the site base, with leading and trailing slash."""
        if self.kind == "page":
            return f"/{self.slug}/"
        return f"/{self.kind}s/{self.slug}/"


def load_site(path: Path) -> Site:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    author = data.get("author", {})
    problems = [
        f"site.toml: missing {key}" for key in ("title", "url") if not data.get(key)
    ]
    if not author.get("name"):
        problems.append("site.toml: missing author.name")
    if problems:
        raise ContentError(problems)
    return Site(
        title=data["title"],
        description=data.get("description", ""),
        url=data["url"].rstrip("/"),
        language=data.get("language", "en"),
        author=Author(author["name"], author.get("url", ""), author.get("note", "")),
        webmention_endpoint=data.get("webmention_endpoint", ""),
    )


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime.combine(value, time(), tzinfo=UTC)
    return None


def _str_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(v, str) and v for v in value):
        return list(value)
    return None


def parse_entry(kind: str, source: Path, text: str) -> tuple[Entry | None, list[str]]:
    """Parse one file; returns the entry (None for a draft) and its schema problems."""
    where = source.as_posix()
    match = FRONTMATTER.match(text)
    if not match:
        return None, [f"{where}: missing frontmatter"]
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        return None, [f"{where}: invalid frontmatter ({error})"]
    if not isinstance(meta, dict):
        return None, [f"{where}: frontmatter must be a mapping"]

    problems: list[str] = []
    slug = source.stem
    if not SLUG.match(slug):
        problems.append(f"{where}: file name must be kebab-case")
    if kind == "page" and slug in RESERVED:
        problems.append(f"{where}: slug {slug!r} is reserved")
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append(f"{where}: title is required")
    published = _as_datetime(meta.get("date"))
    if kind == "post" and published is None:
        problems.append(f"{where}: date is required (YYYY-MM-DD or a timestamp)")
    if kind == "note" and "date" in meta and published is None:
        problems.append(f"{where}: date must be YYYY-MM-DD or a timestamp")
    if kind == "page" and "date" in meta:
        problems.append(f"{where}: pages have no date")
    lists: dict[str, list[str]] = {}
    for key in ("tags", "aliases", "syndication"):
        value = _str_list(meta.get(key))
        if value is None:
            problems.append(f"{where}: {key} must be a list of strings")
        else:
            lists[key] = value
    for tag in lists.get("tags", []):
        if not SLUG.match(tag):
            problems.append(f"{where}: tag {tag!r} must be kebab-case")
    for alias in lists.get("aliases", []):
        if not re.match(r"^/[A-Za-z0-9._~/-]*[A-Za-z0-9._~-]/?$", alias):
            problems.append(
                f"{where}: alias {alias!r} must be a site path such as /old/path/"
            )
    for url in lists.get("syndication", []):
        if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
            problems.append(f"{where}: syndication {url!r} must be an http(s) URL")
    if kind != "post" and lists.get("syndication"):
        problems.append(f"{where}: only posts are syndicated")
    summary = meta.get("summary", "")
    if not isinstance(summary, str):
        problems.append(f"{where}: summary must be a string")
    draft = meta.get("draft", False)
    if not isinstance(draft, bool):
        problems.append(f"{where}: draft must be true or false")
    if problems:
        return None, problems
    if draft:
        return None, []
    return (
        Entry(
            kind=kind,
            slug=slug,
            title=str(title).strip(),
            body=match.group(2).strip() + "\n",
            source=source,
            published=published,
            tags=lists["tags"],
            aliases=lists["aliases"],
            summary=str(summary).strip(),
            syndication=lists["syndication"],
        ),
        [],
    )


def normalize_alias(alias: str) -> str:
    return "/" + alias.strip("/") + "/"


def load_vault(root: Path) -> list[Entry]:
    """Every published entry in the vault, newest posts first; raises ContentError listing all problems."""
    entries: list[Entry] = []
    problems: list[str] = []
    for folder, kind in KINDS.items():
        for source in sorted((root / folder).glob("*.md")):
            entry, found = parse_entry(
                kind, source.relative_to(root), source.read_text(encoding="utf-8")
            )
            problems += found
            if entry:
                entries.append(entry)

    taken: dict[str, str] = {}
    for entry in entries:
        for url in [entry.path, *(normalize_alias(a) for a in entry.aliases)]:
            if url in taken:
                problems.append(
                    f"{entry.source.as_posix()}: {url} is already used by {taken[url]}"
                )
            taken[url] = entry.source.as_posix()
        for tag_url in (f"/tags/{t}/" for t in entry.tags):
            if tag_url in taken and taken[tag_url] != "tags":
                problems.append(
                    f"{entry.source.as_posix()}: {tag_url} is already used by {taken[tag_url]}"
                )
            taken[tag_url] = "tags"
    if problems:
        raise ContentError(problems)
    entries.sort(
        key=lambda e: (e.published or datetime.min.replace(tzinfo=UTC), e.slug),
        reverse=True,
    )
    return entries
