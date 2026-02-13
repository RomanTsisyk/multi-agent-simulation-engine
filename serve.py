#!/usr/bin/env python3
"""FastAPI server for the WarGame viewer.

Serves the viewer UI and a full JSON API for browsing completed and
in-progress game simulations stored in ``logs/game_*/``.

Usage:
    python3 serve.py                                # default port 8080
    python3 serve.py --port 9090                    # custom port
    python3 serve.py --game latest                  # auto-select newest game
    python3 serve.py --game game_20260212_195258    # specific game
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
LOGS_DIR = PROJECT_ROOT / "logs"
VIEWER_DIR = PROJECT_ROOT / "viewer"

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------


def _safe_resolve(base: Path, untrusted: str) -> Path | None:
    """Resolve *untrusted* relative to *base*, blocking directory traversal.

    Returns the resolved ``Path`` when it falls inside *base*, or ``None``
    when the path escapes the allowed directory.
    """
    try:
        resolved = (base / untrusted).resolve()
        if resolved.is_relative_to(base.resolve()):
            return resolved
    except (ValueError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Game discovery and data loading
# ---------------------------------------------------------------------------


def find_games() -> list[dict[str, Any]]:
    """Return metadata for every ``game_*`` directory under ``logs/``.

    Results are sorted newest-first (by directory name, which encodes a
    timestamp).
    """
    if not LOGS_DIR.exists():
        return []
    games: list[dict[str, Any]] = []
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


def _load_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file, returning an empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        return {}


class GameData:
    """Lazily loaded data for a single game session.

    Round files are read from disk on first access so that the server can
    pick up new rounds written by a running simulation without a restart.
    """

    def __init__(self, game_dir: Path) -> None:
        self.game_dir = game_dir
        self.name = game_dir.name
        self._rounds: dict[int, dict[str, Any]] | None = None

    # -- round data ---------------------------------------------------------

    def _ensure_rounds(self) -> dict[int, dict[str, Any]]:
        """Load (or reload) round files from disk."""
        rounds: dict[int, dict[str, Any]] = {}
        for p in sorted(self.game_dir.glob("round_*.json")):
            try:
                num = int(p.stem.split("_")[1])
            except (IndexError, ValueError):
                continue
            rounds[num] = _load_json(p)
        self._rounds = rounds
        return rounds

    @property
    def rounds(self) -> dict[int, dict[str, Any]]:
        # Reload every time so live games are reflected immediately.
        return self._ensure_rounds()

    # -- convenience accessors ----------------------------------------------

    @property
    def status(self) -> dict[str, Any]:
        path = self.game_dir / "status.json"
        return _load_json(path) if path.exists() else {}

    @property
    def summary(self) -> dict[str, Any] | None:
        path = self.game_dir / "game_summary.json"
        return _load_json(path) if path.exists() else None

    @property
    def checkpoint(self) -> dict[str, Any]:
        path = self.game_dir / "checkpoint.json"
        return _load_json(path) if path.exists() else {}

    @property
    def analytics(self) -> dict[str, Any]:
        path = self.game_dir / "analytics.json"
        return _load_json(path) if path.exists() else {}


# ---------------------------------------------------------------------------
# Active game state (module-level so the FastAPI app can reference it)
# ---------------------------------------------------------------------------

_active_game: GameData | None = None


def _get_active() -> GameData:
    """Return the currently selected game or raise 404."""
    if _active_game is None:
        raise HTTPException(
            status_code=404,
            detail="No game selected. Use GET /api/games to list games "
                   "and GET /api/select-game/{name} to pick one.",
        )
    return _active_game


def select_game(name: str) -> GameData:
    """Validate and activate a game by directory name."""
    global _active_game  # noqa: PLW0603
    game_dir = _safe_resolve(LOGS_DIR, name)
    if game_dir is None or not game_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Game '{name}' not found")
    _active_game = GameData(game_dir)
    return _active_game


# ---------------------------------------------------------------------------
# Escalation helpers
# ---------------------------------------------------------------------------

# Valid nuclear posture levels (tactical_use / strategic are NOT valid).
NUCLEAR_POSTURE_SCORES: dict[str, int] = {
    "peacetime": 0,
    "elevated": 2,
    "dispersal": 4,
    "launch_ready": 6,
}

_NATO_ALERT_SCORES: dict[str, int] = {
    "normal": 0,
    "elevated": 1,
    "high": 3,
    "article5": 5,
}


def _compute_escalation(ws: dict[str, Any]) -> int:
    """Derive a 0-10 escalation score from the world state."""
    level = 0
    # NATO alert component
    level += _NATO_ALERT_SCORES.get(ws.get("nato_alert_level", "normal"), 0)
    # Nuclear posture component (highest among all countries)
    nuclear = ws.get("nuclear_posture", {})
    max_nuke = 0
    for posture in nuclear.values():
        max_nuke = max(max_nuke, NUCLEAR_POSTURE_SCORES.get(posture, 0))
    level += max_nuke
    # Corridor component
    if ws.get("corridor_control", "contested") in ("russian", "contested"):
        level += 1
    return min(10, max(0, level))


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WarGame Viewer",
    description="Browse and analyse WarGame simulation logs.",
    docs_url=None,
    redoc_url=None,
)


# -- Static file serving ---------------------------------------------------

def _serve_file(path: Path, content_type: str | None = None) -> Response:
    """Return a ``Response`` for a static file with the right content type."""
    if content_type is None:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return Response(
        content=path.read_bytes(),
        media_type=content_type,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main viewer UI (viewer/index.html)."""
    path = VIEWER_DIR / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="viewer/index.html not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/docs.html", response_class=HTMLResponse)
