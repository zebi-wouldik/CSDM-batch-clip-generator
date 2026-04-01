# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> **Version numbering note:** sub-releases previously written as `133.xx` or `143.x` have been
> renumbered as sequential integers. `133.33` → `134`, `133.34` → `135`, …, `133.42` → `143`,
> `143.0` → `144`, `143.1` → `145`, …, `143.8` → `152`. Each dot was always one real increment.

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

### Changed: Sequence merge gap — close kills now join into one clip

`_build_sequences` previously only merged two adjacent clip windows when they **overlapped**. Now it also merges them when the **gap** between them is ≤ `before_ticks` (the configured Before duration in ticks).

This matches native CSDM behaviour: a second qualifying kill that happens just a few seconds after the first clip ends extends that clip instead of generating a separate one. No new setting needed — the Before duration is the natural gap tolerance.

**Example**: Before = 5s @ 64 ticks/s → two kills up to 5 s apart (after the first clip's `after` padding) get merged into a single sequence.

### Changed: Weapon selector shows active filter count

The weapon section label now reads `weapons (X / Y selected)` in **orange** whenever a partial filter is active, making it immediately visible when unexpected weapons are still checked. Shows `weapons (all / Y)` in muted text when no filter is applied.

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

### Changed: One Tap filter now enforces headshots at SQL level

`kill_mod_one_tap` now adds `AND is_headshot = TRUE` to the SQL query when the headshot column exists, ensuring the DB returns only HS kills before dp2 shot-isolation is applied. Previously, shot count was checked but not headshot. If `headshots_mode = exclude`, the HS clause is skipped (user intent respected). Warns in log if headshot column is missing.

### Fixed: Demo picker "Clear all" UX

When dates are cleared via "Clear all", the demo picker now shows `— all demos (run Preview to filter)` instead of a blank label, making it clear that an empty picker means no filter (all demos included).

### Changed: Preset saving UI — checkboxes instead of radio buttons

Replaced the single "Type" radio selector with four independent checkboxes:
- **Player + events + weapons + filters**
- **Video / encoding settings**
- **Timing + robustness**
- **All settings (full config)** — exclusive; checking it deselects others

Multiple categories can now be combined in one preset (e.g. Player + Timing).
Saved format changed from `{"type": "..."}` to `{"cats": [...]}` — old presets with `"type"` load correctly via backward-compat path.

### Added: Preset hover tooltip

Each saved preset in the list now shows a tooltip on hover with: categories saved, key count, and notable settings (player name, perspective, dates, resolution, FPS, encoder, before/after).

### Confirmed: Filter pipeline order already correct

SQL (weapons → DB mods) → Python date filter → dp2 pre-parse → dp2 filters. No change needed.

---

## [v176]

### Added: Victim's Mate POV feature

Record kills from the perspective of the victim's teammate who has the best angular line-of-sight to the kill, instead of following the victim directly.

**How it works:**

- At each kill tick, player positions and view angles are fetched via `demoparser2` (`parse_ticks`).
- Three body points per potential teammate are checked (head / chest / legs at heights 64, 40, 10 units above feet).
- A teammate qualifies when ≥ 2 of 3 body points fall within the ±45° horizontal FOV of their look direction — equivalent to "at least 50% of the body visible".
- Among all qualifying teammates, the one with the smallest absolute angle to the kill point is chosen ("best angle").
- Active players (the clip subject) are excluded from the mate pool.
- LOS is angle-based only — no BSP ray-cast is available via `demoparser2`.

**Two modes:**

- **Optional** (default): if no qualifying teammate is found, the camera falls back to the normal victim/both perspective for that clip — nothing is skipped.
- **★ Must**: clips with no qualifying teammate are dropped entirely.

**UI:** A new "Mate POV" row with **Enable** and **★ Must** checkboxes appears in the **Capture & Timing** section, below the Switch delay slider. The row is only visible when **POV Victim** or **Both** perspective is selected (Killer mode has no victim phase to override).

**Camera wiring:**

- *Victim mode*: the single camera target is replaced by the mate SID when available.
- *Both mode*: the victim-phase switch (victim_pre_ticks before kill) points to the mate SID when available; killer phase is unaffected.

---

## [v175]

### Fixed: CZ75-Auto (and other weapons) still appearing in "Other" category

Three-layer fix so any DB storage variant resolves correctly:

1. **`weapon_` prefix indexed** — `_WEAPON_LOOKUP` now also stores every key with the `weapon_` prefix (`weapon_cz75a`, `weapon_ak47`, etc.) so internal game names resolve without extra processing.
2. **`_weapon_category` strips prefix** — before the exact lookup, strips a leading `weapon_` from the key so `weapon_cz75a` → lookup `cz75a` → Pistols.
3. **Substring fallback** — `_WEAPON_SUBSTR_FALLBACK` maps substrings to categories for variant spellings that slip past the exact lookup (e.g. `"cz75 auto"`, `"cz75_auto"`, any `"cz75…"` form → Pistols). Covers other common weapons too (deagle, glock, usp, awp, etc.).
4. **"Other" category hidden in UI** — unknown weapons are silently skipped during weapon-filter render rather than grouped under a confusing "Other" header.

---

## [v174]

### Fixed: Tab switching lag and window-drag "momentum"

Two separate root causes:

- **Window drag momentum**: `_remember_layout_state` (debounced 250 ms after every window move) was calling `_on_splitter_release()`, which calls `sashpos(0, x)`. Setting the sash position programmatically fires `<Configure>` on both panes → all `ScrollableFrame`s schedule a 400 ms `_apply_width` reflow → widgets relayout long after the window has stopped moving. Removed the `_on_splitter_release()` call from `_remember_layout_state`; sash snapping now only happens on actual sash-drag.

- **Tab switching lag**: `ScrollableFrame` canvases inside a newly visible tab received `<Configure>` and scheduled `_apply_width` in 400 ms — content reflowed correctly, but 400 ms late. Added `<<NotebookTabChanged>>` binding that immediately flushes all pending scroll-frame widths and wrap-label sizes.

### Fixed: CZ75-Auto shown in "Other" weapon category

Added `"cz75_auto"` (underscore variant) to `WEAPON_CATEGORIES["Pistols"]`. CSDM DB sometimes stores this weapon with an underscore instead of a dash.

### Changed: WALLBANG and BLIND FIRE moved from dp2 to Mods (DB-backed)

CSDM stores penetration and attacker-blind data in the kills table. These two filters can now run directly from the DB without parsing the demo file, matching how Smoke / No-scope / Victim Flashed already work.

- **🧱 WALLBANG** → `kills.penetrated_objects > 0`  or  `kills.has_penetrated / kills.penetrated = TRUE`. Category changed from `dp2` → `mods`.
- **😵 BLIND FIRE** → `kills.attacker_blinded / kills.is_attacker_blinded`. Category changed from `dp2` → `mods`.
- **🪂 AIRBORNE** → no DB equivalent (`attackerinair` is not stored by CSDM). Stays in `dp2`.
- `_dp2_required_sections` no longer adds the `"death"` section for wall_bang and blind_fire.
- The SQL builder's dead `kill_mod_wall_bang` special-case (`if pen_col and not col`) has been removed and replaced with a clean `_mod_sql_expr()` helper that handles int vs bool columns correctly for both inclusion and exclusion clauses.

### Fixed: Both mode — wrong player POV before victim switch

Root cause: `_build_cams_both` appended `(seq["start_tick"], killer_sid)` to the timeline for every kill event in the sequence. Since the timeline was deduplicated by keeping the **last** entry per tick, the camera at `start_tick` ended up on the last-processed kill's killer, not the first active player — visible as a brief flash of a random player's POV at the start of multi-kill clips.

Fix: `initial_sid` from `_seq_anchor_sid` is now the true starting camera and is never placed into the timeline. Only **switch events** go in the timeline: victim switches (`switch_tick → vsid`) and killer-return events (`prev_kill_tick + 1 → next_killer_sid`). First-write-wins per tick (dict, no overwrite).

### Improved: Both mode — switch delay slider shows total clip duration

Added a live **"total before: Xs"** hint label next to the Switch delay slider that updates whenever either the BEFORE or the Switch delay slider changes. Updated tooltip to clarify the three phases: killer phase = BEFORE, victim phase = Switch delay, total before kill = their sum.

---

## [v173]

### Fixed: Deathnotice player names now sourced from the demo file

Player names shown in CSDM deathnotices were previously looked up from the database (`players` table), which reflects the current/latest known name — not the name the player had at the time the demo was recorded.

- `_dp2_parse_demo` now calls `parser.parse_player_info()` as a new `"names"` cache section.
- The resulting `{steamid: name}` map is stored as `demo_names` in the dp2 cache, keyed per demo.
- `_dp2_required_sections` always includes `"names"` so every demo gets at least this minimal parse, even when no dp2 kill modifiers are active.
- `_build_json` resolves player names via a `_name(psid)` helper: **demo cache first, DB fallback**. All `playerName` fields in `playerCameras` and `playersOptions` use this helper.

---

## [v172]

### Fixed: Ferrari Peek dp2_badge placement

`dp2_badge` was packed inside the expandable `_hv_inner` frame (visible only when "Enable" is checked). Moved to the main `_hv_row` frame so it appears inline with the label and checkboxes — consistent with every other dp2-category filter row.

### Improved: Light mode (white theme)

- **White preset softened**: `BG2` changed from `#ffffff` to `#f8f8f8`, `BG3` to `#e4e4e4` — reduces harsh pure-white contrast zones.
- **Light-mode status colours**: Added `_STATUS_COLOURS_LIGHT` with dark-saturated variants (`GREEN #15803d`, `RED #b91c1c`, `YELLOW #b45309`, `BLUE #1d4ed8`) that provide adequate contrast on light backgrounds. `_build_theme` selects the light set when the bg preset has `_is_light: True`; existing dark-mode pastel colours are unchanged.
- Log tags (`ok`, `err`, `warn`, `blue`, badges) reapply via `_reapply_ttk_styles` on theme change, so switching dark → white correctly updates all coloured text in the console.

### Fixed: Console timestamps are per-line, not a live clock

Timestamps now stamp each line at write time (`[HH:MM:SS]` prefix injected in `_log` / `_log_parts`). The live ticking clock that was erroneously added to the header has been removed. Toggle via the **TS** button in the log toolbar.

### Added: INJECTION PREVIEW section (Tools tab)

New collapsible section below PERFORMANCE in the Tools tab shows the exact args that will be injected into CS2 for the current config:
- **HLAE mode**: shows the full `extraArgs` token string broken one-per-line.
- **CS mode**: shows `launch_args` and each `console_cmds` entry.
- Displays on load (`after(200, ...)`), plus a **⟳ Refresh** button for manual update.
- Text widget auto-sizes (4–12 lines). Key labels in accent colour, values in text colour.

### Added: Preview export — HTML / TXT / JSON

The **📤 Export ▾** button in the log toolbar opens a format menu. After running a preview (F6):

- **HTML** — standalone dark-themed file; per-clip table with date, demo, clip index, weapon, filters found, tick, `playdemo` command (click-to-select).
- **TXT** — plain-text columnar table + `cmd:` line per clip.
- **JSON** — structured array of clip objects (same fields), ready for scripting.

All three formats source clip data from `_last_preview_data`. **Filters column shows the filters that actually matched each clip** (`_mf` set from event data), not just the active config filters.

### Fixed: dp2_threads setting not respected (all CPU cores used)

`demoparser2` is a Rust extension that uses Rayon internally. Rayon's global thread pool defaults to all available CPU cores regardless of Python's `ThreadPoolExecutor(max_workers=n)`.

- Added `os.environ.setdefault("RAYON_NUM_THREADS", "1")` at import time (before demoparser2/numpy/pandas are first loaded).
- Also sets `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS` to `"1"` for the same reason.
- `setdefault` is used so a user who deliberately sets those env vars before launching the app keeps their preference.
- Result: `dp2_threads = N` now means N Python workers × 1 Rayon thread each = N cores used, matching the user's intention.

---

### Fixed: Theme change retaining old colours on some widgets

Root cause: `_CHK_KW` and `_BTN_KW` are module-level dicts built at import time with default dark/green values. Any session started with a non-default saved theme would create those widgets (log filter radiobuttons, preset-type radiobuttons, weapon-category checkboxes, autoscroll toggle) with wrong colours. Subsequent `_change_theme` calls could not fix them because the colour_map was keyed on the current theme's values, not the stale defaults.

- **`_apply_theme_globals` now updates `_CHK_KW`/`_BTN_KW` in-place** on every call — startup and runtime both correct.
- **Colour-map collision detection**: if two theme keys share the same old hex value but map to different new values (e.g. amoled `BG == BG2 == #000000`), the ambiguous value is excluded from the generic map rather than producing wrong remapping.
- **`ScrollableFrame.apply_theme()`** added — explicitly sets canvas + inner frame `bg` to `_t("BG")`, bypassing colour_map ambiguity. Handled by `_walk` alongside `Sec`.
- **Log widget** bg changed from hardcoded `"#090909"` to `_t("LOG_BG")` at creation.

---

## [v171]

### Improved: demoparsing performance

- **Auto-scaled thread count:** `dp2_threads` default now uses `min(8, max(2, cpu_count))` instead of a hardcoded 2 — better out-of-the-box utilization on multi-core machines.
- **Vectorized fire + hurt loops:** `for row in arr` loops in `_dp2_parse_demo` replaced with pandas `groupby` operations. Pandas/numpy ops release the GIL during computation, letting other threads run concurrently and reducing visible UI stutter while demoparsing in the background.

### Fixed: TrueView fails silently on old demos

Old demos without TrueView support cause CSDM CLI to output `Raw files not found`. This was previously logged as a dim (non-error) line, so no error was flagged and no retry triggered — the recording appeared to succeed but launched CS2 in spectator mode on the wrong player.

- `Raw files not found` now detected as an error (logged red).
- If TrueView was ON, the script auto-retries that specific demo once with `trueView: false` injected into the config JSON, falling back cleanly to spectator-camera mode.

### Changed: UI section reorganization

- **"RESOLUTION & FRAMERATE"** renamed to **"RESOLUTION, FRAMERATE & WINDOW"**.
- **Window mode** (None / Fullscreen / Windowed / Borderless) and **Send to back on launch** moved from "CS2 EFFECTS" into the renamed section — display/launch settings belong with resolution, not with CS2 effect commands.
- **Close CS2 after each demo** moved from "FINAL ASSEMBLY" into **"IN-GAME OPTIONS"** — it controls CS2 process behavior during recording, consistent with TrueView, death notices, and X-Ray.

---

## [v170]

### Fixed: resize and sash drag still laggy with 50 ms debounce

50 ms is shorter than typical pauses within a drag, so reflows were still triggered mid-interaction. The previous debounce was replaced with a two-tier strategy:

- **Mouse-driven resize (sash drag, in-app interactions):** a global `<ButtonRelease-1>` handler flushes all pending canvas width updates and wraplength updates exactly once when the mouse button is released — zero reflows during the drag itself.
- **OS window-border resize (Tkinter never receives ButtonRelease for OS chrome):** 400 ms debounce fallback fires once after the user stops resizing.

`_WRAP_LABELS` registry added — all `_bind_wraplength`-registered labels are flushed on release alongside `ScrollableFrame` width updates.

---

## [v169]

### Fixed: window resize and sash drag are laggy

Every pixel of resize triggered a synchronous cascade:

```
canvas <Configure> → itemconfigure(inner, width)
  → inner <Configure> → bbox("all") + scrollregion update
    → every desc_label <Configure> → wraplength update
```

All three operations ran on every intermediate event during a drag.

**Fixes:**
- `ScrollableFrame` canvas `<Configure>` now debounces the inner-frame width sync to 50 ms (`after_cancel`/`after`). The entire cascade (inner reflow + all child Configure events) is suppressed during drag and fires once when interaction stops.
- `scrollregion` update replaced `bbox("all")` with `(0, 0, e.width, e.height)` directly from the Configure event — O(1) instead of traversing all canvas items.
- `desc_label` wraplength updates debounced to 50 ms via `_bind_wraplength` helper. The two inline codec-desc labels (`_vcodec_desc`, `_acodec_desc`) share the same helper — no more duplicated binding pattern.

---

## [v168]

### Fixed: scroll wheel still not working on non-Capture tabs

All `ScrollableFrame` canvases share the same screen coordinates inside `ttk.Notebook` (every tab occupies the same rectangle). The `contains_point` check was matching all of them, so `_SCROLL_FRAMES[0]` (Capture) always won. Fix: `winfo_viewable()` guard added — returns `True` only when the canvas AND all its ancestors are mapped, i.e. only for the currently visible tab.

### Fixed: pane sash fighting the geometry manager during drag

`pack_propagate(False)` + `configure(width=N)` on the PanedWindow panes caused the frames to continuously fight `ttk.PanedWindow`'s geometry manager on every drag event. Removed both. Minimum size is now enforced correctly: `_on_splitter_release` snaps the sash back to the clamped position once the drag ends (`sashpos` re-applied after clamping), with no interference during the drag itself.

---

## [v167]

### Fixed: scroll only working in Capture tab

Mouse wheel scrolling previously used per-`ScrollableFrame` `<Enter>`/`<Leave>` bindings combined with recursive `_bind_children`/`_unbind_children` calls on every child widget. This meant scroll only activated after the mouse had physically entered the canvas — which never happens when switching tabs by clicking a header.

**Fix:** entire Enter/Leave machinery removed. A module-level `_SCROLL_FRAMES` registry now holds every live `ScrollableFrame`. A single `bind_all("<MouseWheel>", _global_wheel)` handler installed once in `_build_ui` finds the frame under the cursor and scrolls it. `Text`, `Listbox`, `Scale`, and `Treeview` widgets are excluded so their own native scroll behaviour is preserved. Works on every tab from the first render, with no per-widget rebinding.

### Fixed: inner content not filling tab width on window resize

`ScrollableFrame` was not resizing its inner frame to match the canvas width. A `<Configure>` binding on the canvas now calls `itemconfigure(win_id, width=e.width)` so content always fills the full available width.

### Fixed: log console pane could overlap the notebook pane

`ttk.PanedWindow` was added without minimum pane sizes. The sash could be dragged until the notebook was completely hidden. Both panes now carry an initial `width` constraint via `pack_propagate(False)` preventing either from being collapsed below a usable size.

### Refactor: UI helper layer — `_sep`, `_chk_tip`, dynamic `desc_label`

- `_sep(parent, pady, padx)` — replaces all 12 inline `tk.Frame(…, height=1, bg=BORDER).pack(fill="x", …)` calls.
- `_chk_tip(parent, label, var, tip, …)` — replaces all `hchk + pack + add_tip` 3-liners.
- `desc_label` — `wraplength=700` removed; a `<Configure>` binding sets `wraplength = max(200, widget_width - 10)` so description text wraps to the actual container width at any window size. `_vcodec_desc` and `_acodec_desc` receive the same treatment.
- Hardcoded `width=8` removed from the ADVANCED FFMPEG PARAMS label.

---

## [v166] — continued

### Fixed: match type filter misses competitive/wingman on newer CSDM versions

CSDM has stored competitive and wingman matches under two different `game_mode_str` values depending on its version: the full internal names (`scrimcomp5v5`, `scrimcomp2v2`) and the shorter aliases (`competitive`, `wingman`). A database built with one CSDM version and queried by another would silently skip those game types.

**Fix:** `MATCH_TYPE_DEFS` entries now carry a `db_values: list` instead of a single `db_value: str`. `_MATCH_TYPE_KEY_TO_DB` maps each cfg key to the full list. The SQL builder flattens these lists into the `IN (…)` clause, so both spellings are matched in a single query. The in-DB visibility check and tooltip also use the multi-value list.

Aliases added:

| cfg key | DB values now matched |
|---|---|
| `match_type_competitive` | `scrimcomp5v5`, `competitive` |
| `match_type_wingman` | `scrimcomp2v2`, `wingman` |

---

### Refactor: Clean Code pass — DRY, dead code removal, structural simplification

Behaviour-preserving cleanup across the full file (~180 lines removed):

**DRY / unified helpers**
- `_load_json` / `_save_json` — 6 near-identical JSON persistence functions collapsed into 2 generic helpers; `load_presets`, `save_presets`, `load_saved_players`, `save_saved_players`, `load_asm_names`, `save_asm_names`, `load_config`, `save_config` all reduced to one-liners.
- `_make_highlight_toggle` — shared trace/update closure extracted from `hchk` and `hradio`, which were duplicating ~20 lines of identical widget-highlight logic.
- `_cfg_num` — generic numeric config reader underlying `_cfg_int` and `_cfg_float`; both kept as thin wrappers for call-site compatibility.
- `_page_count()` — helper extracted in `PlayerSearchWidget`; replaced 4 repeated `max(1, (len + ps - 1) // ps)` expressions in `_page_next`, `_page_last`, `_page_jump`, and `_render_page`.
- `_validate_run_inputs()` — player/event guard extracted from `_run` and `_dry_run`.
- `_apply_theme_globals` — replaced 13 manual `global X; X = _THEME["X"]` assignments with a loop over `_THEME_GLOBAL_NAMES`.

**Dead code removed**
- `_engage_trois_tap`, `_disengage_trois_tap` — no-op `pass` methods; call site also cleaned.
- `_on_tag_selected` — never called.
- `_refresh_tag_combo` — `pass` method + 3 call sites.
- `_on_trois_tap_toggle`, `_on_one_tap_toggle` — no-op `pass` methods; removed from `cmd_map` in `_build_filter_row`.
- Full HS-lock chain: `_hs_only_is_required` (always returned `False`) → `_refresh_hs_lock_state` (always called `_unlock_hs`) → `_install_hs_lock_watchers` (installed traces that always no-oped) → `_lock_hs_to_only` (unreachable) → `_unlock_hs` — entire chain removed along with all call sites.

**Eliminated 11 `_apply_*_to_events` one-liner wrappers**
`_apply_spray_transfer_to_events`, `_apply_high_velocity_to_events`, `_apply_flick_to_events`, `_apply_sauveur_to_events`, `_apply_wall_bang_dp2_to_events`, `_apply_airborne_dp2_to_events`, `_apply_attacker_blind_dp2_to_events`, `_apply_collateral_dp2_to_events`, `_apply_trois_shot_to_events`, `_apply_no_trois_shot_to_events`, `_apply_one_tap_to_events` — all were identical `_apply_filter_to_events(…)` delegates. The preview path (`_apply_dp2_filters_to_events`) now builds inline lambdas from the registry data instead of dispatching through named methods.

---

## [v166]

### Fixed: crash — `hchk`/`hradio` traces firing on destroyed widgets

`_refresh_match_type_ui` destroys and recreates its checkbox children on every DB connect. The `var.trace_add("write", _update)` closures registered by each `hchk` call survived widget destruction. The next time any `BooleanVar` changed (theme change via `_retrigger_toggle_vars`, or any other write), the stale `_update` fired, called `.config()` on the destroyed widget, and raised:

```
_tkinter.TclError: invalid command name ".!panedwindow…!checkbutton-1"
```

**Fix:** added a module-level `_safe_trace_remove(var, mode, tid)` helper. Both `hchk` and `hradio` now:
1. Store the trace ID returned by `trace_add`.
2. Guard `_update` with `winfo_exists()` — if the widget is already gone, return immediately.
3. Bind `<Destroy>` on the widget to call `_safe_trace_remove` automatically.

Self-cleaning regardless of how many times the parent frame is rebuilt.

---

### Changed: "Close CS2 after demo" moved to FINAL ASSEMBLY

Previously under RECORDING SYSTEM (wrong — that section covers codec/mode selection). Moved to the top of FINAL ASSEMBLY, separated from the assemble/delete checkboxes by a divider. Correct semantics: closing CS2 is a batch-flow concern, not a recording-system setting.

---

### Fixed: accelerated corpses during demo recording

CS2 demo playback can inherit a residual `host_timescale` from a previous session, causing physics (ragdolls) to simulate faster than real time even when game speed is set to 100 %. Symptom: corpses fall unnaturally fast in recorded clips.

**Fix:** `demo_timescale 1` is now the first command emitted by `_common_cs2_injection`, applied in both HLAE mode (via `extraArgs`) and CS mode (via `autoexec + runtime cfg`). Explicitly resets demo playback speed to 1× before any other physics commands fire.

The "Ragdoll physics" checkbox tooltip now explains the issue and notes that unchecking (`cl_ragdoll_physics_enable 0`) freezes corpses entirely as an alternative.

---

## [v164]

### Fixed: Clutch — false positives in Wingman (and any sub-5v5 mode)

The clutch detection built its initial alive-set exclusively from players who appeared as killers or victims in the kill log. In Wingman (2v2), a teammate who hadn't killed or been killed yet was absent from that set — so the code saw the player's team as already alone before anyone died, triggering phantom clutch windows on every round.

**Fix:** `_fetch_all_kills_for_demos` now runs a second query against the `players` table:

```sql
SELECT match_checksum, team_name, COUNT(DISTINCT steam_id)
FROM players
WHERE match_checksum IN (...)
GROUP BY match_checksum, team_name
```

`_apply_clutch_filter` uses those per-team counts to inject synthetic ghost players into `alive_set` for each slot that isn't yet accounted for by the kill rows. Ghost SIDs are namespaced (`__ghost_<team>_<i>__`) and never collide with real or tracked players. If the `players` table lacks team/side columns, or the roster query fails, behaviour is identical to before — the fix is best-effort with no crash path.

---

### Added: Match type filter (MATCH TYPES section in Capture & Timing)

Filter demos by CS2 match type. The section is **hidden by default** and only appears after the DB connects; only types actually found in your database are shown (no phantom checkboxes for modes you've never played).

**13 known `game_mode_str` values mapped to UI labels:**

| DB value | Label |
|---|---|
| `premier` | 🏆 Premier |
| `scrimcomp5v5` | 🎯 Competitive |
| `scrimcomp2v2` | 🤝 Wingman |
| `casual` | 🎮 Casual |
| `deathmatch` | 💀 Deathmatch |
| `training` / `new_user_training` | 🎓 Training / New User |
| `armsrace` / `gungameprogressive` | 🔫 Arms Race |
| `gungametrbomb` | 💣 Demolition |
| `cooperative` | 🤖 Co-op |
| `skirmish` | ⚡ Skirmish |
| `retake` | ↩ Retakes |

**"Filter by type" master toggle** — when off, no SQL clause is added (zero overhead). When on, a single `m."game_mode_str" IN (...)` clause is injected into both the kills and rounds queries. Type checkboxes grey out when the toggle is off. All keys persist in config.

If the column doesn't exist in the schema (older CSDM database), the entire section stays hidden with no warning.

---

### Fixed: Delete source clips after assembly — residual folders not removed

Two bugs in the cleanup path:

1. **Wrong root guard.** The code compared deleted-folder paths against `cfg["output_dir"]` — the legacy mirror key — instead of `cfg["output_dir_clips"]`, the actual clips root. The guard never matched, so `shutil.rmtree` was either blocked on the wrong path or running unconstrained.

2. **No upward traversal.** Only the immediate parent of each deleted clip was checked. Nested layouts (`<root>/<demo>/<session>/`) left empty intermediate folders behind.

**Fix:** Replaced the flat loop with `_try_remove_dir(d)`, a recursive upward walker. After removing a folder, it attempts the parent, stopping at `output_dir_clips` (resolved with `relative_to` guard) or any non-empty directory. A `visited` set prevents double-visits. The root is never touched.

---

### Changed: "Tools" tab renamed to "Settings"

---

## [v163]

> Internal version bump — no documented changes. Shipped as the baseline before the v164 session.

---

## [v162]

### Fixed: Stop / Kill buttons not lighting up during run

`_run()` set both buttons to `state="normal"` but left `fg=MUTED`, so they remained visually greyed out even while active. Both now receive `fg=RED` on activation and are correctly reset to `fg=MUTED` by `_reset_btns()`.

### Fixed: Map column empty in demo picker

`_map_col` was detected inside the kills query block but evaluated *after* `map_sel` had already been constructed — so `map_sel` was always `""` on the first query run and the map column was never included in the SELECT. Detection moved to before `_build_dsql` / `map_sel`, ensuring the column is fetched from the very first query.

### Fixed: Death notices showing a player's old username

`_player_names` was built from `GROUP BY p.name, p.steam_id ORDER BY p.name`, which surfaces an arbitrary historical name when a player has multiple entries. Changed to `DISTINCT ON (p.steam_id) … ORDER BY p.steam_id, last_seen DESC NULLS LAST` so only the most recent name per SID is kept.

### Removed: Encoder field from Video tab

The Encoder selector (always "FFmpeg", no alternatives) has been removed from the `RECORDING SYSTEM` section. The `encoder` key is still written to the CSDM JSON for compatibility. The section now shows only the System radio buttons (HLAE / CS).

### Fixed: Auto Workshop DL loading wrong map version

`+cl_downloadfilter all` was the previous injection. This tells CS2 to download Workshop content from the CDN — but it pulls the **current published version** of the Workshop item, which may be a completely different map. The injection is replaced with `+sv_pure 0 +sv_lan 1`:

- `sv_pure 0` — disables file validation so CS2 loads whatever map version is installed locally without checking against any CDN.
- `sv_lan 1` — prevents CS2 from reaching external services for content verification.

The old map version must already be cached/installed on the machine. The checkbox tooltip and the "Additional HLAE args" hint are updated to reflect this.

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
