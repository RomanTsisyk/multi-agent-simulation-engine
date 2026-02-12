"""Game engine layer for the wargame simulation.

This package contains the core game loop, world state management,
the Game Master agent, and round logging.

Usage::

    from engine import Game, GameMaster, WorldState, RoundLogger

    game = Game(config={...})
    await game.setup()
    summary = await game.run()
    await game.close()
"""

from engine.game import Game
from engine.game_master import GameMaster
from engine.round_logger import RoundLogger
from engine.world_state import MilitaryUnit, WorldState

__all__ = [
    "Game",
    "GameMaster",
    "MilitaryUnit",
    "RoundLogger",
    "WorldState",
]
