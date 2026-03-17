# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.  
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v77]
### Changed
- **demoparser2 architecture fully refactored** — single point of entry, partial persistent cache:

  **`_dp2_parse_demo(demo_path)`** — new core method, the only place in the codebase that calls `DemoParser`. Parses `weapon_fire` once per demo with all needed player fields (`accuracy_penalty`, `is_scoped`, `velocity_X/Y`, `player_steamid`). Builds and stores two derived indexes under `_dp2_cache[demo_path]`:
    - `"fire_detail"`: `{(sid, wpn_suffix) → [(tick, acc, scoped, vel), …]}` — for TROIS SHOT / NO TROIS SHOT
    - `"fire_ticks"`: `{(sid, wpn_suffix) → [tick, …]}` — for ONE TAP / TROIS TAP (derived from `fire_detail`, no second parse)

    **To add a future filter on a new event type**: add a `parser.parse_event(...)` call here, store the result under a new key, read it in the new filter via `_dp2_cache.get(path, {}).get("new_key", {})`. No other method changes.

  **`_preparse_dp2`** — rewritten around partial cache hits. No more signature check, no more full cache flush. Uses `missing = [dp for dp in paths if dp not in _dp2_cache]` — only unprocessed demos are dispatched to the thread pool. On Preview → Batch with the same demo set, the pre-parse is skipped entirely (`all N demo(s) already cached — skipping`). On a date range change that adds new demos, only the new ones are parsed.

  **`_trois_shot_filter`** — parse/cache block replaced by `_dp2_parse_demo(demo_path)` call + `data.get("fire_detail", {})` read. `from demoparser2 import DemoParser` removed.

  **`_one_tap_filter`** — same: parse/cache block replaced, reads `data.get("fire_ticks", {})`.

- **`_dp2_cache` key scheme changed**: from `("trois_shot"|"one_tap", demo_path)` → `demo_path` directly (unified entry per demo).
- **`_dp2_cache_sig`** removed from `__init__` and `_preparse_dp2` — no longer needed.

### Fixed
- **Pre-parse repeated on Preview → Batch**: with the old signature check, any difference in the cfg between the two calls (even irrelevant fields) would invalidate the sig and flush the full cache. The new partial cache never flushes — demo data persists for the entire session once parsed.
- **`weapon_fire` parsed twice per demo**: `_trois_shot_filter` and `_one_tap_filter` previously each issued a separate `DemoParser.parse_event("weapon_fire", ...)` call. Now one parse populates both `fire_detail` and `fire_ticks`.

---

## [v76]
### Fixed
- **ONE TAP always returned 0 results** (`✗ not isolated` on every kill across all demos): `_one_tap_filter` was indexing weapon_fire shots by `sid` alone — any shot fired by the player with *any* weapon within ±128 ticks invalidated the kill. Since players constantly fire different weapons, every kill was rejected. The index is now keyed by `(sid, weapon_suffix)` matching exactly `_trois_shot_filter`'s approach, so isolation is checked per-weapon: a Desert Eagle kill is only rejected if the player fired another Desert Eagle within the window.
- **TROIS TAP always returned 0 results**: inherited the same bug via `_trois_tap_filter → _one_tap_filter`.
- **Log improved**: `_is_isolated` now logs the weapon name alongside tick and sid for easier diagnosis (`🎯 [Desert Eagle] [tick=…] sid=… → ✓/✗`).

---

## [v75]
### Added
- **`_one_tap_filter`** implemented: uses demoparser2 `weapon_fire` events to verify that exactly one shot was fired within ±128 ticks (~2s at 64 tick/s) around the kill tick. Headshot is pre-guaranteed by the DB query. Result cached under key `("one_tap", demo_path)`.
- **`_no_trois_shot_filter`** implemented: inverse of `_trois_shot_filter` — keeps only kills on eligible weapons that are *not* lucky (precise shots). Non-eligible weapon kills are always passed through.
- **`_trois_tap_filter`** implemented: chains `_trois_shot_filter` → `_one_tap_filter` (TROIS SHOT ∩ ONE TAP). Previously referenced but never defined, causing `AttributeError` on every run with ONE TAP or TROIS TAP enabled.

