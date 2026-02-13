#!/usr/bin/env python3
"""WarGame: Multi-Agent Geopolitical Simulation

Entry point with subcommands:
    python run.py play --preset quick     # Quick game (4 countries, 2 rounds)
    python run.py play --preset medium    # Medium game (7 countries, 5 rounds)
    python run.py play --preset full      # Full game (all countries, 10 rounds)
    python run.py play --preset nato-vs-russia  # NATO vs Russia (20 countries)
    python run.py resume <game_dir>       # Resume from checkpoint
    python run.py view [game_dir]         # Start viewer + open browser
    python run.py list                    # Show past games

Backward compatible: bare `python run.py` works as `play`.
"""
import asyncio
import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from engine.game import Game
from presets import PRESETS, get_preset, list_presets


# ======================================================================
# Config / scenario / country loading (unchanged logic)
# ======================================================================

def _load_config(config_path: str) -> dict:
    """Load and return the top-level config.yaml."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _load_scenario(project_root: Path, scenario_rel_path: str) -> dict:
    """Load the scenario YAML file."""
    scenario_path = project_root / scenario_rel_path
    with open(scenario_path, "r") as f:
        return yaml.safe_load(f)


def _load_countries(
    project_root: Path,
    countries_dir: str,
    country_filter: list[str] | None = None,
) -> dict:
    """Load all country YAML files and return as a dict keyed by code.

    Args:
        project_root: Absolute path to the project root.
        countries_dir: Relative path to the countries directory.
        country_filter: If provided, only include countries whose code
            (uppercased) is in this list.

    Returns:
        Dictionary mapping country code -> country config dict.
    """
    countries_path = project_root / countries_dir
    result = {}

    if not countries_path.exists():
        print(f"WARNING: Countries directory not found: {countries_path}")
        return result

    for yaml_file in sorted(countries_path.glob("*.yaml")):
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)
        if not data:
            continue

        code = data.get("code", yaml_file.stem.upper()[:2])

        # Apply country filter
        if country_filter and code.upper() not in [c.upper() for c in country_filter]:
            continue

        result[code] = data

    return result


def _build_initial_state(scenario: dict) -> dict:
    """Convert the scenario's initial_world_state into the format
    expected by engine.Game._build_initial_state."""
    iws = scenario.get("initial_world_state", {})

    # Build military units from the descriptive military dict
    military_units = []
    mil = iws.get("military", {})

    # Differentiate initial readiness based on role in crisis
    _initial_readiness = {
        "russian_kaliningrad_forces": 9,    # forward-deployed, initiating operation
        "russian_western_district": 6,      # reserve, not fully mobilized yet
        "belarus_forces": 4,                # low readiness, reluctant participant
        "nato_efp_lithuania": 7,            # alert, German-led battlegroup
        "nato_efp_latvia": 6,               # normal readiness, Canadian-led
        "nato_efp_estonia": 6,              # normal readiness, British-led
        "nato_efp_poland": 7,               # elevated, US-led
        "us_forces_poland": 8,              # V Corps HQ, high readiness
        "polish_forces": 7,                 # elevated, border forces mobilizing
        "finnish_forces": 5,                # reserves on standby, not mobilized
    }
    _initial_strength = {
        "russian_kaliningrad_forces": 8,    # reinforced for operation
        "russian_western_district": 7,      # full strength but distant
        "belarus_forces": 4,                # small, poorly equipped
        "nato_efp_lithuania": 5,            # ~1200 troops, small but capable
        "nato_efp_latvia": 5,               # ~2000 troops
        "nato_efp_estonia": 5,              # ~1200 troops
        "nato_efp_poland": 5,               # ~1000 troops
        "us_forces_poland": 7,              # V Corps + support
        "polish_forces": 7,                 # large army, modernizing
        "finnish_forces": 6,                # large reserves, good equipment
    }

    for key, description in mil.items():
        country = _infer_country(key)
        location = _infer_location(key)
        military_units.append({
            "name": key,
            "country": country,
            "type": "ground",
            "location": location,
            "readiness": _initial_readiness.get(key, 5),
            "strength": _initial_strength.get(key, 5),
        })

    # Build markets from economic section
    econ = iws.get("economic", {})
    markets = {
        "oil_price": econ.get("oil_price_brent", 89),
        "euro_usd": econ.get("eur_usd", 1.08),
        "gas_price_eu": econ.get("gas_price_eu", "elevated but stable"),
        "stock_indices": econ.get("stock_markets", "nervous"),
    }

    # Build public opinion
    public_opinion = {}
    po = iws.get("public_opinion", {})
    code_map = {
        "poland": "PL", "germany": "DE", "france": "FR",
        "us": "US", "uk": "GB", "russia": "RU",
    }
    for key, value in po.items():
        parts = key.rsplit("_war_support", 1)
        if len(parts) == 2:
            country_name = parts[0].lower()
            code = code_map.get(country_name, country_name.upper()[:2])
            public_opinion[code] = {"war_support": value}

    # Build media headlines
    media_headlines = iws.get("media", [])

    # Build recent events from the initial_event
    initial_event = scenario.get("initial_event", "")
    recent_events = [
        "Russia announces humanitarian logistics corridor to Kaliningrad",
        "3 Russian BTGs moved to forward positions in Kaliningrad",
        "Baltic Fleet conducting exercises near Lithuanian coast",
        "Cyber activity detected against Lithuanian networks",
        "Belarus troops moved to Lithuanian border",
    ]

    # Diplomatic
    diplo = iws.get("diplomatic", {})

    # Initial nuclear posture -- all nuclear states at peacetime
    nuclear_posture = {
        "RU": "elevated",  # Russia initiating, slightly elevated
        "US": "peacetime",
        "GB": "peacetime",
        "FR": "peacetime",
    }

    return {
        "game_time": "Day 1, 06:00 CET",
        "nato_alert_level": "elevated",
        "nuclear_posture": nuclear_posture,
        "military_units": military_units,
        "military_alerts": {k: str(v) for k, v in mil.items()},
        "markets": markets,
        "diplomatic_relations": {},
        "nato_consensus": {"US": diplo.get("us_stance", "cautious")},
        "public_opinion": public_opinion,
        "sanctions": [],
        "trade_disruptions": [],
        "treaties_invoked": [],
        "un_resolutions": [],
        "recent_events": recent_events,
        "media_headlines": media_headlines,
    }


def _infer_country(key: str) -> str:
    """Infer a country code from a military unit key name."""
    k = key.lower()
    if "russian" in k or "russia" in k:
        return "RU"
    if "belarus" in k:
        return "BY"
    if "nato_efp_lithuania" in k:
        return "DE"
    if "nato_efp_latvia" in k:
        return "CA"
    if "nato_efp_estonia" in k:
        return "GB"
    if "nato_efp_poland" in k:
        return "US"
    if "us_forces" in k:
        return "US"
    if "polish" in k or "poland" in k:
        return "PL"
    if "finnish" in k or "finland" in k:
        return "FI"
    return "??"


def _infer_location(key: str) -> str:
    """Infer a location from a military unit key name."""
    k = key.lower()
    if "kaliningrad" in k:
        return "Kaliningrad Oblast"
    if "western_district" in k:
        return "Western Military District, Russia"
    if "belarus" in k:
        return "Belarus-Lithuania border"
    if "lithuania" in k:
        return "Lithuania"
    if "latvia" in k:
        return "Latvia"
    if "estonia" in k:
        return "Estonia"
    if "poland" in k or "polish" in k:
        return "Poland"
    if "finnish" in k or "finland" in k:
        return "Finland"
    return "Unknown"


def build_game_config(
    raw_config: dict,
    scenario: dict,
    countries: dict,
    initial_state: dict,
    backend_override: str | None = None,
    model_override: str | None = None,
    rounds_override: int | None = None,
) -> dict:
    """Assemble the config dict expected by engine.Game.

    The Game class expects::

        {
            "backend": {"name": "ollama", "model": "...", ...},
            "scenario": {
                "name": "...",
                "rounds": N,
                "countries": { "<CODE>": {...}, ... },
                "initial_state": { ... }
            },
            "logs_dir": "logs"
        }
    """
    llm_cfg = raw_config.get("llm", {})
    backend_name = backend_override or llm_cfg.get("backend", "ollama")
    backend_settings = dict(llm_cfg.get(backend_name, {}))

    if model_override:
        backend_settings["model"] = model_override

    # Remove keys not accepted by backend constructors
    # (temperature is handled per-request, not at constructor level)
    backend_settings.pop("temperature", None)
    # base_url: Ollama uses it, DeepSeek does not (URL is hardcoded in the backend)
    if backend_name != "ollama":
        backend_settings.pop("base_url", None)

    # Add the backend name
    backend_settings["name"] = backend_name

    # For deepseek, inject API key from environment
    if backend_name == "deepseek" and "api_key" not in backend_settings:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if api_key:
            backend_settings["api_key"] = api_key

    game_cfg = raw_config.get("game", {})
    total_rounds = rounds_override or game_cfg.get("rounds", 10)

    return {
        "backend": backend_settings,
        "scenario": {
            "name": scenario.get("name", "Suwalki Gap Crisis"),
            "description": scenario.get("description", ""),
            "background": scenario.get("background", ""),
            "initial_event": scenario.get("initial_event", ""),
            "rounds": total_rounds,
            "countries": countries,
            "initial_state": initial_state,
            "end_conditions": scenario.get("end_conditions", []),
        },
        "logs_dir": game_cfg.get("logs_dir", "logs"),
        "game_master": raw_config.get("game_master", {}),
        "debate": raw_config.get("debate", {}),
    }


# ======================================================================
# Ollama auto-start
# ======================================================================

def _ensure_ollama_running(base_url: str) -> bool:
    """Check if Ollama is reachable; if not, try to start it.

    Returns True if Ollama is reachable after the check.
    """
    import urllib.request
    import urllib.error

    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except (urllib.error.URLError, OSError):
        pass

    # Try to start Ollama
    print("Ollama not running. Attempting to start...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for it to come up
        for _ in range(10):
            time.sleep(1)
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2):
                    print("  Ollama started successfully.")
                    return True
            except (urllib.error.URLError, OSError):
                continue
        print("  WARNING: Ollama did not start within 10 seconds.")
        return False
    except FileNotFoundError:
        print("  WARNING: 'ollama' command not found. Install from https://ollama.ai")
        return False


# ======================================================================
# Subcommand: play
# ======================================================================

async def cmd_play(args: argparse.Namespace) -> None:
    """Run a new game with optional preset."""
    config_path = Path(args.config).resolve()
    project_root = config_path.parent

    # Load configuration
    print("Loading configuration...")
    raw_config = _load_config(str(config_path))

    # Apply preset if specified
    country_filter = None
    rounds_override = args.rounds

    if args.preset:
        preset = get_preset(args.preset)
        print(f"Using preset: {args.preset} -- {preset['description']}")
        country_filter = preset["countries"]  # None means all
        if rounds_override is None:
            rounds_override = preset["rounds"]

    # Override with explicit --countries if provided
    if args.countries:
        country_filter = [c.upper() for c in args.countries]

    # Auto-start Ollama if needed
    llm_cfg = raw_config.get("llm", {})
    backend_name = args.backend or llm_cfg.get("backend", "ollama")
    if backend_name == "ollama":
        backend_cfg = llm_cfg.get("ollama", {})
        base_url = backend_cfg.get("base_url", "http://localhost:11434")
        _ensure_ollama_running(base_url)

    # Pre-flight checks
    from engine.preflight import run_preflight_checks
    num_countries_hint = len(country_filter) if country_filter else None
    ok = run_preflight_checks(
        raw_config, project_root,
        num_countries=num_countries_hint,
        skip_ollama=(backend_name != "ollama"),
    )
    if not ok:
        print("\nPre-flight checks failed. Fix the issues above and retry.")
        sys.exit(1)

    # Load scenario
    game_cfg = raw_config.get("game", {})
    scenario_path = game_cfg.get("scenario", "scenarios/suwalki_gap.yaml")
    print(f"Loading scenario: {scenario_path}")
    scenario = _load_scenario(project_root, scenario_path)

    # Load countries
    countries_dir = game_cfg.get("countries_dir", "countries")
    # Use country_filter from preset or --countries
    if country_filter:
        filter_list = [c.upper() for c in country_filter]
    else:
        filter_list = None
    print(f"Loading countries from: {countries_dir}")
    countries = _load_countries(project_root, countries_dir, filter_list)

    if not countries:
        print("ERROR: No countries loaded. Add YAML files to the countries/ directory.")
        print(f"       Looked in: {project_root / countries_dir}")
        sys.exit(1)

    print(f"  Loaded {len(countries)} countries: {', '.join(countries.keys())}")

    # Build initial state from scenario
    initial_state = _build_initial_state(scenario)

    # Assemble game config
    game_config = build_game_config(
        raw_config=raw_config,
        scenario=scenario,
        countries=countries,
        initial_state=initial_state,
        backend_override=args.backend,
        model_override=args.model,
        rounds_override=rounds_override,
    )

    # Create and run the game
    game = Game(config=game_config)

    try:
        await game.setup()
        await game.run()
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user.")
        if game.logger:
            print(f"  Checkpoint saved to: {game.logger.game_dir}")
            print(f"  Resume with: python run.py resume {game.logger.game_dir}")
    except ConnectionError as e:
        print(f"\nERROR: Cannot connect to LLM backend: {e}")
        print("Make sure Ollama is running: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        if game.logger:
            print(f"\n  Resume with: python run.py resume {game.logger.game_dir}")
        sys.exit(1)
    finally:
        await game.close()

    # Auto-open browser if requested
    if getattr(args, "auto_open", False) and game.logger:
        _open_viewer(game.logger.game_dir)


# ======================================================================
# Subcommand: resume
# ======================================================================

async def cmd_resume(args: argparse.Namespace) -> None:
    """Resume a game from a checkpoint."""
    from engine.checkpoint import load_checkpoint, apply_checkpoint
    from engine.round_logger import RoundLogger

    game_dir = Path(args.game_dir).resolve()
    if not game_dir.exists():
        print(f"ERROR: Game directory not found: {game_dir}")
        sys.exit(1)

    # Load checkpoint
    print(f"Loading checkpoint from {game_dir}...")
    checkpoint = load_checkpoint(game_dir)
    round_completed = checkpoint["round_completed"]
    total_rounds = checkpoint["total_rounds"]
    print(f"  Checkpoint: round {round_completed}/{total_rounds} completed")

    if round_completed >= total_rounds:
        print("  Game already completed. Nothing to resume.")
        sys.exit(0)

    # Load config
    config_path = Path(args.config).resolve()
    project_root = config_path.parent
    raw_config = _load_config(str(config_path))

    # Rebuild game config from the original settings
    game_cfg = raw_config.get("game", {})
    scenario_path = game_cfg.get("scenario", "scenarios/suwalki_gap.yaml")
    scenario = _load_scenario(project_root, scenario_path)
    countries_dir = game_cfg.get("countries_dir", "countries")

    # Use country codes from checkpoint fingerprint if available
    fingerprint = checkpoint.get("config_fingerprint", {})
    country_filter = fingerprint.get("country_codes")

    countries = _load_countries(project_root, countries_dir, country_filter)

    if not countries:
        print("ERROR: No countries loaded.")
        sys.exit(1)

    initial_state = _build_initial_state(scenario)
    game_config = build_game_config(
        raw_config=raw_config,
        scenario=scenario,
        countries=countries,
        initial_state=initial_state,
        backend_override=args.backend,
        model_override=args.model,
        rounds_override=total_rounds,
    )

    # Create game and setup
    game = Game(config=game_config)

    try:
        await game.setup()

        # Reuse existing game directory instead of creating a new one
        game.logger = RoundLogger(str(game_dir))

        # Re-initialize dashboard with existing game dir
        from engine.dashboard import Dashboard
        game.dashboard = Dashboard(
            game_dir=game_dir,
            total_rounds=total_rounds,
            num_countries=len(game.countries),
            scenario_name=game_config.get("scenario", {}).get("name", ""),
        )

        # Apply checkpoint state
        start_round = apply_checkpoint(game, checkpoint)
        print(f"  Resuming from round {start_round}...")

        await game.run(start_round=start_round)
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user.")
        print(f"  Resume again with: python run.py resume {game_dir}")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n  Resume with: python run.py resume {game_dir}")
        sys.exit(1)
    finally:
        await game.close()


# ======================================================================
# Subcommand: view
# ======================================================================

def cmd_view(args: argparse.Namespace) -> None:
    """Start the viewer server and open a browser."""
    port = args.port
    _open_viewer(args.game_dir, port=port)

    # Run serve.py
    serve_script = Path(__file__).parent / "serve.py"
    print(f"Starting viewer server on port {port}...")
    try:
        subprocess.run(
            [sys.executable, str(serve_script), "--port", str(port)],
        )
    except KeyboardInterrupt:
        print("\nViewer stopped.")


def _open_viewer(game_dir=None, port: int = 8080) -> None:
    """Open the viewer in a web browser."""
    url = f"http://localhost:{port}"
    if game_dir:
        game_name = Path(game_dir).name
        url += f"?game={game_name}"
    try:
        webbrowser.open(url)
    except Exception:
        print(f"  Open in browser: {url}")


# ======================================================================
# Subcommand: list
# ======================================================================

def cmd_list(args: argparse.Namespace) -> None:
    """List past game sessions."""
    logs_dir = Path(args.logs_dir)
    if not logs_dir.exists():
        print(f"No logs directory found at: {logs_dir}")
        return

    games = []
    for entry in sorted(logs_dir.iterdir(), reverse=True):
        if entry.is_dir() and entry.name.startswith("game_"):
            rounds = sorted(entry.glob("round_*.json"))
            summary_file = entry / "game_summary.json"
            checkpoint_file = entry / "checkpoint.json"

            info = {
                "name": entry.name,
                "rounds": len(rounds),
                "has_summary": summary_file.exists(),
                "has_checkpoint": checkpoint_file.exists(),
            }

            # Load summary if available
            if summary_file.exists():
                try:
                    with open(summary_file) as f:
                        summary = json.load(f)
                    info["scenario"] = summary.get("scenario", "?")
                    info["total_rounds"] = summary.get("total_rounds", "?")
                    info["rounds_completed"] = summary.get("rounds_completed", "?")
                    info["total_time"] = summary.get("total_time_seconds", 0)
                except Exception:
                    pass

            # Load checkpoint info if available (for incomplete games)
            if checkpoint_file.exists() and not summary_file.exists():
                try:
                    with open(checkpoint_file) as f:
                        ckpt = json.load(f)
                    info["checkpoint_round"] = ckpt.get("round_completed", "?")
                    info["total_rounds"] = ckpt.get("total_rounds", "?")
                except Exception:
                    pass

            games.append(info)

    if not games:
        print("No games found.")
        return

    print(f"\n{'='*65}")
    print(f"  PAST GAMES ({len(games)} found)")
    print(f"{'='*65}")
    for g in games:
        name = g["name"]
        rounds = g["rounds"]

        if g["has_summary"]:
            scenario = g.get("scenario", "?")
            completed = g.get("rounds_completed", "?")
            total = g.get("total_rounds", "?")
            time_s = g.get("total_time", 0)
            time_min = time_s / 60 if time_s else 0
            status = f"COMPLETE ({completed}/{total} rounds, {time_min:.0f}min)"
        elif g["has_checkpoint"]:
            ckpt_round = g.get("checkpoint_round", "?")
            total = g.get("total_rounds", "?")
            status = f"RESUMABLE (round {ckpt_round}/{total})"
        else:
            status = f"{rounds} round files"

        print(f"  {name}  --  {status}")
        if g["has_checkpoint"] and not g["has_summary"]:
            print(f"    Resume: python run.py resume logs/{name}")

    print()


# ======================================================================
# CLI argument parser
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="WarGame: Suwalki Gap Crisis Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Presets:\n"
            "  quick          4 countries (PL,RU,US,DE), 2 rounds\n"
            "  medium         7 countries, 5 rounds\n"
            "  full           All countries, 10 rounds\n"
            "  nato-vs-russia 20 countries, 10 rounds\n"
            "\n"
            "Examples:\n"
            "  python run.py play --preset quick\n"
            "  python run.py play --countries PL RU US --rounds 3\n"
            "  python run.py resume logs/game_20260213_120000\n"
            "  python run.py list\n"
            "  python run.py view\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- play ---
    play_parser = subparsers.add_parser("play", help="Start a new game")
    play_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    play_parser.add_argument("--rounds", type=int, help="Override number of rounds")
    play_parser.add_argument("--backend", choices=["ollama", "deepseek"], help="Override LLM backend")
    play_parser.add_argument("--model", help="Override model name")
    play_parser.add_argument(
        "--countries", nargs="*",
        help="Only include specific countries (codes, e.g. PL RU US DE)",
    )
    play_parser.add_argument(
        "--preset", choices=list(PRESETS.keys()),
        help="Use a named preset configuration",
    )
    play_parser.add_argument(
        "--auto-open", action="store_true",
        help="Auto-open browser viewer after game completes",
    )

    # --- resume ---
    resume_parser = subparsers.add_parser("resume", help="Resume a game from checkpoint")
    resume_parser.add_argument("game_dir", help="Path to the game directory to resume")
    resume_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    resume_parser.add_argument("--backend", choices=["ollama", "deepseek"], help="Override LLM backend")
    resume_parser.add_argument("--model", help="Override model name")

    # --- view ---
    view_parser = subparsers.add_parser("view", help="Start the viewer server")
    view_parser.add_argument("game_dir", nargs="?", default=None, help="Specific game to view")
    view_parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")

    # --- list ---
    list_parser = subparsers.add_parser("list", help="List past game sessions")
    list_parser.add_argument("--logs-dir", default="logs", help="Logs directory (default: logs)")

    return parser


# ======================================================================
# Legacy fallback: bare `python run.py` with old-style args
# ======================================================================

def _is_legacy_invocation(argv: list[str]) -> bool:
    """Detect if the user is using old-style arguments (no subcommand)."""
    if not argv:
        return True  # bare `python run.py`
    # If first arg starts with -- it's legacy style
    if argv[0].startswith("--"):
        return True
    # If first arg is a known subcommand, it's new style
    known_commands = {"play", "resume", "view", "list"}
    if argv[0] in known_commands:
        return False
    return True


async def _legacy_main(argv: list[str]) -> None:
    """Handle legacy invocation (backward compatible)."""
    # Parse with old-style parser
    legacy_parser = argparse.ArgumentParser(
        description="WarGame: Suwalki Gap Crisis Simulation"
    )
    legacy_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    legacy_parser.add_argument("--rounds", type=int, help="Override number of rounds")
    legacy_parser.add_argument(
        "--backend", choices=["ollama", "deepseek"], help="Override LLM backend",
    )
    legacy_parser.add_argument("--model", help="Override model name")
    legacy_parser.add_argument(
        "--countries", nargs="*",
        help="Only include specific countries (codes, e.g. PL RU US DE)",
    )
    legacy_parser.add_argument(
        "--preset", choices=list(PRESETS.keys()),
        help="Use a named preset configuration",
    )
    legacy_parser.add_argument(
        "--auto-open", action="store_true",
        help="Auto-open browser viewer after game completes",
    )
    args = legacy_parser.parse_args(argv)
    await cmd_play(args)


# ======================================================================
# Entry point
# ======================================================================

def main():
    print("=" * 60)
    print("  WARGAME: SUWALKI GAP CRISIS SIMULATION")
    print("  Multi-Agent Geopolitical Wargame")
    print("=" * 60)
    print()

    argv = sys.argv[1:]

    if _is_legacy_invocation(argv):
        asyncio.run(_legacy_main(argv))
        return

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "play":
        asyncio.run(cmd_play(args))
    elif args.command == "resume":
        asyncio.run(cmd_resume(args))
    elif args.command == "view":
        cmd_view(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
