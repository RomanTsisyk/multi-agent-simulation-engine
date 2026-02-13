"""Live progress dashboard for the wargame simulation.

Provides a terminal-based progress display using Rich (with graceful
fallback to plain text) and writes ``status.json`` to the game directory
for the web viewer to poll.

Usage::

    from engine.dashboard import Dashboard, GameStatus

    dashboard = Dashboard(game_dir, total_rounds=10, num_countries=5)
    dashboard.start()
    dashboard.update(phase="briefing", round_num=1)
    ...
    dashboard.stop()
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ======================================================================
# Status dataclass
# ======================================================================

@dataclass
class GameStatus:
    """Current state of the game for display purposes."""
    scenario_name: str = ""
    total_rounds: int = 0
    current_round: int = 0
    phase: str = "setup"  # setup, briefing, deliberation, resolution, complete
    current_country: str = ""
    current_country_index: int = 0
    total_countries: int = 0
    faction_index: int = 0
    total_factions: int = 0
    debate_round: int = 0
    escalation_level: int = 0  # 0-10
    escalation_label: str = "NORMAL"
    last_headlines: list[str] = field(default_factory=list)
    round_times: list[float] = field(default_factory=list)
    eta_seconds: float = 0.0
    game_start_time: float = 0.0
    elapsed_seconds: float = 0.0
    is_running: bool = False
    error: str = ""


# ======================================================================
# Dashboard class
# ======================================================================

class Dashboard:
    """Live terminal dashboard and status.json writer.

    Args:
        game_dir: Path to the game session directory (for status.json).
        total_rounds: Total number of rounds in the game.
        num_countries: Number of countries participating.
        scenario_name: Name of the scenario.
    """

    def __init__(
        self,
        game_dir: Path | str | None = None,
        total_rounds: int = 10,
        num_countries: int = 0,
        scenario_name: str = "",
    ) -> None:
        self.game_dir = Path(game_dir) if game_dir else None
        self.status = GameStatus(
            scenario_name=scenario_name,
            total_rounds=total_rounds,
            total_countries=num_countries,
        )
        self._live = None
        self._has_rich = False

        # Try to import Rich
        try:
            from rich.live import Live
            from rich.console import Console
            self._has_rich = True
            self._console = Console()
        except ImportError:
            self._has_rich = False

    def start(self) -> None:
        """Start the live dashboard display."""
        self.status.game_start_time = time.time()
        self.status.is_running = True

        if self._has_rich:
            try:
                from rich.live import Live
                self._live = Live(
                    self._render(),
                    refresh_per_second=1,
                    console=self._console,
                )
                self._live.start()
            except Exception as e:
                logger.warning("Failed to start Rich Live display: %s", e)
                self._live = None

        self._write_status()

    def stop(self) -> None:
        """Stop the live dashboard display."""
        self.status.is_running = False
        self.status.phase = "complete"
        self.status.elapsed_seconds = time.time() - self.status.game_start_time

        if self._live:
            try:
                self._live.update(self._render())
                self._live.stop()
            except Exception:
                pass
            self._live = None

        self._write_status()

    def update(
        self,
        phase: str | None = None,
        round_num: int | None = None,
        country: str | None = None,
        country_index: int | None = None,
        faction_index: int | None = None,
        total_factions: int | None = None,
        debate_round: int | None = None,
        escalation_level: int | None = None,
        headlines: list[str] | None = None,
        round_time: float | None = None,
        error: str | None = None,
    ) -> None:
        """Update the dashboard status.

        Only provided fields are updated; None fields are left unchanged.
        """
        if phase is not None:
            self.status.phase = phase
        if round_num is not None:
            self.status.current_round = round_num
        if country is not None:
            self.status.current_country = country
        if country_index is not None:
            self.status.current_country_index = country_index
        if faction_index is not None:
            self.status.faction_index = faction_index
        if total_factions is not None:
            self.status.total_factions = total_factions
        if debate_round is not None:
            self.status.debate_round = debate_round
        if escalation_level is not None:
            self.status.escalation_level = escalation_level
            self.status.escalation_label = _escalation_label(escalation_level)
        if headlines is not None:
            self.status.last_headlines = headlines[-3:]  # keep last 3
        if round_time is not None:
            self.status.round_times.append(round_time)
        if error is not None:
            self.status.error = error

        # Recompute ETA
        self.status.elapsed_seconds = time.time() - self.status.game_start_time
        if self.status.round_times and self.status.current_round < self.status.total_rounds:
            avg = sum(self.status.round_times) / len(self.status.round_times)
            remaining = self.status.total_rounds - self.status.current_round
            self.status.eta_seconds = avg * remaining

        # Update Rich display
        if self._live:
            try:
                self._live.update(self._render())
            except Exception:
                pass

        # Write status.json
        self._write_status()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> Any:
        """Build the Rich renderable for the live display."""
        if not self._has_rich:
            return ""

        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.progress_bar import ProgressBar

        s = self.status
        lines: list[str] = []

        # Progress bar
        pct = (s.current_round / s.total_rounds * 100) if s.total_rounds > 0 else 0
        bar_filled = int(pct / 5)  # 20 chars wide
        bar_empty = 20 - bar_filled
        bar = "=" * bar_filled + ">" * (1 if bar_empty > 0 else 0) + " " * max(0, bar_empty - 1)
        lines.append(
            f"[bold cyan]WARGAME[/bold cyan]  [{bar}] "
            f"Round {s.current_round}/{s.total_rounds} {pct:.0f}%"
        )

        # Current activity
        if s.phase == "briefing":
            activity = "Game Master generating briefing"
        elif s.phase == "deliberation":
            country_info = f"{s.current_country}" if s.current_country else "..."
            faction_info = ""
            if s.total_factions > 0:
                faction_info = f" (faction {s.faction_index}/{s.total_factions}, R{s.debate_round})"
            activity = f"{country_info} deliberating{faction_info}"
        elif s.phase == "resolution":
            activity = "Game Master resolving actions"
        elif s.phase == "complete":
            activity = "Game complete"
        elif s.phase == "intel":
            activity = f"Generating intel for {s.current_country}"
        else:
            activity = s.phase.capitalize()

        lines.append(f"Current: {activity}")

        # ETA
        if s.eta_seconds > 0 and s.phase != "complete":
            eta_min = int(s.eta_seconds // 60)
            avg_time = sum(s.round_times) / len(s.round_times) if s.round_times else 0
            lines.append(f"ETA: ~{eta_min} min remaining (avg {avg_time:.1f} min/round)")

        # Escalation
        esc_bar_filled = s.escalation_level
        esc_bar_empty = 10 - esc_bar_filled
        esc_bar = "=" * esc_bar_filled + " " * esc_bar_empty
        esc_color = "green" if s.escalation_level <= 3 else "yellow" if s.escalation_level <= 6 else "red"
        lines.append("")
        lines.append(
            f"ESCALATION: [{esc_bar}] {s.escalation_level}/10 "
            f"[{esc_color}]{s.escalation_label}[/{esc_color}]"
        )

        # Headlines
        if s.last_headlines:
            lines.append("")
            lines.append("[bold]LAST HEADLINES:[/bold]")
            for hl in s.last_headlines[-3:]:
                lines.append(f"  * {hl[:70]}")

        text = "\n".join(lines)
        title = f"WARGAME: {s.scenario_name}" if s.scenario_name else "WARGAME"
        return Panel(text, title=title, border_style="cyan", expand=True)

    # ------------------------------------------------------------------
    # Status file
    # ------------------------------------------------------------------

    def _write_status(self) -> None:
        """Atomically write status.json to the game directory."""
        if not self.game_dir:
            return

        try:
            self.game_dir.mkdir(parents=True, exist_ok=True)
            status_path = self.game_dir / "status.json"
            tmp_path = status_path.with_suffix(".tmp")
            data = asdict(self.status)
            content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(status_path)
        except Exception as e:
            logger.warning("Failed to write status.json: %s", e)


# ======================================================================
# Helpers
# ======================================================================

def _escalation_label(level: int) -> str:
    """Map an escalation level (0-10) to a human-readable label."""
    if level <= 1:
        return "NORMAL"
    elif level <= 3:
        return "ELEVATED"
    elif level <= 5:
        return "HIGH"
    elif level <= 7:
        return "SEVERE"
    elif level <= 9:
        return "CRITICAL"
    else:
        return "NUCLEAR"


def compute_escalation_level(world_state_dict: dict) -> int:
    """Compute a 0-10 escalation level from world state.

    Factors: NATO alert level, nuclear posture, corridor control, casualties.
    """
    level = 0

    # NATO alert
    nato_alert = world_state_dict.get("nato_alert_level", "normal")
    alert_scores = {"normal": 0, "elevated": 1, "high": 3, "article5": 5}
    level += alert_scores.get(nato_alert, 0)

    # Nuclear posture
    nuclear = world_state_dict.get("nuclear_posture", {})
    nuke_scores = {
        "peacetime": 0, "elevated": 1, "dispersal": 2,
        "launch_ready": 4,
    }
    max_nuke = 0
    for posture in nuclear.values():
        max_nuke = max(max_nuke, nuke_scores.get(posture, 0))
    level += max_nuke

    # Corridor control
    corridor = world_state_dict.get("corridor_control", "contested")
    if corridor in ("russian", "contested"):
        level += 1

    # Clamp to 0-10
    return min(10, max(0, level))
