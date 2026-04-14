# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> **Version numbering note:** sub-releases previously written as `133.xx` or `143.x` have been
> renumbered as sequential integers. `133.33` → `134`, `133.34` → `135`, …, `133.42` → `143`,
> `143.0` → `144`, `143.1` → `145`, …, `143.8` → `152`. Each dot was always one real increment.

---

## [v202]

### Fixed: map column detection — `map_name` lives in `demos` table, not `matches`

CSDM stores `map_name` in the `demos` table (a sibling table to `matches`, sharing the same `checksum` PK). Previous code only searched `matches`, so map data was never found.

**Revamp:**
- New static `_detect_map_col(schema)` — single source of truth for detection. Checks `matches` first (backward compat), then falls back to `demos` via `LEFT JOIN demos d ON d.checksum = m.checksum`. Candidates list (`_MAP_COL_CANDIDATES`) is a class-level constant.
- `demos` table now included in the schema fetch at connect time.
- `_map_alias` ("m" or "d") and `_map_join` (JOIN clause or "") stored on the instance alongside `_map_col`. All SQL that references the map column uses these — kills query, rounds query, manual mode query.
- Distinct map fetch reads from the owning table directly (`demos` or `matches`), no join needed for `SELECT DISTINCT`.
- Manual mode query rebuilt using `map_alias` and `map_join` — no more `_find_col` fallback, no dead code.

---

## [v201]

### Fixed: timeout formula; Added: MAP FILTER section; Fixed: map column always visible

**Timeout**: Formula simplified to `max(content × 3, 60s)`. No per-seq or flat overhead. For a 24s demo: 72s = 1m12s. For very short content: 60s floor. User-configured minimum still acts as a floor via `max(user, auto)`.

**Map filter**: New "MAP FILTER" section in Capture tab, after Match Types. Populated dynamically from DB on connect — no hardcoded maps. Map col and distinct values detected at connect time (not lazily in `_query_events`). Deduplication: maps grouped by display key (stripped prefix + lowercase), so "de_dust2" and "DE_dust2" merge to one checkbox. Selecting a map filters the kills + rounds SQL query (`AND m."map_col" IN (...)`). Section shows "No map column found in DB" and disables the toggle when DB has no map column.

**Map column in treeview**: Reverted the v200 hide-when-absent logic — column stays visible at all times (just empty when no DB data).

---

## [v200]

### Fixed: demo picker map column hidden when DB has no map column; removed Workshop DL option; timeout formula tightened

**Map column**: `_map_col` now hides the Map treeview column (width=0) when no map column is found in the DB, instead of showing an empty column. The "broader fallback" detection (any col containing "map") was added in v199 — if it still finds nothing, the column is cleanly suppressed.

**Workshop DL removed**: `hlae_workshop_download` option removed entirely. `downloadWorkshopMap` was a CSDM config key with no reliable CS2-side auto-download behaviour. The injected `sv_pure 0 + sv_lan 1` blocked Steam Workshop validation (causing potential map loading failures). Removed from DEFAULT_CONFIG, PRESET_KEYS, bool_keys, UI, `_inject_cs_runtime_cfg`, `_build_hlae_launch_tokens`, and `_build_json`.

**Timeout formula**: Changed from `×3 + 10s/seq + 180s` to `×2.5 + 10s/seq + 60s`. For a 24s/1-seq demo: was 4m22s → now 2m10s. Timeout log line now colored: duration in orange, content in green, seq count in blue.

---

## [v199]

### Fixed: map column not showing in demo picker

`_find_col` was only checking exact candidates (`map_name`, `game_map`, `map`, `level_name`, `server_map`). If the CSDM DB uses a different column name, detection silently returned `None` and no map data was ever fetched — the Map column in the picker was always blank.

Added a broader fallback: if no exact candidate matches, any column in `matches` whose name contains `"map"` is used. Applied to both the Preview query path and the Manual mode path.

Added a diagnostic log on first detection: shows which column was found, or warns with the first 8 columns from `matches` if nothing matched.

---

## [v198]

### Bump

No new features. Version increment to mark a clean checkpoint after v195–v197 fixes.

---

## [v197]

### Fixed: recording timeout now actually fires and adapts to demo complexity

The watchdog that is supposed to kill a stuck recording and retry was effectively broken in two ways:

1. **CS2 kept stdout open after CSDM was killed.** CSDM inherits the stdout pipe and passes it to CS2. Killing CSDM left CS2 alive with the pipe still open, so `readline()` blocked forever — the timeout appeared to do nothing. Fixed by using a synchronous `subprocess.run` for `taskkill /F /IM cs2.exe` so the pipe is guaranteed closed before the watchdog returns.

2. **The timeout was a fixed value, not adapted to the demo.** Setting "15 minutes" works for a short demo but incorrectly kills a demo with 40 clutch sequences. The `recording_timeout` field (minutes) is now a **minimum floor**, not the sole value. The actual per-demo timeout is calculated automatically from sequence data: `(total clip game-time / timescale) × 3  +  10s per sequence  +  3 min flat`. The computed value is logged so you can see what was used. Setting the field to 0 uses the auto value alone; setting it to a number forces at least that many minutes.

**Technical details:**
- `_exec` watchdog: `subprocess.Popen(["taskkill"...])` → `subprocess.run(["taskkill"...], timeout=15)` — synchronous kill guarantees the pipe closes.
- Per-demo timeout replaces the old single `_rec_timeout_s = user_minutes × 60`. Formula: `(_sum_clip_s / _timescale) * 3 + len(seqs) * 10 + 180`. Accounts for slow-motion factor (`hlae_slow_motion`), sequence count, and clutch full-window sequences (which have baked-in tick ranges that can span entire rounds). `_user_timeout_s` from config is applied as `max(user, auto)` when non-zero.
- Timeout field tooltip updated: 0 = auto-calculated, non-zero = minimum floor.

---

## [v196]

### Fixed: player names back in deathnotices, "By config" no longer needs a tag pre-selected, new name override field

**Player names in deathnotices** were always blank — CSDM was receiving `playerName: ""` for every player. Names from the demo file (recorded username) are now used, with a fallback to the database player table. Nothing is forced or overwritten by the script: if the demo has the name, that's what shows. If not, it's empty, same as before but now intentionally.

**"By config" in Tags** no longer requires a tag to be selected first. It now works the same way as the preview: finds all demos matching the current config (player + events + weapons + dates). If a tag *is* selected, the results are additionally filtered to only already-tagged demos — same behaviour as before but no longer mandatory. Also uses the last preview cache when available, so if you already ran a preview you get the result instantly.

**Active player name override** — new "Name override" field in Capture, just below Mate POV. Leave it empty (default) to use whatever name the demo file has. Type a name to force it for the active player in deathnotices only — useful if the recorded username is wrong or you want a cleaner display name.

**Headshot feedback:** no cvar exists in CS2 for this — the dink sound is hardcoded and silent in demo playback. Not implemented.

**Technical details:**
- `_build_json`: `players_opts[].playerName` now uses `_name(psid)` (was always `""`). `_name()` pulls from `_dp2_cache[demo_path]["demo_names"]` first, then `self._player_names` (DB). New `_name_override` variable (from `cfg["player_name_override"]`) replaces `_name(psid)` for active-player entries when set.
- `_tag_search_demos`: removed the `if not active_ids: return` guard. Tag query is now conditional on `active_ids` being non-empty. Config events query re-uses `self._last_preview_data["evts"]` when the cache is populated. Log line includes `(cached)` when the cache is used.
- New config key `player_name_override` (default `""`), added to the `players` preset group. UI: `sentry` entry in Capture section after the Mate POV row.

---

## [v195]

### Fixed: buttons no longer get hidden when resizing the window or the log console

Resize the window or drag the sash between the categories panel and the log — every row of buttons now reorganizes itself into multiple rows instead of getting clipped off-screen.

**Technical details — `WrapRow` and targeted row conversions:**

New `WrapRow` class (`tk.Frame` subclass): positions children via `place()` in a wrapping layout. Measures available width on every `<Configure>` event (16 ms debounce), wraps items to a new row when they no longer fit, and adjusts its own height automatically. Registered in `_WRAP_ROWS` so a global `<ButtonRelease-1>` handler can flush an immediate relayout after any sash drag (50 ms delay to let PanedWindow finish propagating geometry first). OS window-border resize falls back to a 400 ms debounce on `_on_canvas_configure`.

Rows converted to `WrapRow` — related label+control pairs are grouped into sub-frames so a label and its input always wrap together as a unit:
- **Demo picker** (`pick_btns`): Check all / Uncheck all / Check selected / Uncheck selected
- **Capture events** (`ev_row`): Capture label + KILLS / DEATHS BY / ROUNDS toggles
- **Tag range actions** (`plage_actions`): Apply start / Apply end / Apply full range / After range
- **Retries / Delays / Order** (`rg`): five sub-frame groups — Retries, Delay, Demo pause, Timeout, Order (Chrono / Random) — each stays together when wrapping
- **Suicides / TK** (`tk_row`): two sub-frame groups, each with its three radio buttons
- **Headshots** (`hs_row`): label + All / Only / Exclude radios
- **Window mode** (`win_row`): mode radios group + "Send to back on launch" checkbox

Date range split into two fixed rows (`dr1` / `dr2`): From/To entries on row 1, Today/Clear shortcuts on row 2 — shortcuts no longer compete with the date fields for horizontal space.

