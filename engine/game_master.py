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
import re
from typing import Any

from backends.base import LLMBackend
from engine.world_state import WorldState

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
            {{"name": "<unit name>", "location": "<new loc>", "readiness": <int>, "strength": <int>}}
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
        "public_opinion": {{"<country>": {{"war_support": <int 0-100>, "government_approval": <int 0-100>}}}},
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

The briefing should include 2-4 items such as:
- Intercepted communications or signals intelligence
- Satellite imagery analysis of enemy movements
- Reports from human intelligence assets
- Internal political dynamics (factions within the leadership)
- Assessment of enemy intentions or capabilities
- Cyber intelligence
- Economic intelligence not publicly available

Make it realistic for {country_code}'s actual intelligence capabilities.

Respond with JSON:
{{
    "intel_briefing": "<the classified briefing text>",
    "confidence_level": "<high|medium|low>",
    "items": [
        {{"type": "<sigint|humint|imint|osint|cyber>", "content": "<detail>", "reliability": "<A|B|C|D>"}}
    ]
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

    def __init__(self, backend: LLMBackend, scenario_config: dict) -> None:
        self.backend = backend
        self.scenario = scenario_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_situation_briefing(
        self,
        world_state: WorldState,
        round_num: int,
    ) -> str:
        """Generate the narrative situation report for the start of a round.

        Returns:
            A multi-paragraph narrative briefing string.
        """
        prompt = _BRIEFING_PROMPT_TEMPLATE.format(
            round_num=round_num,
            world_state_json=world_state.to_json(),
        )

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        parsed = _parse_json_response(raw)
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
        prompt = _RESOLVE_PROMPT_TEMPLATE.format(
            round_num=world_state.round_number,
            world_state_json=world_state.to_json(),
            decisions_json=json.dumps(all_country_decisions, indent=2, ensure_ascii=False),
        )

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        parsed = _parse_json_response(raw)

        # Guarantee expected top-level keys exist
        result: dict[str, Any] = {
            "narrative": parsed.get("narrative", "No narrative generated."),
            "world_state_updates": parsed.get("world_state_updates", {}),
            "events": parsed.get("events", []),
            "headlines": parsed.get("headlines", []),
            "surprises": parsed.get("surprises", []),
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
        prompt = _INTEL_PROMPT_TEMPLATE.format(
            country_code=country_code,
            world_state_json=world_state.to_json(),
        )

        raw = await self.backend.generate(
            system_prompt=_GM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        parsed = _parse_json_response(raw)

        # Build a readable briefing from the structured response
        briefing_text = parsed.get("intel_briefing", "")
        items = parsed.get("items", [])
        if items:
            lines = [briefing_text, "", "INTELLIGENCE ITEMS:"]
            for item in items:
                reliability = item.get("reliability", "?")
                itype = item.get("type", "unknown").upper()
                content = item.get("content", "")
                lines.append(f"  [{itype} | Reliability: {reliability}] {content}")
            return "\n".join(lines)

        # Fallback: return raw text if JSON parsing failed
        return briefing_text if briefing_text else raw


# ======================================================================
# Private helpers
# ======================================================================

def _parse_json_response(raw: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response.

    Local models sometimes wrap JSON in markdown fences, include a preamble,
    produce trailing text, or include <think>...</think> reasoning blocks.
    This function tries multiple strategies:
    1. Direct ``json.loads``.
    2. Strip ``<think>...</think>`` blocks (DeepSeek R1 reasoning).
    3. Strip markdown code fences.
    4. Find the outermost ``{...}`` block.
    5. Attempt to fix common JSON issues (trailing commas, single quotes).
    """
    text = raw.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip <think>...</think> reasoning blocks
    text_no_think = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text_no_think != text:
        try:
            return json.loads(text_no_think)
        except json.JSONDecodeError:
            pass
        text = text_no_think

    # 3. Strip markdown fences (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 4. Find outermost { ... } block
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        brace_end = -1
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break
        if brace_end != -1:
            candidate = text[brace_start : brace_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # 5. Try fixing common LLM JSON issues
            fixed = candidate
            # Remove trailing commas before } or ]
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            # Replace single quotes with double quotes (crude but helps)
            if "'" in fixed and '"' not in fixed:
                fixed = fixed.replace("'", '"')
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    logger.warning("Failed to parse JSON from GM response. Returning raw text in wrapper.")
    return {"_raw": text}
