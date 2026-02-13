"""Comprehensive pytest test suite for the WorldState module.

Tests cover:
- MilitaryUnit creation and summary()
- WorldState serialization round-trip (to_dict/from_dict)
- apply_updates() for all update types
- Cascading effects (10 different automatic effects)
- Helper functions (_dedup_strings, _dedup_dicts, _safe_int, _relation_label)
- to_briefing() with and without for_country parameter
"""

import copy
import json
import pytest

from engine.world_state import (
    MilitaryUnit,
    WorldState,
    _dedup_strings,
    _dedup_dicts,
    _safe_int,
    _relation_label,
)


# ======================================================================
# 1. MilitaryUnit Tests
# ======================================================================

class TestMilitaryUnit:
    """Tests for MilitaryUnit dataclass."""

    def test_military_unit_creation_defaults(self):
        """Test creating a MilitaryUnit with default values."""
        unit = MilitaryUnit(
            name="1st Tank Brigade",
            country="Poland",
            type="ground",
            location="Warsaw",
            readiness=8,
            strength=9,
        )
        assert unit.name == "1st Tank Brigade"
        assert unit.country == "Poland"
        assert unit.type == "ground"
        assert unit.location == "Warsaw"
        assert unit.readiness == 8
        assert unit.strength == 9
        assert unit.casualties == 0
        assert unit.supply_level == 10
        assert unit.morale == 7
        assert unit._last_casualty_morale_applied == 0

    def test_military_unit_creation_all_fields(self):
        """Test creating a MilitaryUnit with all fields specified."""
        unit = MilitaryUnit(
            name="Alpha Squadron",
            country="USA",
            type="air",
            location="Ramstein",
            readiness=10,
            strength=8,
            casualties=5,
            supply_level=6,
            morale=9,
            _last_casualty_morale_applied=2,
        )
        assert unit.name == "Alpha Squadron"
        assert unit.country == "USA"
        assert unit.type == "air"
        assert unit.location == "Ramstein"
        assert unit.readiness == 10
        assert unit.strength == 8
        assert unit.casualties == 5
        assert unit.supply_level == 6
        assert unit.morale == 9
        assert unit._last_casualty_morale_applied == 2

    def test_military_unit_summary(self):
        """Test MilitaryUnit.summary() generates correct format."""
        unit = MilitaryUnit(
            name="Naval Task Force 7",
            country="UK",
            type="naval",
            location="Baltic Sea",
            readiness=7,
            strength=8,
            casualties=3,
            supply_level=9,
            morale=6,
        )
        summary = unit.summary()
        assert "Naval Task Force 7" in summary
        assert "UK" in summary
        assert "naval" in summary
        assert "Baltic Sea" in summary
        assert "readiness=7" in summary
        assert "strength=8" in summary
        assert "supply=9" in summary
        assert "morale=6" in summary
        assert "casualties=3" in summary


# ======================================================================
# 2. WorldState Serialization Tests
# ======================================================================

class TestWorldStateSerialization:
    """Tests for WorldState to_dict/from_dict serialization."""

    def test_empty_world_state_serialization(self):
        """Test serialization of an empty WorldState."""
        ws = WorldState()
        data = ws.to_dict()

        assert data["round_number"] == 0
        assert data["game_time"] == "Day 1, 00:00"
        assert data["military_units"] == []
        assert data["markets"] == {}
        assert data["nato_alert_level"] == "normal"
        assert data["corridor_control"] == "contested"

    def test_world_state_serialization_roundtrip(self):
        """Test that to_dict/from_dict preserves all data."""
        ws = WorldState(
            round_number=5,
            game_time="Day 3, 14:00",
            nato_alert_level="elevated",
            corridor_control="nato",
        )
        ws.military_units.append(
            MilitaryUnit(
                name="Test Unit",
                country="Germany",
                type="ground",
                location="Berlin",
                readiness=7,
                strength=8,
            )
        )
        ws.markets = {"oil_price": 110, "gas_price_eu": 85}
        ws.sanctions.append({"from": "US", "target": "RU", "type": "financial"})
        ws.diplomatic_relations = {"US": {"RU": -8, "UK": 9}}
        ws.public_opinion = {"US": {"war_support": 65, "government_approval": 55}}

        # Serialize
        data = ws.to_dict()

        # Deserialize
        ws2 = WorldState.from_dict(data)

        # Verify
        assert ws2.round_number == 5
        assert ws2.game_time == "Day 3, 14:00"
        assert ws2.nato_alert_level == "elevated"
        assert ws2.corridor_control == "nato"
        assert len(ws2.military_units) == 1
        assert ws2.military_units[0].name == "Test Unit"
        assert ws2.military_units[0].country == "Germany"
        assert ws2.military_units[0].readiness == 7
        assert ws2.markets["oil_price"] == 110
        assert ws2.sanctions[0]["from"] == "US"
        assert ws2.diplomatic_relations["US"]["RU"] == -8
        assert ws2.public_opinion["US"]["war_support"] == 65

    def test_world_state_serialization_with_nuclear_penalty_set(self):
        """Test serialization preserves _nuclear_penalty_applied set."""
        ws = WorldState()
        ws.markets["_nuclear_penalty_applied"] = {"US", "RU"}

        # Serialize
        data = ws.to_dict()
        # Set should be converted to list for JSON
        assert isinstance(data["markets"]["_nuclear_penalty_applied"], list)

        # Deserialize
        ws2 = WorldState.from_dict(data)
        # Should be converted back to set
        assert isinstance(ws2.markets["_nuclear_penalty_applied"], set)
        assert ws2.markets["_nuclear_penalty_applied"] == {"US", "RU"}

    def test_to_json_produces_valid_json(self):
        """Test that to_json() produces valid JSON string."""
        ws = WorldState(round_number=3)
        ws.markets = {"oil_price": 95}
        json_str = ws.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["round_number"] == 3
        assert parsed["markets"]["oil_price"] == 95


