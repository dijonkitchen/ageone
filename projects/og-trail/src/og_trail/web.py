"""Browser frontend: a small JSON API over the engine plus one static page.

Standard library only. Games live in memory for the life of the process.
"""

from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any

from .engine import Game, InvalidInput

INDEX_HTML = resources.files(__package__).joinpath("static/index.html").read_text()


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
        self._lock = threading.Lock()

    def create(self, seed: int | None) -> tuple[str, Game]:
        game = Game(seed=seed)
        game_id = secrets.token_urlsafe(8)
        with self._lock:
            self._games[game_id] = game
        return game_id, game

    def get(self, game_id: str) -> Game | None:
        with self._lock:
            return self._games.get(game_id)

    def submit(self, game: Game, value: str) -> None:
        with self._lock:
            game.submit(value)


class Handler(BaseHTTPRequestHandler):
    store: GameStore  # assigned by make_server
    verbose = False

    # --------------------------------------------------------------- routing
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/", "/index.html"}:
            return self._send(HTTPStatus.OK, INDEX_HTML, "text/html; charset=utf-8")
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "games"]:
            game = self.store.get(parts[2])
            if game is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "No such game."})
            return self._json(HTTPStatus.OK, {"id": parts[2], "view": game.view().to_dict()})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        parts = path.strip("/").split("/")
        try:
            body = self._read_json()
        except ValueError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "Body must be JSON."})
        if parts == ["api", "games"]:
            seed = body.get("seed")
            game_id, game = self.store.create(int(seed) if seed is not None else None)
            return self._json(HTTPStatus.CREATED, {"id": game_id, "view": game.view().to_dict()})
        if len(parts) == 4 and parts[:2] == ["api", "games"] and parts[3] == "input":
            found = self.store.get(parts[2])
            if found is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "No such game."})
            game = found
            try:
                self.store.submit(game, str(body.get("value", "")))
            except InvalidInput as exc:
                return self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": str(exc), "id": parts[2], "view": game.view().to_dict()},
                )
            return self._json(HTTPStatus.OK, {"id": parts[2], "view": game.view().to_dict()})
        return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    # --------------------------------------------------------------- helpers
    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected an object")  # noqa: TRY004 (callers answer 400 on ValueError)
        return data

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload), "application/json")

    def _send(self, status: HTTPStatus, body: str, content_type: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        if self.verbose:
            super().log_message(format, *args)


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"store": GameStore()})
    return ThreadingHTTPServer((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    httpd = make_server(host, port)
    url = f"http://{host}:{httpd.server_address[1]}/"
    print(f"OG Trail is running at {url}  (Ctrl-C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
