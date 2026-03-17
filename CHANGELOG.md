# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.  
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v74]
### Added
- **TROIS TAP auto-toggle**: checking both TROIS SHOT + ONE TAP simultaneously auto-enables TROIS TAP and clears the two individual modifiers. Unchecking TROIS TAP restores both. Fully symmetric and bidirectional.
- **DP2 threads** slider in Tools → Performance (1–8, default 2): parallel demo pre-parsing via `ThreadPoolExecutor` before the main batch/preview loop. Logs `⚡ Pre-parsing N demo(s) with X thread(s)…` / `✓ Pre-parse done`.
- Per-demo parse cache (`_dp2_cache`): each `.dem` parsed at most once per run, even when TROIS TAP chains both filters. Reset at the start of every batch and preview run.

### Changed
- **UI fully translated to English** — all remaining French strings:
  - Calendar month names: Janvier → January, Fevrier → February, etc.
  - Weapon categories: Pistolets → Pistols, Fusils → Rifles, Lourdes → Heavy, Couteaux → Knives, Grenades & Utilitaires → Grenades & Utility, Divers → Misc, Autres → Other
  - In-game labels: Physique ragdolls → Ragdoll physics, Sang sur les murs → Blood on walls
  - File dialog filters: Fichier texte → Text file, Tous → All files
  - Tags tab: Recherche → Search
  - Preset section: Nom → Name, sauvegarde → saved, charge → loaded, Donne un nom → Enter a name
  - Dialogs: Supprimer tag → Delete tag, Annuler → Cancel
  - Color picker: Couleurs rapides → Quick colors, Apercu → Preview
  - Error logs: Erreur → Error, CLI introuvable → CLI not found, Schema inconnu → Unknown schema, introuvable → not found, Table de jonction introuvable → Junction table not found, Modificateurs introuvables → Modifiers not found, Col demo introuvable → Demo path column not found
  - TAGS/config logs: Erreur BDD → DB error, Erreur config → Config error
  - Tag log: Tag cree → Tag created
- **Log labels corrected**: TROIS SHOT / TROIS TAP filters no longer log "lucky" / "lucky tap" — now correctly show "TROIS SHOT" / "TROIS TAP"
- `cs2_window_mode` default value: `"aucun"` → `"none"` (internal value, not visible in UI)
- `_WEAPON_CATEGORIES` key aligned: `"Grenades & Utilities"` → `"Grenades & Utility"` to match WEAPON_ICONS

### Removed
- **Skip Intro CS2** option removed: `+novid` / `skipIntro` has no effect in CS2. Removed from DEFAULT_CONFIG, bool_keys, PRESET_KEYS, UI checkbox, and JSON build (`hlae_options["skipIntro"]`).

### Fixed
- **NameError `evt` not defined** (v73 bugfix carried over): loop variable `events` shadowing the parameter in `_trois_shot_filter`, `_no_trois_shot_filter`, `_one_tap_filter` — all corrected to `for evt in events`.

### Performance
- `_trois_shot_filter`: linear `_is_lucky` scan replaced by bisect index `{(sid, wpn_suffix) → [(tick, acc, scoped, vel)]}` — O(log n) per kill instead of O(n)
- `itertuples()` replaced by `to_numpy()` in both `_trois_shot_filter` and `_one_tap_filter` — 5–10× faster DataFrame iteration on large demos

---

## [v73]
### Added
- **DP2 threads** slider in Tools → Performance (1–8, default 2): parallel demo pre-parsing via `ThreadPoolExecutor` before the main batch loop
- Per-demo parse cache (`_dp2_cache`): each `.dem` is parsed at most once per run, even when TROIS TAP chains both TROIS SHOT and ONE TAP filters

### Fixed
- **NameError `evt` not defined** in `_trois_shot_filter`, `_no_trois_shot_filter`, `_one_tap_filter`: loop variable was renamed `events` during translation, shadowing the parameter while the body still referenced `evt`

### Performance
- `_trois_shot_filter`: linear `_is_lucky` scan replaced by bisect index `{(sid, wpn_suffix) → [(tick, acc, scoped, vel)]}` — O(log n) per kill instead of O(n)
- `itertuples()` replaced by `to_numpy()` in both `_trois_shot_filter` and `_one_tap_filter` — 5–10× faster DataFrame iteration on large demos
- Pre-parse step logs progress (`⚡ Pre-parsing N demo(s) with X thread(s)…` / `✓ Pre-parse done`) for both batch and preview runs

---

## [v72]
### Fixed
- "Both" perspective: `victim_pre_s` was not counted in clip duration.  
  `_effective_before(cfg)` now returns `before + victim_pre_s` in Both mode, used at all `_build_sequences` call sites (preview, batch, summary). Sequence starts `before + victim_pre_s` seconds before the kill so the killer phase is complete from the first frame.
- Removed `victim_pre_s ≤ before` clamping in `_build_cams_both` (no longer needed).