Pane minimum sizes: `UI_PANE_LEFT_MIN = 380 px`, `UI_PANE_RIGHT_MIN = 200 px`. Enforced in Python via pixel clamping in `_on_splitter_release` (clamps before saving as %) and `_set_sash` (clamps on startup restore). `_clamp_layout_values` percentage bounds updated to `(38, 80)` to match (38 % ≈ 380 px at the 1000 px minimum window width).

---

## [v194]

### Fixed: POV killer selects wrong/random player

**Root causes (two separate bugs):**

1. **`_build_cams_victim` / `_build_cams_both` — dp2 SID mismatch:** The victim/both camera builders were using `_victim_dp2_sid` (a SteamID with the lower 3 bits zeroed due to CS2 entity-handle encoding from `parse_ticks`). CSDM's CS2 path looks up `playerSteamId` with strict equality against `players.steam_id` in its database — the entity-handle-encoded SID never matched, so `spec_player` was never called and CS2 showed a random player. Fixed by using the DB SteamID (`victim_sid`) directly.

2. **`_build_cams_killer` — overcomplicated tick iteration:** The previous implementation generated one camera entry per "camera tick" (start, pre-kill, post-kill) and started the camera on `anchor_sid` (the primary registered player) rather than the actual killer. If the primary player wasn't the killer, the camera would be pointed at the wrong person before each kill. Also, unnecessary complexity from stacking multiple prior fixes. Replaced with a clean, minimal implementation: one entry at `seq["start_tick"]` pointing to the first killer, plus one entry per subsequent killer change — directly mirroring what CSDM generates internally for highlights.

**Also removed:** The `_victim_dp2_sid` stamp from `_mate_pov_filter` (dead code — it was never a valid SteamID for CSDM).

---

## [v193]

### Fixed: Category boxes (Sec cards) overlap the console on small windows

**What changed:** The left panel's section cards now properly collapse when the window is made small — the console can no longer push them off-screen or cause overlap.

**Why it happened:** `tk.Canvas` without an explicit `height` defaults to ~264px on Windows. Every `ScrollableFrame` hosts a Canvas as its scroll viewport, so each scrollable tab inherited that 264px minimum geometry request. When the window was made short, the layout system had to satisfy that minimum, which could cause the log area to overlap or clip the category sections above it.

**Technical details:**
Added `height=1` to the Canvas inside `ScrollableFrame.__init__`. This collapses its geometry request to 1px so the layout is entirely governed by available space and pack weights rather than the widget's natural size floor. Scrolling still works normally — `height=1` only removes the artificial minimum; the canvas expands to fill its container via `pack(fill="both", expand=True)`.

---

## [v192]

### Fixed: Console too tall hides the Run/Preview/Stop buttons (superseded by v193)

Attempted fix via `height=1` on `tk.Text`. Correctly identified the geometry-request pattern but targeted the wrong widget — the root cause was the `ScrollableFrame` Canvas default height.

---

## [v191]

### Improved: Code quality pass — naming, error handling, docstrings, config migration

**What changed:** A batch of housekeeping improvements based on a full code review. Nothing user-visible — this is all about making the codebase cleaner and easier to maintain.

**Changes:**
- `_alog` / `_alog_parts` renamed to `_async_log` / `_async_log_parts` — the "a" prefix was ambiguous; "async" is unambiguous
- Bare `except Exception: pass` replaced with `except tk.TclError: pass` in all widget-lifecycle contexts (theme changes, tooltip destroy, focus checks, wraplength updates); file I/O handlers narrowed to `except (OSError, ValueError)` and `except OSError`; page-jump input narrowed to `except ValueError`
- Docstrings added to `desc_label`, `sentry`, `scombo`, `mlabel`, `hchk` — all were missing return-type documentation
- Config migrations extracted from `load_config` into a dedicated `_migrate_config(saved, cfg)` function with version comments per migration block — future renames/type changes have a clear home

**Technical details:**
`_migrate_config` is a pure function (no side effects) called once during load. Existing migration logic is unchanged — it was just lifted out and annotated. Each block now has a comment indicating which version introduced the breaking change, making it easier to decide when old migrations can eventually be dropped. Hot-loop `cfg.get()` audit confirmed `_apply_db_postfilters` already caches all config reads before its inner loops.

---

## [v190]

### Fixed: Window drag no longer sluggish

**What changed:** Window movement is instant again. Removed the async log pump that was introduced to keep the window responsive during preview — it was causing more problems than it solved by injecting recurring timer callbacks into the event loop.

**Technical details:**
Removed `_log_pump`, `_drain_log_buffer_once`, `_log_buf`/`_log_buf_lock`, and the 50ms recurring `after()` timer. `_alog` and `_alog_parts` now post directly via `after(0, ...)` per message — the original, simpler approach. The pump was added to batch log writes during heavy preview output, but the recurring timer fired on the main thread even when idle, interfering with Windows' modal drag loop. Window freezing during active preview is normal Tkinter behavior and doesn't need workarounds.

---

## [v189]

### Fixed: Window movement lag (partial — superseded by v190)

Attempted adaptive log pump: 50ms when buffer non-empty, 250ms when idle. Still left a recurring timer running, which didn't fully resolve the drag issue.

---

## [v188]

### Fixed: Tag range dates not showing after DB migration

**What changed:** When calculating date range for tagged demos, if your demo files were moved or deleted from disk, the UI would show "dates undetermined". Now it correctly falls back to the database timestamp.

**Technical details:**
The `_tag_calc_range` query was only fetching demo paths and checksums — the date column from `matches` was missing. When demo files became inaccessible, the code had no fallback date source, so sorting and date extraction failed. Now the query includes the date column and populates `_demo_dates` so `_demo_sort_key()` has a DB date to fall back to.

---

## [v187]

### Added: Export and import tag assignments

**What changed:** New **Transfer** section in Tags panel with two buttons:
- **📤 Export** — Save all your tags and tagged demos to a portable JSON file
- **📥 Import** — Load tags from a JSON file (matching by checksum)

**How to use:**
- Export captures your tag definitions (name + color) and which demos are tagged
- Import into another CSDM database — only demos with matching checksums are tagged; missing tags are created automatically with their original colors
- Perfect for migrating your tags between databases or backups

**Technical details:**
Demos are matched by checksum (not filename), so your tags transfer correctly even if demo paths changed. The import dialog shows missing tags and lets you choose which ones to create. Uses idempotent inserts so re-importing is safe.

---

## [v186]

### Cleaned up: ~300 lines of dead code removed

**What changed:** Removed unused methods, dead loops, and copy-pasted code that served no purpose. The app is now ~3% smaller and easier to maintain.

**Cleaned up:**
- 3 unreferenced methods (`_select_by_label`, `_cfg_scalar`, `_tag_search_last_tagged`)
- Dead simulation loop that computed but never stored values
- Duplicate weapon label branches and redundant condition checks
- Unused variables and overly-broad exception catches

---

## [v185]

### Performance: Optimization and DRY cleanup

**What changed:** Faster database filter processing. Kill modifiers now use caching and shared logic instead of recomputing the same data repeatedly.

**What got faster:**
- Filter detection no longer rebuilds signature tuples 5+ times per kill
- Weapon names are normalized (lowercased/trimmed) once per unique value instead of per-kill
- Duplicate filter logic merged — positive and exclusion paths now share computation

**Technical details:**
Optimized `_apply_db_postfilters`, `_build_filter_badges`, and `_build_clip_badges`. Precomputed lookups (`e_sig`, `e_ksid`, `_norm_wpn`) eliminate redundant string operations in hot loops. Exclusion filter logic reuses cached sig sets from the positive phase.

---

## [v184]

### Fixed: CS2 kept popping to foreground during recording

**What changed:** CS2 now stays behind CSDM during the entire recording. Previously it would return to foreground after a few seconds.

**Why it happened:**
The old code sent CS2 to back once, then stopped. CS2 immediately regained focus. Plus, window matching by title was fragile and unreliable.

**How it's fixed:**
- CS2 is now continuously pushed to back every 500ms (not just once)
- Window matching uses process name detection instead of window title (more reliable)
- The loop stays active for the entire recording duration

---

## [v183]

### Multiple fixes and new features

**Fixed:**
- **Stop button** now cancels preview computations (not just batch runs)
- **Mate POV "Must" mode** could occasionally return active player's POV — tightened precision checks
- **Killer POV** sometimes started on a secondary account before the first kill
- **Death notice names** were outdated — now uses names embedded in the demo itself

**Added:**
- **Recording timeout (minutes)** — Kill hanging recordings and retry automatically
- **Suicide "Only" mode** — Keep only suicide deaths (complements Include/Exclude)
- **Better log messages** — Stop/Kill operations now show timestamp and clear intent

**Changed:**
- **Keyboard shortcuts removed** (F5, F6, Esc) — Use the UI buttons instead
- **French config names→English** (`sauveur`→`savior`, `bourreau`→`bully`) — Backward-compatible, old configs auto-convert

---

## [v182]

### Fixed and improved: Preset UI, logging clarity, and tab organization

**What changed:**
- Quick preset selector added to the top bar with save button
- Duplicate log messages for Mate POV filter removed
- UI tab sections reorganized for better workflow
- Video codec/audio codec controls consolidated into one section
- Fixed exclusion filters being ignored when only `-exclude` was set

