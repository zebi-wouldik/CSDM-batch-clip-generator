<div align="center">

# 🎬 CSDM Batch Clips Generator

**Batch-record CS2 highlight clips directly from your CSDM PostgreSQL database.**

[![Python](https://img.shields.io/badge/python-3.10+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CS2](https://img.shields.io/badge/CS2-compatible-f97316?style=flat-square)](https://www.counter-strike.net/)
[![License](https://img.shields.io/badge/license-do%20what%20you%20want-8b5cf6?style=flat-square)]()

</div>

---

A Python GUI that plugs into [CS Demo Manager](https://cs-demo-manager.com/) and lets you batch-record highlights from your entire CS2 demo library — by player, event type, date range, weapon, and a growing list of kill modifiers (lucky shots, one-taps, clutches, spray transfers...).

Pick your filters → Preview → Run. CSDM handles the actual recording; this tool handles everything else.

---

## Requirements

| Dependency | |
|---|---|
| **Python 3.10+** | |
| **FFmpeg** | Must be in `PATH` |
| **CS Demo Manager** | [cs-demo-manager.com](https://cs-demo-manager.com/) — provides the CLI and PostgreSQL DB |
| `pip install psycopg2-binary` | Required |
| `pip install demoparser2` | Optional — needed for advanced kill modifiers |
| `pip install pywin32` | Optional — CS2 auto-minimize on Windows |

---

## Getting started

```bash
python csdm_batch_clips_generator.py
```

Open the **Tools** tab → connect to PostgreSQL with the same credentials as CSDM.

---

## Workflow

```
Capture tab  →  PLAYER + CAPTURE + KILL FILTERS  →  F6 Preview  →  F5 Run
```

- **Preview** shows clip count, total duration, and a per-demo breakdown — uncheck any demo to exclude it
- **Manual mode** lets you pick any demo from the full database regardless of date range
- **Auto-tag** tags processed demos in CSDM when the batch completes. Tags are **rolled back automatically** if the batch is stopped or killed mid-run.

---

## ⚠ CS recording mode

In **CS** mode, CS2 replays the demo from tick 0 to reach each target tick — a clip near the end of a 40-minute match takes ~40 minutes to record. **HLAE is strongly recommended** for any batch work.

---

## Kill modifiers

### 🔵 demoparser2-powered

> Demos are pre-parsed in parallel before the batch starts. The cache persists for the session — Preview → Batch never re-parses.

| Modifier | What it captures |
|---|---|
| 🎲 **TROIS SHOT** | Lucky kills on precision weapons — bloom too high, unscoped, or moving at shot time |
| 🎲 **TROIS SHOT — Exclude** | Inverse: precise kills only on those same weapons |
| 🎯 **ONE TAP** | Isolated headshot with no other shot fired within ±2s |
| 🎯🎲 **TROIS TAP** | TROIS SHOT + ONE TAP simultaneously |
| 🔫 **Spray Transfer** | ≥2 kills in one continuous burst, no trigger release (auto weapons only) |
| 🏎 **Ferrari Peek** | Moving peek that kills on a single shot then immediately resumes — one-shot condition optional |
| ↩ **Flick** | Large view-angle change in the ~0.5s before the kill |
| 🛡 **Savior** | Kill an enemy who was actively damaging a teammate |

> Modifiers stack with AND logic. Enabling TROIS SHOT + ONE TAP simultaneously auto-converts to TROIS TAP.

### 🟢 DB-only

> No demoparser2 required — runs directly on the CSDM kills table.

| Modifier | What it captures |
|---|---|
| 🚀 **Entry Frag** | First kill of the round |
| 🃏 **Ace** | Player eliminated all 5 opponents in a single round |
| ⚡ **Multi-Kill** | N or more kills in one round within a configurable time window |
| 💀 **BULLY** | Kill the same opponent for the Nth time in the match |
| 💰 **Eco Frag** | Pistol kill against a full-buy opponent |
| 😵 **Blind Fire** | Killer was blinded by a flashbang at shot time |

---

## Clutch mode

Detects rounds where the player was the **last alive** on their team and killed all remaining opponents.

| Option | |
|---|---|
| **1v1 – 1v5** | Filter by opponent count — none checked = all sizes included |
| **Full clutch** | One clip from first kill to last (+ before/after padding) |
| **Per kill** | One clip per kill, standard padding |
| **Win only** | Only clutches where the player's team won the round |

---

## Recording systems

Two systems available: **HLAE** and **CS** (native). The HLAE-specific panel hides automatically when CS mode is selected.

| | HLAE | CS |
|---|:---:|:---:|
| FOV override | ✅ | ❌ |
| Slow motion | ✅ | ❌ |
| AFX streams | ✅ | ❌ |
| CS2 effects (physics, gravity, blood) | ✅ | ✅ |

---

## Shortcuts

| Key | Action |
|---|---|
| `F5` | Run batch |
| `F6` | Preview |
| `Esc` | Stop after current demo |

---

## Built on top of

- [CS Demo Manager](https://cs-demo-manager.com/) by **akiver**
- [demoparser2](https://github.com/LaihoE/demoparser) by **LaihoE**
- [HLAE](https://www.advancedfx.org/)

---

<div align="center">

*Built with Claude. My code knowledge is equal to the void space separating our planet from the sun.*  
*Do as you wish with it.*

</div>
