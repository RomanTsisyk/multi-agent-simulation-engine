"""Checkpoint and resume support for the wargame simulation.

Saves a complete snapshot of game state after each round so that a
crashed or interrupted game can be resumed from the last completed
round.

The checkpoint file is written atomically to ``checkpoint.json``
inside the game's log directory.

Usage::

    from engine.checkpoint import save_checkpoint, load_checkpoint

    # After each round:
    save_checkpoint(game_dir, game_instance, round_completed=3)

    # To resume:
    state = load_checkpoint(game_dir)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_checkpoint(
    game_dir: Path | str,
    round_completed: int,
    world_state_dict: dict,
    diplomatic_inbox: list[dict],
    previous_round_summary: str,
    corridor_hold_rounds: int,
    corridor_was_contested: bool,
    gm_round_history: list[dict],
    agent_histories: dict[str, list[dict]],
    total_rounds: int,
    config: dict | None = None,
) -> Path:
    """Save a checkpoint after a completed round.

    Args:
        game_dir: Path to the game session directory.
        round_completed: The round number that just finished (1-based).
        world_state_dict: Serialised world state from WorldState.to_dict().
        diplomatic_inbox: Pending diplomatic messages for next round.
        previous_round_summary: Text summary for cross-round memory.
        corridor_hold_rounds: Current corridor hold counter.
        corridor_was_contested: Whether corridor was ever contested.
        gm_round_history: Game Master's round history list.
        agent_histories: Dict mapping country code -> synthesiser message history.
        total_rounds: Total rounds configured for the game.
        config: Original game configuration (for resume validation).

    Returns:
        Path to the written checkpoint file.
    """
    game_dir = Path(game_dir)
    game_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "version": 1,
        "round_completed": round_completed,
        "total_rounds": total_rounds,
        "world_state": world_state_dict,
        "diplomatic_inbox": diplomatic_inbox,
        "previous_round_summary": previous_round_summary,
        "corridor_hold_rounds": corridor_hold_rounds,
        "corridor_was_contested": corridor_was_contested,
        "gm_round_history": gm_round_history,
        "agent_histories": agent_histories,
    }

    if config is not None:
        # Store a minimal config fingerprint for validation
        checkpoint["config_fingerprint"] = {
            "scenario_name": config.get("scenario", {}).get("name", ""),
            "total_rounds": config.get("scenario", {}).get("rounds", 0),
            "country_codes": sorted(config.get("scenario", {}).get("countries", {}).keys()),
        }

    checkpoint_path = game_dir / "checkpoint.json"
    tmp_path = checkpoint_path.with_suffix(".tmp")

    try:
        content = json.dumps(checkpoint, indent=2, ensure_ascii=False, default=str)
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(checkpoint_path)
        logger.info("Checkpoint saved: round %d -> %s", round_completed, checkpoint_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return checkpoint_path


def load_checkpoint(game_dir: Path | str) -> dict:
    """Load a checkpoint from a game directory.

    Args:
        game_dir: Path to the game session directory.

    Returns:
        The checkpoint dictionary.

    Raises:
        FileNotFoundError: If no checkpoint.json exists.
        json.JSONDecodeError: If the checkpoint file is corrupted.
    """
    game_dir = Path(game_dir)
    checkpoint_path = game_dir / "checkpoint.json"

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"No checkpoint found in {game_dir}")

    content = checkpoint_path.read_text(encoding="utf-8")
    checkpoint = json.loads(content)

    version = checkpoint.get("version", 0)
    if version != 1:
        logger.warning("Checkpoint version %d (expected 1), attempting to load anyway", version)

    logger.info(
        "Checkpoint loaded: round %d/%d from %s",
        checkpoint.get("round_completed", "?"),
        checkpoint.get("total_rounds", "?"),
        checkpoint_path,
    )

    return checkpoint


def apply_checkpoint(game, checkpoint: dict) -> int:
    """Apply a loaded checkpoint to a Game instance.

    This should be called AFTER game.setup() has initialized all
    objects (backend, countries, GM, logger).  It overwrites the
    mutable state with the checkpointed values.

    Args:
        game: A fully setup Game instance.
        checkpoint: The checkpoint dict from load_checkpoint().

    Returns:
        The round number to start from (round_completed + 1).
    """
    from engine.world_state import WorldState

    round_completed = checkpoint["round_completed"]

    # Restore world state
    game.world_state = WorldState.from_dict(checkpoint["world_state"])
    logger.info("Restored world state from round %d", round_completed)

    # Restore diplomatic inbox
    game._diplomatic_inbox = checkpoint.get("diplomatic_inbox", [])

    # Restore cross-round memory
    game._previous_round_summary = checkpoint.get("previous_round_summary", "")

    # Restore corridor tracking
    game._corridor_hold_rounds = checkpoint.get("corridor_hold_rounds", 0)
    game._corridor_was_contested = checkpoint.get("corridor_was_contested", False)

    # Restore GM round history
    if game.game_master is not None:
        game.game_master._round_history = checkpoint.get("gm_round_history", [])
        logger.info("Restored GM round history (%d entries)", len(game.game_master._round_history))

    # Restore agent message histories (synthesiser agents)
    agent_histories = checkpoint.get("agent_histories", {})
    for code, history in agent_histories.items():
        if code in game.countries:
            country = game.countries[code]
            # Only Country objects (not stubs) have a synthesiser
            if hasattr(country, '_synthesiser'):
                country._synthesiser.message_history = history
                logger.debug("Restored message history for %s", code)

    start_round = round_completed + 1
    logger.info("Resume from round %d (after completing round %d)", start_round, round_completed)
    return start_round


def collect_agent_histories(game) -> dict[str, list[dict]]:
    """Collect serialisable message histories from all country agents.

    Args:
        game: A Game instance with initialised countries.

    Returns:
        Dict mapping country code to the synthesiser's message history.
    """
    histories: dict[str, list[dict]] = {}
    for code, country in game.countries.items():
        if hasattr(country, '_synthesiser'):
            histories[code] = list(country._synthesiser.message_history)
    return histories