**Preset bar:** New dropdown (combobox) + 💾 button in the top header bar — select a preset instantly, save current config to selected name or new preset. `_refresh_preset_list` keeps sidebar and header in sync.

**Logging:** Removed confusing duplicate logs. Mate POV now shows clean `X/N with qualifying mate` message instead of contradictory "0/2 qualifying" + "2 → 2" pair.

**Tab reorganization:**
- Capture tab: Players → Demo Selection → Weapon Filter → Capture & Timing → Kill Filters → Match Types
- Video tab: FINAL ASSEMBLY moved to top, RECORDING SYSTEM to bottom
- **ENCODING section** now consolidates VIDEO CODEC, AUDIO CODEC, and ADVANCED FFMPEG PARAMS

**Technical details:**
- `_dp2_required_sections` now checks both `cfg.get(k)` and `cfg.get(f"{k}_exclude")` so exclusion-only filters don't skip pre-parsing
- `_apply_filter_to_events` has dedicated Mate POV log branch instead of generic log
- ENCODING section structure reduces visual noise by grouping related codec settings

---

## [v181]

### Fixed: Mate POV — SteamID precision loss (complete rewrite)

**Root cause**: `_parse_mate_positions` called `.to_numpy()` on a mixed int/float DataFrame (tick, steamid, X, Y, Z, yaw, pitch, team). NumPy upcasts the entire array to `float64`, which only has 53 bits of mantissa — not enough for 17-digit SteamID64 values. `int(float(76561198347183079))` silently becomes `76561198347183072` (off by 7). Every exact string comparison in `_find_best_mate_sid` was failing because tick_data keys were corrupted.

**What was happening in practice**:
- Victim lookup `tick_data.get(str(victim_sid))` always returned `None` → mate search never ran → camera fell back to raw victim SID → wrong or random player spectated.
- Active-player exclusion (`sid in sids_active`) also failed → wrong mate could be selected.

**Fix — preserve SteamID precision at the source**:

1. **`_parse_mate_positions`** — SteamID column is now extracted via `astype("Int64").astype(str)` while still in pandas (preserving full int64 precision), BEFORE the `.to_numpy()` call that would corrupt it. Numeric columns (positions/angles) go through `.to_numpy()` separately. Tick_data keys now contain correct SteamID64 strings that match the DB.

2. **Fuzzy matching as safety net** — `_find_sid_in_tick(tick_data, db_sid)` and `_fuzzy_sid_in_set(dp2_sid, db_sids_set)` provide tolerance-based lookup (±8) in case any edge case slips through.

3. **`_find_best_mate_sid`** — rewritten to use fuzzy helpers and return `(mate_sid, victim_sid)` tuple so callers always have the correct SID for CSDM.

4. **`_mate_pov_filter`** — stamps `evt["_victim_dp2_sid"]` on every kill for camera fallback.

5. **`_build_cams_victim`** + **`_build_cams_both`** — fallback camera uses `_victim_dp2_sid` instead of raw DB `victim_sid`.

---

## [v180]

### Improved: Clip merging and weapon filter visibility

**What changed:**
- Adjacent kills that are close together now automatically merge into one clip
- Weapon selector now shows how many weapons are currently selected

**Sequence merge gap:** `_build_sequences` now merges two adjacent clip windows not just when they overlap, but also when the gap between them is ≤ your configured Before duration. This matches native CSDM: a kill happening just a few seconds after the first clip ends extends that clip instead of creating a separate one. No new settings — Before duration is the natural tolerance.

