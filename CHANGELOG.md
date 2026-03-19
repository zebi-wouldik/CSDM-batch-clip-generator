# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.  
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v123]
### Fixed

- **dp2 `🚫🎲 Exclude` logic in combined filter scenarios**:
  `Exclude` now behaves as an exclusion gate (removes lucky kills first) before other dp2 matching logic, instead of acting like a broad OR-positive selector that could unexpectedly inflate results in `ANY` mode.
- **Preview/run consistency**:
  the same exclusion-first behavior now applies in both preview (`_apply_dp2_filters_to_events`) and batch worker (`_apply_dp2_modifiers`) paths.
- **Tooltip clarity**:
  Exclude tooltip now states that when combined with other dp2 filters it acts as an exclusion gate first.
- **Version bump**: script version moved to `v123`.

---

## [v122]
### Added

- **Kill filters quick action — "Unselect all"**:
  added a button in the Kill filters logic header to disable all active kill/situation modifiers at once and clear all `★ Must` flags in one click.
- **Version bump**: script version moved to `v122`.

---

## [v121]
### Changed

- **Updated "DEATHS BY" capture tooltip** to explicitly reflect current behavior:
  it now states that deaths use the same active weapon, kill-filter, and situation-filter logic as kills, with the selected player(s) on the victim side.
- **Version bump**: script version moved to `v121`.

---

## [v120]
### Changed

- **Kill filter logic selector is now single-source in UI**:
  replaced duplicated `AT LEAST ONE / ALL AT ONCE / MIXED` blocks for Mods and demoparser2 with one shared selector: **Kill filters logic (Mods + demoparser2)**.
- **DB modifiers moved to Situation category with Clutch**:
  DB postfilters and Clutch are now grouped under **Situation (DB + Clutch)** for clearer mental model and less UI noise.
- **Situation logic remains additive after kill filters**:
  situation modifiers apply after kill-filter selection (`kill_mod_logic_db`), preserving pipeline behavior while improving clarity.
- **DRY cleanup**:
  kill-logic synchronization now goes through one handler (`_on_kill_logic_change`) that keeps internal Mods/dp2 logic state aligned.
- **Version bump**: script version moved to `v120`.

---

## [v119]
### Fixed

- **Headshots auto-lock logic is now context-aware**:
  `🎯 Headshots = Only` is no longer forced just because `ONE TAP` is checked in every case.
- **Force-only now applies only when HS-only output is guaranteed by active logic**:
  - Always forced for `TROIS TAP`.
  - Forced for `ONE TAP` only in HS-strict combinations (for example dp2 `ALL`, or dp2 `MIXED` when ONE TAP is required / sole optional).
  - Not forced for broad OR combinations where non-HS clips can still validly pass.
- **UI + runtime alignment**:
  - HS radio lock/unlock now uses one shared evaluator.
  - DB query headshot coercion uses the same evaluator, avoiding over-filtering.
- **Version bump**: script version moved to `v119`.

---

## [v118]
### Changed

- **DP2 pre-parse is now section-aware** instead of parsing every dataset unconditionally per demo:
  - Parses only required sections by active filters (`fire`, `death`, `hurt`).
  - Avoids heavy `weapon_fire` parsing when only death-flag filters (e.g. WALLBANG/AIRBORNE/BLIND/COLLATERAL) are enabled.
- **DRY refactor for parse requirements**:
  - Added `_dp2_required_sections(cfg)` as single source of truth for filter → required data mapping.
  - `_preparse_dp2` and `_dp2_parse_demo` now share this section model.
- **Incremental cache coverage**:
  - Cache now tracks parsed sections per demo and only fills missing sections, instead of treating cache as all-or-nothing per file.
- **Version bump**: script version moved to `v118`.

---

## [v117]
### Fixed

- **AT LEAST ONE logic across Mods + dp2 now behaves as expected when stacking more filters**:
  when both categories are set to `ANY`, adding dp2 filters no longer unintentionally narrows results through an implicit cross-category AND caused by SQL pre-filtering before dp2 pass.
- **Cross-engine OR union added for `Mods[ANY] + dp2[ANY]`**:
  SQL-backed mod matches (`SMOKE`, `NO-SCOPE`, `VIC.FLASH`) are preserved as `_mf` matches and unioned with dp2 OR results in both preview and batch worker paths.
- **Graceful handling when SQL mod columns are missing in this union mode**:
  if SQL mods cannot be applied from DB but dp2 ANY is active, the query no longer hard-returns empty solely due to missing SQL mod columns.
- **Version bump**: script version moved to `v117`.

---

## [v116]
### Fixed

- **Enable + ★ Must conflict resolved** — previously, checking ★ Must on a filter while its Enable checkbox was unchecked caused Must to be silently ignored. The filter was never added to the `active` list (built by `cfg.get(key)` which requires Enable=True), so `_split_required_optional` never saw it and the required constraint had no effect.

  **Fix — `_wire_enable_must(enable_var, req_var)`**: new method wires bidirectional `trace_add("write")` coupling between every Enable/Must pair:
  - Checking ★ Must while Enable is off → **auto-enables** the filter
  - Unchecking Enable while Must is on → **auto-clears** Must

  Called at UI build time for every modifier row across all three categories (Mods, dp2, DB). The coupling list is stored in `self._must_couplings` for reference.

  Pairs wired: all `_mods` loop entries, all `_dp2` loop entries + TROIS SHOT / TROIS TAP / ONE TAP / SPRAY TRANSFER / FERRARI PEEK / FLICK / SAVIOR individually, and all five DB rows (ENTRY FRAG, ACE, MULTI-KILL, BULLY, ECO FRAG).

---

## [v115]
### Fixed

- **UI freeze during dp2 pre-parse scan eliminated**: preview and batch-run no longer make the window unresponsive while scanning demos.

  **Root cause:** `_alog` was implemented as `self.after(0, lambda: self._log(...))`. Every call from a background thread scheduled one event-loop callback with zero delay. During parallel dp2 pre-parsing (N demos × M threads), hundreds of `after(0)` lambdas piled up in Tk's event queue. Each callback forced a full `Text.configure(state=normal) → insert → see("end") → configure(state=disabled)` redraw cycle. With the queue saturated, mouse and keyboard events couldn't get through — the window appeared frozen.

  **Fix — batched log pump:**
  - `_alog` and `_alog_parts` now append to `self._log_buf: deque` (thread-safe via `_log_buf_lock`) instead of calling `after(0)`.
  - `_log_pump()` runs on the main thread every `_LOG_PUMP_MS = 50` ms via `self.after(50, self._log_pump)`. It drains the entire deque in **one** `Text` operation: one `configure(normal)`, N `insert` calls, one `see("end")`, one `configure(disabled)`. N log messages = 1 redraw regardless of volume.
  - The progress label update inside `_preparse_dp2` is throttled — fires every 5 completed demos and on the last one, instead of every single completion.

- **WALLBANG / AIRBORNE / BLIND FIRE / COLLATERAL were silently skipped during pre-parse** (bug introduced in v112): `_preparse_dp2` had a hardcoded `needs_dp2` guard that only listed the original 8 filters. The 4 new `player_death`-flag filters added in v112 were absent, so enabling only those mods caused the entire dp2 pre-parse to be skipped — the filters then degraded gracefully (passed all kills) rather than actually filtering. Fixed and made **permanently DRY**: `needs_dp2` is now derived directly from `_DP2_FILTER_DEFS` via `{k for k, *_ in self._DP2_FILTER_DEFS}` so it can never fall out of sync with the filter table again.

- **Version bump**: script version moved to `v115`.

---


### Fixed

