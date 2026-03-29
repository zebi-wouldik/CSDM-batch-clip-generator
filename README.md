<div align="center">

# 🎬 CSDM Batch Clips Generator

**Batch-record CS2 highlight clips directly from your CSDM PostgreSQL database.**

[![Python](https://img.shields.io/badge/python-3.10+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CS2](https://img.shields.io/badge/CS2-compatible-f97316?style=flat-square)](https://www.counter-strike.net/)
[![License](https://img.shields.io/badge/license-do%20what%20you%20want-8b5cf6?style=flat-square)]()

</div>

---

A Python GUI that plugs into [CS Demo Manager](https://cs-demo-manager.com/) and lets you batch-record highlights from your entire CS2 demo library — by player, event type, date range, weapon, and a comprehensive set of kill modifiers (lucky shots, one-taps, clutches, spray transfers, wallbangs, flicks, and more).

Pick your filters → Preview → Run. CSDM handles the actual recording; this tool handles everything else.

---

## Requirements

| Dependency | Notes |
|---|---|
| **Python 3.10+** | |
| **FFmpeg** | Must be in `PATH` |
| **CS Demo Manager** | [cs-demo-manager.com](https://cs-demo-manager.com/) — provides the CLI and PostgreSQL DB |
| `pip install psycopg2-binary` | Required |
| `pip install demoparser2` | Needed for advanced kill modifiers (TROIS SHOT, ONE TAP, WALLBANG, AIRBORNE, etc.) |
| `pip install pywin32` | Optional — sends CS2 behind all windows on launch |

---

## Getting started

```bash
python csdm_batch_clips_generator.py
```

Open the **Tools** tab → connect to PostgreSQL with the same credentials as CSDM.

---

## Workflow

```
Capture tab  →  PLAYER + EVENTS + KILL FILTERS  →  F6 Preview  →  F5 Run
```

- **Preview** shows clip count, total duration, a structured filter summary, and a per-demo breakdown with content badges — uncheck any demo to exclude it
- **Manual mode** lets you pick any demo from the full database regardless of date range
- **Auto-tag** tags processed demos in CSDM when the batch completes. Tags are **rolled back automatically** if the batch is stopped or killed mid-run

---

## Preview header

Each preview shows a clean summary block before the demo list:

```
Player:  MAMMOUTH (76561198…)
Dates:   2025-12-19  →  2026-03-19
Events:  Kills
Weapons: 🎯 Rifles(1)
Rec:     POV Killer  |  TrueView: ON  |  Order: Chronological
Filters: dp2 [MIXED]: ★ 🧱 WALLBANG · 💨 SMOKE
Found:   17 demo(s)  ·  23 event(s)
Output:  H:\CS\CSVideos\Raws
```

Each demo line shows a **content badge** (what weapon/event type the clip contains) followed by **filter badges** (which specific filter each kill triggered):

```
09 02 2026  match730_…dem  (5 events → 5 seq) [5✕ AK-47] [💨 SMOKE] [🧱 WALLBANG]
```

---

## Headshot filter

An independent `🎯 Headshots` tri-state radio alongside Suicides and TK — not part of kill-mod logic:

| Mode | Behaviour |
|---|---|
| **All** | No headshot filtering (default) |
| **Only** | Keep headshot kills only |
| **Exclude** | Keep non-headshot kills only |

---

## Match type filter

The **MATCH TYPES** section in Capture & Timing lets you restrict clips to specific CS2 game modes. Hidden by default — appears only after the DB connects, and only shows types actually present in your database.

| Label | DB value(s) |
|---|---|
| 🏆 Premier | `premier` |
| 🎯 Competitive | `scrimcomp5v5`, `competitive` |
| 🤝 Wingman | `scrimcomp2v2`, `wingman` |
| 🎮 Casual | `casual` |
| 💀 Deathmatch | `deathmatch` |
| 🎓 Training / New User | `training`, `new_user_training` |
| 🔫 Arms Race | `armsrace`, `gungameprogressive` |
| 💣 Demolition | `gungametrbomb` |
| 🤖 Co-op | `cooperative` |
| ⚡ Skirmish | `skirmish` |
| ↩ Retakes | `retake` |

Multiple DB values per type handle differences between CSDM versions (some store `competitive`, others `scrimcomp5v5`).

---

## Kill modifier logic

The UI now uses one fixed logic model for both layers:
- **Kill filters** (Mods + demoparser2)
- **Situation filters** (DB + Clutch section, applied after kill filters)

Global matching rule:
- all enabled `★ Must` filters must match
- plus at least one enabled non-`★ Must` filter must match
- if no non-`★ Must` filter is enabled, only required (`★ Must`) filters are enforced

Example: `SMOKE` only → only smoke clips. `SMOKE + WALLBANG` (both non-★) → clips matching at least one of them.

---

## Kill modifiers

### 🔵 demoparser2-powered

> Demos are pre-parsed in parallel before the batch starts. The cache persists for the session — Preview → Batch never re-parses.

| Modifier | What it captures | Source |
|---|---|---|
| 🎲 **TROIS SHOT** | Lucky kills on precision weapons — bloom too high, unscoped, or moving at shot time | `weapon_fire` accuracy |
| 🎲 **TROIS SHOT — Exclude** | Inverse: precise kills only on those same weapons | `weapon_fire` accuracy |
| 🎯 **ONE TAP** | Isolated headshot with no other shot fired within ±2s | `weapon_fire` ticks |
| 🎯🎲 **TROIS TAP** | TROIS SHOT + ONE TAP simultaneously | Combined |
| 🔫 **Spray Transfer** | ≥2 kills in one continuous burst, no trigger release (auto weapons only) | `weapon_fire` gaps |
| 🏎 **Ferrari Peek** | Moving peek that kills on a single shot then immediately resumes | `weapon_fire` velocity |
| ↩ **Flick** | Large view-angle change in the ~0.5s before the kill | `player_death` yaw |
| 🛡 **Savior** | Kill an enemy who was actively damaging a teammate | `player_hurt` events |
| 🧱 **Wallbang** | Penetrating kill through obstacle context that is not a same-shot multi-kill chain | `player_death.penetrated` + shot grouping |
| 🪂 **Airborne** | Bullet of the kill was fired while the killer was not on the ground | `player_death.attackerinair` |
| 😵 **Blind Fire** | Bullet of the kill was fired while the killer was blinded | `player_death.attackerblind` |
| 🎯 **Collateral** | Same bullet penetrates and kills multiple players in one shot chain (validated with a single nearby `weapon_fire`) | `player_death.penetrated` + shot grouping + `weapon_fire` |

> Enabling TROIS SHOT + ONE TAP simultaneously auto-converts to TROIS TAP regardless of the logic setting.

### 🟢 DB-only

> No demoparser2 required — runs directly on the CSDM kills table.

| Modifier | What it captures |
|---|---|
| 💨 **Smoke** | Kill through a smoke grenade |
| 🔭 **No-Scope** | No-scope kill (sniper only) |
| ⚡ **Victim Flashed** | Victim was blinded by a flashbang |
| 🚀 **Entry Frag** | First kill of the round |
| 🃏 **Ace** | Player eliminated all 5 opponents in a single round |
| ⚡ **Multi-Kill** | N or more kills in one round within a configurable time window |
| 💀 **BULLY** | Kill the same opponent for the Nth time in the match |
| 💰 **Eco Frag** | Pistol kill against a full-buy opponent |

---

## Clutch mode

Detects rounds where the player was the **last alive** on their team and killed all remaining opponents.

| Option | |
|---|---|
| **1v1 – 1v5** | Filter by opponent count — none checked = all sizes included |
| **Full clutch** | One clip from first kill to last (+ before/after padding) |
| **Kills only** | One clip per kill during the clutch, standard before/after padding |
| **Win only** | Only clutches where the player's team won the round |

---

## Recording systems

Two systems available: **HLAE** (recommended) and **CS** (native). The HLAE-specific panel hides automatically when CS mode is selected.

| | HLAE | CS |
|---|:---:|:---:|
| FOV override | ✅ | ❌ |
| Slow motion / Game speed | ✅ | ❌ |
| AFX streams | ✅ | ❌ |
| Hide spectator UI | ✅ | ❌ |
| CS2 effects (physics, gravity, blood) | ✅ | ✅ |
| TrueView | ✅ | ✅ |

> **CS mode warning:** CS2 replays the demo from tick 0 to reach each target tick — a clip near the end of a 40-minute match takes ~40 minutes to record. **HLAE is strongly recommended** for any batch work.

> CS2 effects use standard CS2 console commands injected through `hlaeOptions.extraArgs` (HLAE) or a managed runtime cfg `csdm_batch_runtime.cfg` (CS). If the CS2 cfg path cannot be auto-detected, set `cs2_cfg_dir` in `csdm_config.json`.

---

## UI Theme

A **UI THEME** section in the Tools tab lets you change the entire interface colour scheme in real time — no restart needed.

**Background presets:** Dark · AMOLED (pure black) · Deep Blue · White

**Accent presets:** Green · Blue · Orange · Purple · Red · Cyan · Pink · Yellow

**Custom accent:** `🎨 Custom colour…` opens the Windows native colour picker. A darker shade is derived automatically for hover/selected states. Theme persists across sessions.

---

## Shortcuts

| Key | Action |
|---|---|
| `F5` | Run batch |
| `F6` | Preview |
| `Esc` | Stop after current demo |
| `Ctrl+B` | Toggle clip badges ON/OFF |

---

## Built on top of

- [CS Demo Manager](https://cs-demo-manager.com/) by **akiver**
- [demoparser2](https://github.com/LaihoE/demoparser) by **LaihoE**
- [HLAE](https://www.advancedfx.org/)

---

<div align="center">

*Built with Claude. My code knowledge is equal to the void space separating our planet from the sun.*  
*Do as you wish with it.*

*Assisted by GPT-5.3 Codex alongside Claude.*

</div>
