# CSDM Batch Clips Generator

A desktop GUI tool for **batch-recording CS2 highlight clips** from demo files, built on top of [CS Demo Manager (CSDM)](https://cs-demo-manager.com/) and optionally HLAE.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-v78-orange)

---

## What it does

You have a PostgreSQL database of CS2 kills from CSDM. This tool lets you:

- **Query** that database for kills/deaths/rounds (by player, weapon, event type, date range, tags)
- **Filter** them with smart kill modifiers (lucky shot detection, one-tap isolation, headshots only…)
- **Preview** what will be recorded before committing — clip count, total duration, per-demo breakdown
- **Batch-record** all matching sequences as video clips via CSDM CLI (HLAE or CS recording system)
- **Assemble** all clips into a final cut with FFmpeg after the batch

---

## Features

### Kill modifiers (demoparser2-powered)
Powered by [`demoparser2`](https://github.com/LaihoE/demoparser) — reads `accuracy_penalty`, `is_scoped`, and `velocity` directly from the demo at the exact shot tick. Demos are pre-parsed in parallel (1–8 threads) and cached for the session — switching from Preview to Batch never re-parses.

| Modifier | Description |
|---|---|
| **TROIS SHOT** | Keeps only lucky kills: high bloom, unscoped, or moving at shot time. Eligible weapons: Deagle, R8, AWP, SCAR-20, G3SG1, SSG 08 |
| **Exclude** | Inverse of TROIS SHOT — keeps only precise kills on eligible weapons |
| **ONE TAP** | Isolated single-shot headshots: exactly one shot from the same player+weapon in a ±2s window |
| **TROIS TAP** | Intersection of TROIS SHOT ∩ ONE TAP — lucky AND isolated headshot |

Modifiers **stack** with AND logic: combining **Exclude + ONE TAP** gives precise, isolated headshots. TROIS TAP is mutually exclusive with all other modifiers (it is already their intersection).

Checking TROIS SHOT + ONE TAP simultaneously auto-converts to TROIS TAP.

### Recording systems

| System | Behavior |
|---|---|
| **HLAE** *(recommended)* | Injects into CS2 via HLAE. Supports FOV, slow-motion, physics overrides, AFX streams, window mode, and all advanced options |
| **CS** | Native CSDM recording without HLAE. CS2 plays the demo interactively. No HLAE options apply |

The HLAE options panel is automatically hidden when CS is selected.

### Perspectives
| Mode | Behavior |
|---|---|
| **POV Killer** | Camera locked on the killer for the entire clip |
| **POV Victim** | Camera locked on the victim for the entire clip |
| **Both** | Camera on the killer from the start, switches to the victim `N` seconds before the kill |

The **Switch delay** slider (visible in Both mode only) controls how many seconds before the kill the camera switches. It is added on top of the BEFORE value — `before=3s` + `switch=2s` → clip starts 5s before the kill.

### Tag system
- Create, rename, and delete named tags in your CSDM database
- **Auto-tag on export**: automatically tag each demo after a successful recording
- Multi-tag support: select multiple tags simultaneously
- **Tag range**: find the earliest and latest tagged demo to set date filters automatically
- **By config**: preview exactly which demos match your current config and are already tagged
- Active tag selection is saved in `csdm_config.json` and restored on next launch

### Other
- Multi-player support: track multiple Steam IDs simultaneously, all their events merged
- Preset system: save/load full configs or partial configs by category (Player / Video / Timing)
- Structured resolution selector (720p/1080p/1440p/4K × aspect ratio, or free custom dimensions)
- Full HLAE options: FOV, slow-motion, AFX streams, physics overrides, workshop map downloads, extra CLI args
- FFmpeg: custom input/output params, multiple codecs (H.264, H.265, AV1, ProRes…) and containers
- Output folder management: separate folders for raw clips, concatenated clips, and final assembled file
- Final assembly: concatenate all batch clips into one file with FFmpeg after the batch, with optional source deletion
- Retry logic: configurable attempt count and delay between retries
- CS2 window mode injection (None / Fullscreen / Windowed / Borderless) — HLAE only
- Auto-minimize CS2 on launch (requires `pywin32`)
- Clip recording order: chronological or random

---

## Requirements

| Dependency | Required | Install |
|---|---|---|
| Python 3.10+ | ✅ | [python.org](https://python.org) |
| [CSDM](https://cs-demo-manager.com/) | ✅ | CLI (`csdm.CMD`) must be accessible |
| [FFmpeg](https://ffmpeg.org/) | ✅ | Must be in PATH or WinGet |
| PostgreSQL + psycopg2 | ✅ | `pip install psycopg2-binary` |
| [demoparser2](https://github.com/LaihoE/demoparser) | Optional | `pip install demoparser2` — required for TROIS SHOT / ONE TAP / TROIS TAP |
| pywin32 | Optional | `pip install pywin32` — required for CS2 auto-minimize |

---

## Installation

```bash
git clone https://github.com/youruser/csdm-batch.git
cd csdm-batch
pip install psycopg2-binary demoparser2 pywin32
python csdm_batch_clips_generator.py
```

---

## Quick start

1. **Connect** — Tools tab → PostgreSQL section → fill in host/port/user/password/database → Test & Reload
2. **Select a player** — Capture tab → search by Steam ID or name → register with ★ → click to enable
3. **Choose events** — Kills, Deaths, and/or Rounds
4. **Apply filters** — weapon filter, date range, kill modifiers, headshots only, teamkills mode
5. **Preview** (`F6`) — see exactly which demos match, clip count, and total duration before recording
6. **Set output folder** — Tools tab → Output Folders section
7. **Run** (`F5`) — CSDM records each sequence; FFmpeg encodes them

`Esc` stops the batch after the current demo finishes. The ⛔ KILL button terminates immediately.

---

## Configuration

All settings save automatically to `csdm_config.json` in the script directory.

Use the **Presets** section in the Tools tab to save and restore named configurations:

| Preset type | What it saves |
|---|---|
| Full | Everything |
| Player | Player, events, weapons, dates, modifiers, perspective |
| Video | Encoder, codec, resolution, framerate, HLAE options |
| Timing | Before/after seconds, retries, delays |

---

## Kill modifier thresholds

`accuracy_penalty` in demoparser2 = Source2 radians. Observed range: 0.004 (clean stationary) → 0.050 (spam/moving).

| Weapon | Lucky if… |
|---|---|
| Deagle, R8 | `acc > 0.015` |
| AWP, SSG 08 | `is_scoped == False` OR `acc > 0.010` |
| SCAR-20, G3SG1 | `velocity > 100 u/s` OR `is_scoped == False` OR `acc > 0.010` |

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `F5` | Run batch |
| `F6` | Preview |
| `Esc` | Graceful stop (finishes current demo) |

---

## Acknowledgements

- [CS Demo Manager](https://cs-demo-manager.com/) by akiver — the CLI and HLAE integration this tool wraps
- [demoparser2](https://github.com/LaihoE/demoparser) by LaihoE — fast Rust-powered CS2 demo parsing
- [HLAE](https://www.advancedfx.org/) — the recording engine
- Built with Claude Sonnet 4.6. My code knowledge is equal to the void space separating our planet from the sun. The description is also made by Claude since it knows the script better than me. Do as you wish with it.
