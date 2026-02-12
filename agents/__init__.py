"""Agent layer for the multi-agent geopolitical wargame.

This package provides the core agent abstractions:

- :class:`AgentConfig` / :class:`Agent` -- base persona + LLM wrapper.
- :class:`Faction` -- a single advisory voice that participates in debates.
- :class:`CountryConfig` / :class:`Country` -- orchestrates factions and
  produces unified national decisions through structured debate.

Typical usage::

    from agents import AgentConfig, Faction, CountryConfig, Country

    hawk = Faction(
        AgentConfig(name="Gen. Ivanov", role="hawk", personality="..."),
        backend=my_backend,
    )
    country = Country(
        CountryConfig(name="Russia", code="RU", military_strength=8),
        factions=[hawk, ...],
        backend=my_backend,
    )
    result = await country.run_internal_debate("NATO moves east", world_ctx)
"""

from agents.base import Agent, AgentConfig
from agents.country import Country, CountryConfig
from agents.faction import Faction

__all__ = [
    "Agent",
    "AgentConfig",
    "Country",
    "CountryConfig",
    "Faction",
]
