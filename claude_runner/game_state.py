#!/usr/bin/env python3
"""Claude Code Game Runner -- CLI for state I/O.

Wraps the existing WarGame engine so that Claude Code can act as the
LLM backend.  Each subcommand reads or writes game state via the same
engine classes (WorldState, save_checkpoint, RoundLogger) used by the
normal ``run.py`` pipeline.

Usage::

    python3 claude_runner/game_state.py init --preset suwalki-claude
    python3 claude_runner/game_state.py status --game-dir logs/game_XXX
    python3 claude_runner/game_state.py briefing --game-dir logs/game_XXX [--country PL]
    python3 claude_runner/game_state.py country-context --game-dir logs/game_XXX --countries PL LT LV EE FI
    python3 claude_runner/game_state.py apply --game-dir logs/game_XXX --resolution /tmp/resolution.json --round 1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so engine imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import yaml

from engine.checkpoint import save_checkpoint, load_checkpoint
from engine.round_logger import RoundLogger
from engine.world_state import WorldState
from presets import PRESETS, get_preset
from run import _load_scenario, _load_countries, _build_initial_state


# ======================================================================
# Subcommand: init
# ======================================================================

def cmd_init(args: argparse.Namespace) -> None:
    """Initialise a new game from a preset and write the first checkpoint."""
    preset_name = args.preset
    preset = get_preset(preset_name)
    print(f"Preset: {preset_name} -- {preset['description']}")

    country_filter = preset["countries"]
    total_rounds = preset["rounds"]

    # Load scenario
    config_path = (_PROJECT_ROOT / args.config).resolve()
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    game_cfg = raw_config.get("game", {})
    scenario_path = game_cfg.get("scenario", "scenarios/suwalki_gap.yaml")
    scenario = _load_scenario(_PROJECT_ROOT, scenario_path)

    # Load countries
    countries_dir = game_cfg.get("countries_dir", "countries")
    countries = _load_countries(_PROJECT_ROOT, countries_dir, country_filter)
    if not countries:
        print("ERROR: No countries loaded.")
        sys.exit(1)
    print(f"Loaded {len(countries)} countries: {', '.join(sorted(countries.keys()))}")

    # Build initial state
    initial_state = _build_initial_state(scenario)

    # Construct WorldState
    from engine.world_state import MilitaryUnit
    ws = WorldState()
    for u in initial_state.get("military_units", []):
        ws.military_units.append(MilitaryUnit(**u))
    ws.nato_alert_level = initial_state.get("nato_alert_level", "elevated")
    ws.game_time = initial_state.get("game_time", "Day 1, 00:00")
    ws.corridor_control = initial_state.get("corridor_control", "contested")
    ws.nuclear_posture = initial_state.get("nuclear_posture", {})
    ws.military_alerts = initial_state.get("military_alerts", {})
    ws.markets = initial_state.get("markets", {})
    ws.diplomatic_relations = initial_state.get("diplomatic_relations", {})
    ws.nato_consensus = initial_state.get("nato_consensus", {})
    ws.public_opinion = initial_state.get("public_opinion", {})
    ws.sanctions = initial_state.get("sanctions", [])
    ws.trade_disruptions = initial_state.get("trade_disruptions", [])
    ws.treaties_invoked = initial_state.get("treaties_invoked", [])
    ws.un_resolutions = initial_state.get("un_resolutions", [])
    ws.recent_events = initial_state.get("recent_events", [])
    ws.media_headlines = initial_state.get("media_headlines", [])

    # Create game directory
    logs_dir = game_cfg.get("logs_dir", "logs")
    logger = RoundLogger.create_for_new_game(base_dir=logs_dir)
    game_dir = logger.game_dir
    print(f"Game directory: {game_dir}")

    # Save initial checkpoint (round 0 = not yet started)
    save_checkpoint(
        game_dir=game_dir,
        round_completed=0,
        world_state_dict=ws.to_dict(),
        diplomatic_inbox=[],
        previous_round_summary="",
        corridor_hold_rounds=0,
        corridor_was_contested=False,
        gm_round_history=[],
        agent_histories={},
        total_rounds=total_rounds,
        config={
            "scenario": {
                "name": scenario.get("name", "Suwalki Gap Crisis"),
                "rounds": total_rounds,
                "countries": countries,
            }
        },
    )

    # Save a metadata file for easy reference
    meta = {
        "preset": preset_name,
        "scenario": scenario.get("name", ""),
        "total_rounds": total_rounds,
        "country_codes": sorted(countries.keys()),
        "runner": "claude-code",
    }
    meta_path = game_dir / "game_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nGame initialised. Next step:")
    print(f"  python3 claude_runner/game_state.py briefing --game-dir {game_dir}")


# ======================================================================
# Subcommand: status
# ======================================================================

def cmd_status(args: argparse.Namespace) -> None:
    """Show current game status from checkpoint."""
    game_dir = Path(args.game_dir).resolve()
    checkpoint = load_checkpoint(game_dir)

    rc = checkpoint["round_completed"]
    total = checkpoint["total_rounds"]
    ws = WorldState.from_dict(checkpoint["world_state"])

    print(f"Game directory: {game_dir}")
    print(f"Round: {rc}/{total} completed")
    print(f"Game time: {ws.game_time}")
    print(f"NATO alert: {ws.nato_alert_level}")
    print(f"Corridor: {ws.corridor_control}")
    print(f"Military units: {len(ws.military_units)}")
    print(f"Nuclear posture: {ws.nuclear_posture}")

    if ws.recent_events:
        print("\nRecent events:")
        for ev in ws.recent_events[-5:]:
            print(f"  - {ev}")

    # Check for round log files
    round_files = sorted(game_dir.glob("round_*.json"))
    if round_files:
        print(f"\nRound logs: {len(round_files)} files")
        for rf in round_files:
            print(f"  {rf.name}")


# ======================================================================
# Subcommand: briefing
# ======================================================================

def cmd_briefing(args: argparse.Namespace) -> None:
    """Print the world state briefing (optionally for a specific country)."""
    game_dir = Path(args.game_dir).resolve()
    checkpoint = load_checkpoint(game_dir)
    ws = WorldState.from_dict(checkpoint["world_state"])

    country = args.country.upper() if args.country else None
    briefing = ws.to_briefing(for_country=country)
    print(briefing)


# ======================================================================
# Subcommand: country-context
# ======================================================================

def cmd_country_context(args: argparse.Namespace) -> None:
    """Print full context for specified countries (YAML + briefing + inbox)."""
    game_dir = Path(args.game_dir).resolve()
    checkpoint = load_checkpoint(game_dir)
    ws = WorldState.from_dict(checkpoint["world_state"])
    diplomatic_inbox = checkpoint.get("diplomatic_inbox", [])

    codes = [c.upper() for c in args.countries]

    # Load country YAMLs
    config_path = (_PROJECT_ROOT / args.config).resolve()
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)
    countries_dir = raw_config.get("game", {}).get("countries_dir", "countries")
    all_countries = _load_countries(_PROJECT_ROOT, countries_dir, codes)

    for code in codes:
        print(f"\n{'='*70}")
        print(f"  COUNTRY CONTEXT: {code}")
        print(f"{'='*70}")

        # Country YAML profile
        if code in all_countries:
            cfg = all_countries[code]
            print(f"\n--- Profile ---")
            print(f"Name: {cfg.get('name', code)}")
            print(f"Alliances: {', '.join(cfg.get('alliances', []))}")
            print(f"Military strength: {cfg.get('military_strength', '?')}/10")
            print(f"Economic strength: {cfg.get('economic_strength', '?')}/10")
            print(f"Nuclear: {cfg.get('nuclear', False)}")
            leader = cfg.get("leader", "")
            if leader:
                print(f"Leader: {leader}")
            geo = cfg.get("geographic_relevance", "")
            if geo:
                # Truncate to first 500 chars for brevity
                print(f"Geographic relevance: {geo[:500].strip()}")
            # Print faction names if available
            factions = cfg.get("factions", [])
            if factions:
                print(f"Factions ({len(factions)}):")
                for fc in factions:
                    print(f"  - {fc.get('name', '?')} ({fc.get('role', '?')})")
        else:
            print(f"  WARNING: No YAML found for {code}")

        # Per-country briefing
        print(f"\n--- Situation Briefing ---")
        print(ws.to_briefing(for_country=code))

        # Diplomatic inbox
        incoming = _get_incoming_for(code, diplomatic_inbox)
        if incoming:
            print(f"\n--- Diplomatic Inbox ---")
            for msg in incoming:
                ch = msg.get("channel", "public").upper()
                sender = msg.get("from", "?")
                text = msg.get("message", msg.get("content", ""))
                print(f"  [{ch} from {sender}]: {text}")
        print()


def _get_incoming_for(country_code: str, inbox: list[dict]) -> list[dict]:
    """Filter diplomatic inbox for messages visible to country_code."""
    result = []
    for msg in inbox:
        channel = msg.get("channel", "public")
        to = msg.get("to", "").upper()
        if channel == "public":
            result.append(msg)
        elif to == country_code.upper():
            result.append(msg)
    return result


# ======================================================================
# Subcommand: apply
# ======================================================================

def cmd_apply(args: argparse.Namespace) -> None:
    """Apply a GM resolution to the world state and save checkpoint + round log."""
    game_dir = Path(args.game_dir).resolve()
    resolution_path = Path(args.resolution).resolve()
    round_num = args.round

    # Load current checkpoint
    checkpoint = load_checkpoint(game_dir)
    ws = WorldState.from_dict(checkpoint["world_state"])

    # Load resolution JSON
    resolution = json.loads(resolution_path.read_text(encoding="utf-8"))

    # Extract world_state_updates and apply (this runs cascading effects!)
    updates = resolution.get("world_state_updates", {})
    updates["round_number"] = round_num
    ws.apply_updates(updates)

    print(f"Applied updates for round {round_num}")
    print(f"  Game time: {ws.game_time}")
    print(f"  NATO alert: {ws.nato_alert_level}")
    print(f"  Corridor: {ws.corridor_control}")
    print(f"  Military units: {len(ws.military_units)}")

    # Save round log
    round_record = {
        "round": round_num,
        "runner": "claude-code",
        "briefing": resolution.get("briefing", ""),
        "narrative": resolution.get("narrative", ""),
        "country_decisions": resolution.get("country_decisions", []),
        "resolution": {
            "narrative": resolution.get("narrative", ""),
            "world_state_updates": updates,
            "events": resolution.get("events", []),
            "headlines": resolution.get("headlines", []),
            "surprises": resolution.get("surprises", []),
        },
        "world_state_after": ws.to_dict(),
    }
    logger = RoundLogger(str(game_dir))
    log_path = logger.log_round(round_num, round_record)
    print(f"  Round log: {log_path}")

    # Save checkpoint
    total_rounds = checkpoint.get("total_rounds", 10)
    # Preserve GM round history, add this round's summary
    gm_history = checkpoint.get("gm_round_history", [])
    gm_history.append({
        "round": round_num,
        "briefing_summary": resolution.get("narrative", "")[:200],
        "key_decisions": [
            d.get("country", "?") + ": " + (d.get("actions", ["?"])[0] if d.get("actions") else "?")
            for d in resolution.get("country_decisions", [])[:5]
        ],
        "resolution_summary": resolution.get("narrative", "")[:300],
    })
    # Keep only last 5
    if len(gm_history) > 5:
        gm_history = gm_history[-5:]

    ckpt_path = save_checkpoint(
        game_dir=game_dir,
        round_completed=round_num,
        world_state_dict=ws.to_dict(),
        diplomatic_inbox=resolution.get("diplomatic_messages", []),
        previous_round_summary=resolution.get("narrative", "")[:500],
        corridor_hold_rounds=checkpoint.get("corridor_hold_rounds", 0),
        corridor_was_contested=checkpoint.get("corridor_was_contested", False),
        gm_round_history=gm_history,
        agent_histories=checkpoint.get("agent_histories", {}),
        total_rounds=total_rounds,
        config=checkpoint.get("config_fingerprint"),
    )
    print(f"  Checkpoint: {ckpt_path}")

    # Print summary
    events = resolution.get("events", [])
    if events:
        print("\nKey events:")
        for ev in events:
            print(f"  - {ev}")

    headlines = resolution.get("headlines", [])
    if headlines:
        print("\nHeadlines:")
        for hl in headlines:
            print(f"  * {hl}")

    print(f"\nRound {round_num} complete. Next round: {round_num + 1}/{total_rounds}")


# ======================================================================
# CLI parser
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claude Code Game Runner -- state I/O CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialise a new game")
    p_init.add_argument(
        "--preset", required=True,
        choices=list(PRESETS.keys()),
        help="Preset to use",
    )
    p_init.add_argument("--config", default="config.yaml", help="Config file")

    # status
    p_status = sub.add_parser("status", help="Show game status")
    p_status.add_argument("--game-dir", required=True, help="Game directory")

    # briefing
    p_brief = sub.add_parser("briefing", help="Print situation briefing")
    p_brief.add_argument("--game-dir", required=True, help="Game directory")
    p_brief.add_argument("--country", default=None, help="Country code for perspective")

    # country-context
    p_ctx = sub.add_parser("country-context", help="Print country context")
    p_ctx.add_argument("--game-dir", required=True, help="Game directory")
    p_ctx.add_argument("--countries", nargs="+", required=True, help="Country codes")
    p_ctx.add_argument("--config", default="config.yaml", help="Config file")

    # apply
    p_apply = sub.add_parser("apply", help="Apply GM resolution")
    p_apply.add_argument("--game-dir", required=True, help="Game directory")
    p_apply.add_argument("--resolution", required=True, help="Path to resolution JSON")
    p_apply.add_argument("--round", type=int, required=True, help="Round number")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "briefing": cmd_briefing,
        "country-context": cmd_country_context,
        "apply": cmd_apply,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