---

## [v71]
### Changed
- "Exclude lucky" checkbox renamed to "Exclude" (under LUCKY SHOT section)
- Cumulative modifiers: `no_lucky_shot` + `one_tap` now apply sequentially (AND logic). `elif` chains replaced with independent `if` blocks in `_run_batch`, `_dry_run`, and `_redo`. Only `lucky_tap` stays exclusive.
- UI toggles: `no_lucky_shot` and `one_tap` no longer mutually exclusive. Only `lucky_shot ↔ no_lucky_shot` and `lucky_tap ↔ all` remain exclusive.
- Preview summary now shows all actually active modifiers instead of hiding those skipped by `elif` chains.

---

## [v70]
### Changed
- **POV Victim** simplified: camera fixed on the victim of the first kill throughout the clip (no switch, no transition).
- **"Both"** takes over the killer→victim logic from ex-POV Victim v69: camera follows killer from start, switches to victim at `kill_tick − victim_pre_s`. "Switch delay" slider now only visible in Both mode.
- "Switch delay" additive with BEFORE seconds: `before=3s` + `victim_pre_s=2s` → sequence starts 5s before kill; killer phase is complete.

---

## [v69]
### Added
- `APP_VERSION` constant centralizes version string — window title and header label update automatically.

### Changed
- **POV Victim rework**:
  - New parameter "Killer seconds before switch" (`victim_pre_s`, default 2s)
  - Camera only follows events where `killer_sid` belongs to active players — no more jumps to random players in merged multi-kill sequences
  - "Both" mode: transition at exact first kill tick, not arbitrary midpoint of `cam_ticks`
  - "Switch delay" slider visible only when perspective = victim or both

---

## [v68]
### Added
- New modifier **NO LUCKY SHOT** (`kill_mod_no_lucky_shot`): excludes lucky kills — exact inverse of the TROIS SHOT filter. Shown under "Enable" in the TROIS SHOT section.
- New modifier **LUCKY TAP** (`kill_mod_lucky_tap`): intersection TROIS SHOT ∩ ONE TAP — lucky AND isolated headshot kill. Forces HS only. Eligible weapons = TROIS SHOT set. Integrated in preview, `_redo`, `_run_batch`, summary.

### Fixed
- "Free dimensions": definition radio buttons now properly disabled when the checkbox is ticked (stored in `self._def_radios`).

### Changed
- Minimize watcher simplified: Phase 2 (looping re-minimization for 20s) removed. CS2 is minimized once at launch, then the thread stops.

---

## [v67] — 2025-05 *(applied as external patch)*
### Removed
- `stop_guard_event` — no longer needed after Phase 2 removal.

---

## [v66]
### Added
- New modifier **ONE TAP** (demoparser2):
  - Mandatory headshot (forced in DB + locks "HS only")
  - No shot from same player+weapon in the 2s before the shot (silence)
  - No shot from same player+weapon in the 2s after the shot (no follow-up)
  - Detection via bisect on index `(sid, weapon)` → O(log n)
  - Integrated in preview, `_redo`, per-demo `_run_batch`

### Changed
- Tickrate removed from UI (CS2 = fixed 64 ticks); value 64 kept internally.

---

## [v65]
### Fixed
- **LUCKY SHOT thresholds recalibrated**: `accuracy_penalty` in demoparser2 = Source2 radians, real range 0.004–0.050. Old thresholds (0.15–0.30) were unreachable → 0 lucky shots systematically. New: Deagle/R8 > 0.015, snipers > 0.010 (+ scope/vel).
- Removed dead duplicate `filtered` loop (refactoring artifact).

### Added
- Temporary per-kill calibration log: `acc` / `scoped` / `vel` / verdict.

---

## [v64]
### Fixed
- **LUCKY SHOT — 3 bugs** diagnosed via debug logs:
  1. demoparser2 prefixes all requested player fields with `user_` (e.g. `user_accuracy_penalty`). Fixed with dynamic `_col()` resolver.
  2. Match window too small (30 ticks / ~0.23s). Extended to 128 ticks (~1s).
  3. Matching logic: `wp_suffix in wp` instead of fragile `endswith` + double fallback.
- Removed `[DIAG]` logs.

---

## [v63]
### Fixed
- Checking LUCKY SHOT now also unchecks the weapon category checkbox (not just individual weapons).
- Preview (F6 / Preview button) now applies TROIS SHOT filter via demoparser2 in a background thread before showing results — clip count reflects actual lucky kills. Same for preview re-triggered after cancel (already-tagged demos).

### Added
- Indicator `🎲 LUCKY SHOT` visible in preview summary line.

---

