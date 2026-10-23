from posse_bliki.webmention import Response, discover, external_links, send


def fake_get(pages: dict[str, Response]):  # type: ignore[no-untyped-def]
    return lambda url: pages[url]


def test_external_links_skip_own_site_and_duplicates() -> None:
    html = '<a href="https://a.example/x">1</a><a href="/local/">2</a><a href="https://me.example/p">3</a><a href="https://a.example/x">4</a><a href="mailto:a@b">5</a>'
    assert external_links(html, "https://me.example") == ["https://a.example/x"]


def test_discovers_endpoint_from_link_header_before_html() -> None:
    page = Response(
        "https://t.example/post",
        200,
        {"Link": '</wm>; rel="webmention"'},
        '<link rel="webmention" href="/other">',
    )
    assert (
        discover("https://t.example/post", fake_get({"https://t.example/post": page}))
        == "https://t.example/wm"
    )


def test_discovers_endpoint_from_html_link_and_a() -> None:
    link = Response(
        "https://t.example/",
        200,
        {},
        '<link href="https://wm.example/e" rel="webmention">',
    )
    anchor = Response("https://t.example/", 200, {}, '<a rel="webmention" href="e">')
    assert discover("u", fake_get({"u": link})) == "https://wm.example/e"
    assert discover("u", fake_get({"u": anchor})) == "https://t.example/e"


def test_no_endpoint_when_absent_or_error() -> None:
    assert discover("u", fake_get({"u": Response("u", 200, {}, "<p>none</p>")})) is None
    assert discover("u", fake_get({"u": Response("u", 404, {}, "")})) is None


def test_send_posts_source_and_target_and_reports_outcomes() -> None:
    pages = {
        "https://ok.example/": Response(
            "https://ok.example/",
            200,
            {"Link": '<https://ok.example/wm>; rel="webmention"'},
            "",
        ),
        "https://none.example/": Response("https://none.example/", 200, {}, ""),
        "https://bad.example/": Response(
            "https://bad.example/",
            200,
            {"Link": '<https://bad.example/wm>; rel="webmention"'},
            "",
        ),
    }
    posted: list[tuple[str, dict[str, str]]] = []

    def post(url: str, data: dict[str, str]) -> int:
        posted.append((url, data))
        return 400 if "bad" in url else 202

    outcomes = send("https://me.example/p/", list(pages), fake_get(pages), post)
    assert outcomes == {
        "https://ok.example/": "sent",
        "https://none.example/": "no endpoint",
        "https://bad.example/": "rejected (400)",
    }
    assert posted[0] == (
        "https://ok.example/wm",
        {"source": "https://me.example/p/", "target": "https://ok.example/"},
    )


def test_network_errors_do_not_stop_the_batch() -> None:
    def get(url: str) -> Response:
        raise OSError("down")

    assert send("s", ["https://x.example/"], get, lambda u, d: 200) == {
        "https://x.example/": "failed (down)"
    }
