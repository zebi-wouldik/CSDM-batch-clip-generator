<div align="center">

# 🎬 CSDM Batch Clips Generator

**Batch-record CS2 highlight clips directly from your CSDM PostgreSQL database.**

[![Python](https://img.shields.io/badge/python-3.10+-3b82f6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CS2](https://img.shields.io/badge/CS2-compatible-f97316?style=flat-square)](https://www.counter-strike.net/)
[![License](https://img.shields.io/badge/license-do%20what%20you%20want-8b5cf6?style=flat-square)]()

</div>

---

## What is this?

A Python GUI that plugs into [CS Demo Manager](https://cs-demo-manager.com/) and lets you batch-record highlights from your entire CS2 demo library — by player, event type, date range, weapon, and a growing list of kill modifiers (lucky shots, one-taps, clutches, spray transfers...).

Pick your filters → Preview → Run. CSDM handles the actual recording; this tool handles everything else.

---

## Requirements

| Dependency | Notes |
|---|---|
| **Python 3.10+** | |
| **FFmpeg** | Must be in `PATH` |
| **CS Demo Manager** | [cs-demo-manager.com](https://cs-demo-manager.com/) — provides the CLI and PostgreSQL DB |
| `pip install psycopg2-binary` | Required — DB connection |
| `pip install demoparser2` | Optional — needed for advanced kill modifiers (TROIS SHOT, ONE TAP, etc.) |
| `pip install pywin32` | Optional — CS2 auto-minimize on Windows |

---

## Getting started

```bash
python csdm_batch_clips_generator.py
```

Then open the **Tools** tab and connect to PostgreSQL using the same credentials as CSDM.

---

## Workflow

```
Capture tab → select player(s) + filters → F6 Preview → F5 Run
```

- **Preview** shows clip count, estimated duration, and a per-demo breakdown. Uncheck any demo to exclude it.
- **Manual mode** (after preview) lets you pick any demo from the full database, ignoring the date range.
- **Auto-tag** optionally tags processed demos in CSDM when the batch completes.

---

## Kill modifiers

### 🔵 demoparser2-powered
> Demos are pre-parsed in parallel before the batch. The cache persists for the session — Preview → Batch never re-parses.

| Modifier | What it captures |
|---|---|
| 🎲 **TROIS SHOT** | Lucky kills on precision weapons — bloom too high, unscoped, or moving at shot time |
| 🎲 **TROIS SHOT — Exclude** | Inverse: precise kills only on those same weapons |
| 🎯 **ONE TAP** | Isolated headshot with no other shot fired within ±2s |
| 🎯🎲 **TROIS TAP** | TROIS SHOT + ONE TAP simultaneously |
| 🔫 **Spray Transfer** | ≥2 kills in one continuous burst, no trigger release (auto weapons only) |
| 🏎 **Ferrari Peek** | Kill while moving above a configurable speed threshold |
| ↩ **Flick** | Large view-angle change in the ~0.5s before the kill |
| 🛡 **Sauveur** | Kill an enemy who was actively damaging a teammate |

> Modifiers stack with AND logic. Enabling TROIS SHOT + ONE TAP simultaneously auto-converts to TROIS TAP.

---

### 🟢 DB-only
> No demoparser2 required — runs directly on the CSDM kills table.

| Modifier | What it captures |
|---|---|
| 🚀 **Entry Frag** | First kill of the round |
| 🃏 **Ace** | Rounds where the player eliminated all 5 opponents alone |
| ⚡ **Multi-Kill** | N or more kills in one round within a configurable time window |
| 💀 **BULLY** | Kill the same opponent for the Nth time in the match |
| 💰 **Eco Frag** | Pistol kill against a full-buy opponent |
| 😵 **Blind Fire** | Killer was blinded by a flashbang at shot time |

---

## Clutch mode

Detects rounds where the player was the **last alive** on their team and killed all remaining opponents.

| Option | Description |
|---|---|
| **1v1 – 1v5** | Filter by opponent count. None checked = all included. |
| **Full clutch** | One clip from first kill to last kill (+ before/after padding) |
| **Per kill** | One clip per kill, standard padding |
| **Win only** | Only clutches where the player's team won the round |

---

## Recording systems

| System | Notes |
|---|---|
| ⚡ **HLAE** *(recommended)* | Full options: FOV, slow-motion, AFX streams, physics, gravity |
| 🎮 **CS** *(native)* | Simpler setup, fewer options |

The HLAE panel hides automatically when CS mode is selected. CS2 physics effects (ragdoll gravity, blood, dynamic lighting) are HLAE-only for now.

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
