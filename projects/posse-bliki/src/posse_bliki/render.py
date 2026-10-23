"""Markdown to HTML, [[wiki links]], and the page templates."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from html import escape

from markdown_it import MarkdownIt

from posse_bliki.content import ContentError, Entry, Site

WIKILINK = re.compile(r"\[\[([^\[\]|#]+)(?:#([^\[\]|]*))?(?:\|([^\[\]]*))?\]\]")
FENCE = re.compile(r"^\s*(```|~~~)")
CSS = """
:root{color-scheme:light dark;--fg:#1a1a1a;--bg:#fdfdfc;--muted:#666;--link:#0b5cad}
@media(prefers-color-scheme:dark){:root{--fg:#e8e8e6;--bg:#161616;--muted:#9a9a9a;--link:#7ab7ff}}
body{margin:0 auto;max-width:42rem;padding:1rem;font:1.0625rem/1.6 system-ui,sans-serif;color:var(--fg);background:var(--bg)}
a{color:var(--link)}header nav a{margin-right:1rem}.muted{color:var(--muted);font-size:.9rem}
pre{overflow-x:auto;padding:.75rem;background:color-mix(in srgb,var(--fg) 8%,transparent)}
img{max-width:100%}article{margin:2rem 0}
""".strip()


@dataclass
class Vault:
    """Entries by the names a wiki link may use, and the links found while rendering."""

    entries: list[Entry]
    backlinks: dict[str, list[Entry]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._targets: dict[str, Entry] = {}
        for entry in self.entries:
            for name in (entry.slug, entry.title.lower()):
                self._targets.setdefault(name, entry)

    def resolve(self, name: str) -> Entry | None:
        name = name.strip()
        return self._targets.get(name) or self._targets.get(name.lower())


def _link_outside_code(
    line: str, replace: re.Pattern[str], fn: Callable[[re.Match[str]], str]
) -> str:
    parts = line.split("`")
    for i in range(0, len(parts), 2):  # even parts are outside inline code
        parts[i] = replace.sub(fn, parts[i])
    return "`".join(parts)


def resolve_wikilinks(
    entry: Entry, vault: Vault, base: str, problems: list[str]
) -> str:
    """Rewrite [[target]], [[target|text]] and [[target#heading]] to Markdown links; code is left alone."""

    def link(match: re.Match[str]) -> str:
        target = vault.resolve(match.group(1))
        if target is None:
            problems.append(
                f"{entry.source.as_posix()}: unresolved wiki link [[{match.group(1).strip()}]]"
            )
            return match.group(0)
        if target is not entry:
            vault.backlinks.setdefault(target.path, [])
            if entry not in vault.backlinks[target.path]:
                vault.backlinks[target.path].append(entry)
        text = (match.group(3) or target.title).strip()
        anchor = (
            "#" + re.sub(r"[^a-z0-9]+", "-", match.group(2).lower()).strip("-")
            if match.group(2)
            else ""
        )
        return f"[{text}]({base}{target.path}{anchor})"

    out: list[str] = []
    fenced = False
    for line in entry.body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        out.append(line if fenced else _link_outside_code(line, WIKILINK, link))
    return "\n".join(out) + "\n"


_md = MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")


def markdown(text: str) -> str:
    return str(_md.render(text))


def render_entries(site: Site, entries: Iterable[Entry]) -> dict[str, str]:
    """Body HTML per entry path; raises ContentError for unresolved wiki links."""
    entries = list(entries)
    vault = Vault(entries)
    problems: list[str] = []
    html = {
        e.path: markdown(resolve_wikilinks(e, vault, site.base, problems))
        for e in entries
    }
    if problems:
        raise ContentError(problems)
    for entry in entries:  # backlinks are only known after every entry is rendered
        linking = vault.backlinks.get(entry.path)
        if linking:
            items = "".join(
                f'<li><a href="{site.base}{e.path}">{escape(e.title)}</a></li>'
                for e in linking
            )
            html[entry.path] += f"<aside><h2>Linked from</h2><ul>{items}</ul></aside>\n"
    return html


def layout(
    site: Site,
    title: str,
    body: str,
    *,
    path: str,
    webmention: str = "",
    feed: bool = True,
) -> str:
    """A full page; `path` is the page's own path below the site base."""
    full_title = site.title if path == "/" else f"{title} · {site.title}"
    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(full_title)}</title>",
        f'<meta name="description" content="{escape(site.description)}">',
        f'<link rel="canonical" href="{escape(site.url + path)}">',
    ]
    if feed:
        head += [
            f'<link rel="alternate" type="application/rss+xml" title="{escape(site.title)}" href="{site.base}/feed.xml">',
            f'<link rel="alternate" type="application/feed+json" title="{escape(site.title)}" href="{site.base}/feed.json">',
        ]
    if webmention:
        head.append(f'<link rel="webmention" href="{escape(webmention)}">')
    if site.author.url:
        head.append(f'<link rel="me" href="{escape(site.author.url)}">')
    head.append(f"<style>{CSS}</style>")
    nav = "".join(
        f'<a href="{site.base}{href}">{label}</a>'
        for href, label in (("/", "Blog"), ("/notes/", "Notes"), ("/tags/", "Tags"))
    )
    card = (
        f'<p class="h-card muted"><a class="p-name u-url" href="{escape(site.author.url or site.url + "/")}" rel="me">'
        f"{escape(site.author.name)}</a>"
        + (
            f' <span class="p-note">{escape(site.author.note)}</span>'
            if site.author.note
            else ""
        )
        + "</p>"
    )
    return (
        f'<!doctype html>\n<html lang="{escape(site.language)}">\n<head>\n'
        + "\n".join(head)
        + f"\n</head>\n<body>\n<header><nav>{nav}</nav></header>\n<main>\n{body}</main>\n<footer>{card}</footer>\n</body>\n</html>\n"
    )


def entry_html(site: Site, entry: Entry, body_html: str, level: int = 2) -> str:
    """One h-entry, as shown alone or inside an h-feed."""
    url = site.url + entry.path
    author = site.author
    meta = []
    if entry.published:
        iso = entry.published.isoformat()
        meta.append(
            f'<time class="dt-published" datetime="{iso}">{entry.published.date().isoformat()}</time>'
        )
    meta.append(
        f'<a class="p-author h-card" href="{escape(author.url or site.url + "/")}">{escape(author.name)}</a>'
    )
    tags = ", ".join(
        f'<a class="p-category" href="{site.base}/tags/{t}/">{t}</a>'
        for t in entry.tags
    )
    if tags:
        meta.append(tags)
    syndicated = "".join(
        f' <a class="u-syndication" rel="syndication" href="{escape(u)}">{escape(_host(u))}</a>'
        for u in entry.syndication
    )
    if syndicated:
        meta.append(f"Also on:{syndicated}")
    summary = (
        f'<p class="p-summary" hidden>{escape(entry.summary)}</p>'
        if entry.summary
        else ""
    )
    return (
        f'<article class="h-entry">\n<h{level} class="p-name"><a class="u-url" href="{site.base}{entry.path}">{escape(entry.title)}</a></h{level}>\n'
        f'<p class="muted">{" · ".join(meta)}</p>\n{summary}<div class="e-content">\n{body_html}</div>\n'
        f'<data class="u-uid" value="{escape(url)}"></data>\n</article>\n'
    )


def _host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