- **UI freeze during dp2 pre-parse scan eliminated**: preview and batch-run no longer make the window unresponsive while scanning demos.

  **Root cause:** `_alog` was implemented as `self.after(0, lambda: self._log(...))`. Every call from a background thread scheduled one event-loop callback with zero delay. During parallel dp2 pre-parsing (N demos × M threads), hundreds of `after(0)` lambdas piled up in Tk's event queue. Each callback forced a full `Text.configure(state=normal) → insert → see("end") → configure(state=disabled)` redraw cycle. With the queue saturated, mouse and keyboard events couldn't get through — the window appeared frozen.

  **Fix — batched log pump:**
  - `_alog` and `_alog_parts` now append to `self._log_buf: deque` (thread-safe via `_log_buf_lock`) instead of calling `after(0)`.
  - `_log_pump()` runs on the main thread every `_LOG_PUMP_MS = 50` ms via `self.after(50, self._log_pump)`. It drains the entire deque in **one** `Text` operation: one `configure(normal)`, N `insert` calls, one `see("end")`, one `configure(disabled)`. N log messages = 1 redraw regardless of volume.
  - The progress label update inside `_preparse_dp2` is now throttled — it fires every 5 completed demos and on the last one, instead of on every single completion.

- **Version bump**: script version moved to `v115`.

---


### Added

- **MIXED logic mode for all three kill filter categories**:
  Each category (Mods, demoparser2, DB) now has a third option alongside AT LEAST ONE and ALL AT ONCE:

  > **MIXED** — required filters (★ Must) must ALL match, AND at least one of the remaining (optional) filters must also match.

  Example: WALLBANG as ★ Must + SMOKE + BLIND as optional → the kill must be a wallbang AND at least one of smoke/blind.

  Each filter row gains a **★ Must** checkbox, visible only when MIXED mode is active for its category. In AT LEAST ONE or ALL AT ONCE mode, ★ Must checkboxes are hidden.

- **`_on_logic_mode_change(category)`** — single DRY method handles all three category show/hide behaviours via `self._must_widgets: {category: [widget, ...]}`.

- **20 new `_req` config keys** (`kill_mod_<key>_req: False`) — one per filter — stored in config, presets, and session.

### Technical

- **`_split_required_optional(cfg, keys)`** — static DRY helper shared by all three filter engines. Splits active filter keys into `(required, optional)` based on `<key>_req` flags. Used by:
  - SQL mods engine: builds `(req1 AND req2 AND (opt1 OR opt2))` SQL clause.
  - DB postfilter: intersects required sig sets, unions optional sig sets, then intersects both.
  - dp2 worker (`_apply_dp2_modifiers`): AND-chains required filters, OR-unions optionals, intersects results with `_mf` merge.
  - dp2 preview (`_apply_dp2_filters_to_events`): same via nested `_chain`/`_union` closures.

- **Preview header** `Filters:` line shows `★` prefix on required filters in MIXED mode (e.g. `dp2 [MIXED]: ★ 🧱 WALLBANG · 💨 SMOKE`).

- **Version bump**: script version moved to `v114`.

---


### Removed & Fixed

- **"Output: video" radio group removed** — it was the only option and served no purpose. Purged completely: `REC_OUTPUT_OPTIONS` constant, `recording_output` key in `DEFAULT_CONFIG`, `str_keys`, `PRESET_KEYS`, `_collect_config`, `_apply_config`. The CSDM JSON field `recordingOutput` is now hardcoded to `"video"`. The Output column no longer appears in the Video tab RECORDING SYSTEM section.

- **Accent colour preset buttons no longer change colour when switching themes**: the generic `_apply_theme_to_widgets` walker remapped any `fg` that matched the old accent hex — including the fixed per-button colours on the accent row. Fixed by:
  - Storing button references in `self._ac_btn_refs: list[(widget, fixed_fg)]` at build time.
  - Passing a `exclude_ids: frozenset` to `_apply_theme_to_widgets` so those specific widgets are skipped entirely by the walker.
  - After the walk, `_change_theme` explicitly updates only `bg` and `activebackground` on accent buttons to match the new background theme — their `fg` is never touched.
  - `_retrigger_toggle_vars()` is now also called in `_change_theme` (was missing), ensuring all `hchk`/`hradio` widgets re-read `_t()` after every theme switch.

- **Version bump**: script version moved to `v113`.

---


### Fixed & Added

- **WALLBANG, AIRBORNE, BLIND FIRE, COLLATERAL now work via demoparser2**:
  These four mods produced `⚠ Modifiers not found in DB` on every run because CSDM's PostgreSQL `kills` table never stores those columns — confirmed by auditing the CSDM source and the CS2 `player_death` game-event schema. They are now implemented entirely via demoparser2, reading the native fields embedded in every `.dem` file:
  - `🧱 WALLBANG` — `player_death.penetrated > 0`
  - `🪂 AIRBORNE` — `player_death.attackerinair = true`
  - `😵 BLIND FIRE` — `player_death.attackerblind = true`
  - `🎯 COLLATERAL` — `player_death.penetrated > 0` (same bullet-penetration flag)

- **`⚠ Modifiers not found in DB` warning will no longer appear** for these four mods. They no longer go through `_MOD_COLS` at all; only `SMOKE`, `NO-SCOPE`, and `VIC.FLASH` remain as SQL-backed mods (those columns do exist in the DB).

### Technical

- **`_dp2_parse_demo`** — the existing `player_death` parse is extended to also extract `noscope`, `thrusmoke`, `attackerblind`, `penetrated`, `attackerinair` into a new `death_flags: {(tick, killer_sid): {flag: value}}` dict, stored in the dp2 cache alongside `fire_detail`, `view_angles`, `hurt_index`. No additional demo scan.

- **`_death_flag_filter(flag_name, threshold)`** — single DRY generic filter. All four concrete methods delegate to it:
  - `_wall_bang_dp2_filter` → `penetrated ≥ 1`
  - `_airborne_dp2_filter` → `attackerinair = True`
  - `_attacker_blind_dp2_filter` → `attackerblind = True`
  - `_collateral_dp2_filter` → `penetrated ≥ 1`
  Uses `_TICK_MATCH_WINDOW = 2` tick tolerance for matching kill event ticks. Degrades gracefully (passes all kills) when `death_flags` is empty.

- **`_DP2_FILTER_DEFS`** — all four new filters added. They are automatically picked up by `_apply_dp2_modifiers` (worker) and `_apply_dp2_filters_to_events` (preview), including full `_mf` tagging for clip badges.

- **`_FILTER_BADGE_DEFS`** — all four moved from `"mods"` to `"dp2"` category.

- **UI** — the four mods now show a `demoparser2` badge in the Capture tab, clearly indicating they require demoparser2.

- **Version bump**: script version moved to `v112`.

---


### Added

- **UI theme system — background presets + accent colour + custom picker**:
  A new **UI THEME** section in the Tools tab lets you change the entire interface colour scheme in real time without restarting.

  **Background presets** (4):
  - `Dark` — the original near-black dark theme
  - `AMOLED` — true pure black (`#000000`), saves battery on OLED panels
  - `Deep Blue` — dark navy blue tones
  - `White` — light theme with dark text

  **Accent presets** (8): Green (default), Blue, Orange, Purple, Red, Cyan, Pink, Yellow

  **Custom accent** — `🎨 Custom colour…` opens the Windows native colour picker (`colorchooser.askcolor`). A darker shade (`ACCENT2`) is derived automatically at 72% brightness for hover/selected states.

  A coloured swatch next to the picker shows the current active accent at a glance.

- **Theme persists across sessions**: `theme_bg` and `theme_accent` keys in `csdm_config.json`. The theme is applied before any widget is built at startup — no flash of default colours.

### Technical

