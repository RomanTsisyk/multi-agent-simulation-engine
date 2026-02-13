# WarGame UI/UX Concept - Comprehensive Design Specification

**Version**: 1.0
**Date**: 2026-02-13
**Status**: Concept Proposal

---

## 🎯 EXECUTIVE SUMMARY

Transform WarGame from CLI research tool into an interactive geopolitical simulation platform with professional UI/UX. Target market: educational institutions, think tanks, strategy gaming enthusiasts.

**Core Vision**: "The first wargame where political debates matter more than tanks"

**Key Differentiator**: LLM-powered faction debates create unprecedented narrative depth and realism in decision-making.

---

## 📊 CURRENT STATE ANALYSIS

### What Exists Today

**Viewer** (`viewer/index.html` - 1,722 lines):
- Dark-themed SPA in vanilla JavaScript
- Round-by-round navigation
- JSON game log display
- File-based game selection
- **Assessment**: Production-quality foundation, needs enhancement

**Dashboard** (CLI-based):
- Console output showing current phase
- Round progress indicator
- Country deliberation status
- **Assessment**: Functional but not engaging

**Interaction Model**:
- Pure CLI: `python run.py play --preset quick`
- No pause/resume UI
- No human player mode
- Config via YAML file editing

### Pain Points Identified

1. **Barrier to Entry**:
   - Ollama installation (20GB model download)
   - Understanding YAML syntax
   - No visual feedback during 3-hour games

2. **Post-Game Analysis**:
   - JSON logs hard to parse
   - No timeline visualization
   - No "what happened and why" summaries

3. **Limited Engagement**:
   - Pure spectator mode
   - Cannot influence decisions
   - No emotional investment

---

## 🎨 UI/UX DESIGN PHILOSOPHY

### Design Principles

1. **Progressive Disclosure**: Hide complexity, reveal on demand
2. **Real-Time Transparency**: Live updates on all agent activities
3. **Narrative Focus**: Prioritize story over numbers
4. **Educational Clarity**: Explain consequences, not just actions
5. **Responsive Performance**: Smooth even during heavy LLM processing

### Visual Language

