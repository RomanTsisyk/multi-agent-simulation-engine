"""Game presets for the wargame simulation.

Defines named presets that configure the country roster and number
of rounds for common game scenarios.

Usage::

    from presets import PRESETS, get_preset

    preset = get_preset("quick")
    countries = preset["countries"]
    rounds = preset["rounds"]
"""

from __future__ import annotations


# ======================================================================
# Preset definitions
# ======================================================================

PRESETS: dict[str, dict] = {
    "quick": {
        "description": "Quick test game (4 countries, 2 rounds)",
        "countries": ["PL", "RU", "US", "DE"],
        "rounds": 2,
    },
    "medium": {
        "description": "Medium game (7 key countries, 5 rounds)",
        "countries": ["PL", "RU", "US", "DE", "FR", "GB", "LT"],
        "rounds": 5,
    },
    "full": {
        "description": "Full simulation (all countries, 10 rounds)",
        "countries": None,  # None means all available countries
        "rounds": 10,
    },
    "nato-vs-russia": {
        "description": "NATO vs Russia (20 countries, 10 rounds)",
        "countries": [
            # NATO front line
            "PL", "LT", "LV", "EE", "DE", "FR", "GB", "US",
            # NATO support
            "NO", "DK", "NL", "BE", "CZ", "RO", "CA",
            # Russia + allies
            "RU", "BY",
            # Key neutrals / observers
            "FI", "SE", "TR",
        ],
        "rounds": 10,
    },
    "suwalki-claude": {
        "description": "Suwalki Gap via Claude Code (22 countries, 10 rounds)",
        "countries": [
            # Frontline
            "PL", "LT", "LV", "EE",
            # Major NATO
            "US", "GB", "FR", "DE",
            # NATO contributors
            "CA", "NO", "DK", "NL", "BE", "CZ", "RO",
            # New NATO, strategic
            "FI", "SE",
            # NATO wildcards
            "TR", "HU",
            # Adversaries
            "RU", "BY",
            # Global observer
            "CN",
        ],
        "rounds": 10,
    },
}


def get_preset(name: str) -> dict:
    """Look up a preset by name.

    Args:
        name: Preset name (case-insensitive).

    Returns:
        A dict with keys ``description``, ``countries``, and ``rounds``.

    Raises:
        KeyError: If the preset name is not found.
    """
    key = name.lower().strip()
    if key not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    return dict(PRESETS[key])


def list_presets() -> list[dict]:
    """Return a list of all available presets with their metadata.

    Returns:
        List of dicts, each with ``name``, ``description``, ``countries``
        (count or "all"), and ``rounds``.
    """
    result = []
    for name, preset in PRESETS.items():
        countries = preset["countries"]
        country_info = f"{len(countries)} countries" if countries else "all countries"
        result.append({
            "name": name,
            "description": preset["description"],
            "countries": country_info,
            "rounds": preset["rounds"],
        })
    return result
