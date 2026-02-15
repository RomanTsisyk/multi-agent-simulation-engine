# Game Mechanics: Combat, Escalation, Cascading Effects

---

## Combat Resolution

### Combat Effectiveness Formula

```
attacker_effectiveness = strength × (readiness/10) × air_mult × supply_mult
defender_effectiveness = strength × (readiness/10) × terrain_mult × supply_mult

where:
  strength: 1-10 scale (military capability)
  readiness: 1-10 scale (personnel training, equipment condition)
  air_mult: 1.3 (if attacker has air superiority), 1.0 (parity)
  terrain_mult: 1.2 (if defender in forest/urban/mountains), 1.0 (open)
  supply_mult: 1.0 (if supply >= 3), 0.7 (if supply < 3)
```

### Outcome Determination

```
casualty_ratio = attacker_eff / (defender_eff + 0.1)

if casualty_ratio > 1.5:
  → Attacker wins decisively
  → Defender retreats 20-40km
  → Attacker casualties: 5-10% of forces
  → Defender casualties: 15-25%

if casualty_ratio 1.2-1.5:
  → Attacker gains ground (5-15km)
  → Both sides high casualties (10-20%)
  → Attacker supply depleted (-2 level)

if casualty_ratio 1.0-1.2:
  → Stalemate (no territorial change)
  → Both sides moderate casualties (8-12%)
  → Attacker may withdraw due to exhaustion

if casualty_ratio < 1.0:
  → Defender holds position
  → Attacker retreats
  → Attacker casualties: 15-25%
  → Defender casualties: 8-12%
```

### Example: Suwalki Gap Combat

**Round 1 Combat: Poland 2nd Brigade vs Russian 1st Army**

```
POLAND (Attacker)
  strength: 5 (brigade-level)
  readiness: 0.8 (recent mobilization)
  air_mult: 1.3 (NATO air support secured)
  supply_mult: 1.0 (full supply)

  effectiveness = 5 × 0.8 × 1.3 × 1.0 = 5.2

RUSSIA (Defender)
  strength: 5 (army group, outnumbers brigade)
  readiness: 0.6 (recent deployment, logistics thin)
  terrain_mult: 1.2 (entrenched in forest)
  supply_mult: 1.0 (adequate supply)

  effectiveness = 5 × 0.6 × 1.2 × 1.0 = 3.6

casualty_ratio = 5.2 / 3.6 = 1.44 → MARGINAL ATTACKER ADVANTAGE

Outcome:
  ✓ Poland gains 8km
  ✗ 120 Polish casualties
  ✗ 250 Russian casualties

  Poland: readiness ↓ to 0.7 (losses)
  Russia: supply ↓ to 2 (lines stretched)
```

---

## Nuclear Escalation Ladder

### 4-Stage Escalation

```
Stage 1: PEACETIME
  └─ Normal peacetime posture
  └─ Nuclear weapons in storage
  └─ Alert status: 24-48h readiness

Stage 2: ELEVATED
  └─ Intelligence warning (conflict imminent)
  └─ Nuclear weapons moved to secure bunkers
  └─ Alert status: 4-6h readiness
  └─ First-use doctrine authorized

Stage 3: DISPERSAL
  └─ Conflict active (war declared or major offensive)
  └─ Nuclear weapons on mobile launchers
  └─ Alert status: 15-30 min readiness
  └─ Launch officers ready, awaiting authorization

Stage 4: LAUNCH_READY
  └─ Tactical nuclear strike authorized
  └─ Weapons in launch configuration
  └─ First strike may be imminent
  └─ Game end condition if detonation occurs
```

### Escalation Triggers

| Event | Trigger | New Posture |
|-------|---------|-------------|
| Article 5 invoked | NATO formally triggered | Elevated |
| Major offensive begins | >1000 casualties/round | Elevated |
| Capital threatened | Enemy troops within 50km | Dispersal |
| Nuclear-capable ally invaded | Country with nukes loses territory | Dispersal |
| Strategic defeat appears | Can't hold against current odds | Dispersal → Launch_ready |
| Explicit nuclear threat | Opponent threatens nuclear strike | Dispersal → Launch_ready |

### Automatic De-escalation

```
if (casualties = 0 AND active_combat = false) for 3 consecutive rounds:
  launch_ready → dispersal
  dispersal → elevated
  elevated → peacetime
```

**Rationale:** Postures reflect current threat. If fighting stops, relax stance.

### Nuclear First-Strike Outcome

```
if tactical_nuke_detonated:
  → Game immediately ends
  → No winner (mutual destruction/draw)
  → Used for "worse case" analysis
```

---

## Public Opinion Constraints

### War Support Calculation