- **`_build_theme(bg_name, accent)`** — single function building a complete 14-key colour dict. All theme data is in two module-level dicts (`_BG_PRESETS`, `_ACCENT_PRESETS`); adding a new preset is one dict entry.
- **`_apply_theme_globals()`** — atomically updates all module-level colour globals (`BG`, `BG2`, `ORANGE`, etc.) so new widgets built after a theme change automatically use the right colours.
- **`_change_theme()`** — App method that calls `_apply_theme_globals`, walks all existing widgets via `_apply_theme_to_widgets()`, re-applies `ttk.Style`, updates log text tags, and calls `_retrigger_toggle_vars()` to re-fire `hchk`/`hradio` closures.
- **`hchk` / `hradio`** — internal `_update()` closures now call `_t(key)` for live theme lookups instead of being bound to the module-global values at creation time. Theme changes are reflected immediately on all existing checkboxes and radio buttons.
- **`_retrigger_toggle_vars()`** — nudges every `BooleanVar` and `StringVar` to re-trigger the `_update` traces registered by `hchk`/`hradio` across the whole UI.

- **Version bump**: script version moved to `v111`.

---


### Fixed

- **"Modifiers partially not found" warning no longer repeats every preview/run**: the warning for DB columns that don't exist in the user's schema (e.g. `wall_bang`, `airborne`, `attacker_blind`, `collateral`) now fires **at most once per session per unique set of missing modifiers**. Subsequent previews and batch runs are silent about the same absent columns. The warning resets automatically on reconnect, so if a CSDM update adds the columns it will be reported correctly again.

- **Implementation**: added `self._warned_missing_mods: set` (reset on DB reconnect in `_on_load_success`) that caches the `frozenset` of missing modifier keys. The warning block compares against it and only logs when the set changes.

- **Version bump**: script version moved to `v110`.

---


### Changed

- **Headshots filter redesigned — tri-state, fully independent of Mods logic**:
  Replaced the old `headshots_only: bool` checkbox (which lived inside the Mods group and was subject to the ANY/ALL toggle) with a dedicated `🎯 Headshots: All / Only / Exclude` radio group on its own row, alongside Suicides and TK — completely separate from the Mods category and its logic selector.
  - **All** (default) — no headshot filtering.
  - **Only** — keep headshot kills only (`is_headshot = TRUE`).
  - **Exclude** — keep non-headshot kills only (`is_headshot = FALSE`).
  - ONE TAP and TROIS TAP still force `Only` when enabled and lock the radio buttons. They release the lock on disable.

- **New config key `headshots_mode`** (`"all"` | `"only"` | `"exclude"`), replaces `headshots_only: bool`. Stored and restored through existing config persistence.

- **Backward compatibility**: old configs/presets with `headshots_only: true` are automatically migrated to `headshots_mode: "only"` at load time and in `_apply_config`.

- **Preview header** — HS mode is shown on the `Filters:` misc line (`🎯 HS only` / `🎯 no HS`) when active.

- **DRY lock/unlock helpers**: `_lock_hs_to_only()` and `_unlock_hs()` centralise the radio-button disable/enable logic used by ONE TAP, TROIS TAP (`_engage_trois_tap` / `_disengage_trois_tap`).

- **Version bump**: script version moved to `v109`.

---


### Changed & Fixed

- **Clip filter badges are now per-kill accurate** — each demo line shows only the filter(s) that the kills in that specific clip actually triggered, not every globally-active filter. Previously `[KILL AK-47] [💨 SMOKE] [🔭 NOSCOPE] [🧱 WALLBANG] … ` appeared on every line regardless of which filter matched. Now only the relevant badge(s) are shown, e.g. `[KILL AK-47] [😵 BLIND]`.

- **`_mf` (matched-filters) tagging implemented across all three filter stages**:
  - **SQL Mods** (`_query_events`) — each resolved boolean column (smoke, no-scope, wallbang, airborne, victim-flash, attacker-blind, collateral) is fetched alongside the row. `headshots_only` is also tagged via the `is_headshot` column. `_mf` is populated per event at query time with only the keys whose column value is `TRUE` for that row.
  - **DB postfilters** (`_apply_db_postfilters`) — `per_mod_sigs` now carries `(cfg_key, set)` pairs. A `sig_to_keys` map accumulates which filter(s) each kill sig matched; `_mf` is stamped on kept kills accordingly.
  - **dp2 filters** — `_stamp_mf` is called on surviving events in every path: `_apply_filter_to_events` (all AND dict-level passes), TROIS TAP short-circuit, AND chain in worker, and OR union in worker.

- **DRY — `_stamp_mf(events, cfg_key)` static helper**: replaces the repeated 3-line `_mf` set-mutation pattern. One definition, three call sites.

- **DRY — `_DP2_FILTER_DEFS` class-level table**: single source of truth for all 7 dp2 filters `(cfg_key, filter_fn_attr, apply_fn_attr, log_label, result_label, skip_label)`. Both `_apply_dp2_modifiers` (worker) and `_apply_dp2_filters_to_events` (preview) derive their active filter lists from it via `getattr(self, attr)`. The two previously separate inline `_DP2_MODS` local lists are gone. Adding a new dp2 filter now requires touching exactly one place.

- **AND chain `_mf` gap fixed** (`_apply_dp2_modifiers`): the AND path in the per-demo worker was calling raw `filter_fn` without stamping `_mf`. It now calls `_stamp_mf(events, cfg_key)` after each step.

- **TROIS TAP `_mf` gap fixed** (`_apply_dp2_modifiers`): the TROIS TAP short-circuit path was not stamping `_mf`. Now stamps `kill_mod_trois_tap` on all surviving events.

- **Version bump**: script version moved to `v108`.

---


### Changed

- **Clip badges — filter context appended after content badge**:
  Each demo line now shows the content badge *and* one compact badge per active kill filter, e.g.:
  `[KILL AK-47] [😵 BLIND] [💨 SMOKE]`
  Filter badges are blue (`badge_filter` tag) to visually distinguish them from the red content badge.

- **DRY — single source of truth for filter badge definitions**:
  Introduced `_FILTER_BADGE_DEFS` (class-level tuple list with `cfg_key`, `emoji_label`, `category`) and two helpers built from it:
  - `_build_filter_badges(cfg)` — per-clip badge list (used by `_build_clip_badges`).
  - `_build_filter_header_parts(cfg)` — grouped header strings (used by the preview `Filters:` line).
  The three previously hardcoded filter lists in `_show_preview` are gone.

- **Version bump**: script version moved to `v107`.

---


### Changed

- **Clip badges rewritten — content-aware instead of filter-aware**:
  Badges no longer show which filters were active during the search. They now describe what each individual sequence **contains**:
  - Kill clips: `[KILL AK-47]`, `[2✕ M4A1-S]`, `[3✕ AK-47 + M4A1-S]` — weapon(s) used, kill count when > 1.
  - Death clips: `[DEATH by AWP]`, `[2✕ DEATH by AK-47]` — weapon the player was killed by.
  - Round-only clips: `[ROUND]`.

- **Preview header redesigned** — replaced the single bloated `Order: … | N demo(s) 😵 BLIND` line with a structured multi-line block:
  ```
  Player:  …
  Tag:     …          (only when auto-tag is active)
  Dates:   … → …      (only when a date range is set)
  Events:  Kills + Deaths + Clutch [1v3 1v4]
  Weapons: 🎯 Rifles(1)
  Rec:     POV Killer  |  TrueView: ON  |  Order: Chronological
  Filters: Mods [ANY]: 😵 BLIND · 💨 SMOKE  |  DB [ANY]: 🚀 ENTRY
  Found:   17 demo(s)  ·  23 event(s)
  Output:  …
  Dates:   .info › mtime .dem › DB
  ```
  Active kill filters are now grouped by category (Mods / dp2 / DB) with their logic mode on a dedicated `Filters:` line. The `Filters:` line is omitted entirely when no kill filter is active.

- **Version bump**: script version moved to `v106`.

---


