"""Send Webmentions (https://www.w3.org/TR/webmention/) for the external links in a post."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser

LINK_HEADER = re.compile(r'<([^>]*)>\s*;\s*[^,]*?rel="?([^",;]*)"?')


@dataclass(frozen=True)
class Response:
    url: str  # after redirects
    status: int
    headers: dict[str, str]
    body: str


Get = Callable[[str], Response]
Post = Callable[[str, dict[str, str]], int]


class _Links(HTMLParser):
    def __init__(self, rel: str | None = None) -> None:
        super().__init__()
        self.rel = rel
        self.hrefs: list[
            str
        ] = []  # for `rel`, the first <link>/<a> carrying it; otherwise every <a href>

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if self.rel is None:
            if tag == "a" and a.get("href"):
                self.hrefs.append(a["href"])
        elif (
            tag in ("link", "a")
            and "href" in a
            and self.rel in a.get("rel", "").split()
        ):
            self.hrefs.append(a["href"])


def external_links(html: str, own_origin: str) -> list[str]:
    """Distinct http(s) links in the HTML that point away from the site, in order."""
    parser = _Links()
    parser.feed(html)
    seen: list[str] = []
    for href in parser.hrefs:
        parts = urllib.parse.urlparse(href)
        if (
            parts.scheme in ("http", "https")
            and parts.netloc
            and not href.startswith(own_origin)
            and href not in seen
        ):
            seen.append(href)
    return seen


def discover(target: str, get: Get) -> str | None:
    """The target's Webmention endpoint: HTTP Link header first, then <link>/<a rel="webmention">."""
    response = get(target)
    if not 200 <= response.status < 300:
        return None
    for key, value in response.headers.items():
        if key.lower() == "link":
            for href, rel in LINK_HEADER.findall(value):
                if "webmention" in rel.split():
                    return str(urllib.parse.urljoin(response.url, href))
    parser = _Links("webmention")
    parser.feed(response.body)
    return (
        str(urllib.parse.urljoin(response.url, parser.hrefs[0]))
        if parser.hrefs
        else None
    )


def send(source: str, targets: list[str], get: Get, post: Post) -> dict[str, str]:
    """Notify every target that supports Webmention; returns each target's outcome."""
    outcomes: dict[str, str] = {}
    for target in targets:
        try:
            endpoint = discover(target, get)
            if endpoint is None:
                outcomes[target] = "no endpoint"
                continue
            status = post(endpoint, {"source": source, "target": target})
            outcomes[target] = "sent" if 200 <= status < 300 else f"rejected ({status})"
        except OSError as error:
            outcomes[target] = f"failed ({error})"
    return outcomes


def http_get(url: str) -> Response:
    request = urllib.request.Request(
        url, headers={"User-Agent": "posse-bliki-webmention/0.1"}
    )
    with urllib.request.urlopen(request, timeout=15) as r:
        body = r.read(1_000_000).decode(
            r.headers.get_content_charset() or "utf-8", "replace"
        )
        return Response(r.geturl(), r.status, dict(r.headers.items()), body)


def http_post(url: str, data: dict[str, str]) -> int:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(data).encode(),
        headers={"User-Agent": "posse-bliki-webmention/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as r:
            return int(r.status)
    except urllib.error.HTTPError as error:
        return error.code
