# CSDM Batch Clips Generator — v91

Connects to your CSDM PostgreSQL database and batch-records CS2 highlight clips via the CSDM CLI.

---

## Requirements

- Python 3.10+, FFmpeg in PATH
- `pip install psycopg2-binary` (required)
- `pip install demoparser2` (optional — needed for TROIS SHOT / ONE TAP / TROIS TAP / Spray Transfer)
- `pip install pywin32` (optional — CS2 auto-minimize)

---

## Launch

```
python csdm_batch_clips_generator.py
```

Connect in the **Tools** tab (PostgreSQL section). Same credentials as CSDM.

---

## Workflow

**Capture tab** — select player(s), event type(s), date range, filters → **Preview (F6)** → **Run (F5)**

The preview shows clip count, total duration, and a per-demo list. You can uncheck demos to exclude them. After preview, **Manual mode** lets you pick any demo from the full database regardless of date range.

---

## Kill modifiers (demoparser2)

Demos are pre-parsed in parallel before the batch. The cache persists for the session — Preview → Batch never re-parses.

| Modifier | Keeps |
|---|---|
| **TROIS SHOT** | Lucky kills: bloom above threshold, unscoped, or moving at shot time |
| **Exclude** | Inverse — precise kills only |
| **ONE TAP** | One shot fired in a ±2s window around the kill, headshot |
| **TROIS TAP** | TROIS SHOT ∩ ONE TAP |
| **Spray Transfer** | ≥2 kills in one continuous burst (auto weapons: AK, M4, SMGs, M249, Negev, CZ75) |

Modifiers stack (AND logic). TROIS SHOT + ONE TAP checked simultaneously auto-converts to TROIS TAP.

**TROIS SHOT threshold note**: for AWP/SSG08, a scoped shot with `accuracy_penalty > 0.010` is also caught — this covers firing before the scope sway settles, which CS2 treats as imprecise regardless of whether the player is aiming.

---

## Clutch

Detects rounds where the player was the last alive on their team and killed the remaining opponents.

- **Min 1v / Max 1v**: filter by number of opponents faced
- **Full clutch**: one clip from the first kill to the last (+ before/after padding) — not the whole round
- **Per kill**: standard individual clips

---

## Recording

Two systems: **HLAE** (recommended, full options) and **CS** (native). The HLAE panel hides automatically when CS is selected. CS2 Effects (physics, gravity) are injected in HLAE mode; CS mode does not yet support them.

---

## Shortcuts

| Key | Action |
|---|---|
| F5 | Run |
| F6 | Preview |
| Esc | Stop after current demo |

---

## Built on top of

- [CS Demo Manager](https://cs-demo-manager.com/) by akiver
- [demoparser2](https://github.com/LaihoE/demoparser) by LaihoE
- [HLAE](https://www.advancedfx.org/)
- Built with Claude Sonnet 4.6. My code knowledge is equal to the void space separating our planet from the sun. The description is also made by Claude since it knows the script better than me. Do as you wish with it.