### Added

- **Logic mode selector for each kill filter category**:
  Each of the three kill filter sections now has its own **AT LEAST ONE / ALL AT ONCE** radio toggle:
  - **Mods** (DB boolean columns — smoke, wallbang, airborne, etc.): toggles the SQL `WHERE` clause between `OR` and `AND` across the checked mods.
  - **demoparser2 modifiers** (TROIS SHOT, ONE TAP, SPRAY, FERRARI PEEK, FLICK, SAVIOR): in OR mode each filter runs independently on the original kill list and results are unioned; in AND mode filters are chained (each narrows the surviving set). TROIS TAP is always exclusive and bypasses this setting.
  - **DB modifiers** (ENTRY, ACE, MULTI-KILL, BULLY, ECO): in OR mode the per-modifier sig sets are unioned; in AND mode they are intersected — a kill must satisfy every checked modifier simultaneously.
  - All three selectors default to **AT LEAST ONE** (OR), preserving existing behaviour.

- **New config keys** (saved/restored through existing config persistence):
  - `kill_mod_logic_mods` — `"any"` | `"all"`
  - `kill_mod_logic_dp2`  — `"any"` | `"all"`
  - `kill_mod_logic_db`   — `"any"` | `"all"`

### Changed

- **DRY refactor — dp2 filter application**:
  The three previously identical inline blocks that applied demoparser2 filters (preview path, tag-redo path, and a prior shared helper) have been consolidated into a single `_apply_dp2_filters_to_events(evts, cfg)` method. All three call sites now delegate to it. The per-demo worker path goes through `_apply_dp2_modifiers` which was also rewritten to support both logic modes.

- **Version bump**: script version moved to `v105`.

---


### Changed

- **DRY refactor for demo log entries**:
  - Added shared log-entry builders for both Preview and Run paths.
  - `Preview` and `Run` now use the same rendering logic for base line format + badges.
  - This prevents future drift between the two flows.
- **Version bump**: script version moved to `v104`.

---

## [v103]
### Fixed

- **Preview log now shows clip badges**:
  - Inline indicators (`[KILL FILTER: ...]`, `[CONTAINS: ...]`, `[SAFE]`) are now rendered in **Preview** rows too, not only during batch run.
  - Badge visibility still follows `Badges: ON/OFF`.
- **Version bump**: script version moved to `v103`.

---

## [v102]
### Added & Changed

- **Resizable UI layout controls**:
  - Added editable UI settings for window width/height and main split percentage.
  - Added buttons: `Apply`, `Auto`, and `Reset default`.
  - Added option `Remember current layout` to persist manual window resize and splitter moves.
- **Persistent layout config keys**:
  - `ui_window_w`, `ui_window_h`, `ui_split_pct`, `ui_remember_layout`.
  - Layout is auto-saved through existing config persistence.
- **Startup behavior updated**:
  - App now starts using saved window dimensions and saved split ratio.
- **Version bump**: script version moved to `v102`.

---

## [v101]
### Added & Changed

- **Log badge indicators for clip entries**:
  - Each clip line can now show inline, human-readable badges:
    - `[KILL FILTER: ...]` for active kill-filter matches
    - `[CONTAINS: ...]` for detected content terms in clip events
    - `[SAFE]` when no indicator condition is met
  - Added consistent color coding in the log:
    - red for kill-filter indicators
    - amber for contains/warning indicators
    - green for safe indicators
- **Collapsible badge mode**:
  - New log toggle button `Badges: ON/OFF` plus keyboard shortcut `Ctrl+B`.
  - When OFF, badges are collapsed to reduce log density.
- **Accessibility/UX improvements**:
  - Indicator labels are plain text (screen-reader friendly) and keyboard toggleable.
  - Tooltip explains badge toggle and shortcut.
- **Version bump**: script version moved to `v101`.

---

## [v100]
### Changed

- **VirtualDub removed** from the app configuration and UI.
- **Image export modes removed** (`images`, `images_and_video`): output is now fixed to `video`.
- **Backward compatibility safety**:
  - if an old config/preset contains `encoder=VirtualDub`, it is coerced to `FFmpeg`.
  - if an old config/preset contains non-video `recording_output`, it is coerced to `video`.
- **Version bump**: script version moved to `v100`.

---

## [v99]
### Added & Changed

- **CS mode vanilla injection implemented**: CS2 vanilla commands are now injected in CS mode through a managed runtime cfg pipeline instead of being only logged.
- **New shared injection layer**:
  - `_common_cs2_injection(cfg)` builds a common set of vanilla launch arguments and console commands shared by HLAE and CS.
  - Shared section now includes physics/effects commands (`cl_ragdoll_gravity`, `ragdoll_gravity_scale`, `sv_gravity`, `cl_ragdoll_physics_enable`, `violence_hblood`, `r_dynamic`) and window-mode launch flags mapping.
- **HLAE adapter refactor**:
  - `_inject_hlae_extra_args(cfg, shared)` now consumes the shared section and appends HLAE-specific options (`hideSpectatorUi`, scope FOV fix, workshop download, custom extra args) in one place.
  - Keeps `mirv_fov`, `host_timescale`, `afxStream` explicit fields while sharing vanilla commands through `extraArgs`.
- **CS adapter added**:
  - `_inject_cs_runtime_cfg(cfg, shared)` writes `csdm_batch_runtime.cfg` into the detected CS2 cfg directory and ensures `autoexec.cfg` executes it via a managed block.
  - This enables vanilla commands in CS mode at game launch without relying on a non-existent CSDM JSON `csOptions.extraArgs`.
  - If launch-only options are requested, the app now logs a clear warning that they are not injectable through current CSDM CS JSON.
- **Steam library autodetection added**:
  - `_resolve_cs2_cfg_dir(cfg)` resolves CS2 cfg folder from common Steam paths and `libraryfolders.vdf`.
  - Optional manual override via new config key `cs2_cfg_dir`.
- **Version bump**: script/doc version moved to `v99`.
- **Game speed UI refactor**:
  - `Slow-motion (%)` replaced with **`Game Speed (%)`**.
  - Direct numeric input now supports `1..1000` with immediate live feedback (`%` + `x` multiplier).
  - Preset buttons now include >100% values (`125`, `150`, `200`, `500`, `1000`).
  - Value is sanitized/clamped and persists through existing config autosave.
- **CFG robustness hardening**:
  - Added strict parsers (`_cfg_int`, `_cfg_float`, `_cfg_bool`) with fallback + warning logs for invalid values.
  - Runtime cfg injection no longer crashes on malformed config values.

---

## [v98]
### Fixed & Changed

**Ferrari Peek — tightened logic + tooltip rewrite:**
- `APPROACH_WIN` reduced from 192 ticks (3s) to 64 ticks (1s). A fast approach 3s before the shot followed by camping is not a ferrari peek — the movement window must be recent.
- When `one-shot=True`, no prior shot exists in the pre-window (condition 1 eliminates them), so only the velocity at shot time matters. The wide window had no effect in that case.
- Tooltip rewritten around the real concept: *kill faster than the opponent can react* — exposure window shorter than human reaction time (~150–250ms).
- Internal docstring updated to document the actual behaviour of each condition.

**README — Recording section corrected:**
- `CS2 effects` marked ❌ for CS mode (was ✅, incorrect). The physics commands (`cl_ragdoll_gravity`, `sv_gravity`, etc.) are standard CS2 console commands — they work in any mode. The real issue is that CSDM's CS mode JSON schema has no `extraArgs` field to inject them through, so the script logs them but cannot forward them. HLAE is not required for the physics themselves.

---

## [v97]
### Changed — Section restructure, Mods (OR) redesign