## [v62]
### Added
- New modifier **LUCKY SHOT**: lucky kills on precision weapons.
  - Eligible: Deagle, R8, AWP, SCAR-20, G3SG1, SSG 08
  - Detection via demoparser2 (Rust): `accuracy_penalty`, `is_scoped`, `velocity` at exact shot tick
  - Per-weapon thresholds: Deagle/R8 → bloom > 0.30; AWP/SSG → unscoped or bloom > 0.15; SCAR-20/G3SG1 → speed > 100 u/s or unscoped or bloom > 0.15
  - Enable → automatically locks ineligible weapons in filter
  - Requires: `pip install demoparser2`

---

## [v61]
### Fixed
- "Minimize on launch": CS2 briefly appeared on screen.
  - Polling reduced 500ms → 100ms to catch CS2 on its first frames
  - 20s guard phase after first hit: re-minimize if CS2 comes to foreground during map loading
  - Timeout extended to 60s (was 45s)

---

## [v60]
### Changed
- **Resolution & Framerate** section reworked:
  - Definition via radio buttons (720p / 1080p / 1440p / 4K)
  - Aspect ratio selector (16:9 / 4:3 / 21:9 / 16:10 / 1:1) conditional on definition
  - "Custom" checkbox disables both selectors and enables free width × height fields
  - `width`/`height` auto-calculated from (definition × ratio) or entered manually

---

## [v59]
### Fixed
- Modifiers not found in DB: if ALL absent → returns `{}` with error instead of returning all clips unfiltered. If partially absent → warning + apply remaining modifiers only.

---

## [v58]
### Added
- Tags tab — new **TAG RANGE** section: Calculate range, Apply start, Apply end, Full range, After range.

### Changed
- OPERATIONS section restructured: Search / Actions clearly separated.

---

## [v57]
### Fixed
- 📅 now uses the same config ∩ tags intersection as "By config" — no more divergence between the two counts.

---

## [v56]
### Added
- "By config": config ∩ DB tags intersection (demos already tagged in the current period).

### Changed
- 📅 applies `date_from` directly without intermediate button.

### Removed
- `_tag_suggest_btn` widget and `_tag_apply_suggest_date`.

---

## [v55]
### Fixed
- Extra args (`spec_cmd` + `window_mode`) were overwritten before injection.

### Added
- Enhanced logging: prefixes `[PREVIEW/TAGS/config/tag/📅]`, active weapons by category, output folder, auto-tags in preview.

---

## [v54]
### Added
- Separate output folders: raw clips, concatenated, assembled.
- Warning tooltip on Concatenate when Assemble is active.

### Changed
- Concatenate sequences disabled if Delete clips is active.
- `_collect_config` syncs `output_dir ← output_dir_clips` for compat.

---

## [v53]
### Fixed
- `noSpectatorUi`: now injects `hideSpectatorUi` + extraArgs `+cl_draw_only_deathnotices 1` for all CSDM version compatibility.

### Changed
- Tags tab moved between Capture and Video.
- "By config" now requires a selected tag.
- Grey colors (MUTED/DESC_COLOR) brightened for contrast on dark background.
- Automatic versioning: each change increments the version.

---

## [v47]
### Added
- "🔍 By config" restored: full preview (player + events + weapons + dates) in Tags listbox, directly taggable.
- "📅" separated: finds the most recent demo among selected tags, proposes setting `date_from` to the next day.
- `_tag_search_last_tagged` uses selected tags (multi-tag).

---

## [v46]
### Changed
- Moved "Concatenate sequences" to FINAL ASSEMBLY section.

---

## [v45]
### Changed
- Tags operations output to console (removed inline status labels).
- Window size: 1600×900.
- Tags tab width fixed.

---

## [v44]
### Added
- Unicode weapon icons per category (`WEAPON_ICONS`).
- Hover tooltips (`Tooltip` class + `add_tip`) replace inline `desc_label`s.

### Changed
- X-Ray moved to IN-GAME OPTIONS (Video tab).
- AUTO TAG moved to Tags tab, multi-tags via active selection.
- `noSpectatorUi` → `hideSpectatorUi` in hlaeOptions.

---

## [v43]
### Added
- CS2 window mode (None / Fullscreen / Windowed / Borderless) in RESOLUTION & FRAMERATE, injected in extraArgs.
- Option "Minimize CS2 on launch" (requires optional pywin32).
- `_start_cs2_minimize_watcher()`: CS2 window monitoring thread.

---

## [v42]
### Added
- "Since last tag" → button "📅 By config" + separate "📅" button.
- `_show_preview()` extracted as reusable method.

### Fixed
- Already-tagged demos dialog: Yes = include, No = ignore, Cancel = filtered preview.

### Changed
- Startup without `iconify()`.

---

## [v41] *(UI compact refactor)*
### Changed
- Capture tab condensed: options on horizontal rows, Timing + Order merged, Date filter on a single row, reduced padding.
- Tags tab condensed: buttons on a single bar, listbox height = 7.

### Added
- `_tag_search_last_tagged`: finds tagged demos, proposes `date_from + 1d`.