**Color Palette**:
- Primary: Dark slate (#1a1d29) - war room aesthetic
- Accent: Amber (#f59e0b) - warnings, attention
- Success: Emerald (#10b981) - positive actions
- Danger: Red (#ef4444) - escalation, threats
- Info: Blue (#3b82f6) - diplomatic actions
- Nuclear: Orange-red gradient - special status

**Typography**:
- Headings: "Inter" (clean, modern)
- Body: "IBM Plex Sans" (readable, technical)
- Code/Data: "JetBrains Mono" (JSON logs)

**Iconography**:
- Nuclear: ☢️ with glow effect
- Military: ⚔️ with strength indicator
- Diplomatic: 🤝 with channel color-coding
- Economic: 💰 with trend arrows
- Intelligence: 🔍 with confidence meter

---

## 🖥️ CORE UI COMPONENTS

### 1. War Room Dashboard (Main View)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎮 WARGAME                               ⚙️ Settings  👤 Profile ┃
┠───────────────────────────────────────────────────────────────────┨
┃                                                                    ┃
┃  📍 SUWALKI GAP CRISIS              Round 3/10 | Day 2, 06:00 GMT ┃
┃  Status: ⚠️ ESCALATING              Next round in: 00:45          ┃
┃                                                                    ┃
┠───────────────────────────────────────────────────────────────────┨
┃                                                                    ┃
┃  ┌─────────────────────────────────┐  ┌──────────────────────────┐┃
┃  │  🗺️ STRATEGIC MAP               │  │  📡 LIVE INTELLIGENCE    │┃
┃  │                                  │  │                          │┃
┃  │    ┌────────────────┐            │  │  🔴 BREAKING:            │┃
┃  │    │ 🇵🇱 POLAND      │            │  │  Russia escalates to     │┃
┃  │    │   ╱╲╱╲╱╲        │            │  │  LAUNCH_READY            │┃
┃  │    │  ▓▓▓▓▓▓▓ 🇷🇺     │            │  │  Confidence: 95% ☢️      │┃
┃  │    │  SUWALKI GAP    │            │  │                          │┃
┃  │    │  [🔴 RUSSIAN]   │            │  │  📨 Germany → US:        │┃
┃  │    │  Hold: 2/6 days │            │  │  "Need 48h to debate     │┃
┃  │    └────────────────┘            │  │  Article 5 response"     │┃
┃  │                                  │  │  Channel: PRIVATE 🔒     │┃
┃  │  Force Ratio: 🇷🇺 1.4 : 1 🇵🇱    │  │                          │┃
┃  │  Air Superiority: CONTESTED      │  │  ⚔️ Polish 11th Cav Div: │┃
┃  │                                  │  │  Readiness ↓ 8→6 (-2)    │┃
┃  └─────────────────────────────────┘  │  Casualties: +450        │┃
┃                                       │                          │┃
┃  ┌─────────────────────────────────┐  └──────────────────────────┘┃
┃  │  ☢️ NUCLEAR STATUS               │                             ┃
┃  │                                  │  ┌──────────────────────────┐┃
┃  │  🇺🇸 USA:        ELEVATED   ⚠️   │  │  📊 PUBLIC OPINION       │┃
┃  │  🇷🇺 RUSSIA:     LAUNCH_READY ⚠️⚠️│  │                          │┃
┃  │  🇬🇧 UK:         ELEVATED   ⚠️   │  │  🇵🇱 Poland:             │┃
┃  │  🇫🇷 FRANCE:     ELEVATED   ⚠️   │  │  War Support:  ████░ 85% │┃
┃  │  🇨🇳 CHINA:      PEACETIME  ✓   │  │  Gov Approval: ███░░ 72% │┃
┃  │                                  │  │                          │┃
┃  │  Auto-Escalation: ON 🔴          │  │  🇩🇪 Germany:            │┃
┃  │  [View Escalation Ladder]        │  │  War Support:  ██░░░ 42% │┃
┃  └─────────────────────────────────┘  │  Gov Approval: ███░░ 68% │┃
┃                                       │                          │┃
┃  ┌─────────────────────────────────┐  │  🇷🇺 Russia:             │┃
┃  │  🎭 ACTIVE DELIBERATIONS         │  │  War Support:  ████░ 78% │┃
┃  │                                  │  │  Gov Approval: ███░░ 65% │┃
┃  │  🇵🇱 Poland:     ⏳ Round 2/3     │  └──────────────────────────┘┃
┃  │  ├─ President:  "Attack NOW!"    │                             ┃
┃  │  ├─ PM:         "Wait for NATO"  │  ┌──────────────────────────┐┃
┃  │  └─ General:    "Need 24h prep"  │  │  💱 ECONOMIC INDICATORS  │┃
┃  │                                  │  │                          │┃
┃  │  🇩🇪 Germany:    ⏳ Round 2/3     │  │  Oil Price:  $145 ↑+12% │┃
┃  │  ├─ Chancellor: "Diplomacy 1st"  │  │  Gas (EU):   €95  ↑+28% │┃
┃  │  ├─ Defense:    "Mobilize now"   │  │  Market Fear: HIGH 🔴   │┃
┃  │  └─ Business:   "Sanctions hurt" │  │                          │┃
┃  │                                  │  │  Sanctions Active: 47    │┃
┃  │  [View All 20 Countries]         │  │  Trade Disruptions: 23   │┃
┃  └─────────────────────────────────┘  └──────────────────────────┘┃
┃                                                                    ┃
┠───────────────────────────────────────────────────────────────────┨
┃  ⏸️ PAUSE  ⏭️ SKIP TO END  💾 SAVE  📊 ANALYTICS  ⚙️ GAME SPEED  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Key Features**:
- **Live Updates**: WebSocket streaming of all events
- **Interactive Map**: Click regions for details, units, control zones
- **Intelligence Feed**: Scrollable timeline with confidence indicators
- **Deliberation Viewer**: Expand to see full 3-round faction debates
- **Status Indicators**: Color-coded nuclear posture, public opinion bars

---

### 2. Player Mode Interface

When user takes control of a country:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎮 YOU ARE: POLAND (President Andrzej Duda)         Round 3/10   ┃
┠───────────────────────────────────────────────────────────────────┨
┃                                                                    ┃
┃  📋 INTELLIGENCE BRIEFING (may contain inaccuracies)              ┃
┃                                                                    ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  HIGH CONFIDENCE (95%):                                      │ ┃
┃  │  • Russian forces control Suwalki corridor (Day 2/6)         │ ┃
┃  │  • NATO Article 5 vote: 18 support, 7 oppose, 5 undecided   │ ┃
┃  │  • US 2nd Cavalry Regiment en route (ETA: 36 hours)         │ ┃
┃  │                                                               │ ┃
┃  │  MEDIUM CONFIDENCE (70%):                                    │ ┃
┃  │  • Russian tactical nuclear weapons dispersed to Kaliningrad│ ┃
┃  │  • Germany internal debate ongoing (outcome unclear)         │ ┃
┃  │                                                               │ ┃
┃  │  LOW CONFIDENCE (40%):                                       │ ┃
┃  │  • Unconfirmed: Russian logistics struggling                │ ┃
┃  │  • Rumor: China mediating behind scenes                     │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  🎭 YOUR FACTIONS ARE DEBATING (Round 3/3 - Final Statements)     ┃
┃                                                                    ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  🦅 PRESIDENT & NSC (Hawk | Weight: 3.0 in conventional war) │ ┃
┃  │                                                               │ ┃
┃  │  "Every hour we wait strengthens Russian positions. 1939    │ ┃
┃  │  taught us appeasement fails. I propose IMMEDIATE counterattack│ ┃
┃  │  with 11th Cavalry Division + US 2nd Cav when they arrive.  │ ┃
┃  │  Germany's hesitation is UNACCEPTABLE - Article 5 is not    │ ┃
┃  │  optional. We act with or without full NATO consensus."     │ ┃
┃  │                                                               │ ┃
┃  │  [Expand to see Rounds 1-2] ▼                                │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  🕊️ PRIME MINISTER & DIPLOMATS (Diplomat | Weight: 2.0)      │ ┃
┃  │                                                               │ ┃
┃  │  "The President's plan risks fracturing NATO permanently.   │ ┃
┃  │  I propose focused diplomatic pressure: 1) Private call to  │ ┃
┃  │  Scholz threatening bilateral defense pact with UK/US if    │ ┃
┃  │  Germany blocks A5, 2) Public statement invoking solidarity │ ┃
┃  │  clause, 3) 48h deadline for NATO decision. Military option │ ┃
┃  │  remains but we MUST preserve alliance unity."              │ ┃
┃  │                                                               │ ┃
┃  │  [Expand to see Rounds 1-2] ▼                                │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  ⚔️ GENERAL STAFF (Military Realist | Weight: 2.5)           │ ┃
┃  │                                                               │ ┃
┃  │  "Both proposals ignore tactical reality. 11th Cav needs 24h│ ┃
┃  │  to reposition. Current force ratio (1.4:1 disadvantage)    │ ┃
┃  │  guarantees failure. I recommend DEFENSIVE posture + covert │ ┃
┃  │  mobilization. If US 2nd Cav arrives + air superiority      │ ┃
┃  │  established, ratio shifts to 1:1.2 - THEN attack. Patience │ ┃
┃  │  is not weakness, it's tactics."                            │ ┃
┃  │                                                               │ ┃
┃  │  [Expand to see Rounds 1-2] ▼                                │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  ⚡ YOUR DECISION (required in 02:45):                             ┃
┃                                                                    ┃
┃  ○ Accept President's plan (immediate counterattack)              ┃
┃    Predicted outcome: 60% chance recapture, 30% NATO fracture    ┃
┃                                                                    ┃
┃  ○ Accept PM's plan (diplomatic pressure + 48h ultimatum)         ┃
┃    Predicted outcome: 70% NATO unity, 40% corridor still lost    ┃
┃                                                                    ┃
┃  ○ Accept General's plan (delay 24h for reinforcements)           ┃
┃    Predicted outcome: 80% force parity, but Russia holds +1 day  ┃
┃                                                                    ┃
┃  ○ Custom decision:                                               ┃
┃  ┌────────────────────────────────────────────────────────────┐  ┃
┃  │  [Type your custom decision, diplomatic messages, and      │  ┃
┃  │   military orders here. AI will interpret and execute.]    │  ┃
┃  │                                                             │  ┃
┃  └────────────────────────────────────────────────────────────┘  ┃
┃                                                                    ┃
┃  Diplomatic Messages (optional):                                  ┃
┃  To: [Germany ▼]  Channel: [Private ▼]  [Compose message...]     ┃
┃                                                                    ┃
┃  ┌────────────────────────────────────────────────────────────┐  ┃
┃  │           [SUBMIT DECISION AND CONTINUE] ──────►           │  ┃
┃  └────────────────────────────────────────────────────────────┘  ┃
┃                                                                    ┃
┃  💡 Tip: Hover over faction names to see their personalities,     ┃
┃     priorities, and red lines                                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Key Features**:
- **Intelligence with Confidence**: Fog-of-war represented by confidence levels
- **Full Debate Transcript**: See all 3 rounds of internal debate
- **Predicted Outcomes**: AI suggests likely consequences of each option
- **Custom Input**: Free-text for creative strategies
- **Time Pressure**: Decision timer creates urgency
- **Tooltips**: Hover for faction personalities, historical context

---

### 3. Scenario Editor

Visual WYSIWYG editor for creating custom scenarios:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎨 SCENARIO EDITOR                                    [SAVE] [TEST]┃
┠───────────────────────────────────────────────────────────────────┨
┃                                                                    ┃
┃  📝 BASIC INFORMATION                                              ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  Name: [Taiwan Strait Crisis 2027________________]           │ ┃
┃  │  Description: [China announces reunification deadline...]    │ ┃
┃  │                                                               │ ┃
┃  │  Crisis Type: ○ Territorial  ○ Nuclear  ● Hybrid  ○ Economic │ ┃
┃  │  Duration: [10] rounds  Estimated playtime: 2-3 hours        │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  🌍 PARTICIPATING COUNTRIES                                        ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  ACTIVE (15 selected)                                        │ ┃
┃  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │ ┃
┃  │  │ 🇨🇳 CHINA │ │ 🇺🇸 USA   │ │ 🇹🇼 TAIWAN│ │ 🇯🇵 JAPAN │       │ ┃
┃  │  │ Mil: 9   │ │ Mil: 10  │ │ Mil: 6   │ │ Mil: 7   │       │ ┃
┃  │  │ Econ: 9  │ │ Econ: 10 │ │ Econ: 8  │ │ Econ: 8  │       │ ┃
┃  │  │ Nuclear:✓│ │ Nuclear:✓│ │ Nuclear:✗│ │ Nuclear:✗│       │ ┃
┃  │  │ [Edit]   │ │ [Edit]   │ │ [Edit]   │ │ [Edit]   │       │ ┃
┃  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │ ┃
┃  │  ... (11 more)                                 [+ Add Country]│ ┃
┃  │                                                               │ ┃
┃  │  OBSERVERS (spectators with no actions)                      │ ┃
┃  │  🇪🇺 EU, 🇮🇳 India, 🇧🇷 Brazil                               │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  📜 INITIAL SITUATION                                              ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  [Rich text editor with markdown support]                    │ ┃
┃  │                                                               │ ┃
┃  │  On March 1st, 2027, China's President announces a 72-hour  │ ┃
┃  │  deadline for Taiwan to accept reunification under the      │ ┃
┃  │  "One Country, Two Systems Plus" framework. The PLA Eastern │ ┃
┃  │  Theater Command is on high alert. US 7th Fleet is 400km    │ ┃
┃  │  from Taiwan Strait...                                       │ ┃
┃  │                                                               │ ┃
┃  │  [🖼️ Add Image] [📊 Add Data] [🔗 Add Reference]            │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  🎯 VICTORY CONDITIONS                                             ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  ☑️ China controls Taiwan (threshold: 10 rounds)             │ ┃
┃  │     Control metric: [Taiwan gov accepts terms ▼]            │ ┃
┃  │                                                               │ ┃
┃  │  ☑️ US enforces status quo (threshold: 15 rounds)            │ ┃
┃  │     Control metric: [Taiwan independence maintained ▼]      │ ┃
┃  │                                                               │ ┃
┃  │  ☑️ Negotiated settlement                                    │ ┃
┃  │     Trigger: [Both sides accept proposal with >80% overlap ▼]│ ┃
┃  │                                                               │ ┃
┃  │  ☑️ Nuclear catastrophe                                      │ ┃
┃  │     Trigger: [Any nuclear weapon detonated ▼]               │ ┃
┃  │                                                               │ ┃
┃  │  [+ Add Custom Victory Condition]                            │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  ⚙️ ADVANCED SETTINGS                                              ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  GM Creativity: [──────●────] (0.7)  Higher = more surprises│ ┃
┃  │  Escalation Speed: [────●──────] (0.5)  Slower = more time  │ ┃
┃  │  Fog of War: [───────●───] (0.8)  Higher = more inaccuracy  │ ┃
┃  │                                                               │ ┃
┃  │  ☑️ Enable air superiority mechanics                         │ ┃
┃  │  ☑️ Enable logistics/supply chains                           │ ┃
┃  │  ☑️ Enable economic interdependence                          │ ┃
┃  │  ☐ Enable cyber warfare                                      │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  ┌────────────────────────────────────────────────────────────┐  ┃
┃  │  [💾 SAVE SCENARIO]  [🧪 TEST RUN]  [📤 EXPORT YAML]       │  ┃
┃  │  [📋 DUPLICATE]      [🗑️ DELETE]    [📚 SAVE AS TEMPLATE]  │  ┃
┃  └────────────────────────────────────────────────────────────┘  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Key Features**:
- **Drag & Drop**: Add/remove countries visually
- **WYSIWYG Editing**: Rich text for scenario description
- **Victory Condition Builder**: Visual interface for complex win conditions
- **Sliders for Tuning**: GM creativity, escalation speed, fog-of-war
- **Test Run**: Quick validation before saving
- **Export Options**: YAML for advanced users, JSON for API

---

### 4. Post-Game Analytics Dashboard

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  📊 GAME ANALYSIS: Suwalki Gap Crisis #47        NATO Victory     ┃
┠───────────────────────────────────────────────────────────────────┨
┃                                                                    ┃
┃  📈 TIMELINE VISUALIZATION                                         ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  Nuclear Posture ☢️                                          │ ┃
┃  │  High  │             ┌──Russia──┐                            │ ┃
┃  │        │            /            \                           │ ┃
┃  │  Med   │       ┌─US/UK──┐        └──────                    │ ┃
┃  │        │      /          \                                   │ ┃
┃  │  Low   │─────              ────────────────────────          │ ┃
┃  │        └─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬───│ ┃
┃  │              R1    R2    R3    R4    R5    R6    R7    R8   │ ┃
┃  │                                                               │ ┃
┃  │  Corridor Control 🗺️                                         │ ┃
┃  │  RU    │▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░        │ ┃
┃  │  Cont. │░░░░░░░░░░░░▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░        │ ┃
┃  │  NATO  │░░░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓        │ ┃
┃  │        └─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬───│ ┃
┃  │              R1    R2    R3    R4    R5    R6    R7    R8   │ ┃
┃  │                                                               │ ┃
┃  │  [🔍 Zoom] [📊 Export Chart] [🎬 Replay as Video]           │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  🎯 KEY TURNING POINTS                                             ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  ⭐ Round 3: Germany votes YES on Article 5 (probability: 48%)│ ┃
┃  │     "This was the critical moment. Without German support,   │ ┃
┃  │      NATO would have fractured and Russia won by default."   │ ┃
┃  │     Contributing factors:                                    │ ┃
┃  │     • Poland's private threat to Scholz (diplomatic pressure)│ ┃
┃  │     • France's public solidarity statement (peer pressure)   │ ┃
┃  │     • US 2nd Cavalry arrival (credible military option)      │ ┃
┃  │                                                               │ ┃
┃  │  ⭐ Round 5: Russia de-escalates nuclear to Dispersal         │ ┃
┃  │     "This prevented nuclear crisis. Likely due to China's    │ ┃
┃  │      backchannel message warning of economic consequences."  │ ┃
┃  │                                                               │ ┃
┃  │  ⭐ Round 7: NATO counterattack succeeds (force ratio 1:1.3)  │ ┃
┃  │     "Air superiority + reinforcements = tactical victory"    │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  📊 FACTION INFLUENCE ANALYSIS                                     ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  Poland: Which faction dominated decisions?                  │ ┃
┃  │  ┌────────────────────────────────────────────────────────┐ │ ┃
┃  │  │  President (Hawk):        ████████░░ 42% (Rounds 1-3)  │ │ ┃
┃  │  │  PM (Diplomat):           ██████████ 35% (Rounds 4-6)  │ │ ┃
┃  │  │  General Staff (Realist): ██████░░░░ 23% (Rounds 7-8)  │ │ ┃
┃  │  └────────────────────────────────────────────────────────┘ │ ┃
┃  │                                                               │ ┃
┃  │  Insight: Poland's decision-making shifted from hawkish to   │ ┃
┃  │  diplomatic as NATO consensus became critical (R3-R5), then  │ ┃
┃  │  military realism dominated during counterattack execution.  │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  🔀 WHAT IF SCENARIOS                                              ┃
┃  ┌──────────────────────────────────────────────────────────────┐ ┃
┃  │  What if Germany voted NO on Article 5?                      │ ┃
┃  │  ○ Simulate from Round 3 ──────────────► [RUN SIMULATION]   │ ┃
┃  │                                                               │ ┃
┃  │  What if Russia used tactical nuke in Round 5?               │ ┃
┃  │  ○ Simulate from Round 5 ──────────────► [RUN SIMULATION]   │ ┃
┃  │                                                               │ ┃
┃  │  What if USA delayed 2nd Cavalry deployment?                 │ ┃
┃  │  ○ Custom scenario modification ───────► [OPEN EDITOR]      │ ┃
┃  └──────────────────────────────────────────────────────────────┘ ┃
┃                                                                    ┃
┃  📤 EXPORT OPTIONS                                                 ┃
┃  ┌────────────────────────────────────────────────────────────┐  ┃
┃  │  [📄 PDF Report] [📊 Excel Data] [🎬 Video Replay]         │  ┃
┃  │  [🔗 Share Link]  [💾 Save Analysis] [🖨️ Print]           │  ┃
┃  └────────────────────────────────────────────────────────────┘  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Key Features**:
- **Interactive Timeline**: Zoom, pan, overlay multiple metrics
- **AI-Generated Insights**: Explain why outcomes occurred
- **Turning Point Detection**: Highlight critical decisions
- **Faction Influence Chart**: Shows which voices dominated when
- **What-If Simulations**: Branch from any round and explore alternatives
- **Rich Export**: PDF, Excel, video, shareable links

---

## 🔧 TECHNICAL IMPLEMENTATION

### Architecture Stack

**Frontend**:
```
React 18 + TypeScript
├── State Management: Zustand (lightweight, performant)
├── Routing: React Router v6
├── UI Components: Radix UI (headless, accessible)
├── Styling: Tailwind CSS + CSS Modules
├── Charts: Recharts + D3.js for custom viz
├── Real-time: Socket.IO client
└── Build: Vite (fast HMR)
```

**Backend** (additions to existing Python codebase):
```
FastAPI (WebSocket support)
├── WebSocket endpoint: /ws/game/{game_id}
├── REST API: /api/v1/games, /scenarios, /analytics
├── Real-time broadcast: Redis Pub/Sub
├── Session management: JWT tokens
└── File uploads: Scenario YAML validation
```

**Infrastructure**:
```
Docker Compose
├── app: Python + FastAPI
├── ollama: Ollama model server
├── redis: WebSocket message broker
├── nginx: Reverse proxy + static files
└── postgres: User accounts, saved games (optional)
```

### WebSocket Event Protocol

```typescript
// Server → Client events
type ServerEvent =
  | { type: 'round_started', round: number, timestamp: string }
  | { type: 'country_deliberating', country: string, phase: 'debate_r1' | 'debate_r2' | 'synthesis' }
  | { type: 'decision_made', country: string, decision: Decision }
  | { type: 'gm_resolving', status: 'processing' | 'complete' }
  | { type: 'world_state_update', updates: WorldStateUpdate }
  | { type: 'nuclear_escalation', country: string, from: string, to: string }
  | { type: 'corridor_control_change', from: string, to: string, confidence: number }
  | { type: 'end_condition_met', condition: EndCondition, winner?: string }
  | { type: 'error', message: string, severity: 'warning' | 'error' | 'fatal' }

// Client → Server events (player mode)
type ClientEvent =
  | { type: 'player_decision', country: string, decision: Decision, diplomatic_messages: Message[] }
  | { type: 'pause_game' }
  | { type: 'resume_game' }
  | { type: 'set_speed', multiplier: number }
```

### Database Schema (Optional - for user accounts)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE,
  display_name VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE saved_games (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  scenario_name VARCHAR(255),
  checkpoint_path VARCHAR(500),
  round_number INT,
  status VARCHAR(50), -- 'in_progress', 'completed', 'abandoned'
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE custom_scenarios (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  name VARCHAR(255),
  yaml_content TEXT,
  is_public BOOLEAN DEFAULT FALSE,
  plays_count INT DEFAULT 0,
  created_at TIMESTAMP
);

CREATE TABLE analytics_events (
  id UUID PRIMARY KEY,
  game_id UUID REFERENCES saved_games(id),
  event_type VARCHAR(100),
  event_data JSONB,
  timestamp TIMESTAMP
);
```

---

## 🚀 DEVELOPMENT ROADMAP

### Phase 1: Foundation (2 weeks)

**Week 1: Backend WebSocket**
- [ ] Add FastAPI to project
- [ ] Implement WebSocket endpoint `/ws/game/{game_id}`
- [ ] Broadcast events from game loop (round start, decisions, updates)
- [ ] Add Redis for message broker (optional, can use in-memory for MVP)
- [ ] Test with existing viewer HTML (prove concept)

**Week 2: React Dashboard Setup**
- [ ] Initialize React + Vite project in `/ui` directory
- [ ] Set up Tailwind CSS, Radix UI components
- [ ] Create basic layout (header, sidebar, main content)
- [ ] Implement WebSocket connection hook
- [ ] Display live events in feed (basic list)

**Deliverable**: Live dashboard showing real-time game events

---

### Phase 2: Core Interactions (4 weeks)

**Week 3: Map Visualization**
- [ ] D3.js SVG map component
- [ ] Display countries, borders, regions
- [ ] Show corridor control with color coding
- [ ] Unit positions (basic icons)
- [ ] Click interaction for details

**Week 4: Nuclear & Opinion Widgets**
- [ ] Nuclear status panel with escalation ladder
- [ ] Public opinion bars (animated)
- [ ] Economic indicators dashboard
- [ ] Intelligence feed with confidence badges

**Week 5-6: Player Mode**
- [ ] Refactor `Country` class → `AICountry` + `HumanCountry`
- [ ] Player decision UI (accept faction/custom input)
- [ ] Timer component with countdown
- [ ] Diplomatic message composer
- [ ] Submit decision API endpoint

**Deliverable**: Fully functional player mode

---

### Phase 3: Advanced Features (4 weeks)

**Week 7-8: Scenario Editor**
- [ ] WYSIWYG editor for scenario description
- [ ] Country selector with search/filter
- [ ] Victory condition builder (visual)
- [ ] Settings sliders (GM creativity, escalation speed)
- [ ] YAML export/import
- [ ] Test run integration

**Week 9: Analytics Dashboard**
- [ ] Recharts timeline visualization
- [ ] Turning point detection algorithm
- [ ] Faction influence calculations
- [ ] What-if scenario branching
- [ ] Export to PDF/Excel

**Week 10: Polish & Testing**
- [ ] Mobile responsive design
- [ ] Loading states, error boundaries
- [ ] Accessibility (ARIA labels, keyboard nav)
- [ ] Performance optimization (virtualization for long lists)
- [ ] End-to-end testing (Playwright)

**Deliverable**: Production-ready UI

---

### Phase 4: Deployment & Launch (2 weeks)

**Week 11: Infrastructure**
- [ ] Docker Compose configuration
- [ ] Nginx reverse proxy setup
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Environment-based config
- [ ] Health checks, monitoring

**Week 12: Beta Testing**
- [ ] User testing with 10-20 beta users
- [ ] Bug fixes, UX improvements
- [ ] Documentation (user guide, video tutorials)
- [ ] Marketing site (landing page)

**Deliverable**: Public beta launch

---

## 💰 MONETIZATION STRATEGY

### Freemium Model

**Free Tier** (70% of users):
- 1 scenario (Suwalki Gap)
- AI-only mode (pure spectator)
- 5 games/month
- Basic analytics
- Community scenarios (read-only)

**Pro Tier** - $9/month (25% of users):
- All official scenarios (10+)
- Player mode (control 1 country)
- Unlimited games
- Advanced analytics with what-if
- Scenario editor (save 10 custom)
- Export to PDF/Excel
- Priority support

**Enterprise Tier** - $99/month (5% of users):
- White-label deployment
- Custom scenario development
- Multi-player (2-4 humans)
- API access for research
- Private hosted instance
- Dedicated support

### Additional Revenue Streams

**Scenario Marketplace**:
- Users sell custom scenarios ($2-10 each)
- Platform takes 30% cut
- Top creators earn $100-500/month

**Educational Licensing**:
- University site license: $500-2000/year
- 50-500 student accounts
- Professor dashboard, grade integration
- Custom scenarios for coursework

**Corporate Training**:
- Executive crisis simulation: $5000/session
- Custom scenarios for company's industry
- Facilitated 4-hour workshops
- Post-session analysis report

---

## 📊 SUCCESS METRICS

### User Engagement KPIs

1. **DAU/MAU Ratio**: Target 0.25 (high engagement)
2. **Games Completed**: 40% start → finish rate
3. **Average Session Time**: 45+ minutes
4. **Player Mode Adoption**: 60% of users try human control
5. **Scenario Editor Usage**: 20% create custom scenarios

### Business KPIs

1. **Free → Pro Conversion**: 5% in first 3 months
2. **Churn Rate**: <10% monthly for Pro tier
3. **LTV/CAC Ratio**: 3:1 target
4. **MRR Growth**: 15% month-over-month
5. **NPS Score**: 50+ (great product-market fit)

### Technical Performance

1. **WebSocket Latency**: <100ms p95
2. **Page Load Time**: <2s initial
3. **Uptime**: 99.5%
4. **LLM Response Time**: <10s p95 (depends on Ollama/API)

---

## 🎓 COMPETITIVE ANALYSIS

### Existing Wargames Landscape

| Product | Price | UI Quality | AI Quality | Target Market |
|---------|-------|------------|------------|---------------|
| **Command: Modern Ops** | $80 | ⭐⭐⭐⭐ | ⭐⭐ (scripted) | Military enthusiasts |
| **Matrix Games Professional** | $60-200 | ⭐⭐ | ⭐⭐⭐ (human GM) | Professional wargamers |
| **Crisis in the Kremlin** | $30 | ⭐⭐⭐ | ⭐⭐ (basic) | History buffs |
| **Democracy 4** | $27 | ⭐⭐⭐⭐ | ⭐⭐ (rules-based) | Policy simulation fans |
| **WarGame + UI** | Free/$9 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (LLM) | **All of the above** |

### Our Unique Advantages

1. **Narrative Depth**: LLM-generated faction debates create novel-quality stories
2. **Accessibility**: Web-based, no install (vs. Windows-only competitors)
3. **Extensibility**: User-created scenarios (vs. fixed content)
4. **Educational**: Built-in analytics, what-if scenarios (vs. just play)
5. **Modern Stack**: React/Python (vs. legacy C++/Java codebases)

---

## 🔮 FUTURE VISION (12+ months)

### Advanced Features

1. **Multiplayer Co-op**:
   - 2-4 humans control different countries
   - Voice chat integration
   - Shared fog-of-war
   - Leaderboards for competitive play

2. **AI-Generated Map Visuals**:
   - Stable Diffusion for battle scenes
   - DALL-E for propaganda posters
   - Animated unit movements

3. **VR War Room**:
   - Meta Quest 3 / Apple Vision Pro support
   - 3D holographic map
   - Spatial audio for debates
   - Immersive briefing room

4. **Historical Playback**:
   - Load real-world crises (Cuban Missile, Gulf War)
   - Compare AI decisions to actual history
   - Educational mode: "What if JFK chose differently?"

5. **Academic Research Tools**:
   - Batch simulation runner (1000 games)
   - Statistical analysis dashboard
   - Hypothesis testing framework
   - Export to R/Python notebooks

---

## ✅ CONCLUSION

Building a professional UI for WarGame is not only feasible but **strategically critical**. The current codebase has excellent foundations (sophisticated game logic, LLM integration, faction debates), but the CLI-only interface limits its audience to technical users.

**Key Takeaways**:

1. ✅ **Technical Feasibility**: High - existing viewer proves UI can work, WebSocket additions are straightforward
2. ✅ **Market Opportunity**: Large - no competitor has LLM-powered geopolitical simulation with modern UI
3. ✅ **Revenue Potential**: Strong - freemium model with educational licensing can scale to $50K+ MRR
4. ✅ **Development Timeline**: Reasonable - 12 weeks to production-ready UI with 1 full-time developer

**Recommended Next Step**: Build Phase 1 foundation (WebSocket + basic React dashboard) in next 2 weeks to validate concept with real users before committing to full roadmap.

---

**Document Status**: ✅ Ready for Implementation
**Last Updated**: 2026-02-13
**Authors**: Multi-Agent Analysis Team + UI/UX Specialist