**Sections renamed and reorganised in the Capture tab:**
- `EVENTS & CAMERA` → **`CAPTURE`** — KILLS / DEATHS BY / ROUNDS + Perspective only.
- New section **`KILL FILTERS`** — all kill filters grouped together.
- `TIMING & ROBUSTNESS` → **`TIMING`**
- `DATE RANGE & DEMO SELECTION` → **`DEMO SELECTION`**

**Mods (OR) redesigned as per-line layout** (matching DB modifiers style): each mod gets its own label and Enable checkbox on its own row. HS ONLY is now part of this list. Suicides and TK remain on a compact row at the top of the section.

---

## [v97 — Ferrari Peek logic refactor, CS2 Effects fix]
### Changed

**Ferrari Peek — detection logic revised:**
The goal is "faster than the opponent can react" — minimal exposure window. The old logic checked 3 conditions: movement before (3s window), isolated shot, movement after. Condition 3 was noise (the player can retreat without firing again).

New logic — two conditions only:
1. **High velocity at shot time**: max speed in a ±0.5s window around the kill shot ≥ threshold. This directly measures "you were in their FOV for the shortest possible time".
2. **Isolated shot** (optional, `kill_mod_hv_one_shot`): no prior shot within ~0.75s.

Default threshold: **150 u/s** (above walking speed, clearly an active peek). UI label: "Min speed at shot:". Tooltip fully rewritten.

**CS2 EFFECTS — corrections:**
- Physics commands (`cl_ragdoll_gravity`, `sv_gravity`, etc.) are standard CS2 console commands — HLAE is not required for them. In HLAE mode the script injects them via `hlaeOptions.extraArgs`. In CS mode, CSDM's JSON schema has no equivalent field, so they are logged but not forwarded — pending CSDM support.
- README Recording table corrected accordingly.

---

## [v96]
### Fixed & Changed

**Demo picker — double-toggle on first click fixed:** `_on_demo_tree_click` now returns `"break"` to absorb the native Treeview selection event, which was toggling the row state a second time immediately after the first click.

**Clutch options placement fixed:** `_clutch_opts_row` was pack()-ed unconditionally at build time, causing it to appear below all subsequently added widgets. It is now created without packing — `_on_clutch_toggle` controls visibility entirely.

**Player list — sort by name or date:** the DB query now fetches each player's last match date (`MAX(match_date)` via a LEFT JOIN on matches). Two sort buttons added to the DB search widget: **Name ↑↓** and **Date ↑↓** (newest first by default). Clicking the active sort button reverses order. The sort persists across search queries.

**Ferrari Peek — One-shot option:** new `kill_mod_hv_one_shot` bool (default `True`). When checked, condition 1 (no prior fire within ~0.75s) is enforced. Uncheck to allow spray finishers as long as the approach and resume conditions still hold. Added as a checkbox next to Enable in the UI.

---

## [v95]
### Changed — Ferrari Peek: logic refactor

**Old filter:** velocity at shot time ≥ threshold (player was moving fast when they shot).

**New filter — one-shot moving peek:** three conditions, all required:

1. **Isolated shot** — no other fire from the player in the ~0.75s (48 ticks) before the kill shot. Proves it's a one-shot kill, not a spray where the victim died on the last bullet.
2. **Was moving before** — either a prior shot in the 3s approach window had velocity ≥ threshold, or the kill shot itself was at velocity ≥ threshold (no counter-strafe). Counter-strafe is not required ("ou non").
3. **Resumes movement after** — at least one fire from the player within 2s after the kill has velocity ≥ 80 u/s. If no post-kill fire is found the check is skipped (graceful degradation).

**`kill_mod_high_vel_thr`** repurposed as minimum *approach* speed (default 100 u/s, down from 30 u/s "max at shot"). UI label changed from "Max vel at shot:" → "Min approach:". Tooltip rewritten with the three conditions and a CS2 speed reference table.

---

## [v94]
### Changed — Stop/Kill refactor, event toggles, UI fixes, naming

**Stop/Kill refactor:**
- **⏸ STOP** now immediately kills the current CSDM process (instead of waiting for the demo to finish), marks the demo as failed, then stops the batch. No next demo is started.
- **⛔ KILL** kills CSDM + sends `taskkill /F /IM cs2.exe` to terminate CS2 immediately. Assembly is skipped.
- Both actions trigger a **tag rollback**: any demo tagged during the interrupted batch has its tag removed from the DB (`DELETE FROM checksum_tags`). A rollback summary is logged.

