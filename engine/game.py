"""Main game loop for the wargame simulation.

Orchestrates the full lifecycle of a game session:
1. Setup -- load scenario, initialise world state, create agents.
2. Round loop -- briefing, country deliberation, action resolution.
3. Teardown -- write summary, close resources.

Countries are processed **sequentially** because the local LLM backend
can only handle one request at a time.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Any

from backends import LLMBackend, create_backend
from agents.base import AgentConfig
from agents.faction import Faction
from agents.country import Country, CountryConfig
from engine.game_master import GameMaster
from engine.round_logger import RoundLogger
from engine.world_state import MilitaryUnit, WorldState
from utils.json_parser import parse_json_response

logger = logging.getLogger(__name__)

# Try to import rich for pretty console output; fall back to plain print.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    _console = Console()
    _HAS_RICH = True
except ImportError:  # pragma: no cover
    _HAS_RICH = False
    _console = None  # type: ignore[assignment]


# ======================================================================
# Pretty-printing helpers
# ======================================================================

def _print_header(text: str) -> None:
    if _HAS_RICH:
        _console.print(Panel(text, style="bold cyan", expand=False))
    else:
        print(f"\n{'='*60}\n{text}\n{'='*60}")


def _print_phase(country: str, phase: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [bold yellow]{country}[/bold yellow] -- {phase}")
    else:
        print(f"  {country} -- {phase}")


def _print_info(text: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [dim]{text}[/dim]")
    else:
        print(f"  {text}")


def _print_success(text: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [bold green]{text}[/bold green]")
    else:
        print(f"  {text}")


def _print_error(text: str) -> None:
    if _HAS_RICH:
        _console.print(f"  [bold red]{text}[/bold red]")
    else:
        print(f"  ERROR: {text}")


def _print_narrative(text: str) -> None:
    if _HAS_RICH:
        _console.print(Panel(text, title="Round Narrative", style="green", expand=True))
    else:
        print(f"\n--- Round Narrative ---\n{text}\n---")


# ======================================================================
# Country stub (placeholder until agents/ layer is built)
# ======================================================================

class _CountryStub:
    """Minimal stand-in for a country agent.

    When the ``agents`` layer is fully implemented, this will be replaced
    by the real :class:`agents.country.CountryAgent` class.  For now it
    uses the LLM backend directly with a simple prompt to generate
    decisions.
    """

    def __init__(
        self,
        code: str,
        name: str,
        config: dict,
        backend: LLMBackend,
    ) -> None:
        self.code = code
        self.name = name
        self.config = config
        self.backend = backend

    async def deliberate(
        self,
        briefing: str,
        intel: str,
        world_state: WorldState,
    ) -> dict:
        """Run internal deliberation and return a decision dict.

        Returns:
            ``{"country": "<code>", "actions": [...], "diplomatic_messages": [...]}``
        """
        system_prompt = (
            f"You are the national security council of {self.name} ({self.code}). "
            f"Based on the situation briefing and intelligence provided, decide "
            f"what actions your country will take this round. Be realistic about "
            f"your capabilities and constraints.\n\n"
            f"Country profile:\n{_dict_to_text(self.config)}"
        )

        user_msg = (
            f"SITUATION BRIEFING:\n{briefing}\n\n"
            f"CLASSIFIED INTELLIGENCE:\n{intel}\n\n"
            f"Decide your actions for this round. Respond with JSON:\n"
            f'{{"actions": ["<action 1>", "<action 2>", ...], '
            f'"diplomatic_messages": [{{"to": "<country>", "content": "<message>"}}], '
            f'"reasoning": "<brief internal reasoning>"}}'
        )

        raw = await self.backend.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            temperature=0.7,
        )

        # Attempt to parse JSON from the response
        parsed = parse_json_response(raw)
        if "_raw" in parsed:
            # Parsing failed: wrap raw text as a single action
            actions = [parsed["_raw"]]
            diplomatic = []
            reasoning = "Could not parse structured response."
        else:
            actions = parsed.get("actions", [])
            diplomatic = parsed.get("diplomatic_messages", [])
            reasoning = parsed.get("reasoning", "")

        return {
            "country": self.code,
            "country_name": self.name,
            "actions": actions,
            "diplomatic_messages": diplomatic,
            "reasoning": reasoning,
            "raw_response": raw,
        }


def _dict_to_text(d: dict, indent: int = 0) -> str:
    """Recursively format a dictionary as indented text."""
    lines = []
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{prefix}{k}:")
            lines.append(_dict_to_text(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(_dict_to_text(item, indent + 1))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)



# Note: JSON parsing now handled by utils.json_parser.parse_json_response


# ======================================================================
# Main Game class
# ======================================================================

class Game:
    """Orchestrates a full wargame session.

    Args:
        config: A configuration dictionary with at least the following
            keys:

            - ``backend`` (dict): kwargs for :func:`backends.create_backend`
              (must include ``"type"`` or ``"name"``).
            - ``scenario`` (dict): Scenario definition including
              ``"countries"``, ``"initial_state"``, and ``"rounds"``.
            - ``logs_dir`` (str, optional): Base directory for game logs.
              Defaults to ``"logs"``.

    Example *config*::

        {
            "backend": {"name": "ollama", "model": "deepseek-r1:32b"},
            "scenario": {
                "name": "Suwalki Gap Crisis",
                "rounds": 6,
                "countries": {
                    "RUS": {"name": "Russia", ...},
                    "USA": {"name": "United States", ...},
                    ...
                },
                "initial_state": { ... }
            }
        }
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.backend: LLMBackend | None = None
        self.game_master: GameMaster | None = None
        self.world_state: WorldState | None = None
        self.countries: dict[str, Country | _CountryStub] = {}
        self.logger: RoundLogger | None = None
        self.total_rounds: int = config.get("scenario", {}).get("rounds", 6)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Initialise the backend, world state, countries, and GM.

        Must be called before :meth:`run` or :meth:`run_round`.
        """
        _print_header("WARGAME SETUP")

        # --- Backend ---
        backend_cfg = dict(self.config.get("backend", {}))  # copy to avoid mutating config
        backend_name = backend_cfg.pop("name", backend_cfg.pop("type", "ollama"))
        self.backend = create_backend(backend_name, **backend_cfg)
        _print_info(f"Backend: {backend_name}")

        # --- Scenario ---
        scenario_cfg = self.config.get("scenario", {})
        _print_info(f"Scenario: {scenario_cfg.get('name', 'Unnamed')}")
        _print_info(f"Rounds: {self.total_rounds}")

        # --- World state ---
        initial = scenario_cfg.get("initial_state", {})
        self.world_state = self._build_initial_state(initial)
        _print_info(
            f"Military units: {len(self.world_state.military_units)} | "
            f"Countries: {len(scenario_cfg.get('countries', {}))}"
        )

        # --- Countries ---
        for code, country_cfg in scenario_cfg.get("countries", {}).items():
            name = country_cfg.get("name", code)
            country_obj = self._build_country(code, country_cfg, self.backend)
            self.countries[code] = country_obj
            n_factions = len(country_obj.factions) if isinstance(country_obj, Country) else 0
            _print_info(f"  Loaded country: {name} ({code}) - {n_factions} factions")

        # --- Game Master ---
        self.game_master = GameMaster(backend=self.backend, scenario_config=scenario_cfg)
        _print_info("Game Master initialised")

        # --- Logger ---
        logs_dir = self.config.get("logs_dir", "logs")
        self.logger = RoundLogger.create_for_new_game(base_dir=logs_dir)
        _print_info(f"Logging to: {self.logger.game_dir}")

        _print_success("Setup complete.")

    # ------------------------------------------------------------------
    # Round execution
    # ------------------------------------------------------------------

    async def run_round(self, round_num: int) -> dict[str, Any]:
        """Execute a single round of the wargame.

        Steps:
            1. GM generates the situation briefing.
            2. Each country receives the briefing + private intel.
            3. Each country deliberates (sequentially -- one LLM call at a
               time for local models).
            4. GM resolves all actions simultaneously.
            5. World state is updated.
            6. Everything is logged.

        Args:
            round_num: 1-based round number.

        Returns:
            A dictionary containing the full round record (briefing,
            per-country decisions, GM resolution, world state snapshot).
        """
        assert self.game_master is not None
        assert self.world_state is not None
        assert self.logger is not None

        round_start = time.time()
        self.world_state.round_number = round_num

        _print_header(f"ROUND {round_num} of {self.total_rounds}")

        round_record: dict[str, Any] = {
            "round": round_num,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # --- 1. Situation briefing ---
        _print_phase("Game Master", "Generating situation briefing...")
        briefing = await self.game_master.generate_situation_briefing(
            self.world_state, round_num
        )
        round_record["briefing"] = briefing
        _print_info(f"Briefing length: {len(briefing)} chars")

        # --- 2 & 3. Country deliberation (SEQUENTIAL) ---
        all_decisions: list[dict] = []
        diplomatic_messages: list[dict] = []

        for code, country in self.countries.items():
            cname = country.config.name if isinstance(country, Country) else country.name
            _print_phase(cname, "Receiving intelligence...")
            try:
                intel = await self.game_master.generate_private_intel(
                    self.world_state, code
                )
            except Exception as exc:
                _print_error(f"Intel generation failed for {code}: {exc}")
                logger.exception("Intel generation failed for %s", code)
                intel = "Intelligence services report no new developments."

            _print_phase(cname, "Deliberating...")
            try:
                if isinstance(country, Country):
                    # Real multi-faction debate
                    world_context = self.world_state.to_briefing(for_country=code)
                    combined_briefing = f"{briefing}\n\nCLASSIFIED INTELLIGENCE:\n{intel}"
                    debate_result = await country.run_internal_debate(
                        situation_briefing=combined_briefing,
                        world_context=world_context,
                    )
                    decision = {
                        "country": code,
                        "country_name": country.config.name,
                        "actions": debate_result.get("actions", []),
                        "diplomatic_messages": [],
                        "reasoning": debate_result.get("decision", ""),
                        "debate_log": debate_result.get("debate_log", []),
                        "dissent": debate_result.get("dissent", ""),
                    }
                else:
                    # Fallback stub
                    decision = await country.deliberate(
                        briefing=briefing,
                        intel=intel,
                        world_state=self.world_state,
                    )
                all_decisions.append(decision)

                # Collect diplomatic messages
                for msg in decision.get("diplomatic_messages", []):
                    diplomatic_messages.append({
                        "from": code,
                        "to": msg.get("to", "?"),
                        "content": msg.get("content", ""),
                    })

                num_actions = len(decision.get("actions", []))
                _print_info(f"  Actions: {num_actions}")
                if decision.get("dissent"):
                    _print_info(f"  Dissent: {decision['dissent'][:80]}...")

            except Exception as exc:
                _print_error(f"Country {code} failed: {exc}")
                logger.exception("Country %s deliberation failed", code)
                all_decisions.append({
                    "country": code,
                    "country_name": cname,
                    "actions": ["No action taken (agent error)"],
                    "error": str(exc),
                })

        round_record["country_decisions"] = all_decisions
        round_record["diplomatic_messages"] = diplomatic_messages

        # --- 4. Deliver diplomatic messages (for logging; content is
        #     visible to GM during resolution) ---
        if diplomatic_messages:
            _print_info(f"Diplomatic messages exchanged: {len(diplomatic_messages)}")

        # --- 5. GM resolves actions ---
        _print_phase("Game Master", "Resolving actions...")
        try:
            resolution = await self.game_master.resolve_actions(
                self.world_state, all_decisions
            )
        except Exception as exc:
            _print_error(f"GM resolution failed: {exc}")
            logger.exception("GM resolution failed")
            resolution = {
                "narrative": f"Resolution error: {exc}",
                "world_state_updates": {},
                "events": [],
                "headlines": [],
                "surprises": [],
            }

        round_record["resolution"] = resolution

        # --- 6. Apply world state updates ---
        updates = resolution.get("world_state_updates", {})
        self.world_state.apply_updates(updates)
        round_record["world_state_after"] = self.world_state.to_dict()

        # Display narrative
        narrative = resolution.get("narrative", "")
        if narrative:
            _print_narrative(narrative)

        # Display headlines
        headlines = resolution.get("headlines", [])
        if headlines:
            _print_info("Headlines:")
            for hl in headlines:
                _print_info(f"  * {hl}")

        # Display surprises
        surprises = resolution.get("surprises", [])
        if surprises:
            _print_info("Surprise developments:")
            for s in surprises:
                _print_info(f"  ! {s}")

        # --- 7. Log ---
        elapsed = time.time() - round_start
        round_record["elapsed_seconds"] = round(elapsed, 1)
        self.logger.log_round(round_num, round_record)

        _print_success(f"Round {round_num} complete ({elapsed:.1f}s)")
        return round_record

    # ------------------------------------------------------------------
    # Full game run
    # ------------------------------------------------------------------

    async def run(self) -> dict[str, Any]:
        """Run the entire game for the configured number of rounds.

        Returns:
            A summary dictionary with overall game statistics.
        """
        assert self.world_state is not None, "Call setup() before run()."
        assert self.logger is not None

        _print_header(
            f"STARTING WARGAME: {self.config.get('scenario', {}).get('name', 'Unnamed')}"
        )

        game_start = time.time()
        round_records: list[dict] = []
        round_times: list[float] = []

        for round_num in range(1, self.total_rounds + 1):
            try:
                record = await self.run_round(round_num)
                round_records.append(record)

                # Track timing and show ETA
                elapsed_round = record.get("elapsed_seconds", 0)
                round_times.append(elapsed_round)
                avg_time = sum(round_times) / len(round_times)
                remaining = self.total_rounds - round_num
                eta_seconds = avg_time * remaining
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                _print_info(
                    f"Progress: {round_num}/{self.total_rounds} "
                    f"({round_num * 100 // self.total_rounds}%) | "
                    f"Avg {avg_time:.0f}s/round | "
                    f"ETA: {eta_min}m {eta_sec}s"
                )
            except Exception as exc:
                _print_error(f"Round {round_num} failed catastrophically: {exc}")
                logger.exception("Round %d failed", round_num)
                traceback.print_exc()
                # Continue to next round even if this one failed entirely
                continue

        # --- Summary ---
        total_elapsed = time.time() - game_start
        summary: dict[str, Any] = {
            "scenario": self.config.get("scenario", {}).get("name", "Unnamed"),
            "total_rounds": self.total_rounds,
            "rounds_completed": len(round_records),
            "total_time_seconds": round(total_elapsed, 1),
            "final_world_state": self.world_state.to_dict() if self.world_state else {},
            "final_briefing": (
                self.world_state.to_briefing() if self.world_state else ""
            ),
        }
        self.logger.log_summary(summary)

        _print_header("GAME COMPLETE")
        _print_info(f"Rounds completed: {len(round_records)}/{self.total_rounds}")
        _print_info(f"Total time: {total_elapsed:.1f}s")
        _print_info(f"Logs: {self.logger.game_dir}")

        return summary

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release all resources (LLM backend sessions, etc.)."""
        if self.backend:
            await self.backend.close()
            _print_info("Backend closed.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_country(code: str, cfg: dict, backend: LLMBackend) -> Country | _CountryStub:
        """Build a Country with real Faction agents from a country config dict.

        Falls back to _CountryStub if the config has no factions list.
        """
        factions_cfg = cfg.get("factions", [])
        if not factions_cfg:
            return _CountryStub(code=code, name=cfg.get("name", code), config=cfg, backend=backend)

        # Country-level context to inject into faction personalities
        nuclear_status = cfg.get("nuclear", False)
        country_name = cfg.get("name", code)

        factions: list[Faction] = []
        for fc in factions_cfg:
            # Enrich personality with key_relationships and nuclear status
            personality = fc.get("personality", "")
            key_rels = fc.get("key_relationships", {})
            if key_rels:
                allies = ", ".join(key_rels.get("allies", []))
                rivals = ", ".join(key_rels.get("rivals", []))
                if allies:
                    personality += f"\n\nYour key allies: {allies}"
                if rivals:
                    personality += f"\nYour key rivals: {rivals}"
            if nuclear_status:
                personality += f"\n\nIMPORTANT: {country_name} is a nuclear-armed state. This shapes all strategic calculations."

            agent_cfg = AgentConfig(
                name=fc.get("name", "Unknown Faction"),
                role=fc.get("role", "advisor"),
                personality=personality,
                priorities=fc.get("priorities", []),
                red_lines=fc.get("red_lines", []),
                voice=fc.get("voice", ""),
                country_code=code,
            )
            factions.append(Faction(config=agent_cfg, backend=backend))

        description = cfg.get("geographic_relevance", "")
        if nuclear_status:
            description += f"\n{country_name} possesses nuclear weapons."

        country_config = CountryConfig(
            name=country_name,
            code=code,
            alliances=cfg.get("alliances", []),
            military_strength=cfg.get("military_strength", 5),
            economic_strength=cfg.get("economic_strength", 5),
            description=description,
        )
        return Country(config=country_config, factions=factions, backend=backend)

    def _build_initial_state(self, initial: dict) -> WorldState:
        """Construct a :class:`WorldState` from the scenario's initial_state dict."""
        state = WorldState()

        # Military units
        for u in initial.get("military_units", []):
            state.military_units.append(MilitaryUnit(**u))

        # Scalars
        state.nato_alert_level = initial.get("nato_alert_level", "elevated")
        state.game_time = initial.get("game_time", "Day 1, 00:00")

        # Dicts
        state.military_alerts = initial.get("military_alerts", {})
        state.markets = initial.get("markets", {
            "oil_price": 95.0,
            "euro_usd": 1.08,
            "stock_indices": "declining",
        })
        state.diplomatic_relations = initial.get("diplomatic_relations", {})
        state.nato_consensus = initial.get("nato_consensus", {})
        state.public_opinion = initial.get("public_opinion", {})

        # Lists
        state.sanctions = initial.get("sanctions", [])
        state.trade_disruptions = initial.get("trade_disruptions", [])
        state.treaties_invoked = initial.get("treaties_invoked", [])
        state.un_resolutions = initial.get("un_resolutions", [])
        state.recent_events = initial.get("recent_events", [
            "Russia has seized the Suwalki Gap corridor.",
            "Baltic states are cut off from NATO by land.",
            "Emergency NATO summit called.",
        ])
        state.media_headlines = initial.get("media_headlines", [
            "BREAKING: Russian forces occupy Suwalki Gap",
            "NATO calls emergency Article 4 consultations",
            "Baltic states demand immediate response",
            "Global markets tumble on escalation fears",
        ])

        return state
