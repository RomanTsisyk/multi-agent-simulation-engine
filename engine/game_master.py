"""Game Master agent -- the impartial referee of the wargame.

The Game Master is responsible for:
- Generating situation briefings at the start of each round.
- Resolving all country actions simultaneously, checking for realism
  and logical consistency.
- Producing structured world-state updates as parseable JSON.
- Generating country-specific intelligence that only that country
  would realistically know.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backends.base import LLMBackend
from engine.world_state import WorldState
from utils.json_parser import parse_json_response

logger = logging.getLogger(__name__)


# ======================================================================
# System prompts
# ======================================================================

_GM_SYSTEM_PROMPT = """\
You are the Game Master of a realistic, multi-agent geopolitical wargame \
simulating a crisis centred on the Suwalki Gap -- the narrow land corridor \
between Poland and Lithuania that separates the Russian exclave of Kaliningrad \
from Belarus.  Russia has seized this corridor, cutting off the Baltic states \
from the rest of NATO by land.

YOUR ROLE AND RESPONSIBILITIES:
- You are a fair, impartial referee.  You do NOT favour any side.
- You evaluate every action for REALISM.  Can this country actually do this \
  given its real-world military capabilities, economic resources, political \
  constraints, and geographic position?
- You resolve CONFLICTING actions.  When two countries target the same area, \
  the outcome depends on force ratios, readiness, terrain, logistics, and \
  surprise.
- You determine CONSEQUENCES and SECOND-ORDER EFFECTS.  Military action \
  causes civilian casualties, refugee flows, economic disruption, and shifts \
  in public opinion.  Sanctions hurt the sender as well as the target.  \
  Diplomatic moves take time to produce results.
- You generate UNEXPECTED BUT PLAUSIBLE developments ("fog of war") -- \
  intelligence failures, equipment malfunctions, cyberattacks, protests, \
  friendly-fire incidents, media leaks -- at a rate that keeps the game \
  interesting without being arbitrary.
- You track the passage of game time and advance it logically.

REALISM GUIDELINES:
- Ground forces cannot teleport; movement takes time and requires logistics.
- Air superiority matters enormously for ground operations.
- Nuclear escalation is possible but requires extreme political will and has \
  catastrophic consequences.  No side will use nuclear weapons lightly.
- NATO's Article 5 requires political consensus among all members; not all \
  will agree immediately.
- Russia has significant conventional military strength but limited economic \
  resilience under sanctions.
- Cyber and information warfare are constant factors.
- Weather, terrain, and supply lines matter.

LOGISTICS AND ATTRITION RULES:
- Units in combat lose supply_level by 1-2 per round (ammo expenditure).
- Units with supply_level <= 3 suffer -1 readiness per round (degraded ops).
- Units with supply_level <= 1 cannot conduct offensive operations.
- Casualties are cumulative and permanent within a game. High casualties \
  reduce morale (-1 morale per 2 casualty points).
- Morale below 3 risks unit refusing orders or retreating without authorisation.
- Supply lines can be interdicted by air power, special forces, or cyber attacks.
- Resupply requires a secure logistics corridor and takes 1-2 rounds.

You must ALWAYS respond with valid JSON and nothing else.
"""

_BRIEFING_PROMPT_TEMPLATE = """\
Generate the situation briefing for Round {round_num} of the wargame.

Current world state:
{world_state_json}

Write a compelling, detailed, 3-5 paragraph narrative situation report that:
1. Summarises the current strategic situation.
2. Highlights the most important developments from the previous round.
3. Notes any escalation or de-escalation dynamics.
4. Mentions key decisions that countries face this round.

Respond with JSON:
{{
    "briefing": "<the narrative text>"
}}
"""

_RESOLVE_PROMPT_TEMPLATE = """\
All countries have submitted their decisions for Round {round_num}. \
You must now resolve these actions simultaneously.

CURRENT WORLD STATE:
{world_state_json}

COUNTRY DECISIONS THIS ROUND:
{decisions_json}