**Example:** Before = 5s @ 64 ticks/s → two kills up to 5 seconds apart (after the first clip's after padding) merge into one.

**Weapon filter indicator:** The weapon label now shows `weapons (X / Y selected)` in **orange** whenever a partial filter is active, making it obvious when unexpected weapons are still checked. Shows `weapons (all / Y)` muted when no filter is applied.

---

## [v179]

### Fixed: Workshop auto-download confirmation dialog

The "Auto Workshop DL" checkbox now properly auto-confirms the CSDM workshop download dialog by setting `"downloadWorkshopMap": true` in the CSDM video JSON config (in addition to injecting `sv_pure 0 / sv_lan 1` into CS2). Previously, the dialog would still appear, blocking the batch run.

### Fixed: Mate POV parsing in killer mode

Mate POV was being parsed even when perspective was set to killer, doing expensive position lookups for no reason. Two fixes:

1. **Perspective change resets vars**: Switching to killer POV now explicitly resets `kill_mod_mate_pov` and `kill_mod_mate_pov_req` to `False`.
2. **Filter safety guard**: `_mate_pov_filter` now early-returns in killer mode, preventing silent processing even if the var is stale.

**Scenario fixed**: User checked Mate POV in victim mode, switched to killer POV, then ran Preview — mate POV was still being processed wastefully. Now it resets automatically.

---

## [v178]

### Changed: Preset category selector redesigned — mini-tab columns

Replaced the 4 broad checkboxes (Player, Video, Timing, All) with a granular mini-tab column layout:

- **CAPTURE** tab: Active players, Date range, Filters
- **VIDEO** tab: Mode (HLAE/CS), Output name, Encoding, HLAE options, Physics
- **TIMING** tab: Timing & retry
- **ALL** column: Full config checkbox

**PRESET_KEYS** split into new granular sub-keys: `players`, `date`, `filters`, `mode`, `output_name`, `encoding`, `hlae_opts`, `physics`, `timing` (plus backward-compat aliases `player`, `video` for old presets).

The new UI allows fine-grained control over which settings are saved in each preset. Old presets load correctly via backward-compat path.

---

## [v177]

### Improved: Preset system and One Tap filter, UX refinements

**What changed:**
- Preset saving now uses checkboxes instead of single radio button
- Preset tooltips show all settings at a glance
- One Tap filter now properly enforces headshots via SQL
- "Clear all" in demo picker shows clear feedback

**Preset UI:** Replaced single "Type" radio with four independent checkboxes — **Player + events + filters**, **Video / encoding**, **Timing + robustness**, **All settings** (exclusive). Now you can combine multiple categories in one preset (e.g. Player + Timing). Format changed from `{"type": "..."}` to `{"cats": [...]}` with backward-compat for old presets.

**Preset tooltips:** Hover over any saved preset to see categories saved, key count, and notable settings (player name, perspective, dates, resolution, FPS, encoder, before/after).

**One Tap + headshots:** `kill_mod_one_tap` now adds `AND is_headshot = TRUE` to the SQL query (when headshot column exists), ensuring DB returns only HS kills before dp2 shot-isolation. If `headshots_mode = exclude`, the HS clause is skipped. Warns in log if headshot column is missing.

**Demo picker UX:** When dates are cleared via "Clear all", now shows `— all demos (run Preview to filter)` instead of blank, making it clear an empty picker means no filter (all demos included).

---

## [v176]

### Added: Victim's Mate POV feature

**What changed:** Record kills from the perspective of the victim's teammate with the best view of the action, instead of just following the victim.

**How it works:**
- At each kill tick, teammate positions and view angles are checked (`demoparser2` parse_ticks)
- Teammate qualifies if ≥2 of 3 body points (head/chest/legs) fall within ±45° of their look direction (≈50% body visible)
- Best teammate = smallest angle to kill point; active players excluded from consideration
- LOS is angle-based only (no BSP ray-cast available)

**Two modes:**
- **Optional** (default): Falls back to normal victim/both perspective if no qualifying teammate found
- **★ Must**: Drops clips with no qualifying teammate entirely

**UI:** New "Mate POV" row (Enable + ★ Must checkboxes) in **Capture & Timing** section, below Switch delay slider. Only visible when POV is Victim or Both (Killer mode has no victim phase).

**Camera wiring:**
- Victim mode: single camera target replaced by mate SID when available
- Both mode: victim-phase switch points to mate SID; killer phase unaffected

---

## [v175]

### Fixed: Weapons misclassified into "Other" category

**What changed:** CZ75-Auto and other weapons now appear in correct categories instead of getting lumped into "Other".

**Three-layer fix:**
1. **Prefix indexing** — `_WEAPON_LOOKUP` now stores keys with `weapon_` prefix (`weapon_cz75a`, etc.) so internal game names resolve directly
2. **Prefix stripping** — `_weapon_category` strips leading `weapon_` before lookup (e.g. `weapon_cz75a` → lookup `cz75a` → Pistols)
3. **Substring fallback** — `_WEAPON_SUBSTR_FALLBACK` maps substring variants to categories (`"cz75 auto"`, `"cz75_auto"`, etc. all → Pistols). Covers deagle, glock, usp, awp, etc.
4. **UI cleanup** — Unknown weapons silently skipped from render instead of grouped under confusing "Other" header

---

## [v174]

### Fixed and improved: UI responsiveness, filter reorganization, Both mode

**What changed:**
- Tab switching and window dragging no longer stutter
- WALLBANG and BLIND FIRE filters now run from database (faster)
- Both mode now shows correct POV at clip start
- Switch delay slider shows total clip duration

**UI responsiveness:** Two separate lag fixes:
- **Window drag momentum:** Removed `_on_splitter_release()` call from layout state save — sash snapping now only on actual drag (not after window moves)
- **Tab switching:** Added `<<NotebookTabChanged>>` binding to immediately flush scroll-frame widths when tab becomes visible (instead of 400ms delay)

**Filter reorganization:** WALLBANG and BLIND FIRE now run at database level (no demo parsing needed):
- **🧱 WALLBANG** → `kills.penetrated_objects > 0` (category: dp2 → mods)
- **😵 BLIND FIRE** → `kills.attacker_blinded` (category: dp2 → mods)
- **🪂 AIRBORNE** has no DB equivalent, stays in dp2
- Cleaner `_mod_sql_expr()` helper replaces dead special-case logic

**Both mode fixes:**
- **Wrong POV bug:** `_build_cams_both` was using last-processed kill's killer at start instead of first active player. Now `initial_sid` from `_seq_anchor_sid` is the true starting camera, never placed in timeline. Only switch events go in timeline (victim switches + killer returns)
- **Duration hint:** Added live **"total before: Xs"** label next to Switch delay slider showing sum of BEFORE + Switch delay

**Technical details:**
Window drag momentum was caused by `_remember_layout_state` debounce triggering reflow; now only happens on actual sash-drag. Both mode timeline deduplication fixed by first-write-wins dict (no overwrite).

---

## [v173]

### Fixed: Deathnotice player names show correct names from demo time, not current DB

**What changed:** Player names in CSDM deathnotices now show the names they had when the demo was recorded, not their current/latest name from the database.

**Technical details:**
- `_dp2_parse_demo` now parses player info as `"names"` cache section
- Names stored as `{steamid: name}` map (`demo_names`) in dp2 cache, per-demo
- `_dp2_required_sections` includes "names" so every demo gets minimal parse
- `_build_json` resolves names via `_name(psid)` helper: demo cache first, DB fallback. All `playerName` fields use this helper

---

## [v172]

### Fixed and improved: Theme system, console logging, preview export, resource management

**What changed:**
- Light mode (white theme) now has proper contrast and colors
- Console timestamps stamp each line correctly
- Preview results can be exported as HTML/TXT/JSON
- dp2_threads setting now actually controls core usage
- Ferrari Peek badge displays in correct position
- Injection preview tool shows exactly what gets injected

**Light mode overhaul:**
- White preset softened (`#f8f8f8`, `#e4e4e4`) to reduce harsh contrast
- New `_STATUS_COLOURS_LIGHT` dark-saturated palette for light backgrounds
- `_build_theme` auto-selects light colors when bg preset has `_is_light: True`
- Log tags reapply on theme change so dark↔white switching works correctly

**Console improvements:**
- Timestamps now per-line at write time (`[HH:MM:SS]` prefix in `_log`)
- Removed erroneous live ticking clock from header
- Toggle via **TS** button in log toolbar

**Preview export (📤 Export ▾):**
- **HTML** — standalone dark-themed file with per-clip table (date, demo, filters, tick, playdemo command)
- **TXT** — columnar table + `cmd:` line per clip
- **JSON** — structured array for scripting
- **Filters column** shows actual matched filters per clip (not just active config)

**Resource management:**
- Fixed dp2_threads not being respected — Rayon pool was using all cores regardless
- Set `RAYON_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` to "1" at import time
- Result: `dp2_threads = N` now means exactly N cores used

**Added: INJECTION PREVIEW (Tools tab)**
- Collapsible section below PERFORMANCE
- Shows exact args injected into CS2 for current config
- HLAE mode: full `extraArgs` token broken one-per-line
- CS mode: `launch_args` + each `console_cmds` entry
- **⟳ Refresh** button for manual update; auto-sizes (4–12 lines)

**UI fixes:**
- Ferrari Peek dp2_badge moved to main `_hv_row` frame (was hidden inside expandable)

---

### Fixed: Theme change retaining old colours on some widgets

Root cause: `_CHK_KW` and `_BTN_KW` are module-level dicts built at import time with default dark/green values. Any session started with a non-default saved theme would create those widgets (log filter radiobuttons, preset-type radiobuttons, weapon-category checkboxes, autoscroll toggle) with wrong colours. Subsequent `_change_theme` calls could not fix them because the colour_map was keyed on the current theme's values, not the stale defaults.

- **`_apply_theme_globals` now updates `_CHK_KW`/`_BTN_KW` in-place** on every call — startup and runtime both correct.
- **Colour-map collision detection**: if two theme keys share the same old hex value but map to different new values (e.g. amoled `BG == BG2 == #000000`), the ambiguous value is excluded from the generic map rather than producing wrong remapping.
- **`ScrollableFrame.apply_theme()`** added — explicitly sets canvas + inner frame `bg` to `_t("BG")`, bypassing colour_map ambiguity. Handled by `_walk` alongside `Sec`.
- **Log widget** bg changed from hardcoded `"#090909"` to `_t("LOG_BG")` at creation.

---

## [v171]

### Improved: Demo parsing performance and TrueView fallback, UI reorganization

**What changed:**
- Demo parsing is faster with better thread utilization
- TrueView failures now auto-retry instead of failing silently
- Settings sections reorganized for better logical grouping

**Demo parsing speedup:**
- Auto-scaled thread count: `dp2_threads` default now `min(8, max(2, cpu_count))` instead of hardcoded 2
- Better out-of-the-box utilization on multi-core machines
- Vectorized fire/hurt loops: replaced `for row in arr` with pandas `groupby`
- Pandas/numpy operations release GIL during computation, less UI stutter in background

**TrueView fix:**
- Old demos without TrueView cause CSDM CLI to output `Raw files not found`
- Previously logged as dim (non-error) line → no retry → appeared successful but wrong POV
- Now detected as error (logged red)
- If TrueView was ON: auto-retries that demo with `trueView: false` injected, falls back cleanly

**UI reorganization:**
- **"RESOLUTION & FRAMERATE"** → **"RESOLUTION, FRAMERATE & WINDOW"**
- Window mode + Send to back on launch moved from "CS2 EFFECTS" (was wrong logical grouping)
- **Close CS2 after demo** moved from "FINAL ASSEMBLY" to **"IN-GAME OPTIONS"** (controls process behavior, matches TrueView/death notices/X-Ray)

---

## [v170]

### Fixed: Resize and drag interactions still laggy despite debounce

**What changed:** Two-tier resize strategy eliminates reflows mid-interaction while preserving OS-resize support.

**Two-tier approach:**
- **Mouse-driven (sash drag, in-app):** Global `<ButtonRelease-1>` handler flushes all pending canvas width + wraplength updates exactly once on release — zero reflows during drag
- **OS window-border resize:** 400 ms debounce fallback (Tkinter doesn't receive ButtonRelease for OS chrome)

**Technical details:**
50 ms debounce was too short — reflows still triggered mid-drag. `_WRAP_LABELS` registry added: all wraplength-registered labels flushed on release alongside `ScrollableFrame` width updates.

---

## [v169]

### Fixed: Window resize and sash drag cause lag during interaction

**What changed:** Debounced reflow cascade so UI stays responsive during window resizing and sash dragging.

**Problem:** Every pixel of resize triggered synchronous cascade:
```
canvas <Configure> → itemconfigure(inner, width)
  → inner <Configure> → bbox("all") + scrollregion
    → every desc_label <Configure> → wraplength update
```

**Fixes:**
1. **ScrollableFrame debounce:** Canvas `<Configure>` now debounces inner-frame width sync to 50 ms. Entire cascade (reflow + child events) suppressed during drag, fires once when stops
2. **Scrollregion optimization:** Replaced `bbox("all")` traversal with direct Configure event `(0, 0, e.width, e.height)` — O(1) instead of walking all items
3. **Label wraplength:** Debounced to 50 ms via `_bind_wraplength` helper. Codec description labels (`_vcodec_desc`, `_acodec_desc`) share same helper — no duplicate binding

---

## [v168]

### Fixed: Scroll wheel and sash dragging fighting geometry manager

**What changed:**
- Mouse wheel scroll now works on all tabs (not just Capture)
- Sash dragging no longer fights window geometry manager

**Scroll fix:** All `ScrollableFrame` canvases share same screen coords inside `ttk.Notebook`. `contains_point` check was matching all — `_SCROLL_FRAMES[0]` (Capture) always won. Added `winfo_viewable()` guard: returns True only when canvas AND all ancestors mapped (current tab only).

**Sash fix:** `pack_propagate(False)` + `configure(width=N)` made frames fight `ttk.PanedWindow` geometry manager on every drag. Removed both. Minimum size now enforced correctly: `_on_splitter_release` snaps sash to clamped position after drag ends (sashpos reapplied), no interference during

---

## [v167]

### Fixed and improved: Scroll behavior, pane sizing, UI helpers

**What changed:**
- Mouse wheel scroll works on all tabs from first render
- Content fills tab width correctly on resize
- Log pane no longer collapses, console pane collapsible
- UI helper layer refactored to reduce duplicate code

**Scroll fix:** Previous Enter/Leave + recursive _bind_children machinery only worked when mouse physically entered canvas (never happens clicking tab headers). Solution: removed Enter/Leave, added module-level `_SCROLL_FRAMES` registry + single global `bind_all("<MouseWheel>", _global_wheel)` handler. Finds frame under cursor and scrolls it. Text/Listbox/Scale/Treeview widgets excluded (preserve native scroll).

**Content width:** `ScrollableFrame` wasn't resizing inner frame to match canvas width. Added `<Configure>` binding calling `itemconfigure(win_id, width=e.width)`.

**Pane sizing:** `ttk.PanedWindow` had no minimum pane sizes — sash could hide notebook completely. Both panes now have `pack_propagate(False)` constraint preventing collapse.

**UI helpers (DRY):**
- `_sep(parent, pady, padx)` — replaces 12 inline Frame separator calls
- `_chk_tip(parent, label, var, tip, …)` — replaces `hchk + pack + add_tip` 3-liners
- Dynamic `desc_label` with `<Configure>` binding sets `wraplength = max(200, widget_width - 10)` (was hardcoded 700)

---

## [v166]

### Fixed and improved: Match type filtering compatibility, major code cleanup

**What changed:**
- Match type filter now handles both old and new CSDM database formats
- ~180 lines of dead code and duplicate logic removed
- 6 JSON persistence functions replaced with 2 generic helpers
- 11 identical filter wrapper methods eliminated

**Match type fix:** CSDM stores competitive/wingman under different names depending on version (`scrimcomp5v5` vs `competitive`). Databases built with different CSDM versions would silently skip those types. Now: `MATCH_TYPE_DEFS` carries `db_values: list` (not single string). SQL builder flattens into `IN (…)` clause matching both spellings. Tooltip and visibility checks also updated.

**Code cleanup — DRY:**
- `_load_json` / `_save_json` — 6 persistence functions → 2 generic helpers (load_presets, save_presets, etc. now one-liners)
- `_make_highlight_toggle` — shared trace closure extracted from duplicate hchk/hradio logic (~20 lines saved)
- `_cfg_num` — generic numeric reader (cfg_int/cfg_float are thin wrappers)
- `_page_count()` — helper replacing 4 repeated `max(1, (len + ps - 1) // ps)` expressions
- `_validate_run_inputs()` — guard extracted from _run and _dry_run
- `_apply_theme_globals` — replaced 13 manual `global X = _THEME[X]` with loop

**Dead code removed:**
- `_engage_trois_tap`, `_disengage_trois_tap` — no-op methods
- `_on_tag_selected` — never called
- `_refresh_tag_combo` — pass method + 3 call sites
- `_on_trois_tap_toggle`, `_on_one_tap_toggle` — no-op pass methods
- Full HS-lock chain: `_hs_only_is_required` → `_refresh_hs_lock_state` → `_install_hs_lock_watchers` → `_lock_hs_to_only` → `_unlock_hs` (entire unused chain)
- 11 `_apply_*_to_events` one-liner wrappers (all identical delegates; preview path now builds inline lambdas)

---

### Fixed and improved: Widget trace crashes, settings organization, physics timing

**What changed:**
- Fixed crash when theme changes after DB reconnect
- Close CS2 moved to correct settings section
- Corpses no longer fall in fast-motion during recording

**Widget trace crash:** `_refresh_match_type_ui` destroys/recreates checkbox children on every DB connect. But `var.trace_add("write", _update)` closures survived destruction. On next BooleanVar change (theme change, etc.), stale `_update` tried `.config()` on destroyed widget → TclError crash. Fix: `_safe_trace_remove(var, mode, tid)` helper + winfo_exists() guard + `<Destroy>` binding. Self-cleaning regardless of rebuild frequency.

**Settings reorganization:** "Close CS2 after demo" was under RECORDING SYSTEM (wrong — that covers codec/mode). Moved to top of FINAL ASSEMBLY with divider. Correct semantics: closing CS2 is batch-flow concern, not recording-system setting.

**Physics timing:** CS2 inherits residual `host_timescale` from previous session, causing ragdolls to simulate faster. Symptom: corpses fall unnaturally fast. Fix: `demo_timescale 1` now first command in `_common_cs2_injection` (both HLAE and CS mode), resets playback speed to 1× before any physics commands. Tooltip updated with workaround: unchecking `cl_ragdoll_physics_enable` freezes corpses instead.

---

## [v164]

### Fixed and added: Clutch detection in Wingman, match type filtering, cleanup robustness

**What changed:**
- Clutch detection no longer triggers false positives in Wingman
- New match type filter lets you filter by game mode
- Empty folders left behind after clip assembly are now cleaned up properly
- "Tools" tab renamed to "Settings"

**Clutch fix:** Clutch detection built alive-set from kill log only (killer/victim). In Wingman (2v2), a teammate who hadn't killed/died yet was absent → code thought team was alone → false clutch on every round. Fix: `_fetch_all_kills_for_demos` runs second query against `players` table to get per-team roster counts. `_apply_clutch_filter` injects synthetic ghost players (`__ghost_<team>_<i>__`) for unaccounted slots. Best-effort (no crash if players table lacks columns).

**Match type filter:** New **MATCH TYPES** section in Capture & Timing (hidden by default, appears after DB connects). Filter by: 🏆 Premier, 🎯 Competitive, 🤝 Wingman, 🎮 Casual, 💀 Deathmatch, 🎓 Training, 🔫 Arms Race, 💣 Demolition, 🤖 Co-op, ⚡ Skirmish, ↩ Retakes. Master toggle (off = no SQL overhead). Only types in your DB shown (no phantom checkboxes).

**Folder cleanup:** Two bugs fixed:
1. **Wrong root guard** — compared paths against legacy `output_dir` instead of `output_dir_clips`
2. **No upward traversal** — only checked immediate parent, left empty intermediate folders

Solution: `_try_remove_dir(d)` recursive upward walker stops at root or non-empty directory. `visited` set prevents double-visits.

**UI:** "Tools" tab renamed to "Settings"

---

## [v163]

> Internal version bump — no documented changes. Shipped as the baseline before the v164 session.

---

## [v162]

### Fixed and improved: UI button visibility, demo picker, player names, Workshop DL

**What changed:**
- Stop/Kill buttons now visibly light up during recording
- Map column shows up in demo picker correctly
- Death notices show correct player names (not old aliases)
- Auto Workshop DL loads correct map version
- Encoder field removed (always FFmpeg anyway)

**Button visibility:** `_run()` was setting `state="normal"` but leaving `fg=MUTED` → buttons greyed out even while active. Now both get `fg=RED` on activation, reset by `_reset_btns()`.

**Map column bug:** `_map_col` detected inside kills query block but evaluated *after* `map_sel` constructed → always `""` on first query → map column never fetched. Detection moved to before `_build_dsql`, ensuring column included from first query.

**Player names:** `_player_names` used `GROUP BY p.name, p.steam_id ORDER BY p.name` which surfaced arbitrary historical name when player had multiple entries. Changed to `DISTINCT ON (p.steam_id) … ORDER BY steam_id, last_seen DESC NULLS LAST` — now only most recent name per SID.

**Workshop DL fix:** Was using `+cl_downloadfilter all` which downloads current published version from CDN (may be different map entirely). Now uses `+sv_pure 0 +sv_lan 1`: sv_pure 0 disables file validation (loads local version), sv_lan 1 blocks external verification. Requires old map already cached locally. Tooltip updated.

**UI cleanup:** Encoder selector removed from RECORDING SYSTEM (was always "FFmpeg", no alternatives). `encoder` key still written to JSON for compatibility; only System (HLAE/CS) radio buttons shown.

---

## [v161]

### Added: Exclude option on every kill filter

Every kill filter now has an **Exclude** checkbox alongside Enable and ★ Must. Exclude removes all kills that match the filter from results, the inverse of Enable. Enable and Exclude are mutually exclusive per filter — turning one on clears the other. Exclude also clears ★ Must when activated.

**What it means in practice:**

- `💨 SMOKE: Enable` → keep only smoke kills
- `💨 SMOKE: Exclude` → keep everything *except* smoke kills
- Both can be combined with other filters: `🧱 WALLBANG: Enable` + `😵 BLIND FIRE: Exclude` → wallbang kills that are not blind-fire

**UI:** The Exclude hchk appears on every filter row, consistent position after ★ Must. TROIS SHOT's pre-existing Exclude (formerly "no_trois_shot") is folded into the same position. Preview header shows `🚫 badge` for excluded filters. Clip badges show `[🚫badge]` in amber. The "Unselect all" button clears Exclude flags alongside Enable and ★ Must.

**Pipeline — where each category's exclusions are applied:**

| Category | Mechanism |
|---|---|
| **SQL Mods** (SMOKE, NO-SCOPE, VICTIM FLASHED) | `AND NOT col IS TRUE` appended directly to the kills SQL WHERE clause — zero Python overhead, database handles it |
| **dp2 filters** (WALLBANG, AIRBORNE, BLIND FIRE, COLLATERAL, TROIS SHOT, ONE TAP, SPRAY TRANSFER, FERRARI PEEK, FLICK, SAVIOR) | Excluded filters run first on the full kill list; matching kill signatures are collected and stripped before any positive filter runs. Applies in both the batch worker path (`_apply_dp2_modifiers`) and the preview/redo path (`_apply_dp2_filters_to_events`) |
| **DB post-filters** (ENTRY FRAG, ACE, MULTI-KILL, BULLY, ECO FRAG) | Exclusion sig-sets built from the same per-round group logic used for positive detection, then subtracted from `keep_sigs`. Works in all three logic modes (ANY/ALL/MIXED). Exclusion-only mode (no positive filter active, only exclusions) is handled — starts from all kill sigs and subtracts |

Excluded kills are stripped upstream, so `_apply_global_filter_gate_events` naturally ignores them — no changes needed there.

**Technical details:**

- `_NO_AUTO_EXCLUDE` set at module level: `kill_mod_no_trois_shot` (already has its own mechanism) and `kill_mod_trois_tap` (always a positive-only filter) are excluded from auto-generation
- `_FILTER_CONFIG_DEFAULTS`, `_FILTER_BOOL_KEYS`, and `_FILTER_PRESET_PLAYER_KEYS` all auto-derive `key_exclude` entries from the registry loop — adding a new filter in `KILL_FILTER_REGISTRY` automatically gets an Exclude option with no extra code
- `_clear_kill_filters` clears all three suffixes (`""`, `"_req"`, `"_exclude"`) in one loop

---


## [v160]

### Fixed: demo compatibility warning — correct CS2 breaking updates

The previous implementation (v159) was wrong on two levels: it checked for CS:GO `HL2DEMO` headers (which never appear in CSDM's CS2-only database), then switched to an age-based heuristic (also wrong — CS2 demo compatibility has nothing to do with file age).

The correct behaviour: CS2 has had specific **hard breaking engine updates** that make all demos recorded before them completely unplayable on any current CS2 version, regardless of age. These are not gradual; they are binary breaks.

**Known hard breaks now encoded in `_CS2_DEMO_BREAKS`:**
- **July 28 2025 — AnimGraph2**: Valve replaced the entire animation engine with AnimGraph2. Every demo recorded before this date is broken on CS2 ≥ 1.40.8.9. Workaround: downgrade CS2 via Steam beta depot to ≤ 1.40.8.8.
- **February 6 2024 — major format update**: The demo file format changed substantially, breaking parsers and causing playback crashes on all subsequent CS2 versions.

`_check_demo_compat(demo_path)` is now an instance method (uses the existing cached `_get_demo_ts`) that checks the demo's recorded timestamp against each break's cutoff date, newest-first. Returns `{'status': 'ok'|'warn'|'missing', 'break': label, 'tip': explanation}`. Adding future breaking updates is one entry in `_CS2_DEMO_BREAKS`.

Warned demos appear yellow in the picker. Hovering shows a popup naming the breaking update and explaining the workaround.

### Added: map column fetched in rounds query and manual mode

The map name is now populated from all three query paths (kills, rounds, manual mode picker), not just kills. Manual mode uses a `_find_col` lookup as a local fallback if `_map_col` hasn't been detected yet (e.g. when opening the picker before running a preview).

---

## [v159]

### Added: player list — full page navigation

The pagination bar now has four buttons instead of two:

- **◀◀** — jump to page 1
- **◀** — previous page
- **`[N]`** — direct page entry (editable, press Enter or Tab to jump). Syncs automatically with every page change. Invalid input resets to the current page.
- **▶** — next page
- **▶▶** — jump to last page

The label beside the entry shows `/ 14  (110)` (total pages, total count). All far buttons disable and go muted when already at the boundary.

### Added: demo picker — map column

A **Map** column (80 px, non-stretching) appears between Date and Demo in the treeview. The map name is fetched from the `matches` table via `_find_col` against `["map_name", "game_map", "map", "level_name", "server_map"]`. Common CS2 map prefixes (`de_`, `cs_`, `ar_`, etc.) are stripped for brevity. The column is populated in the kills SQL query (no extra round-trip), also in the rounds query and manual mode picker. The cache (`_demo_map_cache`) clears on DB reconnect; `_map_col` re-detects automatically.

### Added: demo picker — CS2 compatibility warning (initial, superseded by v160)

> Note: the HL2DEMO/age-based approach in v159 was incorrect. See v160 for the correct implementation.

---

## [v158]

### Changed: UI revamp — collapsible sections, unified spacing, redesigned chrome

**`Sec` — collapsible section cards.** Every section (PLAYER, CAPTURE & TIMING, KILL FILTERS, etc.) is now a collapsible card. Clicking the header collapses or expands the body. The header has a 3 px orange left accent stripe, bold title, and a `▾`/`▸` toggle arrow. `Sec` is a drop-in replacement for the old `LabelFrame` — all existing widget creation code is unchanged.

**UI spacing constants.** Six `UI_*` constants at the top of the module replace all hardcoded padding values. `UI_SEC_PADX = 14`, `UI_SEC_PADY = 8`, `UI_SEC_GAP = 6` apply uniformly to every section on every tab. The tab scroll inner frame uses `padx=0` so sections fill edge-to-edge. All 25 individual `sec.pack(pady=(...))` calls were stripped — the `Sec.pack()` default handles it.

**Header bar.** Replaced the `" >> " CSDM  Batch vXXX` row with a clean `BG2` bar, 4 px orange left stripe, compact DB status on the right.

**Run bar.** Two-px orange accent line at top. `▶ RUN` (accent bg) | divider | `🔍 Preview` (blue) | divider | `⏸ Stop` / `⛔ Kill` (muted until active). Summary line separated by 1 px border.

**Log panel.** Left accent stripe matches sections. Tighter filter controls.

**Sliders.** Value label uses bold Consolas in ORANGE, fixed-width, right-aligned.

**`hchk` / `hradio`.** `padx` 8→10, `pady` 3→4 — slightly more pill breathing room.

**Theme walker.** `_apply_theme_to_widgets` calls `sec.apply_theme()` on every `Sec` instance it encounters, so collapsible header colours update correctly on theme change.

---

## [v157]

### **🎯 CLUTCH — Complete rewrite. The previous implementation was not functional.**

The clutch feature existed in the codebase since v82 but had been rewritten, patched, and re-patched across more than a dozen versions without ever reaching a working state. This version replaces the entire mechanism from scratch with a clean, reliable implementation.

**What changed for users:**

- Clutch detection now actually works. Enable the 🎯 CLUTCH toggle, pick your size filter (1v1 to 1v5), choose **Kills only** or **Full clutch** mode, optionally check **Wins only** — and you get clips.
- **Kills only** — one clip per kill made during the clutch, using the normal Before/After window. Same behaviour as the regular Kills capture, but restricted to the clutch phase only.
- **Full clutch** — one continuous clip from the exact tick you became last alive until the last kill of the round. Before/After sliders are ignored; the clip spans the entire clutch sequence.
- Size filter: leave all boxes unchecked to capture every clutch, or check specific sizes (1v1, 1v3, etc.) to restrict.
- **Wins only**: only rounds where you killed all remaining opponents are included.
- Clutch is stackable with all other kill filters — other filters narrow the kill set first, clutch restricts to the clutch phase last.

**Technical details:**

The old implementation tried to infer team state from which players appeared as killers in the kills table — missing teammates who hadn't made a kill yet. It also had a separate `_query_clutch_events` DB function with round-bracket logic, side normalisation bugs, winner column detection issues, and was tightly coupled to a `clutch_group` field that multiple downstream filter stages silently dropped.

The new implementation:

- Is a **pure post-query filter** (`_apply_clutch_filter`) applied after all existing DB filters inside `_query_events`. No schema changes. No new DB queries beyond one all-kills fetch per batch.
- Fetches all kills for all relevant demos in one SQL query (`_fetch_all_kills_for_demos`), groups them by round using `round_number` if available or a tick-heuristic fallback.
- Walks kills chronologically per round, maintains a per-team alive-set, and detects the exact tick when the tracked player becomes last alive. Records clutch size and whether the player won.
- Handles DB schemas with or without team/side columns. Without team data, falls back to a SID-set heuristic (player's SIDs vs everyone else).
- Stores `round_tick_min`/`round_tick_max` per clutch window to resolve round-key mismatches between the all-kills query (which may have `round_number`) and the main kills query (which does not).
- `_build_sequences` patched to honour `_seq_start_tick`/`_seq_end_tick` overrides on events, enabling exact-boundary full-clutch clips without touching the Before/After sliders.
- Fully removable: integration points are a guarded call in `_query_events`, an `if/else` branch in `_build_sequences` (safe when keys absent), and a badge branch in `_build_clip_badges`. None break if the clutch block is deleted.

---

### Renamed: "Full round" → "Full clutch"

The old label implied the clip covered the entire CS round (up to 115 seconds). It covers the clutch phase only. Renamed everywhere: UI radio button, config value (`"full_clutch"`), log headers, docstrings.

---

### UI: CAPTURE and TIMING sections merged into CAPTURE & TIMING

Two adjacent sections with tightly related settings merged into one, reducing scrolling and visual noise.

---

### Fixed: ROUNDS capture not working

`cfg["events_rounds"]` was a direct dict key access inside `_query_events`. A missing key (config loaded from disk before the Rounds toggle existed) raised a `KeyError` silently swallowed by `except Exception: pass` — no rounds, no error. Changed to `cfg.get("events_rounds")`. Same fix applied to `cfg["events_kills"]` and `cfg["events_deaths"]`.

---

### Fixed: pre-existing crash in `_worker` — `seqs` was unreachable dead code

`seqs = self._build_sequences(...)` and `t0_seq = time.time()` were placed inside the `if events is None: ... continue` block — completely unreachable. Yet `seqs` and `t_seq` were used immediately after, causing `NameError` on every demo with events. Moved to the correct position after the guard.

---

### Improved: player list pagination

The DB search listbox previously showed 4 rows — all players were loaded but almost none were visible. Replaced with an 8-row paginated display:

- **◀ / ▶** buttons navigate pages.
- `p.2/14 (110 total)` label shows current position.
- Searching always resets to page 1.
- `_select_by_label` jumps to the correct page automatically.
- `_on_lb_select` maps listbox row index to the correct absolute position in the full filtered list.

---

### Fixed: already-tagged demos — picker not updated on "No" answer

Choosing **No** in the already-tagged dialog correctly skipped those demos but left them checked (✓) in the picker. On the next Run they were queued again.

Both **No** and **Cancel** now call a shared `_uncheck_in_picker()` helper that unchecks the already-tagged demos immediately, updates row visuals (✕, greyed text), and refreshes the selection counter. **Yes** leaves the picker unchanged.

---

## [v156]

### Fixed: `_build_clip_badges` — `[ROUND]` badge `NameError` if clutch removed

The `[ROUND]` condition referenced `clutch_events` by name. If the clutch block were deleted, this would raise `NameError`. Rewritten as `not (kill_events or death_events or clutch_events)` — removing clutch terms reduces naturally to the original condition without a dangling name.

---

## [v155]

### Fixed: already-tagged dialog — duplicate inner functions

Cancel and No branches each defined identical `_uncheck_tagged` / `_uncheck_skipped` inner functions. Deduplicated into one `_uncheck_in_picker(paths)` helper called from both.

---

## [v154]

### Added: clutch filter wired into `_query_events`; config keys, UI, and preset support

Clutch filter runs after `_apply_db_postfilters`, gated behind `cfg.get("clutch_enabled")`. Config keys: `clutch_enabled`, `clutch_wins_only`, `clutch_mode`, `clutch_1v1`–`clutch_1v5`. All clutch keys in `PRESET_KEYS["player"]`. UI: master toggle, Wins only, Kills only / Full clutch radio, 1v1–1v5 checkboxes, greyed sub-controls when master is off.

---

## [v153]

### Added: `_fetch_all_kills_for_demos` and `_apply_clutch_filter`

Core clutch detection methods. Both are self-contained and zero-overhead when `clutch_enabled` is False.

### Fixed: `_build_sequences` — `_seq_start_tick`/`_seq_end_tick` override support

Events carrying these keys use them directly as clip boundaries. Normal events (keys absent) hit the unchanged `else` branch.

---

## [v152] *(was v143.8)*

### Fixed: clutch — zero results with TEAM_A / TEAM_B format

`_norm_side("TEAM_A")` returned unrecognised value → hardcoded fallback `"T"` → no victim matched. Fix: detection reads raw `killer_team_name` as `player_team`, classifies by direct string equality. Works for CT/T, TEAM_A/TEAM_B, any scheme.

**Validated:** 23 true 1v3 clutches found across 310 matches, 13 remaining after Win Only.

---

## [v151] *(was v143.6)*

### Fixed: clutch size always reported as 1v5

`op_team_sz − dead_before` = 5 when player kills all opponents alone (deaths happen after last-alive tick, so `dead_before = 0`). Fix: `clutch_size = len(opponent_death) − dead_before`.

---

## [v150] *(was v143.5)*

### Fixed: correct timeline-based last-alive algorithm

Old algorithm required all 4 teammates dead before the player's **first kill** — wrong if the player kills before teammates die. New: `last_alive_tick` = tick of (N−1)th teammate death. Player confirmed in clutch if they have at least one kill strictly after `last_alive_tick`.

---

## [v149] *(was v143.4)*

### Fixed: diagnostic logging; TROIS SHOT/ONE TAP/TROIS TAP decoupled; HS auto-lock removed

Step-by-step diagnostic logging in `_query_clutch_events`. Three dp2 filters made fully independent — automatic coupling removed. Headshot mode always user-controlled.

---

## [v148] *(was v143.3)*

### Fixed: `_norm_side` NameError; missing victim_side inference

`_norm_side()` defined in Step 5, called in Step 2b → `NameError` swallowed silently. When `victim_team_name` absent, `v_side` inferred as opposite of `k_side` (CT↔T).

---

## [v147] *(was v143.2)*

### Fixed: clutch — clean-room rewrite; scroll bugs fixed

New team-size-aware last-alive algorithm using victim deaths only. Peak unique victim SIDs per side infers team size. `bind_all("<MouseWheel>")` replaced with per-widget bindings; scroll on log console and demo list restored.

---

## [v146] *(was v143.1)*

### Fixed: clutch events dropped by four filter stages

Systematic audit: `_apply_global_filter_gate_events`, `_apply_filter_to_events`, `_union`/`mixed` merge loops, and all dp2 worker logic modes all silently dropped clutch events. Fixed in all cases: clutch events separated before logic, unconditionally re-appended at every exit point. `_stamp_mf` skips clutch events.

---

## [v145] *(was v143.0)*

### Fixed: clutch false positives — invisible teammates; configurable ONE TAP window

`all_teammates` built from victims only → teammate who killed but hadn't died was invisible. Fix: includes anyone on player's side appearing as killer **or** victim. `kill_mod_one_tap_s` config key (default 2s) replaces hardcoded tick window.

---

## [v144] *(was v143.0 base)*

### Fixed: clutch 1v0 artefact; require_win as ★ Must

Unconditional `if clutch_size < 1: continue` guard added. Data artefacts (empty round, missing DB rows) always discarded regardless of size filter setting.

---

## [v143] *(was v133.42)*

### Fixed: 1v0 clutch artefact included in "all sizes" mode

`allowed_sizes` empty (all-sizes mode) skipped the size filter → `clutch_size = 0` logged as valid.

---

## [v142] *(was v133.41)*

### Fixed: `require_win` silently ignored when rounds table unavailable; `_norm_side` maps win_reason values

Empty `round_brackets` → `round_winner = None` → guard never fires → Win Only did nothing. `_norm_side` now maps `ct_win`, `bomb_defused`, `t_win`, `target_bombed`, etc.

---

## [v141] *(was v133.40)*

### Fixed: clutch clips never generated when Kills + Clutch both active

Deduplication sig-set dropped clutch versions of kills that already existed. Replaced with `sig→index` dict; existing events stamped with clutch fields in-place.

---

## [v140] *(was v133.39)*

### Fixed: clutch header colour; scroll stops on child widgets; clutch events dropped by `_apply_db_postfilters`

Clutch header used `mlabel` (gray) instead of `slabel` (accent). `<Leave>` checks pointer position before unbinding. `_apply_db_postfilters` now separates and re-appends clutch events unconditionally.

---

## [v139] *(was v133.38)*

### Fixed: `KeyError: 'kill_mod_hv_one_shot'` on startup

Sub-option bool in `extra_config` not in `_FILTER_BOOL_KEYS` → no `BooleanVar` created. `bool_keys`/`int_keys` now auto-derive sub-option entries from `extra_config` fields.

---

## [v138] *(was v133.37)*

### Architecture: Kill Filter Registry

Single `KILL_FILTER_REGISTRY` of `FilterDef` NamedTuples. Kill filter UI: ~340 → ~130 lines (−62%). Adding a filter = one `FilterDef(...)` entry.

---

## [v137] *(was v133.36)*

### Changed: demo picker rework; UI polish

Native multi-select + **✓ Check selected** / **✕ Uncheck selected** buttons. dp2 badge always at far right. Filter name labels use `flabel`, section headers use `slabel`.

---

## [v136] *(was v133.35)*

### Fixed: DB connection leak; SyntaxError from prior session

`try/finally: conn.close()` in `_connect_and_load`. Indentation error repaired.

---

## [v135] *(was v133.34)*

### Fixed: OOM crash on large batches; log widget growing unbounded; tempfile cleanup

LRU eviction on dp2 cache (max 150 demos). `_LOG_MAX_LINES = 8000`. Tempfile `os.path.exists` check moved inside lambda.

---

## [v134] *(was v133.33)*

### Changed: "Minimize on launch" → "Send to back on launch"

`SetWindowPos(HWND_BOTTOM)` instead of minimize. Config key: `cs2_minimize` → `cs2_send_to_back`.

---

## [v133]

### Fixed: camera/player targeting for multi-player batches

Active player order deterministic. Sequence anchor targets first relevant active player.

---

## [v132]

### Fixed: regression rollback in global filter gate

Kill-filter gating restored to kill-event-only enforcement.

---

## [v131]

### Fixed: filter gate applied to KILLS and DEATHS; CS2 minimize once per batch

---

## [v130]

### Fixed: `hlaeOptions` always included in HLAE recording payload

---

## [v129]

### Fixed: recording system normalisation hardening

---

## [v128]

### Fixed: collateral over-detection — stricter same-shot validation

---

## [v127]

### Fixed: wallbang/collateral semantic split; dp2 death-flag helper DRY refactor

---

## [v126]

### Fixed: per-demo filter badges fail-closed — no false-positive tagging when dp2 evidence missing

---

## [v125]

### Fixed: global non-★ OR semantics — adding a filter expands results, not narrows

---

## [v124]

### Changed: logic mode selectors removed; fixed model always used

---

## [v123]

### Fixed: `🚫🎲 Exclude` acts as exclusion gate first in combined scenarios

---

## [v122]

### Added: kill filters "Unselect all" button

---

## [v121]

### Changed: "DEATHS BY" tooltip updated

---

## [v120]

### Changed: unified kill filters logic selector; DB modifiers under Situation

---

## [v119]

### Fixed: headshots auto-lock context-aware

---

## [v118]

### Changed: dp2 pre-parse section-aware; `_dp2_required_sections(cfg)` as single source of truth

---

## [v117]

### Fixed: AT LEAST ONE logic across Mods + dp2 — cross-engine OR union

---

## [v116]

### Fixed: Enable + ★ Must conflict — `_wire_enable_must` bidirectional coupling

---

## [v115]

### Fixed: UI freeze during dp2 pre-parse (batched log pump, 50ms drain); WALLBANG/AIRBORNE/BLIND/COLLATERAL skipped during pre-parse

---

## [v114]

### Added: MIXED logic mode; ★ Must checkboxes; `_split_required_optional` DRY helper

---

## [v113]

### Removed: "Output: video" radio (hardcoded). Fixed: accent button colour on theme switch.

---

## [v112]

### Fixed: WALLBANG/AIRBORNE/BLIND FIRE/COLLATERAL via demoparser2 `player_death` fields

---

## [v111]

### Added: UI theme system — background presets, accent presets, custom hex, persists across sessions

---

## [v110]

### Fixed: "Modifiers not found" warning fires at most once per session per unique missing set

---

## [v109]

### Changed: headshots filter — tri-state radio (All/Only/Exclude), independent of Mods

---

## [v108]

### Fixed: clip badges per-kill accurate; `_mf` tagging across all three filter stages; `_DP2_FILTER_DEFS` single source of truth

---

## [v107]

### Changed: filter context badges appended after content badge; `_FILTER_BADGE_DEFS` DRY

---

## [v106]

### Changed: clip badges content-aware; structured multi-line preview header

---

## [v105]

### Added: logic mode selector per kill filter category; `_apply_dp2_filters_to_events` DRY

---

## [v104]

### Changed: DRY demo log entry builders (Preview and Run share same rendering)

---

## [v103]

### Fixed: preview log shows clip badges

---

## [v102]

### Added: resizable UI layout (window size, split %, Remember layout)

---

## [v101]

### Added: log badge indicators; `Badges: ON/OFF` toggle (Ctrl+B)

---

## [v100]

### Changed: VirtualDub and image export modes removed; output hardcoded to video

---

## [v99]

### Added: CS mode vanilla injection; Steam library autodetection; Game Speed % slider; strict config parsers

---

## [v98]

### Fixed: Ferrari Peek approach window 3s → 1s

---

## [v97]

### Changed: section names (CAPTURE / KILL FILTERS / TIMING / DEMO SELECTION); Mods per-line layout

---

## [v96]

### Fixed: demo picker double-toggle; clutch options placement; player sort by name/date

---

## [v95]

### Changed: Ferrari Peek — three-condition logic (isolated shot, moving before, resumes after)

---

## [v94]

### Changed: Stop/Kill refactor with tag rollback; event styled toggle buttons; SAUVEUR → SAVIOR

---

## [v93]

### Changed: clutch custom range removed; Blind Fire into Mods row; BOURREAU → BULLY; `dp2_badge()` DRY

---

## [v92]

### Added: 9 new kill modifiers (Entry Frag, Ace, Multi-Kill, Bully, Eco Frag, Blind Fire, Ferrari Peek, Flick, Sauveur)

---

## [v91]

### Fixed: `_effective_before` perspective leak; "Full round" → "Full clutch" (first attempt)

---

## [v90]

### Changed: header active player label mirrors Capture tab in real time

---

## [v89]

### Performance: `_ts_cache`, `_col_cache`, persistent DB connection, sort removal, `_spray_transfer_filter` O(shots); last French strings translated

---

## [v88]

### Performance (preliminary): same as v89 core optimisations, first introduced here

---

## [v87]

### Added: 🔫 Spray Transfer; Demo picker with Manual mode; TROIS SHOT weapon lock removed

---

## [v86]

### Fixed: stale DEFAULT_CONFIG comment; inaccurate recording system tooltip

---

## [v85]

### Changed: clutch detection rewritten — real last-alive detection using all kills per match

---

## [v84]

### Fixed: `clutch_require_win` was a stub; side normalisation for all CT/T schema variants

---

## [v83]

### Fixed: CS2 EFFECTS not injected in CS recording mode

---

## [v82]

### Added: 🤝 CLUTCH mode — initial implementation (grouped kills, later corrected)

---

## [v81]

### Fixed: inaccurate CS mode tooltip

---

## [v80]

### Fixed: incorrect CS mode descriptions (startmovie, not interactive)

---

## [v79]

### Added: Fix scope FOV checkbox (`+mirv_fov handleZoom enabled 1`)

---

## [v78]

### Fixed: CS/HLAE UI bleed; HLAE section hidden in CS mode; extended per-demo logging

---

## [v77]

### Changed: demoparser2 architecture — single parse entry point, partial persistent cache, unified key scheme

---

## [v76]

### Fixed: ONE TAP / TROIS TAP always returned 0 — weapon-specific shot index

---

## [v75]

### Added: `_one_tap_filter`, `_no_trois_shot_filter`, `_trois_tap_filter` implemented; full English translation

---

## [v74]

### Added: TROIS TAP auto-toggle; DP2 threads slider; per-demo parse cache; tag selection persisted; full UI English translation

---

## [v73]

> Included in v74 — never shipped standalone.

---

## [v72]

### Fixed: "Both" perspective — `victim_pre_s` not counted in clip duration

---

## [v71]

### Changed: cumulative dp2 modifiers — `elif` chains → independent `if` blocks

---

## [v70]

### Changed: POV Victim simplified; "Both" takes over killer→victim transition logic

---

## [v69]

### Added: `APP_VERSION` constant; POV Victim rework with `victim_pre_s`

---

## [v68]

### Added: NO LUCKY SHOT; LUCKY TAP; Minimize watcher simplified

---

## [v67]

### Removed: `stop_guard_event`

---

## [v66]

### Added: ONE TAP modifier (demoparser2); tickrate removed from UI

---

## [v65]

### Fixed: LUCKY SHOT thresholds recalibrated (old values unreachable in real data)

---

## [v64]

### Fixed: LUCKY SHOT — `user_` prefix, match window, matching logic

---

## [v63]

### Fixed: LUCKY SHOT unchecks weapon category; preview applies TROIS SHOT in background thread

---

## [v62]

### Added: LUCKY SHOT modifier (demoparser2) — initial implementation

---

## [v61]

### Fixed: Minimize on launch briefly shows CS2; polling 500ms → 100ms; 60s timeout

---

## [v60]

### Changed: Resolution & Framerate — definition × ratio × custom free entry

---

## [v59]

### Fixed: modifier not found in DB — fail-closed (returns empty, not all clips)

---

## [v58]

### Added: Tags TAG RANGE section (Calculate range, Apply start/end, Full, After)

---

## [v57]

### Fixed: 📅 uses config ∩ tags intersection

---

## [v56]

### Added: "By config" — config ∩ DB tags intersection

---

## [v55]

### Fixed: extra args overwritten before injection; enhanced logging

---

## [v54]

### Added: separate output folders (raw, concatenated, assembled)

---

## [v53]

### Fixed: `noSpectatorUi` injection; Tags tab moved; grey colours brightened

---

## [v47]

### Added: "🔍 By config" restored; "📅" separated

---

## [v46]

### Changed: "Concatenate sequences" moved to FINAL ASSEMBLY

---

## [v45]

### Changed: Tags output to console; window size 1600×900

---

## [v44]

### Added: weapon icons; hover tooltips; auto-tag multi-tags; X-Ray in Video tab

---

## [v43]

### Added: CS2 window mode; Minimize CS2 on launch; CS2 monitoring thread

---

## [v42]

### Added: "Since last tag" / "📅 By config"; already-tagged demos dialog

---

## [v41]

### Changed: Capture tab condensed; `_tag_search_last_tagged`

---

## [v40]

### Fixed: Workshop map download blocking — auto-accept checkbox

---

## [v39]

### Added: Kill modifiers section (Smoke, No-scope, Wallbang, Airborne, Flash-assisted, Collateral); `hchk` helper

---

## [v38]

### Added: Encoding preset (CPU); Teamkills 3-state; reorder saved players; tag colour swatch

---

## [v37]

### Fixed: presets section misplaced; preset radio buttons overflowing

---

## [v36]

### Fixed: `showKill` logic for victim/spec perspectives

---

## [v35]

### Fixed: POV Victim camera — three distinct bugs

---

## [v34]

### Added: weapon categories reorganised; `DELAYED_EFFECT_WEAPONS`; `victim_death_tick` detection

---

## [v33]

### Fixed: mkv container; `#` in filename; `-movflags` on mkv/avi

---

## [v32]

### Fixed: DB status header showing raw debug info

---

## [v31]

### Changed: 5 tabs → 4 tabs; active player state restored on startup

---

## [v30]

### Fixed: assembly audio/video drift

---

## [v29]

### Fixed: no audio in clips — missing `recordAudio`/`playerVoicesEnabled` fields

---

## [v28]

### Added: X-Ray option; saved assembly names

---

## [v27]

> `snd_mute_losefocus` hypothesis retracted. Real fix in v29.

---

## [v26]

### Changed: version bump; `PlayerSearchWidget` docstring

---

## [v6]

### Changed: weapons loaded from DB dynamically

---

## [v5]

### Fixed: `column m.date does not exist` — PostgreSQL reserved word, quoted at runtime

---

## [v4]

### Added: auto-connect on startup; `PlayerSearchWidget`; config auto-save; 3-tab layout

---

## [v3]

### Fixed: two `TclError` crashes on startup

---

## [v2]

### Added: tkinter GUI; batch loop in daemon thread; launch validation

---

## [v1]

### Added: initial CLI batch script