```
war_support_change = -CASUALTIES_FACTOR
                     - OIL_SHOCK_FACTOR
                     - DURATION_FATIGUE
                     + VICTORY_BOOST
                     + PROPAGANDA_BOOST

where:
  CASUALTIES_FACTOR = (deaths / population) × 100
  OIL_SHOCK_FACTOR = (oil_price - baseline) × 0.5 / 10
  DURATION_FATIGUE = (rounds > 8) × 0.5
  VICTORY_BOOST = if_won_last_round × 3
  PROPAGANDA_BOOST = GM_narrative_effect
```

### Legal Action Gates

```
War Support >= 70%
  ✓ Offensive operations (attack enemy)
  ✓ Foreign deployment (troops outside borders)
  ✓ Air/naval strikes
  ✓ Nuclear escalation (political room)

War Support 50-70%
  ✓ Defensive operations only
  ✓ No foreign troop deployment
  ✗ No offensive into enemy territory
  ✗ Nuclear escalation risky

War Support 30-50%
  ✓ Defensive operations only
  ✗ No offensive operations
  ✗ All other actions blocked
  ⚠ Government stability questioned

War Support < 30%
  ✗ NO military operations (domestic crisis)
  ⚠ Government collapse risk
  ⚠ May trigger coup / political change
```

### Example: Poland Public Opinion Shift

```
Round 1 Start: war_support = 75%
  Action: Invoke Article 5
  Outcome: Small boost (+2%) → 77%

Round 2: 120 casualties (from 1.3M population)
  CASUALTIES_FACTOR = (120/1,300,000) × 100 = 0.009% (negligible)
  Support: 77% (minimal impact for small battle)

Round 5: 5,000 cumulative casualties, oil at $140 (was $70)
  CASUALTIES_FACTOR = (5,000/1,300,000) × 100 = 0.38%
  OIL_SHOCK_FACTOR = (140-70) × 0.5 / 10 = 3.5%
  war_support_change = -0.38 - 3.5 = -3.88%
  New support: 77% - 3.88% = 73.1%

Round 10: 15,000 cumulative casualties, 3rd year of war
  CASUALTIES_FACTOR = 1.15%
  OIL_SHOCK_FACTOR = 3.5% (still elevated)
  DURATION_FATIGUE = 0.5% (year 3)
  war_support_change = -1.15 - 3.5 - 0.5 = -5.15%
  New support: 68% - 5.15% = 62.85%

  ⚠ Crossed 70% threshold → Can no longer conduct offensive ops
```

---

## Cascading Effects System

### Economic Effects

**Oil Price Shock**
```
if active_combat_rounds > 0:
  oil_price_change = casualties_per_round × 0.5 + supply_disruption × 2

Example:
  Round 1: 500 casualties, some supply lines hit
  change = 500 × 0.5 + 2 × 2 = 254
  oil_price: $70 → $80 (global supply fear)

  Round 5: 2000 cumulative casualties, major pipeline threatened
  change = 2000 × 0.5 + 5 × 2 = 1010
  oil_price: $80 → $90 (additional shock)
```

**Sanctions Impact**
```
if (country_A sanctions country_B):
  duration = while_conflict_active
  trade_reduction = 30-50%
  gov_approval_cost = 3% per round

Example: EU sanctions Russia
  Russia trade value lost: $200B (30% of trade)
  EU gas prices ↑ (supply disruption)
  → EU war_support ↓ (economic pain)
```

### Military Supply Degradation

```
supply_level = supply_level - (enemy_sorties × 0.1) - (casualties × 0.05)

if supply < 3:
  combat_effectiveness × 0.7
  readiness ↓ 1 point per round
  morale ↓ 2% per round
```

### Morale & Readiness

```
morale_change = -CASUALTIES_PER_ROUND / 1000
              - LOSSES_OF_TERRITORY × 5
              + VICTORY_BONUS × 3
              - RETREAT_PRESSURE × 2

readiness_change = -SUPPLY_SHORTAGE × 0.5
                  - CASUALTIES_PERCENTAGE × 0.1
                  + REINFORCEMENTS × 0.3
```

### Refugee & Displacement

```
if territory_lost:
  refugees = (population_in_territory / 10) × lost_percentage

Example: Russia controls 15% of Poland (200k people)
  refugees = 200,000 / 10 = 20,000 initial
  + 500 per round (additional displacement)
  → After 5 rounds: 22,500 refugees in EU countries
  → EU gov_approval ↓ 2% (integration costs)
```

---

## Escalation Level (0-10 Scale)

**Global tension metric** combining all factors:

```
escalation_level = (nuclear_component +
                    military_component +
                    economic_component +
                    political_component) / 4

where:

nuclear_component = mean(
  {"peacetime": 0, "elevated": 2, "dispersal": 4, "launch_ready": 6}[posture]
  for all countries
)

military_component = (total_casualties / 100,000) × 2

economic_component = (oil_price - 70) / 20  [0-10 if oil ∈ $70-270]

political_component = (nato_alert_level):
  "peacetime": 0
  "heightened": 1
  "combat": 3
  "maximum": 5
```