INSTRUCTIONS:
1. Evaluate each action for realism.  If a country ordered something \
   impossible or implausible, note it and substitute a lesser realistic \
   outcome.
2. Resolve military conflicts using force ratios, terrain, readiness, \
   surprise, air support, and logistics.
3. Determine economic consequences of all actions.
4. Determine diplomatic consequences.
5. Determine effects on public opinion in all involved countries.
6. Generate 2-4 news headlines that world media would report.
7. Generate 0-2 surprise developments (unexpected but plausible).
8. Advance the game clock appropriately (each round is roughly 12-24 hours \
   of game time).

Respond with a single JSON object (no markdown, no commentary):
{{
    "narrative": "<2-4 paragraph narrative of what happened this round>",
    "world_state_updates": {{
        "game_time": "<new game time string>",
        "military_units_add": [],
        "military_units_remove": [],
        "military_units_update": [
            {{"name": "<unit name>", "location": "<new loc>", "readiness": <int 1-10>, "strength": <int 1-10>, "casualties": <int cumulative>, "supply_level": <int 1-10>, "morale": <int 1-10>}}
        ],
        "military_alerts": {{"<country>": "<alert level>"}},
        "markets": {{"oil_price": <float>, "euro_usd": <float>}},
        "sanctions_add": [{{"from": "<country>", "target": "<country>", "type": "<description>"}}],
        "trade_disruptions_add": [],
        "diplomatic_relations": {{"<country>": {{"<other_country>": <int -10..10>}}}},
        "treaties_invoked_add": [],
        "un_resolutions_add": [],
        "nato_alert_level": "<normal|elevated|high|article5>",
        "nato_consensus": {{"<country>": "<position>"}},
        "nuclear_posture": {{"<nuclear_country>": "<peacetime|elevated|dispersal|launch_ready>"}},
        "nuclear_detonations_add": [{{"attacker": "<country>", "target": "<country|coordinates>", "yield_kt": <int>, "type": "<tactical|strategic>", "timestamp": "<game time>"}}],
        "public_opinion": {{"<country>": {{"war_support": <int 0-100>, "government_approval": <int 0-100>}}}},
        "refugee_flows_add": [{{"from": "<country>", "to": "<country>", "count": <int>, "status": "<fleeing|in_transit|settled|blocked>"}}],
        "humanitarian_crisis_level": {{"<country>": <int 1-10>}},
        "cyber_operations_add": [{{"attacker": "<country>", "target": "<country>", "type": "<ddos|malware|supply_chain|espionage|infrastructure>", "severity": "<low|medium|high|critical>", "infrastructure_affected": "<power_grid|comms|financial|military_c2|none>"}}],
        "infrastructure_status": {{"<country>": {{"power_grid": <int 1-10>, "comms": <int 1-10>, "financial": <int 1-10>, "military_c2": <int 1-10>}}}},
        "recent_events": ["<event1>", "<event2>"],
        "media_headlines": ["<headline1>", "<headline2>"]
    }},
    "events": ["<significant event 1>", "<significant event 2>"],
    "headlines": ["<headline1>", "<headline2>"],
    "surprises": ["<surprise development, if any>"]
}}
"""

_INTEL_PROMPT_TEMPLATE = """\
Generate a PRIVATE intelligence briefing for {country_code}.

This briefing contains information that ONLY {country_code} would know through \
its own intelligence services, satellite reconnaissance, signals intelligence, \
human intelligence networks, and internal government communications.

Current world state:
{world_state_json}

The briefing should include 3-5 items. CRITICAL REALISM RULES FOR INTELLIGENCE:

1. FOG OF WAR: At least ONE item must contain INACCURATE or OUTDATED information \
   that the intelligence service believes is true but is actually wrong. Real \
   intelligence is never perfect. Examples: wrong troop counts, misidentified \
   unit types, outdated positions (12-24h old), misread intentions.

