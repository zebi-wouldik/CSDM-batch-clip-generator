# CSDM-batch-clip-generator
Tool for CS2 clips making.
# CSDM Batch Sequence Generator

A desktop GUI tool for **batch-recording CS2 highlight clips** from demo files, built on top of [CS Demo Manager (CSDM)](https://cs-demo-manager.com/) and HLAE.

![Python 3.x](https://img.shields.io/badge/python-3.x-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

You have a PostgreSQL database of CS2 kills from CSDM. This tool lets you:

- **Query** that database for your kills (by player, weapon, event type, date range, tags)
- **Filter** them with smart kill modifiers (lucky shot detection, one-tap isolation, headshots only…)
- **Batch-record** all matching sequences as video clips via CSDM CLI + HLAE
- **Preview** what will be recorded before committing — clip count, total duration, per-demo breakdown
- **Assemble** all clips into a final cut with FFmpeg after the batch

---

## Features

### Kill modifiers (demoparser2-powered)
Powered by [`demoparser2`](https://github.com/LaihoE/demoparser) — reads `accuracy_penalty`, `is_scoped`, and `velocity` directly from the demo at the exact shot tick.

| Modifier | Description |
|---|---|
| **LUCKY SHOT** | Keeps only lucky kills: high bloom, unscoped, or moving at shot time. Eligible weapons: Deagle, R8, AWP, SCAR-20, G3SG1, SSG 08 |
| **Exclude** | Inverse of LUCKY SHOT — keeps only precise kills on eligible weapons |
| **ONE TAP** | Isolated single-shot headshots: no shot from same player+weapon in ±2s window |
| **LUCKY TAP** | Intersection of LUCKY SHOT ∩ ONE TAP — lucky AND isolated headshot |

Modifiers **stack**: you can combine **Exclude + ONE TAP** to get precise, isolated headshots. LUCKY TAP is mutually exclusive with everything (it already is an intersection).

### Perspectives
| Mode | Behavior |
|---|---|
| **POV Killer** | Camera locked on the killer for the entire clip |
| **POV Victim** | Camera locked on the victim for the entire clip |
| **Both** | Camera on the killer from the start, switches to the victim `N` seconds before the kill. The sequence is automatically extended by `N` seconds so the killer phase is always complete |

The **Switch delay** slider (0–10s, visible in Both mode) controls how many seconds before the kill the camera switches. This value is added to BEFORE seconds — `before=3s` + `switch=2s` → 5s before kill total.

### Tag system
- Create, rename, and delete named tags in your CSDM database
- **Auto-tag on export**: automatically tag each demo after a successful recording
- **Tag range**: find the earliest and latest tagged demo to set date filters automatically
- **By config**: preview exactly which demos match your current player+events+weapons+date config and are already tagged

### Other
- Multi-player support (track multiple Steam IDs simultaneously)
- Preset system (save/load full configs or partial configs by category)
- Structured resolution selector (720p/1080p/1440p/4K × aspect ratio, or free custom)
- Full HLAE options: FOV, slow-motion, AFX streams, physics overrides, workshop downloads
- FFmpeg advanced params (custom input/output args, multiple codecs/containers)
- Output folder management: separate folders for raw clips, concatenated, and final assembled
- Retry logic with configurable delay and attempt count
- CS2 window mode injection (windowed, borderless, fullscreen)
- Auto-minimize CS2 on launch (requires `pywin32`)

---

## Requirements

| Dependency | Required | Notes |
|---|---|---|
| Python 3.10+ | ✅ | |
| [CSDM](https://cs-demo-manager.com/) | ✅ | CLI must be accessible |
| [FFmpeg](https://ffmpeg.org/) | ✅ | Must be in PATH or configured |
| PostgreSQL + psycopg2 | ✅ | `pip install psycopg2-binary` |
| [demoparser2](https://github.com/LaihoE/demoparser) | Optional | Required for LUCKY SHOT / ONE TAP / LUCKY TAP modifiers — `pip install demoparser2` |
| pywin32 | Optional | Required for CS2 auto-minimize — `pip install pywin32` |

---

## Installation

```bash
git clone https://github.com/youruser/csdm-batch.git
cd csdm-batch
pip install psycopg2-binary demoparser2 pywin32
python make_video.py
```

---

## Quick start

1. **Connect** to your PostgreSQL database in the Tools tab (host, port, user, password, database name)
2. **Select a player** — search by Steam ID or name, register them with ★
3. **Choose events** — Kills, Deaths, and/or Rounds
4. **Apply filters** — weapon filter, date range, kill modifiers, headshots only, teamkills mode
5. **Preview** (F6) — see exactly which demos match, clip count, and total duration
6. **Set output folder** — raw clips folder in the Tools tab
7. **Run** (F5) — CSDM records each sequence; FFmpeg encodes them

---

## Configuration

All settings are saved automatically to `config.json` in the script directory. Use the **Presets** section in the Tools tab to save and restore named configurations (full config, or per-category: Player / Video / Timing).

---

## Kill modifier thresholds

`accuracy_penalty` in demoparser2 = Source2 radians. Real observed range: 0.004–0.050.

| Weapon | Lucky if… |
|---|---|
| Deagle, R8 | `acc > 0.015` (not a clean stationary shot) |
| AWP, SSG 08 | `is_scoped == False` OR `acc > 0.010` |
| SCAR-20, G3SG1 | `velocity > 100 u/s` OR `is_scoped == False` OR `acc > 0.010` |

---

## Acknowledgements

- [CS Demo Manager](https://cs-demo-manager.com/) by akiver — the CLI and HLAE integration this tool wraps
- [demoparser2](https://github.com/LaihoE/demoparser) by LaihoE — fast Rust-powered CS2 demo parsing
- [HLAE](https://www.advancedfx.org/) — the recording engine