### Example: Escalation Trajectory

```
Round 1:
  nuclear: 0 (all peacetime)
  military: 0 (no combat yet)
  economic: 0 (price still $70)
  political: 0 (peace)
  → escalation = 0.0

Round 3:
  nuclear: 1.5 (US+RU elevated, NATO heightened)
  military: 0.5 (300 casualties)
  economic: 1.5 (oil $80)
  political: 2 (NATO heightened alert)
  → escalation = (1.5 + 0.5 + 1.5 + 2) / 4 = 1.375

Round 8:
  nuclear: 3.0 (several countries dispersal)
  military: 3.0 (3000 casualties)
  economic: 3.0 (oil $130)
  political: 3 (NATO in combat mode)
  → escalation = (3 + 3 + 3 + 3) / 4 = 3.0

Round 15:
  nuclear: 5.5 (Russia launch_ready, US dispersal)
  military: 5.0 (5000 casualties)
  economic: 4.0 (oil $150)
  political: 4 (NATO maximum alert)
  → escalation = (5.5 + 5.0 + 4.0 + 4) / 4 = 4.625

  ⚠ DANGER ZONE: Any nuclear detonation ends game
```

---

## Supply & Logistics

### Supply Level (1-10)

```
supply_level = (logistics_rating × base_production) -
               (active_units × 0.3) -
               (enemy_disruption × 0.2)

where:
  logistics_rating: 1-10 (how good are supply lines?)
  base_production: 5-10 (peacetime production capacity)
  active_units: # of military units deployed
  enemy_disruption: casualties caused by interdiction
```

### Supply Consequences

```
Supply >= 7: No penalty (full strength)
Supply 5-7: Minor penalty (-10% combat effectiveness)
Supply 3-5: Significant penalty (-30% effectiveness)
Supply < 3: Critical (-30% + readiness ↓, morale ↓)
```

### Example: Russian Supply Line Degradation

```
Round 1: Russia controls corridor, supply secure
  supply_level = 8 (short lines, good logistics)

Round 4: Poland + NATO disruption ongoing
  supply_level = 8 - (3 units × 0.3) - (500 casualties × 0.2/1000) = 7.8

Round 8: NATO air strikes hitting convoys
  supply_level = 8 - (5 units × 0.3) - (2000 casualties × 0.2/1000) = 7.1

Round 12: Constant interdiction, logistics degraded
  supply_level = 8 - (8 units × 0.3) - (5000 casualties × 0.2/1000) = 5.8
  → Crosses into "minor penalty" threshold
  → Russian effectiveness drops to 0.9x next round
```

---

## Territory Control

### Corridor Status

```
if attacker_wins_combat AND (Polish strength > Russian):
  → NATO gains control
  → Baltic states accessible
  → Strategic victory for NATO

if Russian strength > Polish AND NATO_support_insufficient:
  → Russia maintains control
  → Baltics isolated
  → Strategic victory for Russia

if stalemate_for_6_rounds:
  → Negotiated settlement
  → Joint control or DMZ
  → Draw
```

---

## Victory Conditions (Suwalki Scenario)

```
1. NATO Victory
   → Liberate corridor and hold for 3 consecutive rounds
   → OR: Russia agrees to withdraw (negotiation)

2. Russian Victory
   → Control corridor for 6 consecutive rounds (36 hours game time)
   → OR: NATO fractures (Germany, France negotiate separate peace)

3. Nuclear Escalation (Game End)
   → If any nuclear weapon detonates
   → No winner (catastrophic outcome)

4. Negotiated Settlement
   → Both sides agree on ceasefire + terms
   → DMZ established
   → Diplomatic resolution
```

---

## Numerical Reference

### Country Strength Scale (1-10)

| Strength | Military Capability |
|----------|-------------------|
| 1-2 | Minimal (police/militia) |
| 3-4 | Small professional force |
| 5-6 | Regional power |
| 7-8 | Major military |
| 9-10 | Great power (US, Russia, China) |

### Readiness Scale (1-10)

| Readiness | Status |
|-----------|--------|
| 1-3 | Unprepared (peacetime, no mobilization) |
| 4-6 | Alert (mobilized, recent training) |
| 7-8 | Combat ready (deployed, experienced) |
| 9-10 | Elite (special forces, best units) |

### Casualty Reference Points

| Deaths | % of Population | Impact |
|--------|-----------------|--------|
| 100 | <0.01% (Poland, 1.3M) | Negligible |
| 1,000 | 0.08% | -0.5% war support |
| 5,000 | 0.4% | -2% war support |
| 10,000 | 0.8% | -3% war support |
| 50,000 | 4% | -6% war support + morale crisis |

---

**For implementation code, see TECHNICAL.md or engine/game_master.py**
