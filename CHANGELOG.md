# Changelog — CSDM Batch Clips Generator

All notable changes to this project are documented in this file.  
Format inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> **Version numbering note:** sub-releases previously written as `133.xx` or `143.x` have been
> renumbered as sequential integers. `133.33` → `134`, `133.34` → `135`, …, `133.42` → `143`,
> `143.0` → `144`, `143.1` → `145`, …, `143.8` → `152`. Each dot was always one real increment.

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
