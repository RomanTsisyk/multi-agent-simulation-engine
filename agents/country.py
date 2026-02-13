"""Country agent -- orchestrates internal faction debate and diplomacy.

A :class:`Country` owns a set of :class:`Faction` agents that represent
different advisory voices within its leadership.  The main entry-point
is :meth:`run_internal_debate`, which executes a structured three-round
debate and synthesises a unified national decision.
"""

from __future__ import annotations

import asyncio
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

# Phase-specific weight modifiers for dynamic faction influence
_PHASE_MODIFIERS = {
    "diplomatic": {
        "hawk": 0.7,      # Hawks less influential during diplomacy
        "diplomat": 1.5,   # Diplomats dominate
        "pragmatist": 1.3, # Pragmatists relevant
        "military_realist": 0.8,
        "military realist": 0.8,
        "wildcard": 1.0,
        "intelligence": 1.0,
        "economic": 1.2,   # Economic leverage matters
        "hardliner": 0.7,
        "dove": 1.3,
    },
    "hybrid": {
        "hawk": 1.0,
        "diplomat": 1.0,
        "pragmatist": 1.0,
        "military_realist": 1.2,
        "military realist": 1.2,
        "wildcard": 1.5,   # Wildcards thrive in ambiguity
        "intelligence": 1.5, # Intelligence drives hybrid warfare
        "economic": 0.8,
        "hardliner": 1.2,
        "dove": 0.7,
    },
    "conventional": {
        "hawk": 1.2,
        "diplomat": 0.8,
        "pragmatist": 1.0,
        "military_realist": 1.5,  # Military realists dominate conventional war
        "military realist": 1.5,
        "wildcard": 0.8,
        "intelligence": 1.0,
        "economic": 0.7,
        "hardliner": 1.2,
        "dove": 0.5,
    },
    "nuclear": {
        "hawk": 0.5,       # Even hawks are cautious near nuclear threshold
        "diplomat": 1.3,   # Diplomacy becomes critical
        "pragmatist": 1.5, # Pragmatic calculation dominates
        "military_realist": 1.0,
        "military realist": 1.0,
        "wildcard": 0.3,   # Wildcards suppressed - too dangerous
        "intelligence": 1.0,
        "economic": 0.5,
        "hardliner": 0.3,  # Hardliners marginalized
        "dove": 1.5,       # Doves gain voice near extinction
    },
}

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

ACTION DIVERSITY REQUIREMENT:
At least ONE of your 3 actions must be from a NON-MILITARY category:
- Economic warfare (sanctions, trade restrictions, asset freezes, energy cutoffs)
- Information operations (media campaigns, leaked intelligence, counter-propaganda)
- Covert action (intelligence operations, cyber attacks, sabotage)
- Diplomatic initiative (specific proposals with terms, not vague "engage in dialogue")
- Legal/institutional (UN resolution draft, international court filing, treaty invocation with specific articles)
Do NOT propose "enhance readiness" or "strengthen defenses" without specifying exactly WHAT units, WHERE, and by WHEN.

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

