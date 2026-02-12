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

    def summary(self) -> str:
        return (
            f"{self.name} ({self.country} {self.type}) "
            f"@ {self.location} "
            f"[readiness={self.readiness}, strength={self.strength}]"
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
    # Public opinion
    # ------------------------------------------------------------------
    public_opinion: dict[str, dict] = field(default_factory=dict)  # country -> {war_support, government_approval}

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
                            setattr(unit, k, v)
                    break

        # Merge dicts
        self.military_alerts.update(updates.get("military_alerts", {}))
        self.markets.update(updates.get("markets", {}))
        self.nato_consensus.update(updates.get("nato_consensus", {}))

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

        # Replace per-round transient data
        if "recent_events" in updates:
            self.recent_events = updates["recent_events"]
        if "media_headlines" in updates:
            self.media_headlines = updates["media_headlines"]


# ======================================================================
# Private helpers
# ======================================================================

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