### Fixed
- **`AttributeError: '_tkinter.tkapp' object has no attribute '_one_tap_filter'`**: all three filter methods (`_one_tap_filter`, `_no_trois_shot_filter`, `_trois_tap_filter`) were referenced in `_apply_filter_to_events`, `_apply_dp2_modifiers`, and `_preparse_dp2` but never defined — crashing every preview and batch run that used ONE TAP or TROIS TAP.
- **ONE TAP / TROIS SHOT do not uncheck TROIS TAP**: enabling ONE TAP or TROIS SHOT while TROIS TAP was already active left TROIS TAP checked alongside the individual modifier. `_on_one_tap_toggle` and `_on_trois_shot_toggle` now call `_disengage_trois_tap()` and clear the TROIS TAP variable when activated.

### Changed
- **Full English translation** of all remaining French strings in comments, tooltips, and log messages (excluding proper nouns containing "Trois"):
  - Comments: `tir precise immobile` → `precise stationary shot`, `tir en mouvement` → `shot while moving`, `spam (2e+ tir rapide)` → `spam (2nd+ rapid shot)`, `lucky si` → `lucky if`, `pas premier tir immobile` → `not first stationary shot`, `Noms internes` → `Internal names`, `inclure les suicides` → `include suicides`, `kill sans scope` → `no-scope kill`, `kill en wallbang` → `wallbang kill`, `killer en l'air` → `killer airborne`, `Preset encodage … uniquement — sans effet sur GPU` → `Encoding preset … only — no effect on GPU`, `% de vitesse : 100 = normal, 50 = demi-vitesse` → `% of speed : 100 = normal, 50 = half-speed`, `Utilitaires` → `Utilities`, `Lookup plat construit … au lieu de` → `Flat lookup built … instead of`, `Depuis le 1er du mois en cours` → `From the 1st of the current month`, `Depuis le 1er janvier` → `From January 1st`, `la date d'import et non la date de partie` → `the import date and not the actual match date`, `Les codecs GPU … ignorent` → `GPU codecs … ignore`, `Écrire la liste FFmpeg concat` → `Write the FFmpeg concat list`, `Pas d'apostrophes … on utilise les guillemets doubles` → `No apostrophes or quotes … use double quotes`
  - UI / tooltips: `Choisir une couleur` → `Choose a color`, `Kill sans scope (sniper seulement)` → `No-scope kill (sniper only)`, `l'apparence des cadavres et la physique du jeu` → `the appearance of ragdolls and game physics`, `+cl_downloadfilter all dans les Launch Options Steam, pas ici` → `+cl_downloadfilter all in Steam Launch Options, not here`
  - Log messages: `ECHEC:` → `FAILED:`, `=== Tag '…' sur N demo(s) ===` → `=== Tag '…' on N demo(s) ===`
  - Inline comments: `Auto-activer si c'est le premier` → `Auto-activate if it's the first`, `Debug: montrer ce qui est dans la table` → `Debug: show what is in the table`, `tag_on_export = premier tag actif (compat batch) ; les autres sont dans _tags_active` → `tag_on_export = first active tag (batch compat) ; others are in _tags_active`, `Construire la clause joueur pour N SIDs` → `Build the player clause for N SIDs`, `Colonne headshot (optionnelle)` → `Headshot column (optional)`, `ONE TAP et TROIS TAP impliquent headshot obligatoire en BDD` → `ONE TAP and TROIS TAP require mandatory headshot in DB`, `Construire une timeline … explicite` → `Build an explicit … timeline`, `LIKE sur le nom de fichier` → `LIKE on the filename`, `Tk elide sur les tags : on cache ce qui porte un tag "hidden"` → `Tk elide on tags: hide items carrying the "hidden" tag`, `Lignes portant le tag cible` → `Lines carrying the target tag`, `Slider "Avant switch" — visible seulement en mode victim/both` → `"Before switch" slider — visible only in victim/both mode`, `Tout : vider les deux champs` → `All: clear both fields`, `Bloc Ratio d'aspect` → `Aspect Ratio block`, `Arrondir la largeur au multiple de 2 le plus proche (requis par la plupart des codecs)` → `Round width to nearest multiple of 2 (required by most codecs)`, `Trace recsys pour afficher/masquer` → `Trace recsys to show/hide`, `Fallback BDD (souvent = date d'import)` → `Fallback DB (often = import date)`, `Multi-tags : on utilise _tags_active si disponible, sinon tag_name seul` → `Multi-tags: use _tags_active if available, else tag_name alone`
  - Section headers: `TAB CAPTURER` → `TAB CAPTURE`, `TAB OUTILS` → `TAB TOOLS`, `PLAGE DES TAGS` → `TAG DATE RANGE`, `OPÉRATIONS` → `OPERATIONS`
  - Calendar day abbreviations: `Lu Ma Me Je Ve Sa Di` → `Mo Tu We Th Fr Sa Su`
  - Log format: `seuil=` → `threshold=`, `et propose d'appliquer ces dates comme filtre dans Capturer` → `and suggests applying these dates as a filter in Capture`
  - French guillemets `«…»` replaced with standard double quotes `"…"` in all f-strings and log messages

