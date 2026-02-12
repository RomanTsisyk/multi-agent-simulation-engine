"""Round logger -- persists every round of the wargame to disk.

Each game session gets its own directory under ``logs/``.  Within that
directory every round is saved as a separate JSON file, and a
``game_summary.json`` is written at the end.

Directory layout::

    logs/
      game_20260212_143000/
        round_001.json
        round_002.json
        ...
        game_summary.json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RoundLogger:
    """Writes structured round data and game summaries to disk.

    Args:
        game_dir: Absolute or relative path to the game session directory.
            Created automatically if it does not exist.  Typically something
            like ``logs/game_20260212_143000/``.
    """

    def __init__(self, game_dir: str) -> None:
        self.game_dir = Path(game_dir)
        self.game_dir.mkdir(parents=True, exist_ok=True)
        logger.info("RoundLogger initialised -> %s", self.game_dir)

    # ------------------------------------------------------------------
    # Class-level factory
    # ------------------------------------------------------------------

    @classmethod
    def create_for_new_game(cls, base_dir: str = "logs") -> "RoundLogger":
        """Create a logger with an auto-generated timestamped directory.

        Args:
            base_dir: Parent directory that holds all game session folders.

        Returns:
            A new :class:`RoundLogger` instance whose ``game_dir`` is
            ``<base_dir>/game_YYYYMMDD_HHMMSS/``.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        game_dir = os.path.join(base_dir, f"game_{timestamp}")
        return cls(game_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_round(self, round_num: int, data: dict[str, Any]) -> Path:
        """Persist the data for a single round.

        Args:
            round_num: 1-based round number.
            data: Arbitrary JSON-serialisable dictionary containing all
                information captured during the round (briefings, decisions,
                GM resolution, world state snapshot, etc.).

        Returns:
            The :class:`Path` to the written JSON file.
        """
        filename = f"round_{round_num:03d}.json"
        filepath = self.game_dir / filename
        self._write_json(filepath, data)
        logger.info("Logged round %d -> %s", round_num, filepath)
        return filepath

    def log_summary(self, summary: dict[str, Any]) -> Path:
        """Persist the end-of-game summary.

        Args:
            summary: A JSON-serialisable dictionary with game-level
                statistics, final world state, and narrative summary.

        Returns:
            The :class:`Path` to the written JSON file.
        """
        filepath = self.game_dir / "game_summary.json"
        self._write_json(filepath, summary)
        logger.info("Logged game summary -> %s", filepath)
        return filepath

    def log_event(self, event_name: str, data: dict[str, Any]) -> Path:
        """Log an ad-hoc event (e.g. error, diplomatic message).

        Args:
            event_name: Short descriptive slug (used in the filename).
            data: Arbitrary JSON-serialisable payload.

        Returns:
            The :class:`Path` to the written JSON file.
        """
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"event_{timestamp}_{event_name}.json"
        filepath = self.game_dir / filename
        self._write_json(filepath, data)
        logger.debug("Logged event %s -> %s", event_name, filepath)
        return filepath

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        """Atomically write a dictionary as pretty-printed JSON."""
        content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        # Write to a temp file first, then rename for atomicity
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(path)
        except Exception:
            # Clean up temp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise
