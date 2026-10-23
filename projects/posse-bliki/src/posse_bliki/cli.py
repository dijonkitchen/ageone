"""The `bliki` command: build, check, serve, and send Webmentions."""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from posse_bliki import build as builder
from posse_bliki import webmention
from posse_bliki.content import ContentError, load_site, load_vault
from posse_bliki.render import render_entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bliki", description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project folder with site.toml and content/",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="validate the vault and write the site")
    b.add_argument("--out", type=Path, default=Path("_site"))
    b.add_argument(
        "--base-url", help="override the site URL from site.toml (for previews)"
    )
    b.add_argument(
        "--update-urls",
        action="store_true",
        help="record newly published URLs in urls.lock",
    )
    sub.add_parser(
        "check", help="validate the vault and the stable URLs without writing the site"
    )

    s = sub.add_parser(
        "serve", help="build, serve locally, and rebuild when the vault changes"
    )
    s.add_argument("--port", type=int, default=8000)

    w = sub.add_parser(
        "webmention",
        help="send Webmentions for recent posts (run after the site is live)",
    )
    w.add_argument("--since-days", type=int, default=7)
    w.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    root: Path = args.root
    try:
        if args.command == "check":
            with tempfile.TemporaryDirectory() as tmp:
                return _build(root, Path(tmp), False, None)
        if args.command == "build":
            return _build(root, args.out, args.update_urls, args.base_url)
        if args.command == "serve":
            return _serve(root, args.port)
        return _webmention(root, args.since_days, args.dry_run)
    except ContentError as error:
        print("\n".join(error.problems), file=sys.stderr)
        return 1


def _build(root: Path, out: Path, update: bool, base_url: str | None) -> int:
    paths = builder.build(root, out, url=base_url)
    gone = builder.check_urls(root, paths)
    if gone:
        print("\n".join(gone), file=sys.stderr)
        return 1
    if update:
        builder.update_urls(root, paths)
    print(f"built {len(paths)} URLs into {out}")
    return 0


def _serve(root: Path, port: int) -> int:
    out = Path(tempfile.mkdtemp())
    base = f"http://localhost:{port}"

    def rebuild() -> None:
        try:
            _build(root, out, False, base)
        except ContentError as error:
            print("\n".join(error.problems), file=sys.stderr)

    rebuild()
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(out)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"serving {base}/ (Ctrl-C to stop)")

    def stamp() -> float:
        files = [*(root / "content").rglob("*"), root / "site.toml"]
        return max((f.stat().st_mtime for f in files if f.is_file()), default=0.0)

    seen = stamp()
    try:
        while True:
            time.sleep(0.5)
            if (now := stamp()) != seen:
                seen = now
                rebuild()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def _webmention(root: Path, since_days: int, dry_run: bool) -> int:
    site = load_site(root / "site.toml")
    entries = load_vault(root / "content")
    bodies = render_entries(site, entries)
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    parts = urlparse(site.url)
    origin = f"{parts.scheme}://{parts.netloc}"
    for entry in entries:
        if entry.kind != "post" or not entry.published or entry.published < cutoff:
            continue
        targets = webmention.external_links(bodies[entry.path], origin)
        source = site.url + entry.path
        if dry_run:
            print(f"{source}: would notify {len(targets)} targets")
            continue
        for target, outcome in webmention.send(
            source, targets, webmention.http_get, webmention.http_post
        ).items():
            print(f"{source} -> {target}: {outcome}")
    return 0