---

## [v74]
### Added
- **TROIS TAP auto-toggle**: checking both TROIS SHOT + ONE TAP simultaneously auto-enables TROIS TAP and clears the two individual modifiers. Unchecking TROIS TAP does not restore them — it simply disengages. Logic split into `_engage_trois_tap()` / `_disengage_trois_tap()` helpers.
- **DP2 threads** slider in Tools → Performance (1–8, default 2): parallel demo pre-parsing via `ThreadPoolExecutor`. Logs `⚡ Pre-parsing N demo(s) with X thread(s)…` / `✓ Pre-parse done`.
- Per-demo parse cache (`_dp2_cache`): each `.dem` parsed at most once per run, even when TROIS TAP chains both filters. Protected by `threading.Lock` (`_dp2_cache_lock`) against race conditions during parallel pre-parse.
- `_preparse_dp2(cfg, demo_paths)`: centralized pre-parse helper called by both `_worker` and `_dry_run` — replaces duplicated inline blocks.
- **Tag selection persisted**: active (checked) tags are now saved in config as `active_tags` (list of names) and restored on startup. Uses deferred restoration via `_pending_restore_tags` if the DB is not yet connected when config loads.

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
- **Log labels corrected**: TROIS SHOT / TROIS TAP filters no longer log "lucky" / "lucky tap"
- `cs2_window_mode` default value: `"aucun"` → `"none"`
- `_WEAPON_CATEGORIES` key aligned: `"Grenades & Utilities"` → `"Grenades & Utility"` to match WEAPON_ICONS
- `bisect`, `concurrent.futures`, `collections.defaultdict` moved to top-level imports — no longer re-imported on every filter call
- In-script changelog removed — all history now in this file only

### Removed
- **Skip Intro CS2** option: `+novid` / `skipIntro` has no effect in CS2. Removed from DEFAULT_CONFIG, bool_keys, PRESET_KEYS, UI checkbox, and JSON build.

### Fixed
- **NameError `evt` not defined**: loop variable `events` shadowed the parameter in `_trois_shot_filter`, `_no_trois_shot_filter`, `_one_tap_filter` — corrected to `for evt in events`
- **TROIS TAP deactivation**: unchecking TROIS TAP no longer incorrectly restores TROIS SHOT + ONE TAP

### Performance
- `_trois_shot_filter`: linear `_is_lucky` scan replaced by bisect index `{(sid, wpn_suffix) → [(tick, acc, scoped, vel)]}` — O(log n) per kill instead of O(n)
- `itertuples()` replaced by `to_numpy()` in both filters — 5–10× faster DataFrame iteration on large demos
- `_dp2_cache_lock`: thread-safe cache prevents duplicate parsing when multiple threads hit the same demo simultaneously

---

## [v73]
> All v73 changes are included in v74. v73 was never shipped as a standalone release.

### Fixed
- **NameError `evt` not defined** in `_trois_shot_filter`, `_no_trois_shot_filter`, `_one_tap_filter`: loop variable `events` shadowed the parameter while the body still referenced `evt` — introduced during a translation pass by a previous session

