"""World state tracker for the wargame simulation.

Maintains all mutable game state: military positions, economic indicators,
diplomatic relations, NATO status, public opinion, and event history.  The
WorldState dataclass is the single source of truth that is read by every
agent and updated exclusively by the Game Master after each round.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MilitaryUnit:
    """A single military formation or asset on the board."""

    name: str
    country: str
    type: str  # "ground", "air", "naval", "special"
    location: str
    readiness: int  # 1-10
    strength: int  # 1-10
    casualties: int = 0  # cumulative casualties (abstract units)
    supply_level: int = 10  # 1-10 (ammo, fuel, spare parts)
    morale: int = 7  # 1-10

    def summary(self) -> str:
        return (
            f"{self.name} ({self.country} {self.type}) "
            f"@ {self.location} "
            f"[readiness={self.readiness}, strength={self.strength}, "
            f"supply={self.supply_level}, morale={self.morale}, "
            f"casualties={self.casualties}]"
        )


@dataclass
class WorldState:
    """Complete snapshot of the game world at any point in time.

    Every field uses ``default_factory`` so that fresh instances start with
    empty collections rather than sharing mutable defaults.
    """

    round_number: int = 0
    game_time: str = "Day 1, 00:00"

    # ------------------------------------------------------------------
    # Military
    # ------------------------------------------------------------------
    military_units: list[MilitaryUnit] = field(default_factory=list)
    military_alerts: dict[str, str] = field(default_factory=dict)  # country -> alert level

    # ------------------------------------------------------------------
    # Economic
    # ------------------------------------------------------------------
    markets: dict[str, Any] = field(default_factory=dict)  # oil_price, euro_usd, ...
    sanctions: list[dict] = field(default_factory=list)  # {"from": ..., "target": ..., "type": ...}
    trade_disruptions: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Diplomatic
    # ------------------------------------------------------------------
    diplomatic_relations: dict[str, dict[str, int]] = field(default_factory=dict)  # country -> country -> -10..10
    treaties_invoked: list[str] = field(default_factory=list)
    un_resolutions: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # NATO
    # ------------------------------------------------------------------
    nato_alert_level: str = "normal"  # normal, elevated, high, article5
    nato_consensus: dict[str, str] = field(default_factory=dict)  # country -> position

    # ------------------------------------------------------------------
    # Nuclear posture
    # ------------------------------------------------------------------
    # Levels: peacetime -> elevated -> dispersal -> launch_ready -> tactical_use -> strategic
    nuclear_posture: dict[str, str] = field(default_factory=dict)  # country -> posture level

    # ------------------------------------------------------------------
    # Public opinion
    # ------------------------------------------------------------------
    public_opinion: dict[str, dict] = field(default_factory=dict)  # country -> {war_support, government_approval}

    # ------------------------------------------------------------------
    # Humanitarian
    # ------------------------------------------------------------------
    refugee_flows: list[dict] = field(default_factory=list)  # {"from", "to", "count", "status"}
    humanitarian_crisis_level: dict[str, int] = field(default_factory=dict)  # country -> 1-10

    # ------------------------------------------------------------------
    # Cyber & information warfare
    # ------------------------------------------------------------------
    cyber_operations: list[dict] = field(default_factory=list)  # {"attacker", "target", "type", "severity", "infrastructure_affected"}
    infrastructure_status: dict[str, dict[str, int]] = field(default_factory=dict)  # country -> {"power_grid": 1-10, "comms": 1-10, "financial": 1-10, "military_c2": 1-10}

    # ------------------------------------------------------------------
    # Events & media
    # ------------------------------------------------------------------
    recent_events: list[str] = field(default_factory=list)
    media_headlines: list[str] = field(default_factory=list)

    # ==================================================================
    # Serialisation helpers
    # ==================================================================

    def to_dict(self) -> dict:
        """Serialise the entire world state to a JSON-safe dictionary."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WorldState":
        """Reconstruct a WorldState from a previously serialised dictionary."""
        data = copy.deepcopy(data)
        # Reconstitute MilitaryUnit objects
        raw_units = data.pop("military_units", [])
        units = [MilitaryUnit(**u) for u in raw_units]
        state = cls(**data)
        state.military_units = units
        return state

    def to_json(self, indent: int = 2) -> str:
        """Convenience wrapper -- returns a pretty-printed JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    # ==================================================================
    # Briefing generation
    # ==================================================================

    def to_briefing(self, for_country: str | None = None) -> str:
        """Generate a human-readable situation briefing.

        If *for_country* is provided the briefing is written from that
        country's perspective (highlighting its own forces, relations, and
        public opinion).  Otherwise a neutral overview is produced.
        """
        lines: list[str] = []
        lines.append(f"=== SITUATION BRIEFING -- Round {self.round_number} ===")
        lines.append(f"Game time: {self.game_time}")
        lines.append("")

        # --- NATO status ---
        lines.append(f"NATO Alert Level: {self.nato_alert_level.upper()}")
        if self.nato_consensus:
            lines.append("NATO member positions:")
            for country, position in sorted(self.nato_consensus.items()):
                lines.append(f"  {country}: {position}")
        lines.append("")

        # --- Nuclear posture ---
        if self.nuclear_posture:
            lines.append("NUCLEAR POSTURE:")
            for country, posture in sorted(self.nuclear_posture.items()):
                warning = " *** CRITICAL ***" if posture in ("launch_ready", "tactical_use", "strategic") else ""
                lines.append(f"  {country}: {posture.upper()}{warning}")
            lines.append("")

        # --- Military overview ---
        lines.append("MILITARY SITUATION:")
        if for_country:
            own = [u for u in self.military_units if u.country == for_country]
            others = [u for u in self.military_units if u.country != for_country]
            if own:
                lines.append(f"  Your forces ({for_country}):")
                for u in own:
                    lines.append(f"    - {u.summary()}")
            if others:
                lines.append("  Known foreign deployments:")
                for u in others:
                    lines.append(f"    - {u.summary()}")
        else:
            for u in self.military_units:
                lines.append(f"  - {u.summary()}")

        alert_countries = self.military_alerts
        if for_country and for_country in alert_countries:
            lines.append(f"  Your alert level: {alert_countries[for_country]}")
        elif alert_countries:
            lines.append("  Alert levels:")
            for c, lvl in sorted(alert_countries.items()):
                lines.append(f"    {c}: {lvl}")
        lines.append("")

        # --- Economic ---
        lines.append("ECONOMIC SITUATION:")
        if self.markets:
            for key, val in self.markets.items():
                lines.append(f"  {key}: {val}")
        if self.sanctions:
            lines.append("  Active sanctions:")
            for s in self.sanctions:
                lines.append(f"    {s.get('from', '?')} -> {s.get('target', '?')}: {s.get('type', '?')}")
        if self.trade_disruptions:
            lines.append("  Trade disruptions:")
            for td in self.trade_disruptions:
                lines.append(f"    - {td}")
        lines.append("")

        # --- Diplomatic ---
        lines.append("DIPLOMATIC SITUATION:")
        if for_country and for_country in self.diplomatic_relations:
            lines.append(f"  Your relations ({for_country}):")
            for other, score in sorted(self.diplomatic_relations[for_country].items()):
                label = _relation_label(score)
                lines.append(f"    {other}: {score:+d} ({label})")
        elif self.diplomatic_relations:
            for c1, rels in sorted(self.diplomatic_relations.items()):
                for c2, score in sorted(rels.items()):
                    lines.append(f"  {c1} <-> {c2}: {score:+d}")
        if self.treaties_invoked:
            lines.append("  Treaties invoked:")
            for t in self.treaties_invoked:
                lines.append(f"    - {t}")
        if self.un_resolutions:
            lines.append("  UN resolutions:")
            for r in self.un_resolutions:
                lines.append(f"    - {r}")
        lines.append("")

        # --- Public opinion ---
        if for_country and for_country in self.public_opinion:
            po = self.public_opinion[for_country]
            lines.append("DOMESTIC PUBLIC OPINION:")
            lines.append(f"  War support: {po.get('war_support', 'N/A')}%")
            lines.append(f"  Government approval: {po.get('government_approval', 'N/A')}%")
            lines.append("")
        elif self.public_opinion:
            lines.append("PUBLIC OPINION:")
            for c, po in sorted(self.public_opinion.items()):
                lines.append(
                    f"  {c}: war_support={po.get('war_support', '?')}%, "
                    f"gov_approval={po.get('government_approval', '?')}%"
                )
            lines.append("")

        # --- Humanitarian ---
        if self.refugee_flows or self.humanitarian_crisis_level:
            lines.append("HUMANITARIAN SITUATION:")
            if self.refugee_flows:
                total = sum(f.get("count", 0) for f in self.refugee_flows)
                lines.append(f"  Total displaced persons: ~{total:,}")
                for flow in self.refugee_flows[-5:]:  # last 5 flows
                    lines.append(
                        f"  {flow.get('from','?')} -> {flow.get('to','?')}: "
                        f"~{flow.get('count', 0):,} ({flow.get('status', 'ongoing')})"
                    )
            if self.humanitarian_crisis_level:
                for country, level in sorted(self.humanitarian_crisis_level.items()):
                    severity = "CRITICAL" if level >= 8 else "severe" if level >= 5 else "moderate" if level >= 3 else "low"
                    lines.append(f"  {country} crisis level: {level}/10 ({severity})")
            lines.append("")

        # --- Cyber & infrastructure ---
        if self.cyber_operations or self.infrastructure_status:
            lines.append("CYBER & INFRASTRUCTURE:")
            if self.cyber_operations:
                # Show last 5 cyber ops
                for op in self.cyber_operations[-5:]:
                    attacker = op.get("attacker", "?")
                    target = op.get("target", "?")
                    op_type = op.get("type", "?")
                    severity = op.get("severity", "?")
                    lines.append(
                        f"  [{severity}] {attacker} -> {target}: {op_type}"
                    )
            if for_country and for_country in self.infrastructure_status:
                infra = self.infrastructure_status[for_country]
                lines.append(f"  Your infrastructure status ({for_country}):")
                for system, level in sorted(infra.items()):
                    status = "CRITICAL" if level <= 3 else "degraded" if level <= 6 else "operational"
                    lines.append(f"    {system}: {level}/10 ({status})")
            elif self.infrastructure_status:
                for country, infra in sorted(self.infrastructure_status.items()):
                    vals = ", ".join(f"{k}={v}" for k, v in sorted(infra.items()))
                    lines.append(f"  {country}: {vals}")
            lines.append("")

        # --- Recent events ---
        if self.recent_events:
            lines.append("RECENT EVENTS:")
            for ev in self.recent_events:
                lines.append(f"  - {ev}")
            lines.append("")

        # --- Headlines ---
        if self.media_headlines:
            lines.append("MEDIA HEADLINES:")
            for hl in self.media_headlines:
                lines.append(f"  * {hl}")
            lines.append("")

        return "\n".join(lines)

    # ==================================================================
    # Mutation -- apply GM updates
    # ==================================================================

    def apply_updates(self, updates: dict) -> None:
        """Apply a dictionary of updates produced by the Game Master.

        Supported top-level keys (all optional):

        - ``round_number``, ``game_time`` -- scalars, overwritten directly.
        - ``military_units_add`` -- list of dicts; each is appended as a new
          :class:`MilitaryUnit`.
        - ``military_units_remove`` -- list of unit *names* to remove.
        - ``military_units_update`` -- list of dicts with ``name`` and any
          fields to overwrite on the matching unit.
        - ``military_alerts`` -- merged into existing alerts.
        - ``markets`` -- merged into existing market data.
        - ``sanctions_add`` -- list of new sanctions to append.
        - ``trade_disruptions_add`` -- list of strings to append.
        - ``diplomatic_relations`` -- nested dict merged into existing.
        - ``treaties_invoked_add`` -- list of strings to append.
        - ``un_resolutions_add`` -- list of strings to append.
        - ``nato_alert_level`` -- overwrites.
        - ``nato_consensus`` -- merged.
        - ``public_opinion`` -- nested dict merged into existing.
        - ``recent_events`` -- replaces (these are per-round).
        - ``media_headlines`` -- replaces (these are per-round).
        """
        if not updates:
            return

        # Scalars
        if "round_number" in updates:
            self.round_number = updates["round_number"]
        if "game_time" in updates:
            self.game_time = updates["game_time"]
        if "nato_alert_level" in updates:
            self.nato_alert_level = updates["nato_alert_level"]

        # --- Military units ---
        for new_unit in updates.get("military_units_add", []):
            self.military_units.append(MilitaryUnit(**new_unit))

        raw_remove = updates.get("military_units_remove", [])
        remove_names: set[str] = set()
        for item in raw_remove:
            if isinstance(item, str):
                remove_names.add(item)
            elif isinstance(item, dict):
                # LLM sometimes returns [{"name": "..."}] instead of ["..."]
                name = item.get("name", "")
                if name:
                    remove_names.add(name)
        if remove_names:
            self.military_units = [
                u for u in self.military_units if u.name not in remove_names
            ]

        for patch in updates.get("military_units_update", []):
            name = patch.get("name")
            if not name:
                continue
            for unit in self.military_units:
                if unit.name == name:
                    for k, v in patch.items():
                        if k != "name" and hasattr(unit, k):
                            # Coerce types: LLMs sometimes return "7" instead of 7
                            if k in ("readiness", "strength", "casualties",
                                     "supply_level", "morale"):
                                v = _safe_int(v, getattr(unit, k))
                            setattr(unit, k, v)
                    break

        # Merge dicts
        self.military_alerts.update(updates.get("military_alerts", {}))
        self.markets.update(updates.get("markets", {}))
        self.nato_consensus.update(updates.get("nato_consensus", {}))

        # Nuclear posture -- update and auto-escalate peers
        for country, posture in updates.get("nuclear_posture", {}).items():
            posture_lower = posture.lower()
            if posture_lower in _NUCLEAR_LEVELS:
                self.nuclear_posture[country] = posture_lower

        # Append lists
        self.sanctions.extend(updates.get("sanctions_add", []))
        self.trade_disruptions.extend(updates.get("trade_disruptions_add", []))
        self.treaties_invoked.extend(updates.get("treaties_invoked_add", []))
        self.un_resolutions.extend(updates.get("un_resolutions_add", []))

        # Nested dict merge -- diplomatic_relations
        for c1, rels in updates.get("diplomatic_relations", {}).items():
            if c1 not in self.diplomatic_relations:
                self.diplomatic_relations[c1] = {}
            self.diplomatic_relations[c1].update(rels)

        # Nested dict merge -- public_opinion
        for country, opinion in updates.get("public_opinion", {}).items():
            if country not in self.public_opinion:
                self.public_opinion[country] = {}
            self.public_opinion[country].update(opinion)

        # --- Humanitarian ---
        self.refugee_flows.extend(updates.get("refugee_flows_add", []))
        for country, level in updates.get("humanitarian_crisis_level", {}).items():
            self.humanitarian_crisis_level[country] = _safe_int(
                level, self.humanitarian_crisis_level.get(country, 0)
            )

        # --- Cyber operations ---
        self.cyber_operations.extend(updates.get("cyber_operations_add", []))

        # Nested dict merge -- infrastructure_status
        for country, infra in updates.get("infrastructure_status", {}).items():
            if country not in self.infrastructure_status:
                self.infrastructure_status[country] = {
                    "power_grid": 10, "comms": 10,
                    "financial": 10, "military_c2": 10,
                }
            for k, v in infra.items():
                self.infrastructure_status[country][k] = _safe_int(
                    v, self.infrastructure_status[country].get(k, 10)
                )

        # Replace per-round transient data
        if "recent_events" in updates:
            self.recent_events = updates["recent_events"]
        if "media_headlines" in updates:
            self.media_headlines = updates["media_headlines"]

        # --- Cascading automatic effects ---
        self._apply_cascading_effects()

    def _apply_cascading_effects(self) -> None:
        """Apply automatic second-order effects after GM updates.

        These are deterministic rules that model realistic consequences
        without requiring the LLM to remember every interaction.
        """
        # 1. Oil price affects public war support globally
        oil = self.markets.get("oil_price")
        if oil is not None:
            try:
                oil_f = float(oil)
            except (ValueError, TypeError):
                oil_f = 0.0
            if oil_f > 120:
                for country, opinion in self.public_opinion.items():
                    ws = opinion.get("war_support", 50)
                    # High oil = economic pain = less support for war
                    opinion["war_support"] = max(0, ws - 3)

        # 2. Active sanctions on Russia increase EU gas prices
        ru_sanctions = [s for s in self.sanctions if s.get("target") == "RU"]
        if ru_sanctions:
            gas = self.markets.get("gas_price_eu")
            if isinstance(gas, (int, float)):
                # Each new sanction round adds pressure
                self.markets["gas_price_eu"] = round(gas * 1.02, 2)

        # 3. Units with low supply degrade
        for unit in self.military_units:
            if unit.supply_level <= 3:
                unit.readiness = max(1, unit.readiness - 1)
            if unit.supply_level <= 1:
                unit.morale = max(1, unit.morale - 1)

        # 4. High casualties reduce morale
        for unit in self.military_units:
            if unit.casualties >= 2:
                morale_penalty = unit.casualties // 2
                unit.morale = max(1, unit.morale - morale_penalty)
                # Reset casualties counter after applying penalty
                # (penalty was from cumulative; keep casualties as-is)

        # 5. Degraded infrastructure affects public opinion
        for country, infra in self.infrastructure_status.items():
            avg_infra = sum(infra.values()) / max(len(infra), 1)
            if avg_infra < 5 and country in self.public_opinion:
                ga = self.public_opinion[country].get("government_approval", 50)
                self.public_opinion[country]["government_approval"] = max(0, ga - 2)

        # 6. Refugee inflows reduce government approval in receiving countries
        refugee_burden: dict[str, int] = {}
        for flow in self.refugee_flows:
            to_country = flow.get("to", "")
            count = flow.get("count", 0)
            if to_country:
                refugee_burden[to_country] = refugee_burden.get(to_country, 0) + count
        for country, total in refugee_burden.items():
            if total > 50000 and country in self.public_opinion:
                penalty = min(5, total // 100000)
                ga = self.public_opinion[country].get("government_approval", 50)
                self.public_opinion[country]["government_approval"] = max(0, ga - penalty)

        # 7. Nuclear auto-escalation: if any state escalates past dispersal,
        #    all other nuclear states escalate at least to elevated
        max_posture_idx = 0
        for country, posture in self.nuclear_posture.items():
            idx = _NUCLEAR_LEVELS.index(posture) if posture in _NUCLEAR_LEVELS else 0
            max_posture_idx = max(max_posture_idx, idx)
        if max_posture_idx >= 2:  # dispersal or higher
            for country, posture in self.nuclear_posture.items():
                current_idx = _NUCLEAR_LEVELS.index(posture) if posture in _NUCLEAR_LEVELS else 0
                # Others escalate to at least one step below the max
                min_idx = max(1, max_posture_idx - 1)
                if current_idx < min_idx:
                    self.nuclear_posture[country] = _NUCLEAR_LEVELS[min_idx]

        # 7. Nuclear posture affects public opinion dramatically
        for country, posture in self.nuclear_posture.items():
            idx = _NUCLEAR_LEVELS.index(posture) if posture in _NUCLEAR_LEVELS else 0
            if idx >= 3 and country in self.public_opinion:  # launch_ready+
                ws = self.public_opinion[country].get("war_support", 50)
                self.public_opinion[country]["war_support"] = max(0, ws - 5)

        # 8. Clamp all values to valid ranges
        for unit in self.military_units:
            unit.readiness = max(1, min(10, unit.readiness))
            unit.strength = max(0, min(10, unit.strength))
            unit.supply_level = max(0, min(10, unit.supply_level))
            unit.morale = max(1, min(10, unit.morale))
            unit.casualties = max(0, unit.casualties)

        for country, opinion in self.public_opinion.items():
            for key in ("war_support", "government_approval"):
                if key in opinion:
                    opinion[key] = max(0, min(100, opinion[key]))


# ======================================================================
# Constants
# ======================================================================

_NUCLEAR_LEVELS = [
    "peacetime", "elevated", "dispersal",
    "launch_ready", "tactical_use", "strategic",
]

# ======================================================================
# Private helpers
# ======================================================================

def _safe_int(value: Any, default: int) -> int:
    """Coerce a value to int, returning *default* on failure.

    LLMs sometimes return ``"7"`` or ``7.0`` instead of ``7``.
    """
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _relation_label(score: int) -> str:
    """Convert a -10 .. +10 relation score to a human label."""
    if score >= 8:
        return "allied"
    if score >= 4:
        return "friendly"
    if score >= 1:
        return "warm"
    if score == 0:
        return "neutral"
    if score >= -3:
        return "cool"
    if score >= -7:
        return "hostile"
    return "enemy"
