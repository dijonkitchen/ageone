from pathlib import Path

import pytest

SITE = """title = "Test bliki"
description = "A test"
url = "https://example.org/b"
webmention_endpoint = "https://webmention.example/endpoint"

[author]
name = "Ada"
url = "https://example.org/"
"""

FILES = {
    "content/posts/first-post.md": """---
title: First post
date: 2026-01-02
tags: [meta]
aliases: [/old/first/]
summary: Hi
syndication: [https://social.example/ada/1]
---
Hello [[a-note]] and [[Another Page|the page]] and [out](https://other.example/post).

```
[[not-a-link]]
```
""",
    "content/posts/second-post.md": "---\ntitle: Second post\ndate: 2026-02-03T10:00:00+00:00\ntags: [meta, other]\n---\nSecond.\n",
    "content/posts/unfinished.md": "---\ntitle: Unfinished\ndate: 2026-03-01\ndraft: true\n---\nNope.\n",
    "content/notes/a-note.md": "---\ntitle: A note\ntags: [other]\n---\nSee [[first-post]].\n",
    "content/pages/another-page.md": "---\ntitle: Another Page\n---\nA page.\n",
}


def write_vault(root: Path, files: dict[str, str] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "site.toml").write_text(SITE, encoding="utf-8")
    for name, text in (FILES if files is None else files).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return write_vault(tmp_path / "vault")


@pytest.fixture
def built(vault: Path, tmp_path: Path) -> Path:
    from posse_bliki.build import build

    out = tmp_path / "out"
    build(vault, out)
    return out