### Performance
- `_trois_shot_filter`: linear scan replaced by bisect index `{(sid, wpn_suffix) → [(tick,…)]}` — O(log n) per kill instead of O(n)
- `itertuples()` replaced by `to_numpy()` in both filters — 5–10× faster
- Per-demo parse cache and parallel pre-parsing first introduced here, finalized in v74

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

## [v67] *(applied as external patch)*
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

---

## [v40]
### Fixed
- **Workshop map download blocking**: added "Accept Workshop downloads automatically" checkbox in HLAE section (Video tab). When enabled, injects `+cl_downloadfilter all` into `hlaeOptions.extraArgs` so CS2 silently downloads outdated Workshop map versions without interrupting the batch.

---

## [v39]
### Added
- **Kill modifiers section** in Capture tab (OR logic — at least one must match per kill):
  - Smoke: `is_through_smoke`
  - No-scope: `is_no_scope`
  - Wallbang: `is_wall_bang` / `penetrated_objects > 0`
  - Airborne: `is_airborne`
  - Flash-assisted (blind): `is_assisted_flash`
  - Collateral: `is_collateral`
  - If no modifier is checked, no filter is applied (all kills pass).
  - Graceful fallback: warns in log when a column is not found in DB, skips that modifier only.
- **`hchk` helper**: highlighted checkbox — ORANGE2 background + white text when checked, neutral when unchecked. Applied to all checkboxes: weapons, modifiers, in-game options, HLAE options, assembly, etc.

### Changed
- Workshop download note in HLAE section updated to direct user to Steam Launch Options (prior to v40).

---

## [v38]
### Added
- **Preset encodage (CPU)**: combo `ultrafast → veryslow` in Codec Vidéo section. Auto-injected as `-preset <value>` into `ffmpegSettings.outputParameters` for CPU codecs (`libx264`, `libx265`, `libsvtav1`, etc.). No effect on GPU codecs (NVENC/AMF). Not injected if `-preset` already present in manual params.
- **Teamkills — 3rd state "Teamkills only"**: replaces include/exclude checkbox. Radio group with Inclure / Exclure / Teamkills seuls. Injects `AND killer_team = victim_team` in SQL. Correctly sets both `include_teamkills` + `teamkills_only` booleans.
- **Reorder saved players**: ▲▼ buttons on each saved player row. Swaps immediately and persists to `csdm_players.json`. Buttons at extremes are disabled.
- **Tag color swatch on inactive tags**: colored square (border = tag color, fill = neutral background) always visible left of tag name. Fills completely when tag is active.
- **Assembly encoding clarification**: description now explicitly states video is copied without re-encoding (`-c:v copy`) and only audio is re-encoded (AAC) for drift correction.

### Fixed
- **Preset section in Outils tab**: was re-packing the BDD section instead of creating a new `Sec`. Now uses correct `sec_pre` / `sec_load` references.
- **Preset radio buttons**: were all on a single horizontal line causing overflow. Now each radio is on its own line (`anchor="w"`), name field expands to full width.

---

## [v37]
### Fixed
- **Presets section misplaced in Outils tab**: `sec.pack(fill="x", ...)` at line 2910 was re-packing the PostgreSQL section. Fixed by using a properly named `sec_pre` variable.
- **Preset type radio buttons overflowing**: were packed `side="left"` on a single row. Now stacked vertically (`anchor="w"`).

---

## [v36]
### Fixed
- **`showKill` logic corrected for victim/spec perspectives**: previously only `sid` had `showKill: True`, so death notices for filmed victims did not appear. Now:
  - Killer mode: `showKill` on `sid` only.
  - Victim mode: `showKill` on all killers in the sequence so their death notices render.
  - Spec mode: `showKill` on all involved players.
  - `highlightKill` always only on `sid`.

---

## [v35]
### Fixed
- **POV Victim camera not applied**: three distinct bugs:
  1. `_cam_sid_for_event` in victim mode returned `victim_sid` for both kill and death events. Now: `death` event → film `sid` (the active player is the victim); `kill` event → film `victim_sid`.
  2. `playerName` was always `""` in `playerCameras`. Now resolved from `_player_names` for every target SID.
  3. All `victim_sid` from sequence events are now explicitly added to `playersOptions` in victim mode so CSDM recognizes the player even if no camera tick points to them directly.

---

