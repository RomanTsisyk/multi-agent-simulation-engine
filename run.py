#!/usr/bin/env python3
"""WarGame: Multi-Agent Geopolitical Simulation

Entry point that reads config.yaml and scenario files, builds the
configuration dictionary expected by engine.Game, and runs the full
game loop.
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from engine.game import Game


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
    for key, description in mil.items():
        country = _infer_country(key)
        location = _infer_location(key)
        military_units.append({
            "name": key,
            "country": country,
            "type": "ground",
            "location": location,
            "readiness": 7,
            "strength": 7,
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

    return {
        "game_time": "Day 1, 06:00 CET",
        "nato_alert_level": "elevated",
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
        },
        "logs_dir": game_cfg.get("logs_dir", "logs"),
    }


async def async_main(args: argparse.Namespace) -> None:
    """Async entry point -- load everything and run the game."""

    # Resolve config path
    config_path = Path(args.config).resolve()
    project_root = config_path.parent

    # Load configuration
    print("Loading configuration...")
    raw_config = _load_config(str(config_path))

    # Load scenario
    game_cfg = raw_config.get("game", {})
    scenario_path = game_cfg.get("scenario", "scenarios/suwalki_gap.yaml")
    print(f"Loading scenario: {scenario_path}")
    scenario = _load_scenario(project_root, scenario_path)

    # Load countries
    countries_dir = game_cfg.get("countries_dir", "countries")
    country_filter = [c.upper() for c in args.countries] if args.countries else None
    print(f"Loading countries from: {countries_dir}")
    countries = _load_countries(project_root, countries_dir, country_filter)

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
        rounds_override=args.rounds,
    )

    # Create and run the game
    game = Game(config=game_config)

    try:
        await game.setup()
        await game.run()
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user.")
    except ConnectionError as e:
        print(f"\nERROR: Cannot connect to LLM backend: {e}")
        print("Make sure Ollama is running: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await game.close()


def main():
    parser = argparse.ArgumentParser(
        description="WarGame: Suwalki Gap Crisis Simulation"
    )
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--rounds", type=int, help="Override number of rounds"
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "deepseek"],
        help="Override LLM backend",
    )
    parser.add_argument("--model", help="Override model name")
    parser.add_argument(
        "--countries",
        nargs="*",
        help="Only include specific countries (codes, e.g. PL RU US DE)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  WARGAME: SUWALKI GAP CRISIS SIMULATION")
    print("  Multi-Agent Geopolitical Wargame")
    print("=" * 60)
    print()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