# ======================================================================
# 3. apply_updates() Tests
# ======================================================================

class TestApplyUpdates:
    """Tests for WorldState.apply_updates() method."""

    def test_apply_updates_scalars(self):
        """Test updating scalar fields."""
        ws = WorldState()
        ws.apply_updates({
            "round_number": 10,
            "game_time": "Day 5, 12:00",
            "nato_alert_level": "high",
            "corridor_control": "russian",
        })

        assert ws.round_number == 10
        assert ws.game_time == "Day 5, 12:00"
        assert ws.nato_alert_level == "high"
        assert ws.corridor_control == "russian"

    def test_apply_updates_military_units_add(self):
        """Test adding new military units."""
        ws = WorldState()
        ws.apply_updates({
            "military_units_add": [
                {
                    "name": "Unit A",
                    "country": "France",
                    "type": "air",
                    "location": "Paris",
                    "readiness": 9,
                    "strength": 10,
                },
                {
                    "name": "Unit B",
                    "country": "Germany",
                    "type": "ground",
                    "location": "Munich",
                    "readiness": 7,
                    "strength": 8,
                },
            ]
        })

        assert len(ws.military_units) == 2
        assert ws.military_units[0].name == "Unit A"
        assert ws.military_units[0].country == "France"
        assert ws.military_units[1].name == "Unit B"
        assert ws.military_units[1].country == "Germany"

    def test_apply_updates_military_units_remove_strings(self):
        """Test removing military units by name (string format)."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Unit A", "US", "ground", "Berlin", 8, 9)
        )
        ws.military_units.append(
            MilitaryUnit("Unit B", "UK", "air", "London", 7, 8)
        )
        ws.military_units.append(
            MilitaryUnit("Unit C", "France", "naval", "Mediterranean", 6, 7)
        )

        ws.apply_updates({
            "military_units_remove": ["Unit A", "Unit C"]
        })

        assert len(ws.military_units) == 1
        assert ws.military_units[0].name == "Unit B"

    def test_apply_updates_military_units_remove_dicts(self):
        """Test removing military units by name (dict format)."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Unit X", "US", "ground", "Berlin", 8, 9)
        )
        ws.military_units.append(
            MilitaryUnit("Unit Y", "UK", "air", "London", 7, 8)
        )

        # LLM sometimes returns [{"name": "..."}] instead of ["..."]
        ws.apply_updates({
            "military_units_remove": [{"name": "Unit X"}]
        })

        assert len(ws.military_units) == 1
        assert ws.military_units[0].name == "Unit Y"

    def test_apply_updates_military_units_update(self):
        """Test updating existing military units."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Alpha", "US", "ground", "Warsaw", 8, 9)
        )

        ws.apply_updates({
            "military_units_update": [
                {
                    "name": "Alpha",
                    "location": "Kyiv",
                    "readiness": 6,
                    "casualties": 3,
                }
            ]
        })

        unit = ws.military_units[0]
        assert unit.location == "Kyiv"
        assert unit.readiness == 6
        assert unit.casualties == 3
        # Unchanged fields
        assert unit.country == "US"
        # Note: strength is reduced by casualties (3 // 2 = 1), so 9 - 1 = 8
        assert unit.strength == 8

    def test_apply_updates_military_units_update_type_coercion(self):
        """Test that LLM string values are coerced to int."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Beta", "UK", "air", "London", 8, 9)
        )

        # LLM might return strings instead of ints
        ws.apply_updates({
            "military_units_update": [
                {
                    "name": "Beta",
                    "readiness": "7",  # string
                    "strength": "6",   # string
                    "morale": 5.5,     # float
                }
            ]
        })

        unit = ws.military_units[0]
        assert unit.readiness == 7
        assert unit.strength == 6
        assert unit.morale == 5

    def test_apply_updates_markets(self):
        """Test merging market data."""
        ws = WorldState()
        ws.markets = {"oil_price": 100}

        ws.apply_updates({
            "markets": {"gas_price_eu": 80, "euro_usd": 1.1}
        })

        assert ws.markets["oil_price"] == 100  # preserved
        assert ws.markets["gas_price_eu"] == 80
        assert ws.markets["euro_usd"] == 1.1

    def test_apply_updates_sanctions_add(self):
        """Test adding sanctions with deduplication."""
        ws = WorldState()
        ws.sanctions.append({"from": "US", "target": "RU", "type": "financial"})

        ws.apply_updates({
            "sanctions_add": [
                {"from": "EU", "target": "RU", "type": "trade"},
                {"from": "US", "target": "RU", "type": "financial"},  # duplicate
            ]
        })

        # Should have 2 sanctions (duplicate not added)
        assert len(ws.sanctions) == 2
        assert ws.sanctions[0]["from"] == "US"
        assert ws.sanctions[1]["from"] == "EU"

    def test_apply_updates_treaties_invoked_add(self):
        """Test adding treaty invocations with deduplication."""
        ws = WorldState()
        ws.treaties_invoked.append("NATO Article 5")

        ws.apply_updates({
            "treaties_invoked_add": [
                "EU Mutual Defense Clause",
                "nato article 5",  # case-insensitive duplicate
            ]
        })

        # Should have 2 treaties (duplicate not added)
        assert len(ws.treaties_invoked) == 2
        assert "NATO Article 5" in ws.treaties_invoked
        assert "EU Mutual Defense Clause" in ws.treaties_invoked

    def test_apply_updates_diplomatic_relations(self):
        """Test updating diplomatic relations."""
        ws = WorldState()
        ws.diplomatic_relations = {"US": {"UK": 8}}

        ws.apply_updates({
            "diplomatic_relations": {
                "US": {"RU": -9, "UK": 9},  # update UK, add RU
                "RU": {"US": -9},
            }
        })

        assert ws.diplomatic_relations["US"]["UK"] == 9  # updated
        assert ws.diplomatic_relations["US"]["RU"] == -9  # added
        assert ws.diplomatic_relations["RU"]["US"] == -9

    def test_apply_updates_public_opinion(self):
        """Test updating public opinion."""
        ws = WorldState()
        ws.public_opinion = {"US": {"war_support": 60}}

        ws.apply_updates({
            "public_opinion": {
                "US": {"government_approval": 50},
                "UK": {"war_support": 70, "government_approval": 65},
            }
        })

        assert ws.public_opinion["US"]["war_support"] == 60  # preserved
        assert ws.public_opinion["US"]["government_approval"] == 50  # added
        assert ws.public_opinion["UK"]["war_support"] == 70

    def test_apply_updates_nuclear_posture(self):
        """Test updating nuclear posture (with de-escalation prevention)."""
        ws = WorldState()

        ws.apply_updates({
            "nuclear_posture": {
                "US": "elevated",
                "RU": "elevated",
            },
            "recent_events": ["Nuclear forces on alert"]  # Prevent de-escalation
        })

        assert ws.nuclear_posture["US"] == "elevated"
        assert ws.nuclear_posture["RU"] == "elevated"

    def test_apply_updates_nuclear_posture_case_normalization(self):
        """Test that nuclear posture values are normalized to lowercase."""
        ws = WorldState()

        ws.apply_updates({
            "nuclear_posture": {
                "US": "Elevated",  # mixed case
                "RU": "elevated",
            },
            "recent_events": ["Nuclear alert"]  # Prevent de-escalation
        })

        assert ws.nuclear_posture["US"] == "elevated"
        assert ws.nuclear_posture["RU"] == "elevated"

    def test_apply_updates_refugee_flows_add(self):
        """Test adding refugee flows with deduplication."""
        ws = WorldState()
        ws.refugee_flows.append({"from": "Ukraine", "to": "Poland", "count": 100000})

        ws.apply_updates({
            "refugee_flows_add": [
                {"from": "Ukraine", "to": "Germany", "count": 50000},
                {"from": "Ukraine", "to": "Poland", "count": 200000},  # duplicate from/to
            ]
        })

        # Should have 2 flows (duplicate from/to pair not added)
        assert len(ws.refugee_flows) == 2

    def test_apply_updates_cyber_operations_add(self):
        """Test adding cyber operations with deduplication."""
        ws = WorldState()
        ws.cyber_operations.append({
            "attacker": "RU",
            "target": "Ukraine",
            "type": "ddos",
            "severity": "high",
        })

        ws.apply_updates({
            "cyber_operations_add": [
                {
                    "attacker": "RU",
                    "target": "Poland",
                    "type": "malware",
                    "severity": "medium",
                },
                {
                    "attacker": "RU",
                    "target": "Ukraine",
                    "type": "ddos",  # duplicate attacker/target/type
                    "severity": "critical",
                },
            ]
        })

        # Should have 2 ops (duplicate not added)
        assert len(ws.cyber_operations) == 2

    def test_apply_updates_infrastructure_status(self):
        """Test updating infrastructure status."""
        ws = WorldState()
        ws.infrastructure_status = {"Poland": {"power_grid": 10, "comms": 10}}

        ws.apply_updates({
            "infrastructure_status": {
                "Poland": {"power_grid": 7},  # update
                "Ukraine": {"military_c2": 4},  # new country
            }
        })

        assert ws.infrastructure_status["Poland"]["power_grid"] == 7
        assert ws.infrastructure_status["Poland"]["comms"] == 10  # preserved
        # New country gets default values
        assert ws.infrastructure_status["Ukraine"]["power_grid"] == 10
        assert ws.infrastructure_status["Ukraine"]["military_c2"] == 4

    def test_apply_updates_infrastructure_status_type_coercion(self):
        """Test that infrastructure values are coerced to int."""
        ws = WorldState()

        ws.apply_updates({
            "infrastructure_status": {
                "Test": {"power_grid": "8", "comms": 7.5}
            }
        })

        assert ws.infrastructure_status["Test"]["power_grid"] == 8
        assert ws.infrastructure_status["Test"]["comms"] == 7

    def test_apply_updates_recent_events(self):
        """Test that recent_events are replaced (not appended)."""
        ws = WorldState()
        ws.recent_events = ["Old event 1", "Old event 2"]

        ws.apply_updates({
            "recent_events": ["New event 1", "New event 2"]
        })

        assert len(ws.recent_events) == 2
        assert "New event 1" in ws.recent_events
        assert "Old event 1" not in ws.recent_events

    def test_apply_updates_media_headlines(self):
        """Test that media_headlines are replaced (not appended)."""
        ws = WorldState()
        ws.media_headlines = ["Old headline"]

        ws.apply_updates({
            "media_headlines": ["Breaking news!", "Latest update"]
        })

        assert len(ws.media_headlines) == 2
        assert "Breaking news!" in ws.media_headlines
        assert "Old headline" not in ws.media_headlines

    def test_apply_updates_empty_dict(self):
        """Test that applying empty updates does nothing."""
        ws = WorldState(round_number=5)
        original_round = ws.round_number

        ws.apply_updates({})

        assert ws.round_number == original_round


