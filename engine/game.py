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
from engine.analytics import generate_analytics, format_analytics_text
from engine.checkpoint import save_checkpoint, collect_agent_histories
from engine.dashboard import Dashboard, compute_escalation_level
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
        self.dashboard: Dashboard | None = None
        self.total_rounds: int = config.get("scenario", {}).get("rounds", 6)
        # Diplomatic message buffer: messages from previous round delivered next round
        self._diplomatic_inbox: list[dict] = []
        # Cross-round memory: summary of last round's decisions for context
        self._previous_round_summary: str = ""
        # Territorial control tracking for end conditions
        self._corridor_hold_rounds: int = 0
        self._corridor_was_contested: bool = False

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
        debate_max_tokens = self.config.get("debate", {}).get("max_tokens_per_response")
        for code, country_cfg in scenario_cfg.get("countries", {}).items():
            name = country_cfg.get("name", code)
            country_obj = self._build_country(code, country_cfg, self.backend, debate_max_tokens)
            self.countries[code] = country_obj
            n_factions = len(country_obj.factions) if isinstance(country_obj, Country) else 0
            _print_info(f"  Loaded country: {name} ({code}) - {n_factions} factions")

        # --- Game Master ---
        gm_max_tokens = self.config.get("game_master", {}).get("max_tokens")
        self.game_master = GameMaster(
            backend=self.backend,
            scenario_config=scenario_cfg,
            max_tokens=gm_max_tokens,
        )
        _print_info("Game Master initialised")

        # --- Logger ---
        logs_dir = self.config.get("logs_dir", "logs")
        self.logger = RoundLogger.create_for_new_game(base_dir=logs_dir)
        _print_info(f"Logging to: {self.logger.game_dir}")

        # --- Dashboard ---
        self.dashboard = Dashboard(
            game_dir=self.logger.game_dir,
            total_rounds=self.total_rounds,
            num_countries=len(self.countries),
            scenario_name=scenario_cfg.get("name", ""),
        )

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
        if self.dashboard:
            self.dashboard.update(phase="briefing", round_num=round_num)
        _print_phase("Game Master", "Generating situation briefing...")
        briefing = await self.game_master.generate_situation_briefing(
            self.world_state, round_num,
            previous_round_summary=self._previous_round_summary,
        )
        round_record["briefing"] = briefing
        _print_info(f"Briefing length: {len(briefing)} chars")

        # --- 2 & 3. Country deliberation ---
        if self.dashboard:
            self.dashboard.update(phase="deliberation")
        use_parallel = (
            self.backend is not None
            and self.backend.supports_parallel
        )

        if use_parallel:
            _print_info(
                f"Parallel mode: deliberating {len(self.countries)} "
                f"countries concurrently"
            )
            all_decisions, diplomatic_messages = (
                await self._deliberate_parallel(briefing)
            )
        else:
            all_decisions, diplomatic_messages = (
                await self._deliberate_sequential(briefing)
            )

        round_record["country_decisions"] = all_decisions

        # --- 4. Collect diplomatic messages from debate synthesis ---
        outgoing = self._collect_outgoing_messages(all_decisions)
        all_diplomatic = diplomatic_messages + outgoing
        round_record["diplomatic_messages"] = all_diplomatic

        if all_diplomatic:
            _print_info(f"Diplomatic messages exchanged: {len(all_diplomatic)}")
            for dm in all_diplomatic:
                ch = dm.get("channel", "public").upper()
                _print_info(
                    f"  [{ch}] {dm.get('from','?')} -> {dm.get('to','?')}: "
                    f"{dm.get('message','')[:80]}..."
                )

        # Store messages for delivery next round
        self._diplomatic_inbox = all_diplomatic

        # --- 5. GM resolves actions ---
        if self.dashboard:
            self.dashboard.update(phase="resolution")
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

        # BUG FIX 3: Track corridor control based on GM resolution content
        self._update_corridor_control(resolution)

        # Record round summary for GM memory
        if self.game_master is not None:
            # Build compact summary from this round's data
            key_decisions = []
            for dec in all_decisions[:5]:  # Top 5 countries
                country = dec.get("country", "Unknown")
                actions = dec.get("actions", [])
                if actions:
                    key_decisions.append(f"{country}: {actions[0]}")

            briefing_summary = briefing[:200] if briefing else "No briefing"
            resolution_summary = resolution.get("narrative", "")[:300] if resolution else "No resolution"

            self.game_master.record_round_summary(
                round_num=round_num,
                briefing_summary=briefing_summary,
                key_decisions=key_decisions,
                resolution_summary=resolution_summary,
            )

        # Store summary for cross-round memory
        self._previous_round_summary = self._build_round_summary(
            all_decisions, resolution
        )

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

        # Update dashboard with round results
        if self.dashboard:
            ws_dict = self.world_state.to_dict()
            self.dashboard.update(
                round_time=elapsed / 60.0,  # minutes
                escalation_level=compute_escalation_level(ws_dict),
                headlines=headlines,
            )

        _print_success(f"Round {round_num} complete ({elapsed:.1f}s)")
        return round_record

    # ------------------------------------------------------------------
    # Full game run
    # ------------------------------------------------------------------

    async def run(self, start_round: int = 1) -> dict[str, Any]:
        """Run the entire game for the configured number of rounds.

        Args:
            start_round: Round number to start from (default 1). Used for
                resuming from a checkpoint.

        Returns:
            A summary dictionary with overall game statistics.
        """
        assert self.world_state is not None, "Call setup() before run()."
        assert self.logger is not None

        _print_header(
            f"STARTING WARGAME: {self.config.get('scenario', {}).get('name', 'Unnamed')}"
        )
        if start_round > 1:
            _print_info(f"Resuming from round {start_round} (rounds 1-{start_round - 1} already completed)")

        # Start the live dashboard
        if self.dashboard:
            self.dashboard.start()

        game_start = time.time()
        round_records: list[dict] = []
        round_times: list[float] = []
        end_condition_triggered: dict | None = None

        for round_num in range(start_round, self.total_rounds + 1):
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

                # Save checkpoint after each round
                try:
                    save_checkpoint(
                        game_dir=self.logger.game_dir,
                        round_completed=round_num,
                        world_state_dict=self.world_state.to_dict(),
                        diplomatic_inbox=self._diplomatic_inbox,
                        previous_round_summary=self._previous_round_summary,
                        corridor_hold_rounds=self._corridor_hold_rounds,
                        corridor_was_contested=self._corridor_was_contested,
                        gm_round_history=self.game_master._round_history if self.game_master else [],
                        agent_histories=collect_agent_histories(self),
                        total_rounds=self.total_rounds,
                        config=self.config,
                    )
                except Exception as ckpt_err:
                    _print_error(f"Checkpoint save failed: {ckpt_err}")
                    logger.exception("Checkpoint save failed after round %d", round_num)

                # Check victory / end conditions
                end_condition_triggered = self.check_end_conditions()
                if end_condition_triggered:
                    _print_header("ENDGAME CONDITION TRIGGERED")
                    _print_info(f"Condition: {end_condition_triggered.get('description', '?')}")
                    _print_info(f"Winner: {end_condition_triggered.get('winner', '?')}")
                    break

            except Exception as exc:
                _print_error(f"Round {round_num} failed catastrophically: {exc}")
                logger.exception("Round %d failed", round_num)
                traceback.print_exc()
                if self.dashboard:
                    self.dashboard.update(error=str(exc))
                # Continue to next round even if this one failed entirely
                continue

        # Stop the live dashboard
        if self.dashboard:
            self.dashboard.stop()

        # --- Summary ---
        total_elapsed = time.time() - game_start
        summary: dict[str, Any] = {
            "scenario": self.config.get("scenario", {}).get("name", "Unnamed"),
            "total_rounds": self.total_rounds,
            "rounds_completed": len(round_records),
            "total_time_seconds": round(total_elapsed, 1),
            "end_condition": end_condition_triggered,
            "final_world_state": self.world_state.to_dict() if self.world_state else {},
            "final_briefing": (
                self.world_state.to_briefing() if self.world_state else ""
            ),
        }
        self.logger.log_summary(summary)

        # --- Post-game analytics ---
        _print_header("GENERATING POST-GAME ANALYTICS")
        try:
            analytics = generate_analytics(self.logger.game_dir)
            analytics_text = format_analytics_text(analytics)
            print(analytics_text)

            # Save analytics to file
            analytics_path = self.logger.game_dir / "analytics.json"
            import json as _json
            analytics_path.write_text(
                _json.dumps(analytics, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            _print_info(f"Analytics saved to: {analytics_path}")
        except Exception as exc:
            _print_error(f"Analytics generation failed: {exc}")
            logger.exception("Analytics failed")

        _print_header("GAME COMPLETE")
        _print_info(f"Rounds completed: {len(round_records)}/{self.total_rounds}")
        _print_info(f"Total time: {total_elapsed:.1f}s")
        _print_info(f"Logs: {self.logger.game_dir}")

        return summary

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def check_end_conditions(self) -> dict | None:
        """Check if any end/victory condition has been met.

        Returns the triggered condition dict, or None.
        """
        assert self.world_state is not None
        conditions = self.config.get("scenario", {}).get("end_conditions", [])
        if not conditions:
            return None

        for cond in conditions:
            ctype = cond.get("type", "")
            cid = cond.get("id", "")

            if ctype == "catastrophic" and cid == "nuclear_detonation":
                # FIX: Check actual detonations, not posture levels
                # Countries can now escalate to launch_ready without ending game
                if len(self.world_state.nuclear_detonations) > 0:
                    return cond

            if ctype == "political" and cid == "nato_collapse":
                # BUG FIX 2: Improved NATO collapse detection with positive/negative indicator analysis
                refusals = 0
                for pos in self.world_state.nato_consensus.values():
                    if not isinstance(pos, str):
                        pos = str(pos)
                    pos_lower = pos.lower()

                    # Check for positive indicators (support for Article 5)
                    positive_indicators = [
                        "support", "agree", "invoke", "commit", "stand with",
                        "honor", "activate", "defend", "solidarity"
                    ]
                    has_positive = any(indicator in pos_lower for indicator in positive_indicators)

                    # Check for negative indicators (refusal/opposition)
                    negative_indicators = [
                        "refuse", "reject", "oppose", "will not", "cannot support",
                        "no to article", "decline", "abstain"
                    ]
                    has_negative = any(indicator in pos_lower for indicator in negative_indicators)

                    # Special case: single word "no"
                    is_plain_no = pos.strip().lower() == "no"

                    # Count as refusal only if negative indicators exist WITHOUT positive indicators
                    if (has_negative or is_plain_no) and not has_positive:
                        refusals += 1

                if refusals >= 3:
                    return cond

            # BUG FIX 1: Implement territorial control end conditions
            if ctype == "territorial_control" and cid == "russian_corridor_hold":
                corridor_control = getattr(self.world_state, "corridor_control", None)
                if corridor_control == "russian":
                    self._corridor_hold_rounds += 1
                    # Default threshold: 6 rounds = 3 days at 12hr/round
                    # Can be overridden in end condition config
                    threshold = cond.get("threshold_rounds", 6)
                    if self._corridor_hold_rounds >= threshold:
                        return cond
                else:
                    self._corridor_hold_rounds = 0

            if ctype == "territorial_control" and cid == "nato_corridor_liberated":
                corridor_control = getattr(self.world_state, "corridor_control", None)
                # Track if corridor was ever contested or Russian-controlled
                if corridor_control in ("contested", "russian"):
                    self._corridor_was_contested = True
                # Trigger if corridor is now NATO-controlled after being contested
                if corridor_control == "nato" and self._corridor_was_contested:
                    return cond

            # Other conditions are checked via keywords in recent events
            if ctype == "diplomatic" and cid == "ceasefire_agreement":
                for ev in self.world_state.recent_events:
                    if "ceasefire" in ev.lower() and "agree" in ev.lower():
                        return cond

        return None

    async def close(self) -> None:
        """Release all resources (LLM backend sessions, etc.)."""
        if self.backend:
            await self.backend.close()
            _print_info("Backend closed.")

    # ------------------------------------------------------------------
    # Deliberation strategies
    # ------------------------------------------------------------------

    async def _deliberate_one_country(
        self, code: str, country: Country | _CountryStub, briefing: str,
    ) -> dict:
        """Run intel + deliberation for a single country.

        Returns a decision dict.  Used by both sequential and parallel paths.
        """
        assert self.game_master is not None
        assert self.world_state is not None

        cname = country.config.name if isinstance(country, Country) else country.name

        # Intel
        try:
            intel = await self.game_master.generate_private_intel(
                self.world_state, code
            )
        except Exception as exc:
            logger.exception("Intel generation failed for %s", code)
            intel = "Intelligence services report no new developments."

        # Deliberation
        try:
            if isinstance(country, Country):
                world_context = self.world_state.to_briefing(for_country=code)
                # Inject incoming diplomatic messages into briefing
                incoming_msgs = self._get_incoming_messages(code)
                combined_briefing = f"{briefing}\n\nCLASSIFIED INTELLIGENCE:\n{intel}"
                if incoming_msgs:
                    combined_briefing += "\n\nINCOMING DIPLOMATIC MESSAGES:\n" + incoming_msgs
                debate_result = await country.run_internal_debate(
                    situation_briefing=combined_briefing,
                    world_context=world_context,
                )
                decision = {
                    "country": code,
                    "country_name": country.config.name,
                    "actions": debate_result.get("actions", []),
                    "diplomatic_messages": debate_result.get("diplomatic_messages", []),
                    "reasoning": debate_result.get("decision", ""),
                    "debate_log": debate_result.get("debate_log", []),
                    "dissent": debate_result.get("dissent", ""),
                }
            else:
                decision = await country.deliberate(
                    briefing=briefing,
                    intel=intel,
                    world_state=self.world_state,
                )
        except Exception as exc:
            logger.exception("Country %s deliberation failed", code)
            decision = {
                "country": code,
                "country_name": cname,
                "actions": ["No action taken (agent error)"],
                "error": str(exc),
            }

        _print_phase(cname, f"{len(decision.get('actions', []))} actions")
        if decision.get("dissent"):
            _print_info(f"  Dissent: {decision['dissent'][:80]}...")

        return decision

    async def _deliberate_sequential(
        self, briefing: str,
    ) -> tuple[list[dict], list[dict]]:
        """Process all countries one at a time (for local backends)."""
        all_decisions: list[dict] = []
        diplomatic_messages: list[dict] = []

        for idx, (code, country) in enumerate(self.countries.items()):
            cname = country.config.name if isinstance(country, Country) else country.name
            n_factions = len(country.factions) if isinstance(country, Country) else 0
            if self.dashboard:
                self.dashboard.update(
                    country=cname,
                    country_index=idx + 1,
                    total_factions=n_factions,
                )
            _print_phase(cname, "Deliberating...")
            decision = await self._deliberate_one_country(code, country, briefing)
            all_decisions.append(decision)
            for msg in decision.get("diplomatic_messages", []):
                diplomatic_messages.append({
                    "from": code, "to": msg.get("to", "?"),
                    "content": msg.get("content", ""),
                })

        return all_decisions, diplomatic_messages

    async def _deliberate_parallel(
        self, briefing: str,
    ) -> tuple[list[dict], list[dict]]:
        """Process all countries concurrently (for API backends).

        Each country's internal debate is still sequential (round 2 depends
        on round 1), but different countries deliberate simultaneously.
        This turns a 30-country round from ~35 min to ~3 min with an API.
        """
        tasks = []
        country_order: list[str] = []

        for code, country in self.countries.items():
            country_order.append(code)
            tasks.append(
                self._deliberate_one_country(code, country, briefing)
            )

        # Run all countries concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_decisions: list[dict] = []
        diplomatic_messages: list[dict] = []

        for code, result in zip(country_order, results):
            if isinstance(result, Exception):
                cname = code
                if code in self.countries:
                    c = self.countries[code]
                    cname = c.config.name if isinstance(c, Country) else c.name
                _print_error(f"Country {cname} failed: {result}")
                all_decisions.append({
                    "country": code,
                    "country_name": cname,
                    "actions": ["No action taken (agent error)"],
                    "error": str(result),
                })
            else:
                all_decisions.append(result)
                for msg in result.get("diplomatic_messages", []):
                    diplomatic_messages.append({
                        "from": code, "to": msg.get("to", "?"),
                        "content": msg.get("content", ""),
                    })

        return all_decisions, diplomatic_messages

    # ------------------------------------------------------------------
    # Cross-round memory
    # ------------------------------------------------------------------

    @staticmethod
    def _build_round_summary(all_decisions: list[dict], resolution: dict) -> str:
        """Build a concise summary of what happened last round.

        This is injected into the next round's briefing to prevent
        countries from repeating the same actions and to give the GM
        context about the previous round's developments.
        """
        lines = ["PREVIOUS ROUND ACTIONS SUMMARY:"]
        for decision in all_decisions:
            code = decision.get("country", "??")
            name = decision.get("country_name", code)
            actions = decision.get("actions", [])
            if actions:
                action_str = "; ".join(str(a)[:100] for a in actions[:4])
                lines.append(f"  {name} ({code}): {action_str}")

        narrative = resolution.get("narrative", "")
        if narrative:
            # Take first 500 chars of narrative as outcome summary
            lines.append(f"\nOUTCOME: {narrative[:500]}")

        surprises = resolution.get("surprises", [])
        if surprises:
            lines.append("SURPRISE DEVELOPMENTS:")
            for s in surprises:
                lines.append(f"  - {s}")

        return "\n".join(lines)

    def _update_corridor_control(self, resolution: dict) -> None:
        """Update corridor control status based on GM resolution content.

        FIX: Uses regex word boundaries and confidence scoring to reduce
        false positives from fragile substring matching. Prefers explicit
        corridor_control field from GM if provided.
        """
        import re
        assert self.world_state is not None

        # PRIORITY 1: Check if GM provided explicit structured field
        updates = resolution.get("world_state_updates", {})
        if "corridor_control" in updates:
            explicit_control = str(updates["corridor_control"]).lower()
            if explicit_control in ("russian", "nato", "contested"):
                self.world_state.corridor_control = explicit_control
                return  # Trust explicit field, skip text analysis

        # PRIORITY 2: Analyze narrative text with improved pattern matching
        text_to_analyze = resolution.get("narrative", "").lower()

        for event in resolution.get("events", []):
            text_to_analyze += " " + str(event).lower()

        for headline in resolution.get("headlines", []):
            text_to_analyze += " " + str(headline).lower()

        # Also check recent_events from world state
        for event in self.world_state.recent_events:
            text_to_analyze += " " + str(event).lower()

        # Define regex patterns with word boundaries (more robust)
        # Pattern format: (pattern, confidence_weight)
        russian_patterns = [
            (r'\brussian\s+(forces\s+)?control\b.*\b(corridor|suwalki)', 1.0),
            (r'\bcorridor\s+(seized|captured)\b.*\brussia', 0.9),
            (r'\brussia\s+holds?\s+.*\bcorridor\b', 0.9),
            (r'\bcorridor\s+secured\b.*\brussia', 0.8),
            (r'\bsuwalki\s+seized\b', 0.8),
        ]

        nato_patterns = [
            (r'\bnato\s+(forces\s+)?control\b.*\b(corridor|suwalki)', 1.0),
            (r'\bcorridor\s+(liberated|recaptured|retaken|freed)\b', 0.9),
            (r'\bnato\s+holds?\s+.*\bcorridor\b', 0.9),
            (r'\brussian\s+withdrawal\b.*\bcorridor\b', 0.8),
        ]

        contested_patterns = [
            (r'\b(fighting|combat|battle)\s+(continues|ongoing)\b.*\b(corridor|suwalki)', 1.0),
            (r'\bcontested\s+.*\b(corridor|suwalki)', 0.9),
            (r'\bfierce\s+(fighting|combat)\b.*\b(corridor|suwalki)', 0.8),
            (r'\bneither\s+side\s+controls\b', 0.9),
        ]

        # Calculate confidence scores for each state
        russian_score = sum(weight for pattern, weight in russian_patterns
                           if re.search(pattern, text_to_analyze))
        nato_score = sum(weight for pattern, weight in nato_patterns
                        if re.search(pattern, text_to_analyze))
        contested_score = sum(weight for pattern, weight in contested_patterns
                             if re.search(pattern, text_to_analyze))

        # Determine control based on highest confidence score
        # Require minimum threshold (0.7) to change state
        max_score = max(russian_score, nato_score, contested_score)

        if max_score >= 0.7:
            if contested_score == max_score:
                self.world_state.corridor_control = "contested"
            elif russian_score == max_score:
                self.world_state.corridor_control = "russian"
            elif nato_score == max_score:
                self.world_state.corridor_control = "nato"
        # Else: maintain current state (ambiguous signal)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_incoming_messages(self, country_code: str) -> str:
        """Return formatted diplomatic messages addressed to *country_code*.

        A country sees:
        - All ``public`` messages from any sender.
        - ``private`` messages addressed specifically to it.
        - ``backchannel`` messages addressed specifically to it (marked deniable).

        Returns an empty string if there are no relevant messages.
        """
        lines: list[str] = []
        for msg in self._diplomatic_inbox:
            channel = msg.get("channel", "public")
            to = msg.get("to", "").upper()
            sender = msg.get("from", "??")
            text = msg.get("message", "")

            if channel == "public":
                lines.append(f"[PUBLIC from {sender}]: {text}")
            elif channel == "private" and to == country_code.upper():
                lines.append(f"[PRIVATE from {sender}]: {text}")
            elif channel == "backchannel" and to == country_code.upper():
                lines.append(f"[BACKCHANNEL from {sender} -- deniable]: {text}")
        return "\n".join(lines)

    def _collect_outgoing_messages(
        self, all_decisions: list[dict],
    ) -> list[dict]:
        """Extract diplomatic messages from all country decisions and tag sender."""
        messages: list[dict] = []
        for decision in all_decisions:
            sender = decision.get("country", "??")
            for msg in decision.get("diplomatic_messages", []):
                messages.append({
                    "from": sender,
                    "to": msg.get("to", "??"),
                    "channel": msg.get("channel", "public"),
                    "message": msg.get("message", msg.get("content", "")),
                })
        return messages

    @staticmethod
    def _build_country(
        code: str, cfg: dict, backend: LLMBackend,
        debate_max_tokens: int | None = None,
    ) -> Country | _CountryStub:
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
            factions.append(Faction(config=agent_cfg, backend=backend, max_tokens=debate_max_tokens))

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
        return Country(
            config=country_config,
            factions=factions,
            backend=backend,
            max_tokens_per_response=debate_max_tokens,
        )

    def _build_initial_state(self, initial: dict) -> WorldState:
        """Construct a :class:`WorldState` from the scenario's initial_state dict."""
        state = WorldState()

        # Military units
        for u in initial.get("military_units", []):
            state.military_units.append(MilitaryUnit(**u))

        # Scalars
        state.nato_alert_level = initial.get("nato_alert_level", "elevated")
        state.game_time = initial.get("game_time", "Day 1, 00:00")
        state.corridor_control = initial.get("corridor_control", "contested")

        # Dicts
        state.nuclear_posture = initial.get("nuclear_posture", {})
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