IMPORTANT: You MUST include at least ONE diplomatic message. In a real \
crisis, every country communicates with allies, adversaries, or neutral \
parties. Think about who {country_name} would NEED to talk to right now. \
Examples:
- TO: US | CHANNEL: private | MESSAGE: We request immediate deployment of additional forces to our eastern border
- TO: RU | CHANNEL: backchannel | MESSAGE: We are open to a 48-hour ceasefire to allow humanitarian corridors
- TO: UN | CHANNEL: public | MESSAGE: We call on the Security Council to convene an emergency session
Only write "None" if the country is completely isolated with zero diplomatic contacts.
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
        max_tokens_per_response: int | None = None,
    ) -> None:
        self.config = config
        self.factions = factions
        self.backend = backend
        self.max_tokens_per_response = max_tokens_per_response
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
            max_tokens=max_tokens_per_response,
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

        # Detect crisis phase from world context for dynamic faction weights
        crisis_phase = self._detect_crisis_phase(world_context)
        self.logger.info("Crisis phase detected: %s", crisis_phase)

        # Build faction memory from previous rounds
        faction_memory = ""
        if hasattr(self, '_previous_debate_summary') and self._previous_debate_summary:
            faction_memory = (
                f"\n\nPREVIOUS ROUND DEBATE SUMMARY:\n{self._previous_debate_summary}\n"
                "You MUST propose at least one action DIFFERENT from your previous "
                "recommendations. Explain why you are changing or maintaining your position."
            )

        # Inject previous-round context into the briefing
        enriched_briefing = situation_briefing + faction_memory

        # Reset all faction histories so each debate starts clean
        for faction in self.factions:
            faction.reset_history()

        debate_log: list[dict[str, str]] = []

        # -- FAST PATH: single faction -- skip debate, just get position + synthesise
        if len(self.factions) == 1:
            self.logger.info("Single faction -- skipping debate rounds")
            faction = self.factions[0]
            position = await faction.initial_position(
                enriched_briefing, world_context, max_tokens=self.max_tokens_per_response
            )
            debate_log.append({
                "round": 1,
                "faction": faction.config.name,
                "role": faction.config.role,
                "content": position,
            })
        else:
            # -- Round 1: Initial positions ------------------------------------
            # PARALLEL: Each faction speaks independently without seeing others
            self.logger.info("Round 1: Initial positions")
            round1_positions: dict[str, str] = {}

            tasks = [
                faction.initial_position(
                    enriched_briefing, world_context, max_tokens=self.max_tokens_per_response
                )
                for faction in self.factions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for faction, result in zip(self.factions, results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        "Faction %s failed in Round 1: %s", faction.config.name, result
                    )
                    position = f"[{faction.config.name} was unable to respond]"
                else:
                    position = result

                round1_positions[faction.config.name] = position
                debate_log.append({
                    "round": 1,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": position,
                })

            # -- Round 2: Rebuttal / cross-faction response --------------------
            # PARALLEL: Each faction sees all Round 1 positions (no dependency between Round 2 responses)
            self.logger.info("Round 2: Rebuttal")
            round2_positions: dict[str, str] = {}

            tasks = []
            for faction in self.factions:
                # Gather all *other* factions' Round-1 positions
                other_positions = [
                    f"[{name} ({self._faction_by_name(name).config.role})]:\n{pos}"
                    for name, pos in round1_positions.items()
                    if name != faction.config.name
                ]

                tasks.append(
                    faction.debate_respond(
                        topic=situation_briefing,
                        other_positions=other_positions,
                        world_context=world_context,
                        max_tokens=self.max_tokens_per_response,
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for faction, result in zip(self.factions, results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        "Faction %s failed in Round 2: %s", faction.config.name, result
                    )
                    rebuttal = f"[{faction.config.name} was unable to respond]"
                else:
                    rebuttal = result

                round2_positions[faction.config.name] = rebuttal
                debate_log.append({
                    "round": 2,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": rebuttal,
                })

            # -- Round 3: Final statements ------------------------------------
            # PARALLEL: Each faction sees the same full transcript (no dependency between Round 3 responses)
            self.logger.info("Round 3: Final statements")

            # Build a readable transcript of rounds 1-2 for context
            transcript_so_far = self._format_transcript(debate_log)

            tasks = [
                faction.final_statement(
                    topic=situation_briefing,
                    debate_history=transcript_so_far,
                    world_context=world_context,
                    max_tokens=self.max_tokens_per_response,
                )
                for faction in self.factions
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for faction, result in zip(self.factions, results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        "Faction %s failed in Round 3: %s", faction.config.name, result
                    )
                    final = f"[{faction.config.name} was unable to respond]"
                else:
                    final = result

                debate_log.append({
                    "round": 3,
                    "faction": faction.config.name,
                    "role": faction.config.role,
                    "content": final,
                })

        # -- Synthesis: distil into a unified decision ---------------------
        self.logger.info("Synthesising debate into decision...")
        decision_raw = await self._synthesise(debate_log, world_context, crisis_phase)

        decision, actions, dissent, diplomatic_messages = self._parse_synthesis(decision_raw)

        # Save debate summary for next round memory
        debate_summary_parts = []
        for entry in debate_log:
            debate_summary_parts.append(
                f"- {entry.get('faction', '?')}: advocated {entry.get('content', '?')[:100]}"
            )
        self._previous_debate_summary = "\n".join(debate_summary_parts[-6:])  # Keep last 6 entries

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
    def _detect_crisis_phase(world_context: str) -> str:
        """Detect the current crisis phase from world context keywords.

        Phases are detected in priority order (most severe first):
        1. nuclear: Nuclear threats, launch readiness, tactical weapons
        2. conventional: Active combat, military operations, attacks
        3. hybrid: Cyber warfare, disinformation, false flags
        4. diplomatic: Default state, negotiations, talks

        Args:
            world_context: Current world state description.

        Returns:
            One of "nuclear", "conventional", "hybrid", "diplomatic".
        """
        context_lower = world_context.lower()

        # Nuclear indicators (highest priority)
        nuclear_keywords = [
            "nuclear",
            "launch_ready",
            "launch ready",
            "tactical_use",
            "tactical use",
            "strategic weapons",
            "icbm",
            "defcon",
            "warhead",
            "nuclear threshold",
        ]
        if any(keyword in context_lower for keyword in nuclear_keywords):
            return "nuclear"

        # Conventional warfare indicators
        conventional_keywords = [
            "combat",
            "offensive",
            "attack",
            "military operation",
            "invasion",
            "troops deployed",
            "air strike",
            "ground forces",
            "artillery",
            "tank",
            "bombing",
            "casualties",
        ]
        if any(keyword in context_lower for keyword in conventional_keywords):
            return "conventional"

        # Hybrid warfare indicators
        hybrid_keywords = [
            "cyber",
            "disinformation",
            "hybrid",
            "false flag",
            "little green men",
            "proxy",
            "sabotage",
            "covert",
            "special operations",
            "information warfare",
        ]
        if any(keyword in context_lower for keyword in hybrid_keywords):
            return "hybrid"

        # Default to diplomatic phase
        return "diplomatic"

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

    def _compute_faction_weights(self, crisis_phase: str = "conventional") -> str:
        """Compute influence weights for each faction based on role and crisis phase.

        Weights are dynamically adjusted based on the current crisis phase:
        - diplomatic: Diplomats and economic advisors gain influence
        - hybrid: Intelligence and wildcards thrive in ambiguity
        - conventional: Military realists and hawks dominate
        - nuclear: Pragmatists and doves gain voice, wildcards suppressed

        Args:
            crisis_phase: One of "diplomatic", "hybrid", "conventional", "nuclear".

        Returns:
            Formatted string describing faction weights for the synthesis prompt.
        """
        # Base weights by role
        base_weights = {
            "hawk": 3,
            "military_realist": 3,
            "military realist": 3,
            "diplomat": 2,
            "pragmatist": 2,
            "wildcard": 1,
            "intelligence": 1,
            "economic": 1,
            "hardliner": 2,
            "dove": 1,
        }

        # Get phase modifiers, default to conventional if phase unknown
        phase_modifiers = _PHASE_MODIFIERS.get(crisis_phase, _PHASE_MODIFIERS["conventional"])

        lines = []
        for f in self.factions:
            role = f.config.role.lower()
            base_weight = base_weights.get(role, 2)
            modifier = phase_modifiers.get(role, 1.0)
            final_weight = base_weight * modifier

            lines.append(
                f"  - {f.config.name} ({f.config.role}): "
                f"influence weight {final_weight:.1f} "
                f"(base {base_weight} × phase modifier {modifier})"
            )

        if lines:
            return (
                f"Crisis phase: {crisis_phase.upper()}\n"
                f"Faction influence weights (higher = more influence on final decision):\n"
                + "\n".join(lines)
            )
        return ""

    async def _synthesise(
        self, debate_log: list[dict[str, str]], world_context: str, crisis_phase: str
    ) -> str:
        """Ask the synthesis agent to distil the debate into a decision.

        Args:
            debate_log: Full debate transcript as list of dicts.
            world_context: Current world state.
            crisis_phase: Detected crisis phase (affects faction weights).
        """
        self._synthesiser.reset_history()

        faction_weights_text = self._compute_faction_weights(crisis_phase)
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