# ======================================================================
# 4. Cascading Effects Tests
# ======================================================================

class TestCascadingEffects:
    """Tests for WorldState._apply_cascading_effects()."""

    def test_cascading_oil_price_reduces_war_support(self):
        """Test that oil price > $120 reduces war support (one-time per threshold)."""
        ws = WorldState()
        ws.public_opinion = {
            "US": {"war_support": 70, "government_approval": 60},
            "UK": {"war_support": 65, "government_approval": 55},
        }

        # First update: oil crosses $120
        ws.apply_updates({"markets": {"oil_price": 125}})

        # War support should decrease by 3
        assert ws.public_opinion["US"]["war_support"] == 67
        assert ws.public_opinion["UK"]["war_support"] == 62

        # Second update: oil stays above $120 but doesn't cross new threshold
        ws.apply_updates({"markets": {"oil_price": 130}})

        # War support should NOT decrease again
        assert ws.public_opinion["US"]["war_support"] == 67
        assert ws.public_opinion["UK"]["war_support"] == 62

        # Third update: oil crosses $140 (new threshold)
        ws.apply_updates({"markets": {"oil_price": 145}})

        # War support should decrease again
        assert ws.public_opinion["US"]["war_support"] == 64
        assert ws.public_opinion["UK"]["war_support"] == 59

    def test_cascading_oil_price_below_threshold_no_effect(self):
        """Test that oil price < $120 doesn't affect war support."""
        ws = WorldState()
        ws.public_opinion = {"US": {"war_support": 70}}

        ws.apply_updates({"markets": {"oil_price": 100}})

        # War support should not change
        assert ws.public_opinion["US"]["war_support"] == 70

    def test_cascading_sanctions_increase_gas_price(self):
        """Test that sanctions on Russia increase EU gas prices (capped at 200)."""
        ws = WorldState()
        ws.markets = {"gas_price_eu": 100}

        ws.apply_updates({
            "sanctions_add": [{"from": "US", "target": "RU", "type": "energy"}]
        })

        # Gas price should increase by 2%
        assert ws.markets["gas_price_eu"] == 102.0

        # Apply more sanctions
        ws.apply_updates({
            "sanctions_add": [{"from": "EU", "target": "RU", "type": "financial"}]
        })

        # Gas price should increase again
        assert ws.markets["gas_price_eu"] > 102.0

    def test_cascading_sanctions_gas_price_capped_at_200(self):
        """Test that gas price from sanctions is capped at 200."""
        ws = WorldState()
        ws.markets = {"gas_price_eu": 198}

        ws.apply_updates({
            "sanctions_add": [{"from": "US", "target": "RU", "type": "energy"}]
        })

        # Gas price should be capped at 200
        assert ws.markets["gas_price_eu"] == 200

    def test_cascading_low_supply_reduces_readiness(self):
        """Test that units with supply_level <= 3 lose readiness."""
        ws = WorldState()

        # Add units through apply_updates to ensure they exist before cascading
        ws.apply_updates({
            "military_units_add": [
                {
                    "name": "Unit A",
                    "country": "US",
                    "type": "ground",
                    "location": "Berlin",
                    "readiness": 8,
                    "strength": 9,
                    "supply_level": 3,
                },
                {
                    "name": "Unit B",
                    "country": "UK",
                    "type": "air",
                    "location": "London",
                    "readiness": 7,
                    "strength": 8,
                    "supply_level": 5,
                },
            ]
        })

        # Unit A should lose 1 readiness
        assert ws.military_units[0].readiness == 7
        # Unit B should not change
        assert ws.military_units[1].readiness == 7

    def test_cascading_critical_supply_reduces_morale(self):
        """Test that units with supply_level <= 1 lose morale."""
        ws = WorldState()

        ws.apply_updates({
            "military_units_add": [
                {
                    "name": "Unit A",
                    "country": "US",
                    "type": "ground",
                    "location": "Berlin",
                    "readiness": 8,
                    "strength": 9,
                    "supply_level": 1,
                    "morale": 7,
                },
                {
                    "name": "Unit B",
                    "country": "UK",
                    "type": "air",
                    "location": "London",
                    "readiness": 7,
                    "strength": 8,
                    "supply_level": 3,
                    "morale": 7,
                },
            ]
        })

        # Unit A should lose 1 morale
        assert ws.military_units[0].morale == 6
        # Unit B should not lose morale (only readiness)
        assert ws.military_units[1].morale == 7

    def test_cascading_casualties_reduce_morale_delta_based(self):
        """Test that casualties reduce morale based on delta (not compounding)."""
        ws = WorldState()
        unit = MilitaryUnit("Alpha", "US", "ground", "Berlin", 8, 9, morale=8)
        ws.military_units.append(unit)

        # First update: 4 casualties
        ws.apply_updates({
            "military_units_update": [{"name": "Alpha", "casualties": 4}]
        })

        # Morale penalty: 4 // 2 = 2
        assert ws.military_units[0].morale == 6
        assert ws.military_units[0]._last_casualty_morale_applied == 2

        # Second update: 6 casualties (delta = 2)
        ws.apply_updates({
            "military_units_update": [{"name": "Alpha", "casualties": 6}]
        })

        # Additional penalty: (6 // 2) - 2 = 1
        assert ws.military_units[0].morale == 5
        assert ws.military_units[0]._last_casualty_morale_applied == 3

    def test_cascading_casualties_reduce_strength(self):
        """Test that casualties reduce unit strength."""
        ws = WorldState()

        ws.apply_updates({
            "military_units_add": [
                {
                    "name": "Unit A",
                    "country": "US",
                    "type": "ground",
                    "location": "Berlin",
                    "readiness": 8,
                    "strength": 10,
                    "casualties": 6,
                }
            ]
        })

        # Strength reduction: 6 // 2 = 3, so 10 - 3 = 7
        assert ws.military_units[0].strength == 7

    def test_cascading_infrastructure_damage_reduces_approval(self):
        """Test that degraded infrastructure reduces government approval."""
        ws = WorldState()

        ws.apply_updates({
            "infrastructure_status": {
                "Poland": {"power_grid": 3, "comms": 4, "financial": 5, "military_c2": 6}
            },
            "public_opinion": {
                "Poland": {"government_approval": 60}
            }
        })

        # Average infrastructure: (3+4+5+6)/4 = 4.5 < 5
        # Approval should decrease by 2
        assert ws.public_opinion["Poland"]["government_approval"] == 58

    def test_cascading_refugee_burden_reduces_approval(self):
        """Test that large refugee inflows reduce government approval."""
        ws = WorldState()

        # Note: refugee_flows_add dedups based on (from, to), so only one flow is added
        ws.apply_updates({
            "refugee_flows_add": [
                {"from": "Ukraine", "to": "Poland", "count": 250000},
            ],
            "public_opinion": {
                "Poland": {"government_approval": 60}
            }
        })

        # Total refugees to Poland: 250000
        # Penalty: min(5, 250000 // 100000) = 2
        assert ws.public_opinion["Poland"]["government_approval"] == 58

    def test_cascading_nuclear_auto_escalation_dispersal(self):
        """Test that if one state reaches dispersal, others escalate."""
        ws = WorldState()

        # Initialize with peacetime first
        ws.apply_updates({
            "nuclear_posture": {
                "US": "peacetime",
                "UK": "peacetime",
            },
            "recent_events": ["Tensions rising"]
        })

        # Then escalate one to dispersal (with provocative event to prevent de-escalation)
        ws.apply_updates({
            "nuclear_posture": {
                "RU": "dispersal",
            },
            "recent_events": ["Nuclear forces dispersed"]
        })

        # US and UK should auto-escalate to at least elevated (one step below dispersal)
        assert ws.nuclear_posture["US"] == "elevated"
        assert ws.nuclear_posture["UK"] == "elevated"
        assert ws.nuclear_posture["RU"] == "dispersal"

    def test_cascading_nuclear_auto_escalation_launch_ready(self):
        """Test escalation when one state reaches launch_ready."""
        ws = WorldState()

        # Initialize first
        ws.apply_updates({
            "nuclear_posture": {
                "US": "elevated",
                "UK": "peacetime",
            },
            "recent_events": ["Military tensions"]
        })

        # Then escalate one to launch_ready (with provocative event)
        ws.apply_updates({
            "nuclear_posture": {
                "RU": "launch_ready",
            },
            "recent_events": ["Nuclear weapons ready for launch"]
        })

        # Others should escalate to dispersal (one below launch_ready)
        assert ws.nuclear_posture["US"] == "dispersal"
        assert ws.nuclear_posture["UK"] == "dispersal"
        assert ws.nuclear_posture["RU"] == "launch_ready"

    def test_cascading_nuclear_posture_reduces_war_support(self):
        """Test that nuclear posture >= launch_ready reduces war support (one-time)."""
        ws = WorldState()

        ws.apply_updates({
            "nuclear_posture": {"US": "launch_ready"},
            "public_opinion": {"US": {"war_support": 70}}
        })

        # War support should decrease by 5
        assert ws.public_opinion["US"]["war_support"] == 65

        # Apply updates again (no posture change)
        ws.apply_updates({})

        # War support should NOT decrease again (de-escalation happens without provocative events)
        # So we need to prevent de-escalation with a provocative event
        ws.apply_updates({
            "recent_events": ["Nuclear forces on high alert"]
        })

        # War support should stay at 65
        assert ws.public_opinion["US"]["war_support"] == 65

    def test_cascading_nuclear_posture_penalty_removed_on_deescalation(self):
        """Test that penalty can be reapplied after de-escalation and re-escalation."""
        ws = WorldState()

        # First escalation
        ws.apply_updates({
            "nuclear_posture": {"US": "launch_ready"},
            "public_opinion": {"US": {"war_support": 70}}
        })
        assert ws.public_opinion["US"]["war_support"] == 65

        # De-escalate (force it with no provocative events)
        ws.apply_updates({
            "nuclear_posture": {"US": "elevated"},
            "recent_events": ["Diplomatic talks begin"]
        })

        # Re-escalate
        ws.apply_updates({
            "nuclear_posture": {"US": "launch_ready"},
            "recent_events": ["Nuclear alert"]
        })

        # Penalty should be applied again
        assert ws.public_opinion["US"]["war_support"] == 60

    def test_cascading_article5_invocation_escalates_nato_alert(self):
        """Test that Article 5 invocation auto-escalates NATO alert level."""
        ws = WorldState()
        ws.nato_alert_level = "normal"

        ws.apply_updates({
            "treaties_invoked_add": ["NATO Article 5"]
        })

        assert ws.nato_alert_level == "article5"

    def test_cascading_article5_consensus_escalates_nato_alert(self):
        """Test that NATO consensus for Article 5 escalates alert level."""
        ws = WorldState()

        ws.apply_updates({
            "nato_alert_level": "normal",
            "nato_consensus": {
                "US": "support Article 5 activation",
                "UK": "invoke Article 5",
                "Germany": "activate collective defense",
            }
        })

        # 3 supporters should escalate to article5
        assert ws.nato_alert_level == "article5"

    def test_cascading_article5_partial_consensus_escalates_to_high(self):
        """Test that partial Article 5 consensus escalates to high."""
        ws = WorldState()

        ws.apply_updates({
            "nato_alert_level": "normal",
            "nato_consensus": {
                "US": "support Article 5 activation",
            }
        })

        # 1 supporter should escalate to high
        assert ws.nato_alert_level == "high"

    def test_cascading_nuclear_deescalation_when_no_provocations(self):
        """Test nuclear de-escalation when no provocative events occur."""
        ws = WorldState()

        # First set up escalated postures
        ws.apply_updates({
            "nuclear_posture": {"US": "dispersal", "RU": "elevated"},
            "recent_events": ["Nuclear alert"]
        })

        # Then apply non-provocative events
        ws.apply_updates({
            "recent_events": ["Diplomatic talks resume", "Ceasefire holds"]
        })

        # Should de-escalate by one level
        assert ws.nuclear_posture["US"] == "elevated"
        assert ws.nuclear_posture["RU"] == "peacetime"

    def test_cascading_nuclear_no_deescalation_with_provocations(self):
        """Test nuclear posture stays same when provocative events occur."""
        ws = WorldState()
        ws.nuclear_posture = {"US": "dispersal"}
        ws.recent_events = ["Nuclear missile test conducted", "Military strike on border"]

        ws.apply_updates({})  # Trigger cascading effects

        # Should NOT de-escalate
        assert ws.nuclear_posture["US"] == "dispersal"

    def test_cascading_value_clamping_readiness(self):
        """Test that readiness is clamped to 1-10."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Unit A", "US", "ground", "Berlin", 1, 9, supply_level=2)
        )

        ws.apply_updates({})  # Trigger cascading effects

        # Readiness should not go below 1
        assert ws.military_units[0].readiness == 1

    def test_cascading_value_clamping_strength(self):
        """Test that strength is clamped to 1-10 (minimum 1, not 0)."""
        ws = WorldState()

        ws.apply_updates({
            "military_units_add": [
                {
                    "name": "Unit A",
                    "country": "US",
                    "type": "ground",
                    "location": "Berlin",
                    "readiness": 8,
                    "strength": 2,
                    "casualties": 10,
                }
            ]
        })

        # Strength reduction: 10 // 2 = 5, so 2 - 5 = -3, clamped to 1 (minimum)
        assert ws.military_units[0].strength == 1

    def test_cascading_value_clamping_morale(self):
        """Test that morale is clamped to 1-10."""
        ws = WorldState()
        ws.military_units.append(
            MilitaryUnit("Unit A", "US", "ground", "Berlin", 8, 9, supply_level=1, morale=1)
        )

        ws.apply_updates({})  # Trigger cascading effects

        # Morale should not go below 1
        assert ws.military_units[0].morale == 1

    def test_cascading_value_clamping_war_support(self):
        """Test that war_support is clamped to 0-100."""
        ws = WorldState()

        ws.apply_updates({
            "public_opinion": {"US": {"war_support": 2}},
            "markets": {"oil_price": 125}
        })

        # War support: 2 - 3 = -1, clamped to 0
        assert ws.public_opinion["US"]["war_support"] == 0

    def test_cascading_value_clamping_government_approval(self):
        """Test that government_approval is clamped to 0-100."""
        ws = WorldState()

        ws.apply_updates({
            "infrastructure_status": {
                "Poland": {
                    "power_grid": 2,
                    "comms": 2,
                    "financial": 2,
                    "military_c2": 2
                }
            },
            "public_opinion": {"Poland": {"government_approval": 1}}
        })

        # Average infrastructure: (2+2+2+2)/4 = 2 < 5
        # Approval: 1 - 2 = -1, clamped to 0
        assert ws.public_opinion["Poland"]["government_approval"] == 0


# ======================================================================
# 5. Helper Functions Tests
# ======================================================================

class TestHelperFunctions:
    """Tests for private helper functions."""

    def test_dedup_strings_no_duplicates(self):
        """Test _dedup_strings with no duplicates."""
        existing = ["Event A", "Event B"]
        new_items = ["Event C", "Event D"]

        result = _dedup_strings(existing, new_items)

        assert len(result) == 4
        assert "Event C" in result
        assert "Event D" in result

    def test_dedup_strings_with_duplicates(self):
        """Test _dedup_strings removes duplicates (case-insensitive)."""
        existing = ["Event A", "Event B"]
        new_items = ["event a", "Event C", "EVENT B"]

        result = _dedup_strings(existing, new_items)

        assert len(result) == 3
        assert "Event A" in result
        assert "Event B" in result
        assert "Event C" in result

    def test_dedup_strings_with_whitespace(self):
        """Test _dedup_strings handles whitespace correctly."""
        existing = ["Event A"]
        new_items = [" event a ", "Event B"]

        result = _dedup_strings(existing, new_items)

        # " event a " should be treated as duplicate of "Event A"
        assert len(result) == 2
        assert "Event B" in result

    def test_dedup_dicts_no_duplicates(self):
        """Test _dedup_dicts with no duplicates."""
        existing = [{"from": "US", "target": "RU", "type": "financial"}]
        new_items = [{"from": "EU", "target": "RU", "type": "trade"}]

        result = _dedup_dicts(existing, new_items, key_fields=("from", "target", "type"))

        assert len(result) == 2

    def test_dedup_dicts_with_duplicates(self):
        """Test _dedup_dicts removes duplicates based on key_fields."""
        existing = [{"from": "US", "target": "RU", "type": "financial"}]
        new_items = [
            {"from": "us", "target": "ru", "type": "FINANCIAL"},  # case-insensitive duplicate
            {"from": "EU", "target": "RU", "type": "trade"},
        ]

        result = _dedup_dicts(existing, new_items, key_fields=("from", "target", "type"))

        # Should have 2 items (duplicate not added)
        assert len(result) == 2

    def test_dedup_dicts_partial_key_match(self):
        """Test _dedup_dicts only matches when ALL key_fields match."""
        existing = [{"from": "US", "target": "RU", "type": "financial"}]
        new_items = [{"from": "US", "target": "RU", "type": "trade"}]  # different type

        result = _dedup_dicts(existing, new_items, key_fields=("from", "target", "type"))

        # Should have 2 items (not a duplicate because type differs)
        assert len(result) == 2

    def test_dedup_dicts_with_non_dict(self):
        """Test _dedup_dicts skips non-dict items."""
        existing = [{"from": "US", "target": "RU"}]
        new_items = ["not a dict", {"from": "EU", "target": "RU"}]

        result = _dedup_dicts(existing, new_items, key_fields=("from", "target"))

        # Should have 2 items (string skipped)
        assert len(result) == 2

    def test_safe_int_with_int(self):
        """Test _safe_int with integer input."""
        assert _safe_int(42, 0) == 42

    def test_safe_int_with_string(self):
        """Test _safe_int with string input."""
        assert _safe_int("7", 0) == 7

    def test_safe_int_with_float(self):
        """Test _safe_int with float input."""
        assert _safe_int(7.5, 0) == 7

    def test_safe_int_with_invalid_string(self):
        """Test _safe_int with invalid string returns default."""
        assert _safe_int("invalid", 99) == 99

    def test_safe_int_with_none(self):
        """Test _safe_int with None returns default."""
        assert _safe_int(None, 10) == 10

    def test_relation_label_allied(self):
        """Test _relation_label for allied relationship."""
        assert _relation_label(10) == "allied"
        assert _relation_label(8) == "allied"

    def test_relation_label_friendly(self):
        """Test _relation_label for friendly relationship."""
        assert _relation_label(7) == "friendly"
        assert _relation_label(4) == "friendly"

    def test_relation_label_warm(self):
        """Test _relation_label for warm relationship."""
        assert _relation_label(3) == "warm"
        assert _relation_label(1) == "warm"

    def test_relation_label_neutral(self):
        """Test _relation_label for neutral relationship."""
        assert _relation_label(0) == "neutral"

    def test_relation_label_cool(self):
        """Test _relation_label for cool relationship."""
        assert _relation_label(-1) == "cool"
        assert _relation_label(-3) == "cool"

    def test_relation_label_hostile(self):
        """Test _relation_label for hostile relationship."""
        assert _relation_label(-4) == "hostile"
        assert _relation_label(-7) == "hostile"

    def test_relation_label_enemy(self):
        """Test _relation_label for enemy relationship."""
        assert _relation_label(-8) == "enemy"
        assert _relation_label(-10) == "enemy"


# ======================================================================
# 6. to_briefing() Tests
# ======================================================================

class TestToBriefing:
    """Tests for WorldState.to_briefing() method."""

    def test_to_briefing_basic_neutral(self):
        """Test basic briefing generation without for_country."""
        ws = WorldState(round_number=3, game_time="Day 2, 08:00")
        ws.nato_alert_level = "elevated"

        briefing = ws.to_briefing()

        assert "Round 3" in briefing
        assert "Day 2, 08:00" in briefing
        assert "ELEVATED" in briefing

    def test_to_briefing_with_for_country(self):
        """Test briefing generation with for_country parameter."""
        ws = WorldState(round_number=1)
        ws.military_units.append(
            MilitaryUnit("Alpha", "US", "ground", "Berlin", 8, 9)
        )
        ws.military_units.append(
            MilitaryUnit("Beta", "UK", "air", "London", 7, 8)
        )
        ws.public_opinion = {"US": {"war_support": 65, "government_approval": 55}}

        briefing = ws.to_briefing(for_country="US")

        assert "Your forces (US)" in briefing
        assert "Alpha" in briefing
        assert "Known foreign deployments" in briefing
        assert "Beta" in briefing
        assert "DOMESTIC PUBLIC OPINION" in briefing
        assert "War support: 65%" in briefing

    def test_to_briefing_nuclear_posture(self):
        """Test briefing includes nuclear posture with warnings."""
        ws = WorldState()
        ws.nuclear_posture = {
            "US": "elevated",
            "RU": "launch_ready",
        }

        briefing = ws.to_briefing()

        assert "NUCLEAR POSTURE" in briefing
        assert "US: ELEVATED" in briefing
        assert "RU: LAUNCH_READY" in briefing
        assert "CRITICAL" in briefing  # Warning for launch_ready

    def test_to_briefing_economic_situation(self):
        """Test briefing includes economic data."""
        ws = WorldState()
        ws.markets = {"oil_price": 110, "gas_price_eu": 85}
        ws.sanctions.append({"from": "US", "target": "RU", "type": "financial"})
        ws.trade_disruptions.append("Black Sea shipping halted")

        briefing = ws.to_briefing()

        assert "ECONOMIC SITUATION" in briefing
        assert "oil_price: 110" in briefing
        assert "Active sanctions" in briefing
        assert "US -> RU: financial" in briefing
        assert "Trade disruptions" in briefing
        assert "Black Sea shipping halted" in briefing

    def test_to_briefing_diplomatic_relations_neutral(self):
        """Test briefing shows diplomatic relations (neutral view)."""
        ws = WorldState()
        ws.diplomatic_relations = {
            "US": {"RU": -8, "UK": 9},
            "RU": {"US": -8},
        }
        ws.treaties_invoked.append("NATO Article 5")
        ws.un_resolutions.append("Condemn Russian aggression")

        briefing = ws.to_briefing()

        assert "DIPLOMATIC SITUATION" in briefing
        assert "US <-> RU: -8" in briefing
        assert "US <-> UK: +9" in briefing
        assert "Treaties invoked" in briefing
        assert "NATO Article 5" in briefing
        assert "UN resolutions" in briefing

    def test_to_briefing_diplomatic_relations_for_country(self):
        """Test briefing shows diplomatic relations for specific country."""
        ws = WorldState()
        ws.diplomatic_relations = {
            "US": {"RU": -9, "UK": 8},
        }

        briefing = ws.to_briefing(for_country="US")

        assert "Your relations (US)" in briefing
        assert "RU: -9 (enemy)" in briefing
        assert "UK: +8 (allied)" in briefing

    def test_to_briefing_humanitarian_situation(self):
        """Test briefing includes humanitarian data."""
        ws = WorldState()
        ws.refugee_flows = [
            {"from": "Ukraine", "to": "Poland", "count": 100000, "status": "ongoing"},
            {"from": "Ukraine", "to": "Germany", "count": 50000, "status": "ongoing"},
        ]
        ws.humanitarian_crisis_level = {"Ukraine": 9}

        briefing = ws.to_briefing()

        assert "HUMANITARIAN SITUATION" in briefing
        assert "Total displaced persons: ~150,000" in briefing
        assert "Ukraine -> Poland: ~100,000" in briefing
        assert "Ukraine crisis level: 9/10 (CRITICAL)" in briefing

    def test_to_briefing_cyber_and_infrastructure(self):
        """Test briefing includes cyber and infrastructure status."""
        ws = WorldState()
        ws.cyber_operations.append({
            "attacker": "RU",
            "target": "Poland",
            "type": "ddos",
            "severity": "high",
        })
        ws.infrastructure_status = {
            "Poland": {"power_grid": 7, "comms": 8, "financial": 9, "military_c2": 10}
        }

        briefing = ws.to_briefing()

        assert "CYBER & INFRASTRUCTURE" in briefing
        assert "[high] RU -> Poland: ddos" in briefing
        assert "Poland: comms=8" in briefing

    def test_to_briefing_infrastructure_for_country(self):
        """Test briefing shows detailed infrastructure for specific country."""
        ws = WorldState()
        ws.infrastructure_status = {
            "US": {"power_grid": 10, "comms": 9, "financial": 8, "military_c2": 2}
        }

        briefing = ws.to_briefing(for_country="US")

        assert "Your infrastructure status (US)" in briefing
        assert "military_c2: 2/10 (CRITICAL)" in briefing
        assert "comms: 9/10 (operational)" in briefing

    def test_to_briefing_recent_events(self):
        """Test briefing includes recent events."""
        ws = WorldState()
        ws.recent_events = ["Russian forces advance", "NATO reinforces eastern flank"]

        briefing = ws.to_briefing()

        assert "RECENT EVENTS" in briefing
        assert "Russian forces advance" in briefing
        assert "NATO reinforces eastern flank" in briefing

    def test_to_briefing_media_headlines(self):
        """Test briefing includes media headlines."""
        ws = WorldState()
        ws.media_headlines = ["Breaking: Escalation imminent", "Diplomatic talks stall"]

        briefing = ws.to_briefing()

        assert "MEDIA HEADLINES" in briefing
        assert "Breaking: Escalation imminent" in briefing
        assert "Diplomatic talks stall" in briefing

    def test_to_briefing_military_alerts(self):
        """Test briefing includes military alert levels."""
        ws = WorldState()
        ws.military_alerts = {"US": "DEFCON 3", "RU": "High Alert"}

        briefing = ws.to_briefing()

        assert "Alert levels" in briefing
        assert "US: DEFCON 3" in briefing

    def test_to_briefing_military_alerts_for_country(self):
        """Test briefing shows own alert level for specific country."""
        ws = WorldState()
        ws.military_alerts = {"US": "DEFCON 3", "RU": "High Alert"}

        briefing = ws.to_briefing(for_country="US")

        assert "Your alert level: DEFCON 3" in briefing

    def test_to_briefing_empty_sections_omitted(self):
        """Test that empty sections are not included in briefing."""
        ws = WorldState()

        briefing = ws.to_briefing()

        # Should not include section headers for empty data
        assert "HUMANITARIAN SITUATION" not in briefing
        assert "CYBER & INFRASTRUCTURE" not in briefing


# ======================================================================
# Integration Tests
# ======================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_round_simulation(self):
        """Test a complete round of game updates."""
        ws = WorldState()

        # Initialize state
        ws.apply_updates({
            "round_number": 1,
            "game_time": "Day 1, 12:00",
            "military_units_add": [
                {
                    "name": "1st Armored Division",
                    "country": "US",
                    "type": "ground",
                    "location": "Poland",
                    "readiness": 9,
                    "strength": 10,
                }
            ],
            "markets": {"oil_price": 95, "gas_price_eu": 75},
            "public_opinion": {
                "US": {"war_support": 70, "government_approval": 60}
            },
            "nuclear_posture": {"US": "peacetime", "RU": "peacetime"},
        })

        assert ws.round_number == 1
        assert len(ws.military_units) == 1

        # Apply combat effects
        ws.apply_updates({
            "round_number": 2,
            "game_time": "Day 2, 00:00",
            "military_units_update": [
                {"name": "1st Armored Division", "casualties": 4, "supply_level": 7}
            ],
            "markets": {"oil_price": 130},
            "sanctions_add": [{"from": "US", "target": "RU", "type": "energy"}],
            "nuclear_posture": {"RU": "elevated"},
        })

        unit = ws.military_units[0]
        # Casualties should reduce morale: 4 // 2 = 2
        assert unit.morale == 5
        # Oil price spike should reduce war support
        assert ws.public_opinion["US"]["war_support"] < 70
        # Sanctions should increase gas price
        assert ws.markets["gas_price_eu"] > 75

        # Generate briefing
        briefing = ws.to_briefing(for_country="US")
        assert "1st Armored Division" in briefing
        assert "casualties=4" in briefing

    def test_serialization_after_cascading_effects(self):
        """Test that state can be serialized after cascading effects."""
        ws = WorldState()

        # Apply cascading effects
        ws.apply_updates({
            "nuclear_posture": {"US": "launch_ready"},
            "public_opinion": {"US": {"war_support": 70}}
        })

        # Serialize and deserialize
        data = ws.to_dict()
        ws2 = WorldState.from_dict(data)

        # Verify penalty tracking is preserved
        assert "_nuclear_penalty_applied" in ws2.markets
        assert "US" in ws2.markets["_nuclear_penalty_applied"]
        assert ws2.public_opinion["US"]["war_support"] == 65