async def docs_page():
    """Serve the documentation page (viewer/docs.html)."""
    path = VIEWER_DIR / "docs.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="viewer/docs.html not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


# -- Game listing and selection ---------------------------------------------

@app.get("/api/games")
async def api_games():
    """List all available game sessions (newest first)."""
    games = find_games()
    # Annotate which game is currently active.
    active_name = _active_game.name if _active_game else None
    for g in games:
        g["active"] = g["name"] == active_name
    return JSONResponse(games)


@app.get("/api/select-game/{game_name}")
async def api_select_game(game_name: str):
    """Switch the active game to *game_name*."""
    gd = select_game(game_name)
    rounds = gd.rounds
    return JSONResponse({
        "selected": gd.name,
        "round_count": len(rounds),
        "has_summary": gd.summary is not None,
    })


# -- Legacy endpoints (used by viewer/index.html) --------------------------

@app.get("/api/game/{game_name}")
async def api_game_full(game_name: str):
    """Return every round and the summary for *game_name* (legacy)."""
    game_dir = _safe_resolve(LOGS_DIR, game_name)
    if game_dir is None or not game_dir.is_dir():
        raise HTTPException(status_code=404, detail="Game not found")
    gd = GameData(game_dir)
    all_data: dict[str, Any] = {
        "rounds": [gd.rounds[n] for n in sorted(gd.rounds)],
        "summary": gd.summary,
    }
    return JSONResponse(all_data)


@app.get("/api/summary/{game_name}")
async def api_summary(game_name: str):
    """Return the game summary JSON for *game_name* (legacy)."""
    fpath = _safe_resolve(LOGS_DIR, f"{game_name}/game_summary.json")
    if fpath is None or not fpath.exists():
        raise HTTPException(status_code=404, detail="Summary not found")
    return JSONResponse(_load_json(fpath))


@app.get("/api/round/{game_name}/{filename}")
async def api_round_file(game_name: str, filename: str):
    """Return a single round file by game name and filename (legacy)."""
    fpath = _safe_resolve(LOGS_DIR, f"{game_name}/{filename}")
    if fpath is None or not fpath.exists() or fpath.suffix != ".json":
        raise HTTPException(status_code=404, detail="Round file not found")
    return JSONResponse(_load_json(fpath))


@app.get("/api/status/{game_name}")
async def api_status_for_game(game_name: str):
    """Return the live status file for *game_name* (legacy)."""
    fpath = _safe_resolve(LOGS_DIR, f"{game_name}/status.json")
    if fpath is None or not fpath.exists():
        raise HTTPException(
            status_code=404,
            detail="Status not found (game may not be running)",
        )
    return JSONResponse(_load_json(fpath))