## [v34]
### Added
- **Weapon categories reorganized**:
  - `Couteaux` (Knives): split from Equipement, includes all skin variants.
  - `Grenades (Effet)`: HE, incendiary, molotov, inferno, zeus, decoy (explodes at end).
  - `Grenades (Collision)`: flashbang, smoke, HE, incendiary, molotov, decoy — all grenades that can kill by direct projectile impact before detonation.
  - `C4 / World`: C4, world damage, suicide, world_entity.
  - Old `Equipement` category removed.
- **`DELAYED_EFFECT_WEAPONS` constant**: set of weapon names for which `death_tick` should be used instead of `killer_tick` (HE, molotov, inferno, incendiary).
- **`victim_death_tick` column detection**: `_query_events` now searches for `victim_death_tick` / `death_tick` / `killed_tick` in kills table. When found and weapon is in `DELAYED_EFFECT_WEAPONS`, uses death tick as event tick instead of throw tick — fixes clips where victim had not yet died at the recorded tick.
- **Deaths by equipment clarified**: note added in UI explaining that `Deaths` + weapon filter = deaths of active players caused by that equipment specifically.

### Fixed
- **`decoy` missing from Grenades (Effet)**: decoy explosion can kill; `weapon_name` in DB is `"decoy"` — now included.

---

## [v33]
### Fixed
- **`mkv` container rejected by FFmpeg**: `-f mkv` is not a valid FFmpeg format name. Added `_FMT_MAP = {"mkv": "matroska", ...}` to translate container names to FFmpeg format strings.
- **`#` in output filename crashing FFmpeg**: `#` is interpreted as a sequence marker on the command line. When filename contains `#`, `%`, `?`, or `*`, assembly now writes to a temp file (`_csdm_tmp_<hex>.mp4`) and renames after success.
- **`-movflags +faststart` on mkv/avi**: this flag is MP4/MOV-specific. Now only applied when container is `mp4` or `mov`.

---

## [v32]
### Fixed
- **DB status header showing raw debug info**: `jt=checksum_tags(checksum,tag_id) col_date:analyze_date(timestamp with time zone)` was displayed in the header status label. Now shows only `OK — N joueurs, N tags`. If date column is undetected, a warning goes to the log only.

---

## [v31]
### Changed
- **Tab reorganization** (5 tabs → 4 tabs):
  - `Config` + `BDD` + `Presets` → `Capturer` + `Outils`
  - `Capturer`: player, events, timing, order, date filter, weapons, auto-tag.
  - `Outils`: CHEMINS + PostgreSQL connection + Presets.
  - `Vidéo` and `Tags` unchanged.
- **`CHEMINS` section moved** from `Capturer` to `Outils` (logical grouping with other infrastructure settings).

### Fixed
- **Active player state not restored on startup**: `PlayerSearchWidget.__init__` activated all saved accounts by default, ignoring the `steam_ids` list saved in config. Now reads `steam_ids` from config after UI build and applies exactly that set.
- **`_apply_config` additive SIDs**: loading a preset was adding SIDs instead of replacing. Now clears `_active_sids` before applying preset `steam_ids`.

### Removed
- **"Vérifier un tag en BDD" section**: removed from Tags tab (redundant). Method `_verify_tag_in_db` deleted.

---

## [v30]
### Fixed
- **Assembly audio/video drift**: clips produced with HLAE have a `start: -0.025057` audio timestamp. `-c copy` accumulated this offset across 100+ clips (~3s drift). Assembly now uses:
  - `-fflags +genpts`: recomputes negative/missing PTS at input.
  - `-c:v copy`: video copied without re-encoding.
  - `-c:a aac -af aresample=async=1000`: audio re-encoded lightly to resync against video timeline.
  - `-movflags +faststart`: fast seek in final mp4.

---

## [v29]
### Fixed
- **No audio in clips**: sequences were missing `"recordAudio": true` and `"playerVoicesEnabled": true` fields — CSDM simply did not record audio when these were absent. Identified by comparing against CSDM's own JSON export. Also added `"showXRay": true` and `"showAssists": false` which were missing.
- **Already-tagged demos dialog**: before batch start, if auto-tag is enabled, queries DB for demos already having the target tag. If any found, shows dialog listing them: Yes = skip, No = include anyway. One dialog for entire batch.