**Events row — styled toggle buttons:**
- "Kills" and "Deaths" checkboxes replaced by styled toggle buttons: **KILLS** and **DEATHS BY**. Green when active, muted when off. "Rounds" gets the same treatment.
- "Deaths" label renamed to **DEATHS BY** to clarify it captures the player dying (from the killer's POV).

**CS mode warning improved:** now explicitly warns that CS2 plays the demo from tick 0 to reach each target tick, making batch recording extremely slow. HLAE is strongly recommended.

**Perspective moved to bottom of section:** the Perspective row and Switch delay slider now appear at the very end of the EVENTS & CAMERA section, after Clutch — no longer interrupting the modifier flow.

**SAUVEUR → SAVIOR:** UI label and log strings updated. Config key `kill_mod_sauveur` unchanged.

**Ferrari Peek default threshold: 280 → 230 u/s:** corrected to reflect actual CS2 max run speeds (knife/C4 = 250, AK-47 = 215, pistols ≈ 240). 230 u/s sits above max rifle speed and captures real aggressive peeks. Tooltip updated with accurate values.

**Spray Transfer tooltip:** now explicitly mentions CZ75-Auto as the only full-auto pistol included.

---

## [v93]
### Changed — UI cleanup & modifier reorganisation

**Clutch — Custom range removed:** `clutch_custom_enabled`, `clutch_custom_min`, `clutch_custom_max` removed entirely. The 1v1–1v5 checkboxes are sufficient; the custom range was redundant. Config keys, UI row, `_on_clutch_custom_toggle`, and `_clutch_allowed_sizes` logic all cleaned up accordingly.

**Perspective moved:** now sits above the modifier list (between the HS/TK options and Mods), instead of below the clutch block.

**Blind Fire moved into Mods row:** `😵 Blind Fire` is now part of the `Mods (OR)` inline row alongside Smoke, Wallbang, etc. The separate `ab_row` block is gone.

**BOURREAU → BULLY:** label renamed in UI and comments.

**Tooltips simplified:** verbose multi-line technical descriptions reduced to 1–2 user-facing lines across all modifiers.

**`demoparser2` badge centralised:** `dp2_badge(parent)` helper introduced — creates the blue label and attaches the tooltip in one call. Replaces the repeated `tk.Label(... "demoparser2")` + `add_tip(...)` pattern used in every dp2-powered modifier row.

---

## [v92]
### Added — 9 new kill modifiers

**DB-only (no demoparser2):**
- **🚀 Entry Frag** — first kill of the round (earliest tick). Identifies space-makers. Uses kills table + round grouping.
- **🃏 Ace** — player eliminates all 5 opponents in one round. Detected by counting distinct victim SIDs per round.
- **⚡ Multi-Kill** — ≥N kills in one round within T seconds. Configurable N (2–5) and window (seconds). Triple = 3, Quadra = 4.
- **💀 Bourreau** — kills the same victim for the Nth time in the match. Only the Nth+ kill is kept. Configurable repeat threshold.
- **💰 Eco Frag** — pistol kill against a full-buy opponent (rifle/LMG/auto-sniper). Uses `victim_weapon` column if present; falls back to including all pistol kills if column absent.
- **😵 Blind Fire** — player was blinded (flashed) at shot time. Uses `attacker_blind`/`is_blind` column.

**demoparser2-powered:**
- **🏎 Ferrari Peek** — kill while moving above a velocity threshold (default 280 u/s). Velocity is already in the `fire_detail` cache from the existing `weapon_fire` parse — no new parse needed.
- **↩ Flick** — large view-angle change in the ~0.5s before the kill. Configurable minimum degrees (default 50°). Uses `view_angle_Y` from a new `player_death` parse added to `_dp2_parse_demo`.
- **🛡 Sauveur** — player kills an enemy who was actively hurting a teammate within ~2s before the kill. Uses `player_hurt` events from a new parse added to `_dp2_parse_demo`.

### Changed
- **`_dp2_parse_demo`** extended: now also parses `player_death` (view angles) and `player_hurt` (damage events) in the same demo parse pass. Both stored in `_dp2_cache` as `view_angles` and `hurt_index`. Cached for the session — no re-parse on batch.
- **`kill_mod_assisted_flash` UI label** corrected: "Flashed" → "Victim flashed" (the *victim* was blinded). Previously ambiguous.
- **`kill_mod_attacker_blind`** added as a separate modifier for when the *killer* was blinded. Previously `is_blind`/`attacker_blind` was incorrectly merged into `assisted_flash`.
- **`_apply_db_postfilters()`** new method: runs Entry Frag, Ace, Multi-Kill, Bourreau, Eco-Frag as post-query filters on the already-fetched results dict. Called at the end of `_query_events` — no extra DB round-trip, no SQL complexity added to the main query.
- `_show_preview` summary line extended with all new modifier badges.
- New `int` config keys: `kill_mod_multi_kill_n`, `kill_mod_multi_kill_s`, `kill_mod_bourreau_n`, `kill_mod_high_vel_thr`, `kill_mod_flick_deg`.

---

## [v91]
### Fixed
- **`_effective_before` perspective leak**: `victim_pre_s` was added to `before` regardless of perspective mode because `victim_pre_s=2` is stored in config and persisted across sessions. A saved config with `perspective=both` would inflate clip duration even after switching back to `POV Killer`. Added `max(0, ...)` guard and clarified docstring: only `perspective == "both"` triggers the addition.

### Changed
- **"Full round" → "Full clutch"** everywhere (UI radio label, clutch tooltip, config comment, `_build_clutch_sequences` docstring). A clutch clip spans `first_kill_tick − before` to `last_kill_tick + after` — not the entire CS round. The old name implied the full 115s round was recorded.
- **Adaptive preview avg line**: The `▶ N clips | avg. Xs/clip` line is now context-aware:
  - Regular clips only → `avg. Xs/clip`
  - Clutch clips only → `avg. Xs/clutch`
  - Mixed → `N clips avg. Xs  +  M clutch avg. Ys` (separate averages, since clutch duration is structurally different from per-kill clips)

### Notes — TROIS SHOT scoped behaviour (confirmed, no change)
For AWP/SSG08, the lucky condition is `(not scoped) OR (acc > 0.010)`. A **scoped** shot is still caught as "lucky" if `acc > 0.010` — this covers the case where the player scoped in and fired before the sway settled (CS2 accuracy_penalty doesn't drop to minimum the instant you scope). This is correct: "aiming" doesn't guarantee a precise shot if the scope isn't fully steadied. No threshold change needed.

---

## [v90]
### Changed
- **Header active player label** now mirrors the exact text from the Capture tab's active-accounts label (`_active_lbl`) in real time. Previously `_hdr_player_lbl` was updated by `_on_player_change` only — which only fired on DB-list selection and showed a truncated single-player shortname. The header now always shows the same string as the tab (e.g. `3 active: PLURTH WURTH, MAMMOUTH, TROIS SHOT TROIS`).
- `_update_active_lbl` (in `PlayerSearchWidget`) now also calls `app._hdr_player_lbl.config(...)` with the same text and colour via `winfo_toplevel()`.
- `_on_player_change` simplified: delegates to `player_search._update_active_lbl()` instead of computing its own truncated label — removes a divergence between the two display points.
- Fixed French string: `"Actif : {name}"` → `"Active: {name}"`.

---

## [v89]
### Performance
All optimisations are transparent — no behaviour change.

- **`_ts_cache`**: `_get_demo_ts()` now caches the result of reading `.info` files and calling `stat()` on the first call per demo path. With 127 demos and 3–5 calls per Preview (sort key, date filter, format date, picker), this reduces disk reads from ~400–600 to 127.

- **`_col_cache`**: `_find_col(table, candidates)` results are memoised in `self._col_cache`. The DB schema never changes between calls, so the 12+ repeated list scans per `_query_events()` call are replaced by a single dict lookup.

- **Persistent DB connection** (`_pg()` / `_pg_fresh()`): `self._pg()` now returns a cached `psycopg2` connection, creating a new one only on the first call or if the connection was closed/broken. Background threads (load, tag searches, demo picker manual mode) use `_pg_fresh()` to avoid sharing the main-thread connection. Saves ~12 TCP handshakes per session.

- **`_query_events` `finally` block**: no longer calls `conn.close()` on the persistent connection (replaced by `pass`).

- **`_build_sequences` sort removed**: `sorted(events, key=…)` was called on every demo's event list. Since `_query_events` already issues `ORDER BY m."dc",k."tc"`, events arrive pre-sorted. The O(n log n) sort is now O(n).

- **`_demo_sort_key` normalises in-place**: raw date values from `_demo_dates` are normalised to `int` timestamps on the first parse and written back. Subsequent calls for the same demo skip the `strptime` / `timestamp()` conversion entirely.

- **`_dp2_verbose = False`**: per-kill log lines inside `_trois_shot_filter`, `_one_tap_filter`, and `_spray_transfer_filter` are suppressed by default. Each `_alog()` call dispatches a `self.after(0, lambda…)` to the Tk event queue — with 200 kills × 2 active filters this was flooding the queue with 400+ idle callbacks on every Preview. Set `self._dp2_verbose = True` in the constructor to re-enable for debugging.

- **`_spray_transfer_filter` rewritten** (single-pass burst segmentation): the old algorithm walked shots backward and forward for each kill tick — O(kills × shots) with two nested closure functions redefined per loop iteration. The new algorithm segments `shots` into bursts in a single O(shots) pass, then assigns kills to bursts in a single O(kills + bursts) sweep. Also fixed a latent bug: the forward walk used `shots[i-1]` as the reference for gap detection, which could reference a shot from before the kill tick rather than the previous shot in the forward scan.

### Fixed
- Last 3 French strings in UI/logs: `"Connexion..."` → `"Connecting..."`, `"Tags erreur:"` → `"Tags error:"`, `"Assemblage: FFmpeg introuvable."` → `"Assembly: FFmpeg not found."`.
- `_ts_cache` and `_col_cache` cleared in `_on_load_ok` so reconnecting to a different DB doesn't serve stale column lookups or demo dates.
- `_db_conn = None` added to `__init__`; `_dp2_verbose = False` added to `__init__`.

---

## [v88]
### Performance
- **`_ts_cache`** — `_get_demo_ts()` now caches results in `self._ts_cache`. On a 127-demo Preview, the `.info` file read + `stat()` fallback was called 3–5× per demo (sort key, date filter, display, picker). Now called once per demo per session. Cleared on DB reconnect.
- **`_col_cache`** — `_find_col()` now memoizes results in `self._col_cache` keyed by `(table, tuple(candidates))`. The DB schema does not change between runs; repeated list scans are eliminated. Cleared on DB reconnect.
- **Persistent DB connection** — `_pg()` reuses `self._db_conn` (liveness-checked before reuse) instead of opening a new psycopg2 TCP connection on every call (~14 connections per session → 1). Background threads (load, tags, picker, clutch) call `_pg_fresh()` to avoid sharing the main-thread connection. `_query_events` no longer closes the persistent connection in its `finally` block.
- **`_build_sequences` sort removed** — kills arrive pre-sorted by `ORDER BY m."dc",k."tc"` in SQL. The `sorted(..., key=lambda x: x["tick"])` call is now skipped (O(n log n) → O(n) per demo).
- **`_demo_sort_key` date normalisation** — raw datetime/string values from `_demo_dates` are parsed with `strptime` only once and written back as `int` timestamps, avoiding repeated parsing of the same value on subsequent sort calls.
- **Per-kill filter logging suppressed** — `_dp2_verbose = False` flag added. The 3 per-kill `_alog()` calls inside `_trois_shot_filter`, `_one_tap_filter`, and `_spray_transfer_filter` are now no-ops by default. Each `_alog()` call queues a `self.after(0, lambda…)` dispatch to the Tk main thread — on 200 kills × 2 active filters this produced ~400 Tk queue events per Preview just for debug lines. Flag can be set to `True` in code for diagnosis.
- **`_spray_transfer_filter` rewritten** — replaced O(kills²) nested walk (per-kill: `_find_burst_start` backward scan + forward scan) with a single O(shots) pass that segments all shots into bursts upfront, then a single O(kills) pass to assign kills to bursts. Also fixes a latent bug: the previous forward walk used `shots[i-1]` when `i == pos_end` which could reference a shot before the kill tick rather than the previous shot in the forward sequence.

### Fixed
- Last 3 French strings: `"Connexion..."` → `"Connecting..."`, `"Tags erreur:"` → `"Tags error:"`, `"Assemblage: FFmpeg introuvable."` → `"Assembly: FFmpeg not found."`

---

## [v87]
### Added
- **🔫 SPRAY TRANSFER** modifier — new filter in the Capture tab (demoparser2 required):
  - Captures kills that are part of a continuous automatic-weapon burst: the player kills ≥2 opponents without releasing the trigger between shots.
  - Detection: gap between consecutive `weapon_fire` events for the same player+weapon must stay ≤ `SPRAY_MAX_GAP_TICKS` (22 ticks ≈ 0.34s at 64 tick/s) across all kills in the burst.
  - Eligible weapons: all full-auto rifles (AK-47, M4A4, M4A1-S, Galil AR, FAMAS, SG 553, AUG), all SMGs (MAC-10, MP9, MP7, MP5-SD, UMP-45, P90, PP-Bizon), M249, Negev, CZ75-Auto.
  - Explicitly excluded: AWP, SSG 08, SCAR-20, G3SG1 (snipers/auto-snipers), all shotguns, all other pistols.
  - New constants: `SPRAY_TRANSFER_WEAPONS_LOWER`, `SPRAY_MAX_GAP_TICKS = 22`.
  - New method: `_spray_transfer_filter()` + `_apply_spray_transfer_to_events()`.
  - Wired into `_preparse_dp2`, `_apply_dp2_modifiers`, `_dry_run`, `_redo`, `_show_preview` summary.

- **Demo picker** — the DATE FILTER section becomes DATE RANGE & DEMO SELECTION:
  - After every Preview, the list of found demos populates a `ttk.Treeview` (7 rows visible, scrollable) with columns: ✓ (checked state), `dd-mm-yyyy hh:mm` date, demo name (truncated to last 43 chars with `…` prefix for long names like `match730_…668.dem`).
  - Click any row or the ✓ column to toggle inclusion. Check all / Uncheck all / Toggle selected buttons.
  - **Manual mode** checkbox: loads all demos from the DB, allowing full individual selection regardless of date range. Preserves existing checked state when switching.
  - Picker filter applied in `_worker`: demos unchecked in the picker are excluded from the batch. If picker is empty (no preview yet), no filter applied.
  - Clear all button also clears the picker.
  - New methods: `_demo_picker_populate()`, `_demo_picker_clear()`, `_on_demo_tree_click()`, `_demo_picker_set_all()`, `_demo_picker_toggle_selected()`, `_on_picker_mode_change()`, `_demo_picker_get_active()`, `_demo_picker_fmt_name()`, `_demo_picker_fmt_date()`.

### Changed
- **TROIS SHOT — weapon lock removed entirely**:
  - `TROIS_SHOT_ELIGIBLE_LOWER` constant deleted.
  - `_refresh_weapons_lock()` method deleted.
  - Weapon deselection blocks removed from `_on_trois_shot_toggle()`, `_engage_trois_tap()`.
  - `_trois_shot_filter()` no longer skips kills on "ineligible" weapons — it tries to evaluate any weapon against `CSDM_TO_DP2_WEAPON`; weapons with no threshold are simply not kept (no weapon filter side-effect in the UI).
  - Tooltips on TROIS SHOT and TROIS TAP updated: "locks ineligible weapons" removed.
  - `_no_trois_shot_filter` and `_trois_tap_filter` docstrings updated.

- **Clutch tooltip simplified**: removed technical detail about column names. New concise version fits one hover panel.
- **Preview log**: "Armes: toutes" / "Armes: …" → "Weapons: all" / "Weapons: …" (last French strings in UI log).

### Fixed
- Last call to `_refresh_weapons_lock(False)` in `_on_no_trois_shot_toggle` removed.
- `_on_picker_mode_change`: removed erroneous `self.v["clutch_enabled"]` guard.
- `sp_str` now correctly included in the preview summary log line.

---

## [v86]
### Fixed
- **`DEFAULT_CONFIG` clutch comment was stale** — still read `"multi-kill sequences in a single round"` (description from the original wrong implementation). Updated to `"player is last alive on team, kills remaining opponents"`.
- **Recording system tooltip was inaccurate** — still said physics/effects are "NOT injected by this tool in CS mode". Updated to reflect v83 behaviour: CS2 Effects are injected in HLAE mode; in CS mode they are not yet supported due to the absence of `extraArgs` in the CS JSON schema.

### Notes
- Clutch detection logic has been correct since v82: the algorithm fetches all kills per match, checks that all teammates died before the player's first kill tick in the round, counts opponents still alive at that moment, and compares against min/max. The tooltip and labels ("Min 1v:" / "Max 1v:") already described this correctly — only the config comment was stale.

---

## [v85]
### Changed
- **Clutch detection completely rewritten** — now detects *real* clutch situations instead of simple multi-kills per round:

  **Old behaviour (wrong)**: grouped kills by the same player in the same round where they made ≥ N kills. A player making 3 kills while 4 teammates were still alive was counted as a "clutch."

  **New behaviour (correct)**: a clutch is defined as:
  1. At the tick of the player's first kill in the round, **all teammates are already dead** (player is the sole survivor of their team).
  2. The number of opponents still alive at that exact tick ≥ `clutch_min_kills` and ≤ `clutch_max_kills`.

  **Algorithm change**: `_query_clutch_events` now fetches **all kills from all matches** the player participated in (not just their own kills), reconstructs per-round who was alive on each side at every tick, and verifies the last-alive condition before accepting a clutch.

  **Requires**: `killer_side` / `victim_side` columns in the kills table. Without side data, clutches cannot be verified and nothing is captured (rather than capturing incorrect data).

  **Logs**: each detected clutch now logs the clutch size explicitly: `🤝 1v3 clutch [demo.dem] tick=12345 (3 kills)`.

- **UI labels corrected**:
  - "Min kills" → "Min 1v" / "Max 1v" — reflects that the number is opponents alive at clutch start, not a kill count.
  - Combo now includes `1` as an option (1v1 clutch).
  - Tooltip fully rewritten to accurately describe detection logic, side-data requirement, and Win only behaviour.

### Fixed
- `require_win` was previously only applied if both side *and* winner were found; the side inference from victim_side now provides a reliable fallback when `killer_side` column is absent.
- Clutch log in `_query_events` now shows `1v2, 1v3…` notation instead of raw kill counts.

---

## [v84]
### Fixed
- **`clutch_require_win` was never actually filtering** — the entire body of the `if require_win:` block was a `pass` (TODO stub). Implemented properly:
  - The clutch kill query now also fetches `killer_side` / `killer_team_name` / `attacker_side` from the kills table.
  - Both killer side and round winner values are normalised to `"CT"` or `"T"` from all known CSDM schema variants (`COUNTER_TERRORIST`, `Counter-Terrorist`, `counter_terrorist` → `"CT"`; `TERRORIST`, `Terrorist` → `"T"`).
  - If killer side and winner both known and don't match → clutch skipped.
  - If either is absent (old schema / missing column) → clutch included rather than silently dropped.
  - `_killer_side` added to the `_internal` fields stripped from clean kill dicts before storage.
- **3 remaining French comments translated**:
  - `# date inconnue + filtre actif → on exclut` → `# unknown date + active filter → exclude`
  - `# timeout 60s pour trouver CS2` → `# 60s timeout to find CS2`
  - `# Phase 1 : attendre CS2 (polling rapide 100ms)` → `# Phase 1: wait for CS2 (fast polling 100ms)`

---

## [v83]
### Fixed
- **CS2 EFFECTS not injected in CS recording mode**: the physics console commands (`cl_ragdoll_gravity`, `ragdoll_gravity_scale`, `sv_gravity`, `cl_ragdoll_physics_enable`, `violence_hblood`, `r_dynamic`) were still inside the `if recsys == "HLAE":` block in `_build_json`, meaning they had no effect when System = CS. They are now built unconditionally. In HLAE mode they are appended to `hlaeOptions.extraArgs` as before. In CS mode they are logged for informational purposes (CSDM CS mode does not currently expose an `extraArgs` equivalent — will be wired when CSDM adds that field).

---

## [v82]
### Added
- **🤝 CLUTCH mode** — new capture type in the Capture tab:
  - Grouped kills: one clutch = all kills by the same player in the same round where they achieved ≥ `clutch_min_kills` kills.
  - Round detection uses the `rounds` table tick brackets when available; falls back to coarse 2-minute windows otherwise.
  - **Min kills** (2–5) and **Max kills** (2–5) sliders — e.g. Min=2 Max=3 captures only 1v2 and 1v3.
  - **Full round** clip mode: one continuous sequence from first kill − BEFORE to last kill + AFTER.
  - **Per kill** clip mode: standard individual sequences (normal merging applies).
  - **Win only** option: restricts to rounds with a recorded winner (requires `winner`/`winner_side` in the rounds table).
  - Deduplicated against regular Kill events — enabling Kills + Clutch simultaneously never produces duplicates.
  - `_query_clutch_events(...)` — full DB query with round brackets, tick assignment, and group filtering.
  - `_build_clutch_sequences(groups, ...)` — builds one contiguous sequence per clutch group.
  - `_on_clutch_toggle()` — shows/hides clutch options row.
  - `events_clutch` added to `_build_run_cfg`.

### Changed
- **Video tab — HLAE/CS2 sections properly separated**:
  - **⚡ HLAE OPTIONS** (hidden in CS mode): FOV, slow-motion, AFX stream, No spectator UI, Fix scope FOV, Auto Workshop download, window mode, Minimize on launch, extra HLAE args.
  - **🎮 CS2 EFFECTS** (always visible): window mode, Minimize on launch, `cl_ragdoll_gravity`, `ragdoll_gravity_scale`, `sv_gravity`, ragdoll physics, blood on walls, dynamic lighting. Section title and description make it clear these work in both modes.

---

## [v81]
### Fixed
- **Inaccurate CS mode tooltip** — the claims added in v78/v80 were still partially wrong:
  - "slow-motion not supported in CS mode" — **false**: `host_timescale` is a native CS2 command that works without HLAE.
  - "physics overrides not supported in CS mode" — **false**: `cl_ragdoll_gravity`, `ragdoll_gravity_scale`, `sv_gravity`, `cl_ragdoll_physics_enable`, `violence_hblood`, `r_dynamic` are all native CS2 console commands.
  - "window mode not supported in CS mode" — **false**: `-windowed`, `-noborder`, `-fullscreen` are standard CS2 launch options.
  - Corrected to: these are **native CS2 features that work in CS mode but are not injected by this tool** (the CSDM JSON has no `csOptions` equivalent of `hlaeOptions` to pass them through).
  - What IS genuinely HLAE-exclusive: `mirv_fov` (custom FOV), AFX streams, `hideSpectatorUi`, scope FOV fix (`mirv_fov handleZoom`), and all `mirv_*` commands.

---

## [v80]
### Fixed
- **Incorrect CS mode descriptions** — two claims added in v78 were factually wrong and have been corrected:
  1. *"CS2 plays the demo interactively from start to finish — the demo viewer UI is visible"* — removed. According to the official CSDM documentation, CS mode uses CS2's `startmovie` command to generate raw files (.tga + .wav), exactly like HLAE does internally. There is no difference in how CS2 launches or plays the demo between the two modes.
  2. *"do NOT minimize CS2 during recording"* in the batch log warning — removed. The `cs2_minimize` watcher works in both modes and minimizing is safe in both.
- Tooltip now correctly states: `CS = native CSDM recording via CS2's startmovie command`.

---

## [v79]
### Added
- **Fix scope FOV** checkbox in HLAE OPTIONS (enabled by default). Injects `+mirv_fov handleZoom enabled 1` into HLAE extraArgs. Without this, setting a custom FOV via HLAE overrides the zoom FOV when a player uses a scoped weapon (AWP, SSG 08, SCAR-20, G3SG1) — the scope appears at the custom FOV instead of the correct zoomed-in FOV. This is the only CS2-specific HLAE fix recommended by the official HLAE documentation and the community; `mirv_fix animations` was removed from HLAE as CS2 now handles animation smoothing natively. Saved in config, included in Video presets, logged in batch header as `ScopeFOV:fix`.

---

## [v78]
### Fixed
- **CS mode: "Game error" on every demo** — root cause was a bad demo file, not the minimize watcher. The `cs2_minimize` watcher works in both HLAE and CS modes and is left unchanged.
- **CS mode / HLAE mode UI bleed** — `_on_recsys_change` only changed the section title color, leaving all HLAE widgets (FOV, slow-motion, physics, window mode) permanently visible and editable even in CS mode. It now calls `pack_forget()` on the entire `_hlae_sec` when CS is selected, and restores it with `pack()` when HLAE is selected. Window mode and Minimize remain in RESOLUTION & FRAMERATE (always visible, unchanged).

### Added
- **Per-demo extended logging** in batch run: each demo now logs sequence tick ranges and duration (`seq 1/2  tick 1234→5678  (6.0s)`), active RecSys/Output/TrueView/Concat settings, and HLAE options actually injected (FOV, timescale, AFX, extraArgs).
- **CS mode runtime warning** in batch log: `ℹ RecSys CS: HLAE options ignored. CS2 plays the demo interactively — do NOT minimize CS2 during recording.`
- **RECORDING SYSTEM tooltip for CS** now documents exactly what CS mode does and doesn't support (no FOV, no slow-motion, no physics, no window mode; demo plays from start to finish interactively).
- **Tooltips in TIMING & ROBUSTNESS**: Seconds BEFORE, Seconds AFTER, Close CS2 after demo, Retries, Delay, Demo pause, Order — all now have hover tooltips with recommended values and behavior notes.
- `_slider()` now returns its frame so `add_tip()` can be attached to it.

### Changed
- **HLAE section fully hidden in CS mode** (not just greyed-out title). Switching back to HLAE restores it. Window mode and Minimize on launch remain in RESOLUTION & FRAMERATE and are always accessible regardless of recording system.
- Remaining French in `_build_json` camera comments translated: `Notre joueur meurt`, `Notre joueur tue`, `Phase victim`, `Cible initiale`, `title="Couleur"`.

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
