"""Country agent -- orchestrates internal faction debate and diplomacy.

A :class:`Country` owns a set of :class:`Faction` agents that represent
different advisory voices within its leadership.  The main entry-point
is :meth:`run_internal_debate`, which executes a structured three-round
debate and synthesises a unified national decision.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agents.base import Agent, AgentConfig
from agents.faction import Faction

if TYPE_CHECKING:
    from backends.base import LLMBackend


# ======================================================================
# Configuration
# ======================================================================

@dataclass
class CountryConfig:
    """Static attributes of a country in the simulation.

    Attributes:
        name: Full display name (e.g. ``"United States"``).
        code: Short code used as a key throughout the engine (e.g. ``"US"``).
        alliances: List of country codes this nation is allied with.
        military_strength: Power index from 1 (weakest) to 10 (strongest).
        economic_strength: Economic index from 1 (weakest) to 10 (strongest).
        description: Optional narrative description of the country's
            current strategic posture.
    """

    name: str
    code: str
    alliances: list[str] = field(default_factory=list)
    military_strength: int = 5
    economic_strength: int = 5
    description: str = ""


# ======================================================================
# Synthesis prompt -- used to distil the debate into a decision
# ======================================================================

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a neutral analyst summarising the outcome of an internal \
leadership debate for country {country_name} ({country_code}).

Your job is to read the full debate transcript and produce a SINGLE \
coherent decision that reflects the WEIGHTED balance of opinions. \
{faction_weights_text}
Where factions disagree, favour the higher-weighted faction's view \
but note any significant dissent. Pay special attention to red lines \
that any faction refused to cross.

Each action MUST be specific and executable — not vague aspirations. \
Good: "Deploy 2nd Armoured Brigade to Suwalki corridor within 48h" \
Bad: "Strengthen military posture"

Respond in EXACTLY the following structure (plain text, no code block):

DECISION: <one-paragraph summary of what the country decides to do>
ACTIONS:
1. <specific military, diplomatic, or economic action with details>
2. <specific action with target, timeline, or scope>
3. <specific action (optional)>
DISSENT: <which faction(s) objected and what red line was at stake, or "None">
DIPLOMATIC_MESSAGES:
- TO: <country code> | CHANNEL: <public|private|backchannel> | MESSAGE: <the message text>
- TO: <country code> | CHANNEL: <public|private|backchannel> | MESSAGE: <the message text>
(Write "None" if no diplomatic messages this round. Public messages are visible \
to all countries. Private messages are only visible to the recipient. \
Backchannel messages are secret and deniable.)
"""

_DIPLOMACY_SYSTEM_PROMPT = """\
You are the collective leadership of {country_name} ({country_code}).

Country profile:
- Military strength: {military_strength}/10
- Economic strength: {economic_strength}/10
- Alliances: {alliances}
{description}

You have received a diplomatic message from {from_country}.  \
Discuss internally (think step-by-step) and then craft a single, \
official diplomatic response.  The response should reflect your \
country's interests, alliances, and strategic posture.

Respond ONLY with the diplomatic reply -- no internal deliberation \
should be visible in the output.
"""


# ======================================================================
# Country class
# ======================================================================