2. CONTRADICTIONS: If possible, include one item that partially contradicts \
   another item (e.g. SIGINT suggests attack, but HUMINT suggests diplomacy). \
   Real intelligence often presents conflicting pictures.

3. CONFIDENCE LEVELS: Each item MUST have an individual confidence level. \
   Not all intelligence is equally reliable. HUMINT from a new source is less \
   reliable than satellite imagery.

4. INTELLIGENCE GAPS: Mention 1-2 things the intelligence service DOES NOT \
   know and is trying to find out. Absence of information is itself information.

Item types:
- Intercepted communications or signals intelligence
- Satellite imagery analysis of enemy movements
- Reports from human intelligence assets
- Internal political dynamics (factions within the leadership)
- Assessment of enemy intentions or capabilities
- Cyber intelligence
- Economic intelligence not publicly available

Make it realistic for {country_code}'s actual intelligence capabilities. \
A small country has weaker SIGINT/IMINT; a major power has better coverage \
but still has blind spots.

Respond with JSON:
{{
    "intel_briefing": "<the classified briefing text>",
    "overall_confidence": "<high|medium|low>",
    "items": [
        {{"type": "<sigint|humint|imint|osint|cyber>", "content": "<detail>", "confidence": "<high|medium|low>", "reliability": "<A|B|C|D>", "caveat": "<any limitation or doubt about this item>"}}
    ],
    "intelligence_gaps": ["<what we don't know yet>", "<another gap>"],
    "fog_of_war_note": "<internal note: which item above is inaccurate and why -- this is for GM tracking only>"
}}
"""


class GameMaster:
    """The impartial Game Master agent that adjudicates each round.

    Args:
        backend: An :class:`~backends.base.LLMBackend` instance used for
            all GM inference calls.
        scenario_config: A dictionary containing the scenario definition
            (countries, initial state, constraints, etc.).
    """

    def __init__(
        self,
        backend: LLMBackend,
        scenario_config: dict,
        max_tokens: int | None = None,
    ) -> None:
        self.backend = backend
        self.scenario = scenario_config
        self.max_tokens = max_tokens
        self._round_history: list[dict] = []

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_resolution(self, parsed: dict) -> dict:
        """Validate and correct resolution response from LLM.

        Args:
            parsed: The parsed JSON response from resolve_actions LLM call.

        Returns:
            A validated/corrected dictionary with all required fields.
        """
        # Check and fix required fields
        if "narrative" not in parsed or not isinstance(parsed.get("narrative"), str) or not parsed["narrative"].strip():
            logger.warning("GM resolution missing or empty 'narrative' field, setting default")
            parsed["narrative"] = "The round concluded with various actions unfolding across the theater of operations."

        if "world_state_updates" not in parsed or not isinstance(parsed.get("world_state_updates"), dict):
            logger.warning("GM resolution missing or invalid 'world_state_updates' field, setting empty dict")
            parsed["world_state_updates"] = {}

        if "events" not in parsed or not isinstance(parsed.get("events"), list):
            logger.warning("GM resolution missing or invalid 'events' field, setting empty list")
            parsed["events"] = []

        if "headlines" not in parsed or not isinstance(parsed.get("headlines"), list):
            logger.warning("GM resolution missing or invalid 'headlines' field, setting empty list")
            parsed["headlines"] = []

        if "surprises" not in parsed or not isinstance(parsed.get("surprises"), list):
            parsed["surprises"] = []

        # Validate and clamp numeric values in world_state_updates
        wsu = parsed["world_state_updates"]

        # Validate military_units_update if present
        if "military_units_update" in wsu and isinstance(wsu["military_units_update"], list):
            for i, unit in enumerate(wsu["military_units_update"]):
                if not isinstance(unit, dict):
                    logger.warning(f"GM resolution military_units_update[{i}] is not a dict, removing")
                    wsu["military_units_update"][i] = None
                    continue

                # Check for required 'name' field
                if "name" not in unit:
                    logger.warning(f"GM resolution military_units_update[{i}] missing 'name' field, removing entry")
                    wsu["military_units_update"][i] = None
                    continue

                # Clamp numeric values to valid ranges
                if "readiness" in unit:
                    if not isinstance(unit["readiness"], (int, float)):
                        logger.warning(f"GM resolution unit '{unit['name']}' readiness is not numeric, removing")
                        del unit["readiness"]
                    else:
                        unit["readiness"] = max(1, min(10, int(unit["readiness"])))

                if "strength" in unit:
                    if not isinstance(unit["strength"], (int, float)):
                        logger.warning(f"GM resolution unit '{unit['name']}' strength is not numeric, removing")
                        del unit["strength"]
                    else:
                        unit["strength"] = max(1, min(10, int(unit["strength"])))

                if "supply_level" in unit:
                    if not isinstance(unit["supply_level"], (int, float)):
                        logger.warning(f"GM resolution unit '{unit['name']}' supply_level is not numeric, removing")
                        del unit["supply_level"]
                    else:
                        unit["supply_level"] = max(1, min(10, int(unit["supply_level"])))

                if "morale" in unit:
                    if not isinstance(unit["morale"], (int, float)):
                        logger.warning(f"GM resolution unit '{unit['name']}' morale is not numeric, removing")
                        del unit["morale"]
                    else:
                        unit["morale"] = max(1, min(10, int(unit["morale"])))

                if "casualties" in unit:
                    if not isinstance(unit["casualties"], (int, float)):
                        logger.warning(f"GM resolution unit '{unit['name']}' casualties is not numeric, removing")
                        del unit["casualties"]
                    else:
                        unit["casualties"] = max(0, int(unit["casualties"]))

            # Remove None entries (invalid units)
            wsu["military_units_update"] = [u for u in wsu["military_units_update"] if u is not None]

        # Validate public_opinion values
        if "public_opinion" in wsu and isinstance(wsu["public_opinion"], dict):
            countries_to_remove = []
            for country, opinion in wsu["public_opinion"].items():
                if not isinstance(opinion, dict):
                    logger.warning(f"GM resolution public_opinion[{country}] is not a dict, removing")
                    countries_to_remove.append(country)
                    continue

                if "war_support" in opinion:
                    if not isinstance(opinion["war_support"], (int, float)):
                        logger.warning(f"GM resolution public_opinion[{country}] war_support is not numeric, removing")
                        del opinion["war_support"]
                    else:
                        opinion["war_support"] = max(0, min(100, int(opinion["war_support"])))

                if "government_approval" in opinion:
                    if not isinstance(opinion["government_approval"], (int, float)):
                        logger.warning(f"GM resolution public_opinion[{country}] government_approval is not numeric, removing")
                        del opinion["government_approval"]
                    else:
                        opinion["government_approval"] = max(0, min(100, int(opinion["government_approval"])))

            # Remove invalid countries after iteration
            for country in countries_to_remove:
                del wsu["public_opinion"][country]

        return parsed

    def _validate_intel(self, parsed: dict) -> dict:
        """Validate and correct intel response from LLM.

        Args:
            parsed: The parsed JSON response from generate_private_intel LLM call.

        Returns:
            A validated/corrected dictionary with all required fields.
        """
        # Check required fields
        if "intel_briefing" not in parsed or not isinstance(parsed.get("intel_briefing"), str):
            logger.warning("GM intel missing or invalid 'intel_briefing' field, setting default")
            parsed["intel_briefing"] = "Intelligence briefing unavailable at this time."

        if "items" not in parsed or not isinstance(parsed.get("items"), list):
            logger.warning("GM intel missing or invalid 'items' field, setting empty list")
            parsed["items"] = []

        # Validate each item has required fields
        valid_items = []
        for i, item in enumerate(parsed["items"]):
            if not isinstance(item, dict):
                logger.warning(f"GM intel items[{i}] is not a dict, skipping")
                continue

            if "type" not in item or "content" not in item:
                logger.warning(f"GM intel items[{i}] missing 'type' or 'content' field, skipping")
                continue

            valid_items.append(item)

        parsed["items"] = valid_items

        return parsed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_round_summary(
        self,
        round_num: int,
        briefing_summary: str,
        key_decisions: list[str],
        resolution_summary: str,
    ) -> None:
        """Record a compact summary of a completed round for context in future rounds.

        Args:
            round_num: The round number that just completed.
            briefing_summary: A 1-2 sentence summary of the situation at round start.
            key_decisions: List of major actions countries took this round.
            resolution_summary: A 1-2 sentence summary of what happened/changed.
        """
        summary = {
            "round": round_num,
            "briefing_summary": briefing_summary,
            "key_decisions": key_decisions,
            "resolution_summary": resolution_summary,
        }
        self._round_history.append(summary)

        # Keep only the last 5 rounds to prevent context overflow
        if len(self._round_history) > 5:
            self._round_history = self._round_history[-5:]

    def _build_history_context(self, max_rounds: int = 3) -> str:
        """Build a formatted history context string from recent rounds.

        Args:
            max_rounds: Maximum number of recent rounds to include.

        Returns:
            A formatted string summarizing recent round history, or empty string if no history.
        """
        if not self._round_history:
            return ""

        recent = self._round_history[-max_rounds:]
        lines = ["PREVIOUS ROUNDS SUMMARY:"]
        for entry in recent:
            round_num = entry["round"]
            resolution = entry.get("resolution_summary", "")
            decisions = entry.get("key_decisions", [])

            decisions_str = "; ".join(decisions[:3]) if decisions else "No major actions"
            lines.append(
                f"Round {round_num}: {resolution} "
                f"(Key actions: {decisions_str})"
            )

        lines.append("")  # blank line after history
        return "\n".join(lines)

    async def generate_situation_briefing(
        self,
        world_state: WorldState,
        round_num: int,
        previous_round_summary: str = "",
    ) -> str:
        """Generate the narrative situation report for the start of a round.

        Returns:
            A multi-paragraph narrative briefing string.
        """
        # Build history context from previous rounds
        history_context = self._build_history_context(max_rounds=3)

        # Construct the prompt with history inserted between world state and instructions
        prompt_parts = [
            f"Generate the situation briefing for Round {round_num} of the wargame.",
            "",
            "Current world state:",
            world_state.to_json(),
        ]

        # Insert history context if available
        if history_context:
            prompt_parts.append("")
            prompt_parts.append(history_context)

        # Add the main instructions
        prompt_parts.append("")
        prompt_parts.append(
            "Write a compelling, detailed, 3-5 paragraph narrative situation report that:\n"
            "1. Summarises the current strategic situation.\n"
            "2. Highlights the most important developments from the previous round.\n"
            "3. Notes any escalation or de-escalation dynamics.\n"
            "4. Mentions key decisions that countries face this round."
        )

        if history_context:
            prompt_parts.append(
                "\nIMPORTANT: Consider the narrative arc from previous rounds. "
                "The briefing should show CONTINUITY and PROGRESSION. "
                "Reference earlier developments where relevant. "
                "Show how the situation is evolving, not just the current snapshot."
            )

        prompt_parts.append(
            "\nRespond with JSON:\n"
            "{\n"
            '    "briefing": "<the narrative text>"\n'
            "}"
        )

        prompt = "\n".join(prompt_parts)

        if previous_round_summary:
            prompt += (
                f"\n\n{previous_round_summary}\n\n"
                "IMPORTANT: The briefing must reflect what CHANGED since last round. "
                "Do NOT repeat the same narrative. Focus on NEW developments, "
                "consequences of previous actions, and evolving dynamics. "
                "The situation should PROGRESS — escalation, de-escalation, "
                "new crises, or diplomatic breakthroughs."
            )

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=self.max_tokens,
        )

        parsed = parse_json_response(raw)
        briefing = parsed.get("briefing", raw)
        return briefing

    async def resolve_actions(
        self,
        world_state: WorldState,
        all_country_decisions: list[dict],
    ) -> dict:
        """Resolve all country decisions and return structured updates.

        Args:
            world_state: The current world state *before* this round's
                actions take effect.
            all_country_decisions: A list of decision dicts, each containing
                at least ``"country"`` and ``"actions"`` keys.

        Returns:
            A dictionary with keys ``narrative``, ``world_state_updates``,
            ``events``, ``headlines``, and ``surprises``.
        """
        # Condense decisions to save context: strip debate_log, raw_response
        condensed = []
        for d in all_country_decisions:
            condensed.append({
                "country": d.get("country", "??"),
                "country_name": d.get("country_name", ""),
                "actions": d.get("actions", []),
                "reasoning": str(d.get("reasoning", ""))[:300],
                "diplomatic_messages": d.get("diplomatic_messages", []),
            })

        # Build history context for resolution
        history_context = self._build_history_context(max_rounds=3)

        # Construct the prompt with history
        prompt_parts = [
            f"All countries have submitted their decisions for Round {world_state.round_number}. "
            "You must now resolve these actions simultaneously.",
            "",
            "CURRENT WORLD STATE:",
            world_state.to_json(),
        ]

        # Insert history context if available
        if history_context:
            prompt_parts.append("")
            prompt_parts.append(history_context)
            prompt_parts.append(
                "IMPORTANT: Consider the narrative arc and previous developments when resolving actions. "
                "Ensure continuity with past events and escalation patterns. "
                "Second-order effects from previous rounds should influence outcomes."
            )

        prompt_parts.append("")
        prompt_parts.append("COUNTRY DECISIONS THIS ROUND:")
        prompt_parts.append(json.dumps(condensed, indent=2, ensure_ascii=False))

        prompt_parts.append("")
        prompt_parts.append(
            "INSTRUCTIONS:\n"
            "1. Evaluate each action for realism.  If a country ordered something "
            "impossible or implausible, note it and substitute a lesser realistic outcome.\n"
            "2. Resolve military conflicts using force ratios, terrain, readiness, "
            "surprise, air support, and logistics.\n"
            "3. Determine economic consequences of all actions.\n"
            "4. Determine diplomatic consequences.\n"
            "5. Determine effects on public opinion in all involved countries.\n"
            "6. Generate 2-4 news headlines that world media would report.\n"
            "7. Generate 0-2 surprise developments (unexpected but plausible).\n"
            "8. Advance the game clock appropriately (each round is roughly 12-24 hours of game time)."
        )

        prompt_parts.append(
            "\nRespond with a single JSON object (no markdown, no commentary):\n"
            "{\n"
            '    "narrative": "<2-4 paragraph narrative of what happened this round>",\n'
            '    "world_state_updates": {\n'
            '        "game_time": "<new game time string>",\n'
            '        "military_units_add": [],\n'
            '        "military_units_remove": [],\n'
            '        "military_units_update": [\n'
            '            {"name": "<unit name>", "location": "<new loc>", "readiness": <int 1-10>, "strength": <int 1-10>, "casualties": <int cumulative>, "supply_level": <int 1-10>, "morale": <int 1-10>}\n'
            "        ],\n"
            '        "military_alerts": {"<country>": "<alert level>"},\n'
            '        "markets": {"oil_price": <float>, "euro_usd": <float>},\n'
            '        "sanctions_add": [{"from": "<country>", "target": "<country>", "type": "<description>"}],\n'
            '        "trade_disruptions_add": [],\n'
            '        "diplomatic_relations": {"<country>": {"<other_country>": <int -10..10>}},\n'
            '        "treaties_invoked_add": [],\n'
            '        "un_resolutions_add": [],\n'
            '        "nato_alert_level": "<normal|elevated|high|article5>",\n'
            '        "nato_consensus": {"<country>": "<position>"},\n'
            '        "nuclear_posture": {"<nuclear_country>": "<peacetime|elevated|dispersal|launch_ready>"},\n'
            '        "nuclear_detonations_add": [{"attacker": "<country>", "target": "<country|coordinates>", "yield_kt": <int>, "type": "<tactical|strategic>", "timestamp": "<game time>"}],\n'
            '        "public_opinion": {"<country>": {"war_support": <int 0-100>, "government_approval": <int 0-100>}},\n'
            '        "refugee_flows_add": [{"from": "<country>", "to": "<country>", "count": <int>, "status": "<fleeing|in_transit|settled|blocked>"}],\n'
            '        "humanitarian_crisis_level": {"<country>": <int 1-10>},\n'
            '        "cyber_operations_add": [{"attacker": "<country>", "target": "<country>", "type": "<ddos|malware|supply_chain|espionage|infrastructure>", "severity": "<low|medium|high|critical>", "infrastructure_affected": "<power_grid|comms|financial|military_c2|none>"}],\n'
            '        "infrastructure_status": {"<country>": {"power_grid": <int 1-10>, "comms": <int 1-10>, "financial": <int 1-10>, "military_c2": <int 1-10>}},\n'
            '        "recent_events": ["<event1>", "<event2>"],\n'
            '        "media_headlines": ["<headline1>", "<headline2>"]\n'
            "    },\n"
            '    "events": ["<significant event 1>", "<significant event 2>"],\n'
            '    "headlines": ["<headline1>", "<headline2>"],\n'
            '    "surprises": ["<surprise development, if any>"]\n'
            "}"
        )

        prompt = "\n".join(prompt_parts)

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=self.max_tokens,
        )

        parsed = parse_json_response(raw)

        # Validate and correct the response
        validated = self._validate_resolution(parsed)

        # Check if response is critically incomplete (both narrative and world_state_updates are effectively empty)
        is_critically_incomplete = (
            (not validated.get("narrative") or validated["narrative"] == "The round concluded with various actions unfolding across the theater of operations.")
            and not validated.get("world_state_updates")
        )

        # Retry once if critically incomplete
        if is_critically_incomplete:
            logger.warning("GM resolution critically incomplete, retrying with simplified prompt")
            retry_prompt = (
                "Your previous response was incomplete. Please provide a valid JSON response with "
                "at least a 'narrative' field (describing what happened this round in 2-4 paragraphs) "
                "and 'world_state_updates' field (containing any changes to the world state).\n\n"
                f"{prompt}"
            )

            raw_retry = await self.backend.generate(
                system_prompt=_GM_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": retry_prompt}],
                temperature=0.5,
                max_tokens=self.max_tokens,
            )

            parsed_retry = parse_json_response(raw_retry)
            validated = self._validate_resolution(parsed_retry)

        # Return the validated result
        result: dict[str, Any] = {
            "narrative": validated["narrative"],
            "world_state_updates": validated["world_state_updates"],
            "events": validated["events"],
            "headlines": validated["headlines"],
            "surprises": validated["surprises"],
        }
        return result

    async def generate_private_intel(
        self,
        world_state: WorldState,
        country_code: str,
    ) -> str:
        """Generate a country-specific classified intelligence briefing.

        Returns:
            The intelligence briefing as a formatted string.
        """
        # Build history context for intel (last 2 rounds for recent developments)
        history_context = self._build_history_context(max_rounds=2)

        # Construct the prompt with history
        prompt_parts = [
            f"Generate a PRIVATE intelligence briefing for {country_code}.",
            "",
            f"This briefing contains information that ONLY {country_code} would know through "
            "its own intelligence services, satellite reconnaissance, signals intelligence, "
            "human intelligence networks, and internal government communications.",
            "",
            "Current world state:",
            world_state.to_json(),
        ]

        # Insert history context if available
        if history_context:
            prompt_parts.append("")
            prompt_parts.append(history_context)
            prompt_parts.append(
                "IMPORTANT: Intelligence reports should reference evolving situations from previous rounds. "
                "Track developments over time (e.g., 'enemy force buildup continues', "
                "'diplomatic posture has shifted from...')."
            )

        prompt_parts.append("")
        prompt_parts.append(
            f"The briefing should include 3-5 items. CRITICAL REALISM RULES FOR INTELLIGENCE:\n"
            "\n"
            "1. FOG OF WAR: At least ONE item must contain INACCURATE or OUTDATED information "
            "that the intelligence service believes is true but is actually wrong. Real "
            "intelligence is never perfect. Examples: wrong troop counts, misidentified "
            "unit types, outdated positions (12-24h old), misread intentions.\n"
            "\n"
            "2. CONTRADICTIONS: If possible, include one item that partially contradicts "
            "another item (e.g. SIGINT suggests attack, but HUMINT suggests diplomacy). "
            "Real intelligence often presents conflicting pictures.\n"
            "\n"
            "3. CONFIDENCE LEVELS: Each item MUST have an individual confidence level. "
            "Not all intelligence is equally reliable. HUMINT from a new source is less "
            "reliable than satellite imagery.\n"
            "\n"
            "4. INTELLIGENCE GAPS: Mention 1-2 things the intelligence service DOES NOT "
            "know and is trying to find out. Absence of information is itself information.\n"
            "\n"
            "Item types:\n"
            "- Intercepted communications or signals intelligence\n"
            "- Satellite imagery analysis of enemy movements\n"
            "- Reports from human intelligence assets\n"
            "- Internal political dynamics (factions within the leadership)\n"
            "- Assessment of enemy intentions or capabilities\n"
            "- Cyber intelligence\n"
            "- Economic intelligence not publicly available\n"
            "\n"
            f"Make it realistic for {country_code}'s actual intelligence capabilities. "
            "A small country has weaker SIGINT/IMINT; a major power has better coverage "
            "but still has blind spots."
        )

        prompt_parts.append(
            "\nRespond with JSON:\n"
            "{\n"
            '    "intel_briefing": "<the classified briefing text>",\n'
            '    "overall_confidence": "<high|medium|low>",\n'
            "    \"items\": [\n"
            '        {"type": "<sigint|humint|imint|osint|cyber>", "content": "<detail>", "confidence": "<high|medium|low>", "reliability": "<A|B|C|D>", "caveat": "<any limitation or doubt about this item>"}\n'
            "    ],\n"
            '    "intelligence_gaps": ["<what we don\'t know yet>", "<another gap>"],\n'
            '    "fog_of_war_note": "<internal note: which item above is inaccurate and why -- this is for GM tracking only>"\n'
            "}"
        )

        prompt = "\n".join(prompt_parts)

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=self.max_tokens,
        )

        parsed = parse_json_response(raw)

        # Validate and correct the response
        validated = self._validate_intel(parsed)

        # Build a readable briefing from the structured response
        briefing_text = validated.get("intel_briefing", "")
        items = validated.get("items", [])
        if items:
            lines = [briefing_text, "", "INTELLIGENCE ITEMS:"]
            for item in items:
                reliability = item.get("reliability", "?")
                confidence = item.get("confidence", "medium").upper()
                itype = item.get("type", "unknown").upper()
                content = item.get("content", "")
                caveat = item.get("caveat", "")
                lines.append(
                    f"  [{itype} | Reliability: {reliability} | "
                    f"Confidence: {confidence}] {content}"
                )
                if caveat:
                    lines.append(f"    CAVEAT: {caveat}")

            # Intelligence gaps
            gaps = validated.get("intelligence_gaps", [])
            if gaps:
                lines.append("")
                lines.append("INTELLIGENCE GAPS (what we do NOT know):")
                for gap in gaps:
                    lines.append(f"  - {gap}")

            return "\n".join(lines)

        # Fallback: return raw text if JSON parsing failed
        return briefing_text if briefing_text else raw



# Note: JSON parsing is handled by utils.json_parser.parse_json_response