---

## [v28]
### Added
- **X-Ray option**: checkbox in Capture tab → `showXRay` in each sequence JSON.

### Fixed
- **Assembly output filename without extension**: extension was added before resolving absolute path, so `"H:\...\MyFilm"` (already absolute, no extension) was not corrected. Extension is now added after path resolution.
- **Saved assembly names**: replaced hardcoded "quick titles" list with a personal saved-names system. Names persist in `csdm_asm_names.json`. "Save current name" button adds the current field value; click to restore; ✕ to delete.

---

## [v27]
### Fixed
- **`snd_mute_losefocus` hypothesis retracted**: the real audio bug was missing `recordAudio: true` / `playerVoicesEnabled: true` in sequences (fixed in v29). The `-mirv_exec` injection added in this version was removed.

---

## [v26]
### Changed
- **Version bump** from v25 to v26 in title, header label, and docstring.
- `PlayerSearchWidget` docstring updated to reflect multi-select behavior.

---

## [v6]
### Changed
- **Weapons loaded from DB**: `WEAPONS` hardcoded list removed. On connect, `SELECT DISTINCT weapon_name FROM kills` populates the weapons grid dynamically — no missing weapons regardless of game version or custom content.
- **`_build_weapons_grid(weapons)`** added: rebuilds the checkbutton grid after DB load; preserves saved selections from config; displays a count label (`N armes chargées`).

### Fixed
- **Weapons grid not appearing**: `pack(before=hidden_widget)` silently failed. Grid now packs normally after the status label.

---

## [v5]
### Fixed
- **`column m.date does not exist`**: `date` is a reserved word in PostgreSQL and cannot be used unquoted as a column name. The column name is now discovered at connect time via `information_schema.columns` (first `date`/`timestamp` column in `matches`) and injected quoted (e.g. `"date"`) into every query. If no date column is found, date filters are silently skipped instead of crashing.

---

## [v4]
### Added
- **Connexion BDD au démarrage**: connects to PostgreSQL automatically on launch; loads all players into `PlayerSearchWidget` without user action.
- **`PlayerSearchWidget`**: replaces the dropdown — text field + filtered listbox. Typing any substring of name or Steam ID narrows the list in real time. Restores last selected player from config on startup.
- **Config auto-save** (`csdm_config.json`, same directory as script): all fields written to disk every 5 seconds via `_auto_save_loop`. Restored on next launch — no re-entry needed.
- **`DEFAULT_CONFIG` / `load_config` / `save_config`** helpers: merge saved config over defaults so new keys added in future versions are always present.

### Changed
- **3-tab layout**: `Configuration` / `Base de données` / `Exécuter`. DB credentials moved to their own tab; `Base de données` tab shows connection status and explains the query logic.
- **Player selection**: SteamID field removed — player chosen from BDD-loaded list; Steam ID shown read-only below the list.

---

## [v3]
### Fixed
- **`TclError: bad screen distance "0 16"`**: `pady=(0, 16)` passed to `tk.Frame()` constructor — tkinter Frames only accept scalar padding in the constructor; tuple padding must be passed to `.pack()`. Moved to `log_wrap.pack(pady=(0, 16))`.
- **`TclError: unknown option "-placeholder_text"`**: `placeholder_text` is not a valid tkinter `Entry` option. Removed; hint text moved to a `Label` below the field.

---

## [v2]
### Added
- **tkinter GUI**: full graphical interface replacing the bare Python script — path fields with `...` browse buttons, event checkboxes, before/after sliders, date fields, weapon tag-buttons, encoder radio buttons, live log pane with color tags, STOP button.
- **Batch loop with thread**: `_worker` runs in a `daemon` thread; UI stays responsive. Progress label updated per demo (`i/total`).
- **Validation on launch**: checks for missing CSDM path, missing demos folder, empty Steam ID, no event selected before starting.

---

## [v1]
### Added
- **Initial CLI batch script**: loops over all `.dem` files in a folder and calls `csdm video <demo> --mode player …` for each. Hardcoded config block at top of file (paths, Steam ID, event type, timing, encoder). Summary printed at end (`✓ Réussi / ✗ Échec`).