class Country:
    """A country with multiple internal factions that debate before acting.

    The debate protocol follows three rounds:

    1. **Initial positions** -- each faction independently states their
       stance on the situation briefing.
    2. **Rebuttal** -- each faction reads all other factions' Round-1
       positions and responds (argue, concede, propose compromise).
    3. **Final statements** -- each faction delivers a closing position
       informed by the full debate so far.

    After the three rounds a *synthesis* agent (with a neutral system
    prompt) distils the transcript into a structured decision.

    Args:
        config: Country-level configuration.
        factions: List of :class:`Faction` instances representing the
            advisory voices inside this country.
        backend: An initialised LLM backend used by the synthesis step.
    """

    def __init__(
        self,
        config: CountryConfig,
        factions: list[Faction],
        backend: LLMBackend,
    ) -> None:
        self.config = config
        self.factions = factions
        self.backend = backend
        self.logger = logging.getLogger(f"country.{config.code}")

        # Build a lightweight synthesis agent that has no faction bias
        self._synthesiser = Agent(
            config=AgentConfig(
                name=f"{config.name} Decision Synthesiser",
                role="neutral_analyst",
                personality=(
                    "You are impartial. You summarise debates objectively "
                    "and extract actionable decisions."
                ),
                country_code=config.code,
            ),
            backend=backend,
            temperature=0.4,  # low temp for deterministic summaries
        )

    # ------------------------------------------------------------------
    # Internal debate
    # ------------------------------------------------------------------

    async def run_internal_debate(
        self, situation_briefing: str, world_context: str
    ) -> dict:
        """Execute a three-round internal faction debate.

        Args:
            situation_briefing: Description of the crisis or event that
                requires a national decision.
            world_context: Current world state summary.

        Returns:
            A dict with the following keys:

            - ``"country"`` -- country display name.
            - ``"country_code"`` -- country short code.
            - ``"situation"`` -- the original briefing.
            - ``"debate_log"`` -- list of dicts, one per utterance, each
              containing ``"round"``, ``"faction"``, ``"role"``, and
              ``"content"``.
            - ``"decision"`` -- unified decision text.
            - ``"actions"`` -- list of 1-3 concrete actions.
            - ``"dissent"`` -- minority dissent summary (may be empty).
        """
        self.logger.info(
            "Starting internal debate (%d factions) on: %.80s...",
            len(self.factions),
            situation_briefing,
        )

        # Reset all faction histories so each debate starts clean
        for faction in self.factions:
            faction.reset_history()

        debate_log: list[dict[str, str]] = []

        # -- FAST PATH: single faction -- skip debate, just get position + synthesise
        if len(self.factions) == 1:
            self.logger.info("Single faction -- skipping debate rounds")
            faction = self.factions[0]
            position = await faction.initial_position(
                situation_briefing, world_context
            )
            debate_log.append({
                "round": 1,
                "faction": faction.config.name,
                "role": faction.config.role,
                "content": position,
            })
        else:
            # -- Round 1: Initial positions ------------------------------------
            self.logger.info("Round 1: Initial positions")
            round1_positions: dict[str, str] = {}

            for faction in self.factions:
                self.logger.debug("  Faction %s speaking...", faction.config.name)
                position = await faction.initial_position(
                    situation_briefing, world_context
                )
                round1_positions[faction.config.name] = position
                debate_log.append({
                    "round": 1,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": position,
                })

            # -- Round 2: Rebuttal / cross-faction response --------------------
            self.logger.info("Round 2: Rebuttal")
            round2_positions: dict[str, str] = {}

            for faction in self.factions:
                # Gather all *other* factions' Round-1 positions
                other_positions = [
                    f"[{name} ({self._faction_by_name(name).config.role})]:\n{pos}"
                    for name, pos in round1_positions.items()
                    if name != faction.config.name
                ]

                self.logger.debug("  Faction %s responding...", faction.config.name)
                rebuttal = await faction.debate_respond(
                    topic=situation_briefing,
                    other_positions=other_positions,
                    world_context=world_context,
                )
                round2_positions[faction.config.name] = rebuttal
                debate_log.append({
                    "round": 2,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": rebuttal,
                })

            # -- Round 3: Final statements ------------------------------------
            self.logger.info("Round 3: Final statements")

            # Build a readable transcript of rounds 1-2 for context
            transcript_so_far = self._format_transcript(debate_log)

            for faction in self.factions:
                self.logger.debug(
                    "  Faction %s delivering final statement...",
                    faction.config.name,
                )
                final = await faction.final_statement(
                    topic=situation_briefing,
                    debate_history=transcript_so_far,
                    world_context=world_context,
                )
                debate_log.append({
                    "round": 3,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": final,
                })

        # -- Synthesis: distil into a unified decision ---------------------
        self.logger.info("Synthesising debate into decision...")
        decision_raw = await self._synthesise(debate_log, world_context)

        decision, actions, dissent, diplomatic_messages = self._parse_synthesis(decision_raw)

        self.logger.info(
            "Debate concluded. Decision: %.120s...", decision
        )

        return {
            "country": self.config.name,
            "country_code": self.config.code,
            "situation": situation_briefing,
            "debate_log": debate_log,
            "decision": decision,
            "actions": actions,
            "dissent": dissent,
            "diplomatic_messages": diplomatic_messages,
        }

    # ------------------------------------------------------------------
    # Diplomacy
    # ------------------------------------------------------------------

    async def receive_diplomatic_message(
        self,
        from_country: str,
        message: str,
        world_context: str,
    ) -> str:
        """Process an incoming diplomatic message and craft a response.

        The country considers its strategic profile, alliances, and the
        current world context before responding.

        Args:
            from_country: Name or code of the sending country.
            message: The diplomatic message body.
            world_context: Current world state.

        Returns:
            The official diplomatic response as a string.
        """
        self.logger.info(
            "Received diplomatic message from %s (%.60s...)",
            from_country,
            message,
        )

        system_prompt = _DIPLOMACY_SYSTEM_PROMPT.format(
            country_name=self.config.name,
            country_code=self.config.code,
            military_strength=self.config.military_strength,
            economic_strength=self.config.economic_strength,
            alliances=", ".join(self.config.alliances) or "None",
            from_country=from_country,
            description=(
                f"- Strategic posture: {self.config.description}"
                if self.config.description
                else ""
            ),
        )

        messages = [
            {
                "role": "user",
                "content": (
                    f"--- WORLD CONTEXT ---\n{world_context}\n\n"
                    f"--- DIPLOMATIC MESSAGE FROM {from_country.upper()} ---\n"
                    f"{message}"
                ),
            }
        ]

        response = await self.backend.generate(
            system_prompt=system_prompt,
            messages=messages,
            temperature=0.6,
        )

        self.logger.info(
            "Diplomatic response drafted (%d chars)", len(response)
        )
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _faction_by_name(self, name: str) -> Faction:
        """Look up a faction by its ``config.name``."""
        for f in self.factions:
            if f.config.name == name:
                return f
        raise KeyError(f"No faction named {name!r} in country {self.config.code}")

    @staticmethod
    def _format_transcript(debate_log: list[dict[str, str]]) -> str:
        """Render a debate log into a human-readable transcript string."""
        lines: list[str] = []
        current_round = 0
        for entry in debate_log:
            rnd = entry["round"]
            if rnd != current_round:
                current_round = rnd
                lines.append(f"\n{'='*60}")
                lines.append(f"  ROUND {rnd}")
                lines.append(f"{'='*60}\n")
            lines.append(
                f"[{entry['faction']} ({entry['role']})]:\n"
                f"{entry['content']}\n"
            )
        return "\n".join(lines)

    def _compute_faction_weights(self) -> str:
        """Compute influence weights for each faction based on role.

        During a military crisis, military and hawk factions gain influence.
        During peacetime or diplomacy-heavy phases, diplomats gain influence.
        This is a heuristic based on role archetypes.
        """
        role_weights = {
            "hawk": 3,
            "military_realist": 3,
            "military realist": 3,
            "diplomat": 2,
            "pragmatist": 2,
            "wildcard": 1,
            "intelligence": 1,
            "economic": 1,
        }
        lines = []
        for f in self.factions:
            role = f.config.role.lower()
            weight = role_weights.get(role, 2)
            lines.append(f"  - {f.config.name} ({f.config.role}): influence weight {weight}/3")
        if lines:
            return (
                "Faction influence weights (higher = more influence on final decision):\n"
                + "\n".join(lines)
            )
        return ""

    async def _synthesise(
        self, debate_log: list[dict[str, str]], world_context: str
    ) -> str:
        """Ask the synthesis agent to distil the debate into a decision."""
        self._synthesiser.reset_history()

        faction_weights_text = self._compute_faction_weights()
        system_prompt = _SYNTHESIS_SYSTEM_PROMPT.format(
            country_name=self.config.name,
            country_code=self.config.code,
            faction_weights_text=faction_weights_text,
        )

        transcript = self._format_transcript(debate_log)

        prompt = (
            f"Here is the full internal debate transcript:\n\n"
            f"{transcript}\n\n"
            "Now produce the unified decision, actions, and dissent "
            "summary as instructed."
        )

        response = await self.backend.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response

    @staticmethod
    def _parse_synthesis(raw: str) -> tuple[str, list[str], str, list[dict]]:
        """Parse the synthesis agent's output into structured fields.

        Expects the format produced by ``_SYNTHESIS_SYSTEM_PROMPT``:

        .. code-block:: text

            DECISION: ...
            ACTIONS:
            1. ...
            2. ...
            DISSENT: ...
            DIPLOMATIC_MESSAGES:
            - TO: XX | CHANNEL: public | MESSAGE: ...

        If parsing fails the raw text is returned as the decision with
        an empty actions list and no dissent.

        Returns:
            A tuple of ``(decision, actions, dissent, diplomatic_messages)``.
        """
        decision = ""
        actions: list[str] = []
        dissent = ""
        diplomatic_messages: list[dict] = []

        # State machine: which section are we currently accumulating?
        section: str | None = None
        decision_lines: list[str] = []
        dissent_lines: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()

            # Detect section headers
            if stripped.upper().startswith("DECISION:"):
                section = "decision"
                remainder = stripped.split(":", 1)[1].strip()
                if remainder:
                    decision_lines.append(remainder)
                continue
            elif stripped.upper().startswith("ACTIONS:"):
                section = "actions"
                continue
            elif stripped.upper().startswith("DISSENT:"):
                section = "dissent"
                remainder = stripped.split(":", 1)[1].strip()
                if remainder:
                    dissent_lines.append(remainder)
                continue
            elif stripped.upper().startswith("DIPLOMATIC_MESSAGES:"):
                section = "diplomatic"
                continue

            # Accumulate content into the active section
            if section == "decision" and stripped:
                decision_lines.append(stripped)
            elif section == "actions" and stripped:
                # Strip leading numbering like "1." or "- " using regex
                action_text = re.sub(r"^\d+[.)]\s*|^-\s*", "", stripped)
                if action_text:
                    actions.append(action_text)
            elif section == "dissent" and stripped:
                dissent_lines.append(stripped)
            elif section == "diplomatic" and stripped:
                msg = _parse_diplomatic_line(stripped)
                if msg:
                    diplomatic_messages.append(msg)

        decision = " ".join(decision_lines) if decision_lines else raw.strip()
        dissent = " ".join(dissent_lines) if dissent_lines else ""

        return decision, actions, dissent, diplomatic_messages

    def __repr__(self) -> str:
        faction_names = [f.config.name for f in self.factions]
        return (
            f"Country(name={self.config.name!r}, "
            f"code={self.config.code!r}, "
            f"factions={faction_names!r})"
        )


def _parse_diplomatic_line(line: str) -> dict | None:
    """Parse a diplomatic message line like:

    ``- TO: US | CHANNEL: private | MESSAGE: We propose joint patrols``

    Returns a dict with keys ``to``, ``channel``, ``message`` or None.
    """
    stripped = re.sub(r"^-\s*", "", line.strip())
    if stripped.lower() == "none":
        return None

    parts: dict[str, str] = {}
    for segment in stripped.split("|"):
        segment = segment.strip()
        if ":" in segment:
            key, value = segment.split(":", 1)
            parts[key.strip().lower()] = value.strip()

    to_country = parts.get("to", "").strip()
    channel = parts.get("channel", "public").strip().lower()
    message = parts.get("message", "").strip()

    if not to_country or not message:
        return None

    return {"to": to_country, "channel": channel, "message": message}
