#!/usr/bin/env python3
"""Lightweight dev server for the WarGame viewer.

Serves the viewer UI and exposes a small JSON API so the browser can
discover and load game logs automatically (no manual file picking).

Usage:
    python3 serve.py                     # default port 8080
    python3 serve.py --port 9090         # custom port
    python3 serve.py --game latest       # auto-select latest game
    python3 serve.py --game game_20260212_195258  # specific game
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOGS_DIR = PROJECT_ROOT / "logs"
VIEWER_DIR = PROJECT_ROOT / "viewer"


def _safe_resolve(base: Path, untrusted: str) -> Path | None:
    """Resolve an untrusted path safely, preventing directory traversal."""
    try:
        resolved = (base / untrusted).resolve()
        if resolved.is_relative_to(base.resolve()):
            return resolved
    except (ValueError, OSError):
        pass
    return None


def find_games() -> list[dict]:
    """Return a list of game sessions sorted by name (newest first)."""
    if not LOGS_DIR.exists():
        return []
    games = []
    for entry in sorted(LOGS_DIR.iterdir(), reverse=True):
        if entry.is_dir() and entry.name.startswith("game_"):
            rounds = sorted(entry.glob("round_*.json"))
            summary = entry / "game_summary.json"
            games.append({
                "name": entry.name,
                "rounds": [r.name for r in rounds],
                "has_summary": summary.exists(),
                "round_count": len(rounds),
            })
    return games


class ViewerHandler(SimpleHTTPRequestHandler):
    """Serves viewer files and a tiny JSON API."""

    def do_GET(self):
        # API: list all games
        if self.path == "/api/games":
            self._json_response(find_games())
            return

        # API: get specific round file
        if self.path.startswith("/api/round/"):
            # /api/round/game_xxx/round_001.json
            parts = self.path[len("/api/round/"):].split("/", 1)
            if len(parts) == 2:
                fpath = _safe_resolve(LOGS_DIR, f"{parts[0]}/{parts[1]}")
                if fpath and fpath.exists() and fpath.suffix == ".json":
                    self._file_response(fpath)
                    return
            self._error_response(404, "Round file not found")
            return

        # API: get game summary
        if self.path.startswith("/api/summary/"):
            game_name = self.path[len("/api/summary/"):]
            fpath = _safe_resolve(LOGS_DIR, f"{game_name}/game_summary.json")
            if fpath and fpath.exists():
                self._file_response(fpath)
                return
            self._error_response(404, "Summary not found")
            return

        # API: get all rounds for a game
        if self.path.startswith("/api/game/"):
            game_name = self.path[len("/api/game/"):]
            game_dir = _safe_resolve(LOGS_DIR, game_name)
            if game_dir and game_dir.is_dir():
                all_data = {"rounds": [], "summary": None}
                for rf in sorted(game_dir.glob("round_*.json")):
                    with open(rf) as f:
                        all_data["rounds"].append(json.load(f))
                summary_f = game_dir / "game_summary.json"
                if summary_f.exists():
                    with open(summary_f) as f:
                        all_data["summary"] = json.load(f)
                self._json_response(all_data)
                return
            self._error_response(404, "Game not found")
            return

        # API: get live status for a game
        if self.path.startswith("/api/status/"):
            game_name = self.path[len("/api/status/"):]
            fpath = _safe_resolve(LOGS_DIR, f"{game_name}/status.json")
            if fpath and fpath.exists():
                self._file_response(fpath)
                return
            self._error_response(404, "Status not found (game may not be running)")
            return

        # Serve viewer/index.html at root
        if self.path == "/" or self.path == "/index.html":
            self._file_response(VIEWER_DIR / "index.html", "text/html")
            return

        # Serve other viewer static files
        safe_path = self.path.lstrip("/")
        viewer_file = _safe_resolve(VIEWER_DIR, safe_path)
        if viewer_file and viewer_file.exists() and viewer_file.is_file():
            self._file_response(viewer_file)
            return

        self._error_response(404, "Not found")

    def _json_response(self, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file_response(self, path: Path, content_type: str | None = None):
        if content_type is None:
            ext = path.suffix.lower()
            content_type = {
                ".html": "text/html",
                ".json": "application/json",
                ".js": "application/javascript",
                ".css": "text/css",
                ".svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, code, message):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quieter logging - only show API calls and errors
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description="WarGame Viewer Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    args = parser.parse_args()

    games = find_games()
    print(f"WarGame Viewer Server")
    print(f"  Found {len(games)} game(s) in logs/")
    for g in games[:5]:
        print(f"    {g['name']}: {g['round_count']} rounds")
    print(f"\n  Open: http://localhost:{args.port}")
    print(f"  Press Ctrl+C to stop\n")

    server = HTTPServer(("127.0.0.1", args.port), ViewerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
