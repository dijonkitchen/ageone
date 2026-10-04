import json
import threading
import urllib.error
import urllib.request

import pytest

from og_trail import web


@pytest.fixture(scope="module")
def server():
    httpd = web.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def call(base: str, path: str, body: dict[str, object] | None = None, method: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method or ("POST" if data else "GET"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"null"), resp.headers
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null"), err.headers


def test_index_serves_the_gui(server):
    with urllib.request.urlopen(server + "/") as resp:
        body = resp.read().decode()
        assert resp.headers["Content-Type"].startswith("text/html")
    assert "OG Trail" in body
    assert "/api/games" in body


def test_new_game_returns_id_and_first_view(server):
    status, body, _ = call(server, "/api/games", {"seed": 4})
    assert status == 201
    assert body["id"]
    assert body["view"]["phase"] == "setup_name"
    assert body["view"]["input_type"] == "text"


def test_submitting_input_advances_the_game(server):
    _, body, _ = call(server, "/api/games", {"seed": 4})
    gid = body["id"]
    status, body, _ = call(server, f"/api/games/{gid}/input", {"value": "Alex"})
    assert status == 200
    assert body["view"]["phase"] == "setup_profession"
    assert {c["id"] for c in body["view"]["choices"]} == {"tech", "nurse", "barista"}

    status, body, _ = call(server, f"/api/games/{gid}")
    assert status == 200
    assert body["view"]["phase"] == "setup_profession"


def test_invalid_input_is_a_400_with_a_message(server):
    _, body, _ = call(server, "/api/games", {"seed": 4})
    gid = body["id"]
    call(server, f"/api/games/{gid}/input", {"value": "Alex"})
    status, body, _ = call(server, f"/api/games/{gid}/input", {"value": "astronaut"})
    assert status == 400
    assert "not one of the choices" in body["error"]
    assert body["view"]["phase"] == "setup_profession"


def test_unknown_game_is_a_404(server):
    status, _body, _ = call(server, "/api/games/nope")
    assert status == 404
    status, _body, _ = call(server, "/api/games/nope/input", {"value": "x"})
    assert status == 404


def test_malformed_json_is_a_400(server):
    req = urllib.request.Request(
        server + "/api/games",
        data=b"{not json",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code == 400


def test_unknown_route_is_a_404(server):
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(server + "/nothing-here")
    assert err.value.code == 404


def test_same_seed_gives_same_story_on_both_frontends(server):
    """The browser and terminal are different views of one engine."""
    from og_trail.engine import Game

    local = Game(seed=77)
    _, body, _ = call(server, "/api/games", {"seed": 77})
    gid = body["id"]
    for value in ("Alex", "barista", "", "leave", "continue", "continue"):
        local.submit(value)
        _, body, _ = call(server, f"/api/games/{gid}/input", {"value": value})
    assert body["view"] == local.view().to_dict()


def test_cli_can_launch_the_web_server(monkeypatch):
    from og_trail import cli

    launched: dict[str, object] = {}
    monkeypatch.setattr(
        web, "serve", lambda host, port, open_browser: launched.update(host=host, port=port)
    )
    assert cli.main(["web", "--port", "0"]) == 0
    assert launched == {"host": "127.0.0.1", "port": 0}