# -- Active-game endpoints (demo-style API) --------------------------------

@app.get("/api/status")
async def api_status():
    """Game status overview for the active game."""
    gd = _get_active()
    return JSONResponse(gd.status)


@app.get("/api/rounds")
async def api_rounds():
    """List rounds in the active game with summary info."""
    gd = _get_active()
    summaries: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        rd = gd.rounds[num]
        ws = rd.get("world_state_after", {})
        summaries.append({
            "round": num,
            "game_time": ws.get("game_time", ""),
            "escalation": _compute_escalation(ws),
            "oil_price": ws.get("markets", {}).get("oil_price", 0),
            "corridor_control": ws.get("corridor_control", "unknown"),
            "headline": (ws.get("media_headlines", [None]) or [None])[0],
            "num_countries": len(rd.get("country_decisions", [])),
            "nato_alert": ws.get("nato_alert_level", "unknown"),
            "nuclear_posture": ws.get("nuclear_posture", {}),
        })
    return JSONResponse(summaries)


@app.get("/api/rounds/{round_num}")
async def api_round(round_num: int):
    """Full data for a specific round in the active game."""
    gd = _get_active()
    rounds = gd.rounds
    if round_num not in rounds:
        raise HTTPException(status_code=404, detail=f"Round {round_num} not found")
    return JSONResponse(rounds[round_num])


@app.get("/api/countries")
async def api_countries():
    """List all countries that appear in the active game."""
    gd = _get_active()
    countries: dict[str, dict[str, Any]] = {}
    for num in sorted(gd.rounds):
        for dec in gd.rounds[num].get("country_decisions", []):
            code = dec.get("country", "")
            if code and code not in countries:
                countries[code] = {
                    "code": code,
                    "name": dec.get("country_name", code),
                    "rounds_present": [],
                }
            if code:
                countries[code]["rounds_present"].append(num)
    return JSONResponse(sorted(countries.values(), key=lambda c: c["name"]))


@app.get("/api/countries/{country_code}")
async def api_country(country_code: str):
    """Decisions for a single country across all rounds (active game)."""
    gd = _get_active()
    country_code = country_code.upper()
    decisions: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        for dec in gd.rounds[num].get("country_decisions", []):
            if dec.get("country") == country_code:
                decisions.append({"round": num, **dec})
    if not decisions:
        raise HTTPException(status_code=404, detail=f"Country {country_code} not found")
    return JSONResponse({
        "country": country_code,
        "name": decisions[0].get("country_name", country_code),
        "decisions": decisions,
    })


@app.get("/api/world-state/{round_num}")
async def api_world_state(round_num: int):
    """World state snapshot for a specific round (active game)."""
    gd = _get_active()
    rounds = gd.rounds
    if round_num not in rounds:
        raise HTTPException(status_code=404, detail=f"Round {round_num} not found")
    return JSONResponse(rounds[round_num].get("world_state_after", {}))


# -- Chart data endpoints --------------------------------------------------

@app.get("/api/charts/oil-price")
async def api_chart_oil_price():
    """Oil price (and EUR/USD) across all rounds."""
    gd = _get_active()
    data: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        ws = gd.rounds[num].get("world_state_after", {})
        markets = ws.get("markets", {})
        data.append({
            "round": num,
            "game_time": ws.get("game_time", f"Round {num}"),
            "oil_price": markets.get("oil_price", 0),
            "euro_usd": markets.get("euro_usd", 0),
        })
    return JSONResponse(data)


@app.get("/api/charts/war-support")
async def api_chart_war_support():
    """War support by country across all rounds."""
    gd = _get_active()
    countries_data: dict[str, list[dict[str, Any]]] = {}
    for num in sorted(gd.rounds):
        ws = gd.rounds[num].get("world_state_after", {})
        for country_code, opinion in ws.get("public_opinion", {}).items():
            if country_code not in countries_data:
                countries_data[country_code] = []
            countries_data[country_code].append({
                "round": num,
                "war_support": opinion.get("war_support", 0),
            })
    return JSONResponse(countries_data)


