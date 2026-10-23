from pathlib import Path

import pytest

from posse_bliki.content import ContentError, load_vault, parse_entry

from .conftest import write_vault


def parse(kind: str, name: str, text: str) -> list[str]:
    return parse_entry(kind, Path(f"content/{kind}s/{name}.md"), text)[1]


def test_valid_post_has_no_problems() -> None:
    entry, problems = parse_entry(
        "post",
        Path("content/posts/ok.md"),
        "---\ntitle: T\ndate: 2026-01-01\n---\nBody\n",
    )
    assert problems == [] and entry is not None and entry.path == "/posts/ok/"


@pytest.mark.parametrize(
    ("kind", "name", "text", "expected"),
    [
        ("post", "p", "no frontmatter", "missing frontmatter"),
        ("post", "p", "---\ndate: 2026-01-01\n---\n", "title is required"),
        ("post", "p", "---\ntitle: T\n---\n", "date is required"),
        ("post", "Bad Name", "---\ntitle: T\ndate: 2026-01-01\n---\n", "kebab-case"),
        (
            "post",
            "p",
            "---\ntitle: T\ndate: 2026-01-01\ntags: [Bad Tag]\n---\n",
            "tag 'Bad Tag'",
        ),
        (
            "post",
            "p",
            "---\ntitle: T\ndate: 2026-01-01\ntags: nope\n---\n",
            "tags must be a list",
        ),
        (
            "post",
            "p",
            "---\ntitle: T\ndate: 2026-01-01\naliases: [old]\n---\n",
            "alias 'old'",
        ),
        (
            "post",
            "p",
            "---\ntitle: T\ndate: 2026-01-01\nsyndication: [ftp://x]\n---\n",
            "must be an http(s) URL",
        ),
        (
            "note",
            "n",
            "---\ntitle: T\nsyndication: [https://x.example/]\n---\n",
            "only posts are syndicated",
        ),
        ("page", "tags", "---\ntitle: T\n---\n", "reserved"),
        ("page", "pg", "---\ntitle: T\ndate: 2026-01-01\n---\n", "pages have no date"),
        ("post", "p", "---\ntitle: [unclosed\n---\n", "invalid frontmatter"),
    ],
)
def test_schema_problems_name_the_file(
    kind: str, name: str, text: str, expected: str
) -> None:
    problems = parse(kind, name, text)
    assert any(expected in p and f"{name}.md" in p for p in problems), problems


def test_drafts_are_not_published() -> None:
    entry, problems = parse_entry(
        "post",
        Path("content/posts/d.md"),
        "---\ntitle: T\ndate: 2026-01-01\ndraft: true\n---\n",
    )
    assert entry is None and problems == []


def test_vault_lists_newest_posts_first(vault: Path) -> None:
    posts = [e.slug for e in load_vault(vault / "content") if e.kind == "post"]
    assert posts == ["second-post", "first-post"]


def test_url_collisions_are_reported(tmp_path: Path) -> None:
    files = {
        "content/posts/a.md": "---\ntitle: A\ndate: 2026-01-01\naliases: [/x/]\n---\n",
        "content/notes/b.md": "---\ntitle: B\naliases: [/x/]\n---\n",
    }
    vault = write_vault(tmp_path, files)
    with pytest.raises(ContentError, match="already used"):
        load_vault(vault / "content")
