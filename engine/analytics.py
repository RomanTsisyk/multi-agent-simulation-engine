"""Post-game analytics -- generates a structured analysis after the simulation.

Reads all round logs from a game session and produces:
- Escalation timeline (tension score per round)
- Country aggression / diplomacy scores
- Pivotal moments (decisions that changed the course of events)
- Nuclear posture evolution
- Casualty and humanitarian summary
- Diplomatic message network
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def generate_analytics(game_dir: str | Path) -> dict[str, Any]:
    """Analyse a completed game and return a structured report.

    Args:
        game_dir: Path to the game session directory containing
            ``round_NNN.json`` files and ``game_summary.json``.

    Returns:
        A dictionary containing all analytics sections.
    """
    game_dir = Path(game_dir)
    rounds = _load_rounds(game_dir)
    summary = _load_summary(game_dir)

    if not rounds:
        logger.warning("No round data found in %s", game_dir)
        return {"error": "No round data found"}

    report: dict[str, Any] = {
        "game_dir": str(game_dir),
        "rounds_analysed": len(rounds),
    }

    report["escalation_timeline"] = _escalation_timeline(rounds)
    report["country_scores"] = _country_scores(rounds)
    report["pivotal_moments"] = _pivotal_moments(rounds)
    report["nuclear_evolution"] = _nuclear_evolution(rounds)
    report["casualty_summary"] = _casualty_summary(rounds)
    report["humanitarian_summary"] = _humanitarian_summary(rounds)
    report["diplomatic_network"] = _diplomatic_network(rounds)
    report["end_condition"] = summary.get("end_condition")

    return report


def format_analytics_text(report: dict[str, Any]) -> str:
    """Format an analytics report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  POST-GAME ANALYTICS REPORT")
    lines.append("=" * 70)
    lines.append(f"Rounds analysed: {report.get('rounds_analysed', 0)}")
    lines.append("")

    # End condition
    ec = report.get("end_condition")
    if ec:
        lines.append(f"GAME ENDED BY: {ec.get('description', 'N/A')}")
        lines.append(f"  Winner: {ec.get('winner', 'N/A')}")
        lines.append("")

    # Escalation timeline
    lines.append("ESCALATION TIMELINE:")
    for entry in report.get("escalation_timeline", []):
        bar = "#" * entry.get("tension", 0)
        lines.append(
            f"  Round {entry['round']:2d} | {bar:<20s} "
            f"({entry.get('tension', 0)}/10) {entry.get('note', '')}"
        )
    lines.append("")

    # Country scores
    lines.append("COUNTRY SCORES:")
    for code, scores in sorted(report.get("country_scores", {}).items()):
        lines.append(
            f"  {code}: actions={scores.get('total_actions', 0)}, "
            f"military={scores.get('military_actions', 0)}, "
            f"diplomatic={scores.get('diplomatic_actions', 0)}, "
            f"messages_sent={scores.get('messages_sent', 0)}"
        )
    lines.append("")

    # Pivotal moments
    pivotal = report.get("pivotal_moments", [])
    if pivotal:
        lines.append("PIVOTAL MOMENTS:")
        for pm in pivotal:
            lines.append(
                f"  Round {pm['round']}: [{pm.get('country', '?')}] "
                f"{pm.get('description', '?')}"
            )
        lines.append("")

    # Nuclear evolution
    nuc = report.get("nuclear_evolution", [])
    if nuc:
        lines.append("NUCLEAR POSTURE EVOLUTION:")
        for entry in nuc:
            postures = ", ".join(
                f"{c}={p}" for c, p in entry.get("postures", {}).items()
            )
            lines.append(f"  Round {entry['round']}: {postures}")
        lines.append("")

    # Casualties
    cas = report.get("casualty_summary", {})
    if cas:
        lines.append("CASUALTY SUMMARY (final state):")
        for unit, data in sorted(cas.items()):
            if data.get("casualties", 0) > 0:
                lines.append(
                    f"  {unit} ({data.get('country', '?')}): "
                    f"casualties={data['casualties']}, "
                    f"strength={data.get('strength', '?')}/10, "
                    f"morale={data.get('morale', '?')}/10"
                )
        lines.append("")

    # Humanitarian
    hum = report.get("humanitarian_summary", {})
    if hum.get("total_refugees", 0) > 0:
        lines.append("HUMANITARIAN SUMMARY:")
        lines.append(f"  Total refugees: ~{hum['total_refugees']:,}")
        for country, level in hum.get("crisis_levels", {}).items():
            lines.append(f"  {country} crisis level: {level}/10")
        lines.append("")

    # Diplomatic network
    diplo = report.get("diplomatic_network", {})
    if diplo:
        lines.append("DIPLOMATIC MESSAGE NETWORK:")
        lines.append(f"  Total messages: {diplo.get('total_messages', 0)}")
        for pair, count in sorted(
            diplo.get("pair_counts", {}).items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            lines.append(f"  {pair}: {count} messages")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


# ======================================================================
# Internal analysis functions
# ======================================================================

def _load_rounds(game_dir: Path) -> list[dict]:
    """Load all round JSON files, sorted by round number."""
    rounds = []
    for path in sorted(game_dir.glob("round_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rounds.append(data)
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
    return rounds


def _load_summary(game_dir: Path) -> dict:
    """Load game_summary.json if present."""
    path = game_dir / "game_summary.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _escalation_timeline(rounds: list[dict]) -> list[dict]:
    """Compute a rough tension score (1-10) per round."""
    timeline = []
    for rd in rounds:
        rnum = rd.get("round", 0)
        ws = rd.get("world_state_after", {})

        score = 0
        note_parts: list[str] = []

        # NATO alert level
        nato = ws.get("nato_alert_level", "normal")
        if nato == "article5":
            score += 3
            note_parts.append("Article 5")
        elif nato == "high":
            score += 2
        elif nato == "elevated":
            score += 1

        # Military engagements (check events/surprises for combat keywords)
        events = rd.get("resolution", {}).get("events", [])
        surprises = rd.get("resolution", {}).get("surprises", [])
        combat_words = {"attack", "combat", "strike", "offensive", "assault", "fire", "casualt"}
        all_events = " ".join(events + surprises).lower()
        if any(w in all_events for w in combat_words):
            score += 2
            note_parts.append("combat")

        # Nuclear posture
        nuc = ws.get("nuclear_posture", {})
        max_nuc = 0
        for posture in nuc.values():
            levels = ["peacetime", "elevated", "dispersal", "launch_ready"]
            idx = levels.index(posture) if posture in levels else 0
            max_nuc = max(max_nuc, idx)
        if max_nuc >= 3:
            score += 3
            note_parts.append(f"nuclear:{levels[max_nuc]}")
        elif max_nuc >= 2:
            score += 1

        # Sanctions
        sanctions = ws.get("sanctions", [])
        if len(sanctions) > 3:
            score += 1

        score = min(10, max(1, score))
        timeline.append({
            "round": rnum,
            "tension": score,
            "note": ", ".join(note_parts) if note_parts else "",
        })

    return timeline


def _country_scores(rounds: list[dict]) -> dict[str, dict]:
    """Count actions and categorise them per country."""
    scores: dict[str, dict] = {}

    military_keywords = {
        "deploy", "mobiliz", "attack", "strike", "patrol", "intercept",
        "reinforce", "fortif", "brigade", "battalion", "division",
    }
    diplomatic_keywords = {
        "negotiate", "diplomat", "propose", "ambassador", "treaty",
        "ceasefire", "summit", "dialogue", "channel",
    }

    for rd in rounds:
        for dec in rd.get("country_decisions", []):
            code = dec.get("country", "?")
            if code not in scores:
                scores[code] = {
                    "total_actions": 0,
                    "military_actions": 0,
                    "diplomatic_actions": 0,
                    "messages_sent": 0,
                }

            actions = dec.get("actions", [])
            scores[code]["total_actions"] += len(actions)

            for action in actions:
                al = action.lower()
                if any(kw in al for kw in military_keywords):
                    scores[code]["military_actions"] += 1
                if any(kw in al for kw in diplomatic_keywords):
                    scores[code]["diplomatic_actions"] += 1

            scores[code]["messages_sent"] += len(
                dec.get("diplomatic_messages", [])
            )

    return scores


def _pivotal_moments(rounds: list[dict]) -> list[dict]:
    """Identify key turning points based on surprise events and escalation."""
    pivotal = []
    pivot_keywords = {
        "nuclear", "article 5", "ceasefire", "invasion", "retreat",
        "surrender", "breakthrough", "collapse",
    }
    # Match escalation but not de-escalation
    escalation_patterns = [" escalat", "escalat ", "escalation", "escalate", "escalating"]

    for rd in rounds:
        rnum = rd.get("round", 0)
        resolution = rd.get("resolution", {})

        # Check surprises
        for surprise in resolution.get("surprises", []):
            sl = surprise.lower()
            # Check keywords
            if any(kw in sl for kw in pivot_keywords):
                pivotal.append({
                    "round": rnum,
                    "country": "GM",
                    "description": surprise,
                    "type": "surprise",
                })
            # Check escalation patterns (but not de-escalation)
            elif any(pattern in sl for pattern in escalation_patterns) and "de-escalat" not in sl and "deescalat" not in sl:
                pivotal.append({
                    "round": rnum,
                    "country": "GM",
                    "description": surprise,
                    "type": "surprise",
                })

        # Check country actions for escalatory moves
        for dec in rd.get("country_decisions", []):
            code = dec.get("country", "?")
            for action in dec.get("actions", []):
                al = action.lower()
                # Check keywords
                if any(kw in al for kw in pivot_keywords):
                    pivotal.append({
                        "round": rnum,
                        "country": code,
                        "description": action,
                        "type": "action",
                    })
                # Check escalation patterns (but not de-escalation)
                elif any(pattern in al for pattern in escalation_patterns) and "de-escalat" not in al and "deescalat" not in al:
                    pivotal.append({
                        "round": rnum,
                        "country": code,
                        "description": action,
                        "type": "action",
                    })

    return pivotal


def _nuclear_evolution(rounds: list[dict]) -> list[dict]:
    """Track nuclear posture changes across rounds."""
    evolution = []
    prev: dict[str, str] = {}

    for rd in rounds:
        rnum = rd.get("round", 0)
        ws = rd.get("world_state_after", {})
        postures = ws.get("nuclear_posture", {})
        if postures and postures != prev:
            evolution.append({"round": rnum, "postures": dict(postures)})
            prev = dict(postures)

    return evolution


def _casualty_summary(rounds: list[dict]) -> dict[str, dict]:
    """Extract final casualty state from the last round."""
    if not rounds:
        return {}

    last_ws = rounds[-1].get("world_state_after", {})
    units = last_ws.get("military_units", [])
    result = {}
    for u in units:
        name = u.get("name", "?")
        result[name] = {
            "country": u.get("country", "?"),
            "casualties": u.get("casualties", 0),
            "strength": u.get("strength", "?"),
            "morale": u.get("morale", "?"),
            "supply_level": u.get("supply_level", "?"),
        }
    return result


def _humanitarian_summary(rounds: list[dict]) -> dict:
    """Summarise refugee flows and crisis levels from final state."""
    if not rounds:
        return {}

    last_ws = rounds[-1].get("world_state_after", {})
    flows = last_ws.get("refugee_flows", [])
    total = sum(f.get("count", 0) for f in flows)
    crisis = last_ws.get("humanitarian_crisis_level", {})

    return {
        "total_refugees": total,
        "flows": flows,
        "crisis_levels": crisis,
    }


def _diplomatic_network(rounds: list[dict]) -> dict:
    """Build a summary of diplomatic message exchanges."""
    total = 0
    pair_counts: dict[str, int] = {}

    for rd in rounds:
        for msg in rd.get("diplomatic_messages", []):
            total += 1
            sender = msg.get("from", "?")
            receiver = msg.get("to", "?")
            pair = f"{sender} -> {receiver}"
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    return {"total_messages": total, "pair_counts": pair_counts}