@app.get("/api/charts/nuclear")
async def api_chart_nuclear():
    """Nuclear posture timeline (valid levels only).

    Posture values: peacetime (0), elevated (2), dispersal (4),
    launch_ready (6). Invalid / legacy values (e.g. tactical_use,
    strategic) are mapped to 0.
    """
    gd = _get_active()
    data: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        ws = gd.rounds[num].get("world_state_after", {})
        np_map = ws.get("nuclear_posture", {})
        entry: dict[str, Any] = {
            "round": num,
            "game_time": ws.get("game_time", ""),
        }
        for country, posture in np_map.items():
            entry[country] = NUCLEAR_POSTURE_SCORES.get(posture, 0)
            entry[f"{country}_label"] = posture
        data.append(entry)
    return JSONResponse(data)


@app.get("/api/charts/escalation")
async def api_chart_escalation():
    """Escalation level timeline for the active game."""
    gd = _get_active()
    data: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        ws = gd.rounds[num].get("world_state_after", {})
        data.append({
            "round": num,
            "game_time": ws.get("game_time", ""),
            "escalation": _compute_escalation(ws),
            "events": ws.get("recent_events", []),
        })
    return JSONResponse(data)


@app.get("/api/charts/military")
async def api_chart_military():
    """Military balance (NATO vs RU/BY aggregate) across rounds."""
    gd = _get_active()
    data: list[dict[str, Any]] = []
    for num in sorted(gd.rounds):
        ws = gd.rounds[num].get("world_state_after", {})
        units = ws.get("military_units", [])
        nato_str = ru_str = nato_cas = ru_cas = 0
        for u in units:
            c = u.get("country", "")
            s = u.get("strength", 0)
            cas = u.get("casualties", 0)
            if c in ("RU", "BY"):
                ru_str += s
                ru_cas += cas
            else:
                nato_str += s
                nato_cas += cas
        data.append({
            "round": num,
            "nato_strength": nato_str,
            "ru_strength": ru_str,
            "nato_casualties": nato_cas,
            "ru_casualties": ru_cas,
        })
    return JSONResponse(data)


# -- Catch-all: serve other viewer static files -----------------------------

@app.get("/{file_path:path}")
async def static_files(file_path: str, request: Request):
    """Serve remaining static assets from the viewer/ directory.

    Path-traversal is blocked by ``_safe_resolve``.
    """
    if not file_path:
        # Redirect bare trailing-slash to index
        return await index()
    resolved = _safe_resolve(VIEWER_DIR, file_path)
    if resolved is None or not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return _serve_file(resolved)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="WarGame Viewer Server (FastAPI)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument(
        "--game",
        type=str,
        default=None,
        help='Auto-select a game at startup. Use "latest" for the newest game.',
    )
    args = parser.parse_args()

    # Discover games
    games = find_games()
    print(f"\nWarGame Viewer Server (FastAPI + Uvicorn)")
    print(f"  Found {len(games)} game(s) in logs/")
    for g in games[:5]:
        print(f"    {g['name']}: {g['round_count']} rounds")

    # Auto-select game if requested
    global _active_game  # noqa: PLW0603
    if args.game:
        if args.game == "latest":
            if games:
                _active_game = GameData(LOGS_DIR / games[0]["name"])
                print(f"\n  Auto-selected latest game: {_active_game.name}")
            else:
                print("\n  WARNING: --game latest requested but no games found")
        else:
            game_dir = LOGS_DIR / args.game
            if game_dir.is_dir():
                _active_game = GameData(game_dir)
                print(f"\n  Auto-selected game: {_active_game.name}")
            else:
                print(f"\n  WARNING: Game '{args.game}' not found in logs/")
                sys.exit(1)

    print(f"\n  Open: http://localhost:{args.port}")
    print(f"  API:  http://localhost:{args.port}/api/games")
    print(f"  Docs: http://localhost:{args.port}/docs.html")
    print(f"  Press Ctrl+C to stop\n")

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
