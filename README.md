# CSDM Batch Clips Generator — v93

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
| **TROIS SHOT** | Lucky kills on precision weapons (bloom, unscoped, or moving at shot time) |
| **Exclude** | Inverse — precise kills only |
| **ONE TAP** | Single headshot with no other shot within ±2s |
| **TROIS TAP** | TROIS SHOT ∩ ONE TAP |
| **Spray Transfer** | ≥2 kills in one continuous burst (auto weapons only) |
| **Ferrari Peek** | Kill while moving above a speed threshold |
| **Flick** | Large view-angle change in the ~0.5s before the kill |
| **Sauveur** | Kill an enemy who was actively damaging a teammate |

Modifiers stack (AND logic). TROIS SHOT + ONE TAP checked simultaneously auto-converts to TROIS TAP.

---

## Kill modifiers (DB only)

No demoparser2 required — runs directly on the CSDM kills table.

| Modifier | Keeps |
|---|---|
| **Entry Frag** | First kill of the round |
| **Ace** | Rounds where the player eliminated all 5 opponents |
| **Multi-Kill** | N or more kills in one round within a time window |
| **BULLY** | Kill the same opponent for the Nth time in the match |
| **Eco Frag** | Pistol kill against a full-buy opponent |
| **Blind Fire** | Player was blinded at shot time |

---

## Clutch

Detects rounds where the player was the last alive on their team and killed the remaining opponents.

- **1v1–1v5**: filter by number of opponents faced (none checked = all included)
- **Full clutch**: one clip from the first kill to the last (+ before/after padding)
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
