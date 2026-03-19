#!/usr/bin/env python3
"""CSDM Batch Clips Generator v123"""


import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
import subprocess, threading, json, os, tempfile, time, shutil, re, uuid, random, shlex
import bisect, concurrent.futures
from collections import defaultdict, deque
import calendar as cal_mod
from datetime import datetime, timedelta, date
from pathlib import Path

try:
    import psycopg2
    HAS_PG = True
except ImportError:
    HAS_PG = False

# ═══════════════════════════════════════════════════════
#  Version
# ═══════════════════════════════════════════════════════
APP_VERSION = "v123"

# ═══════════════════════════════════════════════════════
#  Theme
# ═══════════════════════════════════════════════════════
#  Theme system
# ═══════════════════════════════════════════════════════

# Background presets — each defines the full bg family
_BG_PRESETS = {
    "dark":    {"BG": "#0e0e0e", "BG2": "#141414", "BG3": "#1a1a1a",
                "BORDER": "#252525", "TEXT": "#e0e0e0", "MUTED": "#999999",
                "DESC_COLOR": "#888888", "LOG_BG": "#090909"},
    "amoled":  {"BG": "#000000", "BG2": "#000000", "BG3": "#0a0a0a",
                "BORDER": "#1a1a1a", "TEXT": "#e0e0e0", "MUTED": "#888888",
                "DESC_COLOR": "#777777", "LOG_BG": "#000000"},
    "deepblue":{"BG": "#0a0f1e", "BG2": "#0d1526", "BG3": "#111d35",
                "BORDER": "#1a2a4a", "TEXT": "#cdd6f4", "MUTED": "#7a8fba",
                "DESC_COLOR": "#6a7faa", "LOG_BG": "#080d18"},
    "white":   {"BG": "#f0f0f0", "BG2": "#ffffff", "BG3": "#e8e8e8",
                "BORDER": "#cccccc", "TEXT": "#111111", "MUTED": "#666666",
                "DESC_COLOR": "#888888", "LOG_BG": "#fafafa"},
}

# Semantic accent colours — accent + darker shade
_ACCENT_PRESETS = {
    "green":    {"ACCENT": "#22c55e", "ACCENT2": "#16a34a"},
    "blue":     {"ACCENT": "#3b82f6", "ACCENT2": "#2563eb"},
    "orange":   {"ACCENT": "#f97316", "ACCENT2": "#ea580c"},
    "purple":   {"ACCENT": "#a855f7", "ACCENT2": "#9333ea"},
    "red":      {"ACCENT": "#ef4444", "ACCENT2": "#dc2626"},
    "cyan":     {"ACCENT": "#06b6d4", "ACCENT2": "#0891b2"},
    "pink":     {"ACCENT": "#ec4899", "ACCENT2": "#db2777"},
    "yellow":   {"ACCENT": "#eab308", "ACCENT2": "#ca8a04"},
}

# Status colours — always the same regardless of accent/bg
_STATUS_COLOURS = {
    "GREEN":  "#86efac",
    "RED":    "#f87171",
    "YELLOW": "#fde68a",
    "BLUE":   "#93c5fd",
}

def _build_theme(bg_name: str, accent_name_or_hex: str) -> dict:
    """Build a complete theme dict from a bg-preset name and accent name or raw hex.

    Returns a flat dict with all colour keys used throughout the UI.
    """
    bg = _BG_PRESETS.get(bg_name, _BG_PRESETS["dark"])
    if accent_name_or_hex in _ACCENT_PRESETS:
        ac = _ACCENT_PRESETS[accent_name_or_hex]
        accent  = ac["ACCENT"]
        accent2 = ac["ACCENT2"]
    else:
        # Raw hex from custom colour picker
        accent  = accent_name_or_hex if accent_name_or_hex.startswith("#") else "#22c55e"
        # Derive darker shade: darken by ~20%
        try:
            h = accent.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r2, g2, b2 = int(r * 0.72), int(g * 0.72), int(b * 0.72)
            accent2 = f"#{r2:02x}{g2:02x}{b2:02x}"
        except Exception:
            accent2 = accent
    return {
        "BG":        bg["BG"],
        "BG2":       bg["BG2"],
        "BG3":       bg["BG3"],
        "BORDER":    bg["BORDER"],
        "TEXT":      bg["TEXT"],
        "MUTED":     bg["MUTED"],
        "DESC_COLOR":bg["DESC_COLOR"],
        "LOG_BG":    bg["LOG_BG"],
        "ORANGE":    accent,
        "ORANGE2":   accent2,
        "GREEN":     _STATUS_COLOURS["GREEN"],
        "RED":       _STATUS_COLOURS["RED"],
        "YELLOW":    _STATUS_COLOURS["YELLOW"],
        "BLUE":      _STATUS_COLOURS["BLUE"],
    }

# Active theme — populated at startup and updated on theme change
_THEME: dict = _build_theme("dark", "green")

def _t(key: str) -> str:
    """Return the current theme colour for a given key."""
    return _THEME[key]

# Apply the initial theme to module-level globals for backward compat
BG       = _THEME["BG"]
BG2      = _THEME["BG2"]
BG3      = _THEME["BG3"]
BORDER   = _THEME["BORDER"]
ORANGE   = _THEME["ORANGE"]
ORANGE2  = _THEME["ORANGE2"]
TEXT     = _THEME["TEXT"]
MUTED    = _THEME["MUTED"]
GREEN    = _THEME["GREEN"]
RED      = _THEME["RED"]
YELLOW   = _THEME["YELLOW"]
BLUE     = _THEME["BLUE"]
DESC_COLOR = _THEME["DESC_COLOR"]

def _apply_theme_globals(bg_name: str, accent: str):
    """Recompute _THEME and update every module-level colour global in-place.

    Called at startup (before widgets) and again when user changes theme.
    After this, any new widget creation will use the updated globals.
    Existing widgets are updated by App._apply_theme_to_widgets().
    """
    global _THEME
    global BG, BG2, BG3, BORDER, ORANGE, ORANGE2, TEXT, MUTED
    global GREEN, RED, YELLOW, BLUE, DESC_COLOR
    _THEME = _build_theme(bg_name, accent)
    BG        = _THEME["BG"]
    BG2       = _THEME["BG2"]
    BG3       = _THEME["BG3"]
    BORDER    = _THEME["BORDER"]
    ORANGE    = _THEME["ORANGE"]
    ORANGE2   = _THEME["ORANGE2"]
    TEXT      = _THEME["TEXT"]
    MUTED     = _THEME["MUTED"]
    GREEN     = _THEME["GREEN"]
    RED       = _THEME["RED"]
    YELLOW    = _THEME["YELLOW"]
    BLUE      = _THEME["BLUE"]
    DESC_COLOR = _THEME["DESC_COLOR"]

FONT_MONO = ("Consolas", 10)
FONT_SM = ("Consolas", 9)
FONT_DESC = ("Consolas", 8)

# Shared kwargs for flat checkbox/radio widgets
_CHK_KW = dict(font=FONT_SM, bg=BG2, fg=MUTED, activebackground=BG2,
               activeforeground=ORANGE, selectcolor=BG3,
               relief="flat", bd=0, cursor="hand2", highlightthickness=0)
_BTN_KW = dict(relief="flat", bd=0, cursor="hand2", highlightthickness=0,
               activebackground=BORDER, activeforeground=ORANGE)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csdm_config.json")
PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csdm_presets.json")
PLAYERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csdm_players.json")
ASM_NAMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csdm_asm_names.json")
CSDM_RUNTIME_CFG_NAME = "csdm_batch_runtime.cfg"
CSDM_RUNTIME_BLOCK_START = "// >>> CSDM_BATCH_RUNTIME START >>>"
CSDM_RUNTIME_BLOCK_END = "// <<< CSDM_BATCH_RUNTIME END <<<"

EVENTS = ["Kills", "Deaths", "Rounds"]
ENCODER_OPTIONS = ["FFmpeg"]
RECSYS_OPTIONS = ["HLAE", "CS"]
VIDEO_CONTAINERS = ["mp4", "avi", "mkv", "mov", "webm"]
PERSP_LABELS = {"killer": "POV Killer", "victim": "POV Victim", "both": "Both"}

KILL_FILTER_LABELS = {
    "kill_mod_trois_shot": "TROIS SHOT",
    "kill_mod_no_trois_shot": "NO TROIS SHOT",
    "kill_mod_trois_tap": "TROIS TAP",
    "kill_mod_one_tap": "ONE TAP",
    "kill_mod_spray_transfer": "SPRAY",
    "kill_mod_high_velocity": "FERRARI PEEK",
    "kill_mod_flick": "FLICK",
    "kill_mod_sauveur": "SAVIOR",
    "kill_mod_entry_frag": "ENTRY",
    "kill_mod_ace": "ACE",
    "kill_mod_multi_kill": "MULTI",
    "kill_mod_bourreau": "BULLY",
    "kill_mod_eco_frag": "ECO",
    "kill_mod_attacker_blind": "BLIND",
    "kill_mod_through_smoke": "THROUGH SMOKE",
    "kill_mod_no_scope": "NO SCOPE",
    "kill_mod_wall_bang": "WALLBANG",
    "kill_mod_airborne": "AIRBORNE",
    "kill_mod_assisted_flash": "ASSISTED FLASH",
    "kill_mod_collateral": "COLLATERAL",
}

VIDEO_CODECS_INFO = {
    "libx264": "H.264 CPU — Universal, compatible everywhere.",
    "libx265": "H.265/HEVC CPU — Better compression, slower.",
    "libsvtav1": "AV1 CPU (SVT) — Modern, excellent compression.",
    "libaom-av1": "AV1 CPU (ref) — Very slow but max quality.",
    "h264_nvenc": "H.264 GPU NVIDIA — Ultra-fast.",
    "hevc_nvenc": "HEVC GPU NVIDIA — H.265 accelerated.",
    "av1_nvenc": "AV1 GPU NVIDIA — RTX 40xx+.",
    "h264_amf": "H.264 GPU AMD — Fast (RX 5000+).",
    "hevc_amf": "HEVC GPU AMD — H.265 accelerated.",
    "av1_amf": "AV1 GPU AMD — RX 7000+.",
    "libvpx-vp9": "VP9 CPU — Good quality, slow.",
    "prores_ks": "ProRes — Large files, pro quality.",
    "utvideo": "UT Video — Lightweight lossless.",
    "rawvideo": "Raw — Uncompressed raw.",
}
VIDEO_CODECS = list(VIDEO_CODECS_INFO.keys())

AUDIO_CODECS_INFO = {
    "libmp3lame": "MP3 — Compatible everywhere.",
    "aac": "AAC — Better than MP3, modern standard.",
    "pcm_s16le": "PCM WAV — Raw uncompressed.",
    "libopus": "Opus — Excellent, especially streaming/voice.",
    "flac": "FLAC — Compressed lossless.",
}
AUDIO_CODECS = list(AUDIO_CODECS_INFO.keys())

RESOLUTIONS = [
    ("1280x720", 1280, 720), ("1920x1080", 1920, 1080),
    ("2560x1440", 2560, 1440), ("3840x2160", 3840, 2160),
]
FRAMERATES = [30, 60, 120, 240, 300]

# ── TROIS SHOT ────────────────────────────────────────────────────────────
# Thresholds calibrated from real demoparser2 data (accuracy_penalty in Source2 radians):
#   precise stationary shot  ≈ 0.004
#   shot while moving        ≈ 0.010–0.025
#   spam (2nd+ rapid shot)   ≈ 0.030–0.050
#   max observed        ≈ 0.050
#
# Per-weapon logic:
#   Deagle / R8   : lucky if acc > 0.015  (not first stationary shot)
#   AWP / SSG 08  : lucky if NOT scoped  (is_scoped False at shot tick)
#   SCAR-20/G3SG1 : lucky if vel > 100 u/s OR acc > 0.012 OR not scoped
TROIS_SHOT_THRESHOLDS = {
    "weapon_deagle":   {"acc": 0.015, "scope": False, "vel": False},
    "weapon_revolver": {"acc": 0.015, "scope": False, "vel": False},
    "weapon_awp":      {"acc": 0.010, "scope": True,  "vel": False},
    "weapon_scar20":   {"acc": 0.010, "scope": True,  "vel": True},
    "weapon_g3sg1":    {"acc": 0.010, "scope": True,  "vel": True},
    "weapon_ssg08":    {"acc": 0.010, "scope": True,  "vel": False},
}
# Mapping CSDM names (lowercase) → demoparser2 name
CSDM_TO_DP2_WEAPON = {
    "deagle":         "weapon_deagle",
    "desert eagle":   "weapon_deagle",
    "revolver":       "weapon_revolver",
    "r8 revolver":    "weapon_revolver",
    "awp":            "weapon_awp",
    "scar-20":        "weapon_scar20",
    "scar20":         "weapon_scar20",
    "g3sg1":          "weapon_g3sg1",
    "ssg 08":         "weapon_ssg08",
    "ssg08":          "weapon_ssg08",
    "ssg-08":         "weapon_ssg08",
}
# Tick window for demoparser2 shot matching (~1 second at CS2 64 tick/s)
DP2_TICK_WINDOW = 128

# ── SPRAY TRANSFER ────────────────────────────────────────────────────────
# Automatic weapons eligible for spray transfer detection.
# A spray transfer = player kills ≥2 victims in one continuous burst
# (no trigger release — no gap > SPRAY_MAX_GAP ticks between weapon_fire events).
# Excluded: snipers (AWP, SSG08), auto-snipers (SCAR-20, G3SG1), shotguns, pistols.
# CZ75-Auto is a pistol but fires automatically — included.
SPRAY_TRANSFER_WEAPONS: set = {
    # Rifles (fully automatic)
    "ak47", "m4a1", "m4a1_silencer", "galilar", "famas", "sg556", "aug",
    "ak-47", "m4a4", "m4a1-s", "galil ar", "sg 553",
    # SMGs
    "mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon",
    "mac-10", "mp5-sd", "ump-45", "pp-bizon",
    # Heavy auto
    "m249", "negev",
    # CZ75 (only full-auto pistol)
    "cz75a", "cz75-auto",
}
# Lowercase version for fast lookup
SPRAY_TRANSFER_WEAPONS_LOWER: set = {w.lower() for w in SPRAY_TRANSFER_WEAPONS}
# demoparser2 weapon_fire suffix → display name (for logging)
# CS2 RPM reference values (approximate) used to compute max gap between shots:
#   AK-47: 600 rpm → ~6.4 ticks/shot at 64tick
#   M4A4:  666 rpm → ~5.8 ticks/shot
#   M249:  750 rpm → ~5.1 ticks/shot
# We allow 3× the cycle time as tolerance for spray transfer detection.
# At 64 tick: 3 × (64*60 / RPM_min) = 3 × (3840/600) ≈ 19 ticks max gap.
SPRAY_MAX_GAP_TICKS = 22  # ~0.34s at 64tick — generous to handle peeks/lag

# Base definitions (height) available in structured selector
DEFINITIONS = [
    ("720p",  720),
    ("1080p", 1080),
    ("1440p", 1440),
    ("4K",    2160),
]

# Aspect ratio → (width, height) of ratio to calculate width
ASPECT_RATIOS = [
    ("16:9",  16, 9),
    ("4:3",   4,  3),
    ("21:9",  21, 9),
    ("16:10", 16, 10),
    ("1:1",   1,  1),
]

TAG_PRESET_COLORS = [
    "#f97316", "#ef4444", "#eab308", "#22c55e", "#3b82f6",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f43f5e", "#6366f1",
    "#0ea5e9", "#84cc16", "#d946ef", "#f59e0b", "#10b981",
    "#6b7280", "#a855f7", "#e11d48", "#0891b2", "#65a30d",
]

# ═══════════════════════════════════════════════════════
#  Weapon Categories for CS2
# ═══════════════════════════════════════════════════════
WEAPON_CATEGORIES = {
    "Pistols": [
        "usp_silencer", "hkp2000", "glock", "p250", "fiveseven",
        "cz75a", "tec9", "elite", "deagle", "revolver",
        "usp-s", "p2000", "glock-18", "five-seven", "cz75-auto",
        "tec-9", "dual berettas", "desert eagle", "r8 revolver",
        "USP-S", "P2000", "Glock-18", "P250", "Five-SeveN",
        "CZ75-Auto", "Tec-9", "Dual Berettas", "Desert Eagle", "R8 Revolver",
    ],
    "SMGs": [
        "mac10", "mp9", "mp7", "mp5sd", "ump45", "p90", "bizon",
        "mac-10", "mp5-sd", "ump-45", "pp-bizon",
        "MAC-10", "MP9", "MP7", "MP5-SD", "UMP-45", "P90", "PP-Bizon",
    ],
    "Rifles": [
        "ak47", "m4a1", "m4a1_silencer", "galilar", "famas", "sg556", "aug",
        "ak-47", "m4a4", "m4a1-s", "galil ar", "sg 553",
        "AK-47", "M4A4", "M4A1-S", "Galil AR", "FAMAS", "SG 553", "AUG",
    ],
    "Snipers": [
        "awp", "ssg08", "scar20", "g3sg1",
        "ssg 08", "scar-20",
        "AWP", "SSG 08", "SCAR-20", "G3SG1",
    ],
    "Heavy": [
        "nova", "xm1014", "mag7", "sawedoff", "m249", "negev",
        "mag-7", "sawed-off",
        "Nova", "XM1014", "MAG-7", "Sawed-Off", "M249", "Negev",
    ],
    "Knives": [
        "knife", "knife_t", "knife_karambit", "knife_m9_bayonet", "knife_butterfly",
        "knife_push", "knife_tactical", "knife_falchion", "knife_survival_bowie",
        "knife_ursus", "knife_gypsy_jackknife", "knife_stiletto", "knife_widowmaker",
        "knife_skeleton", "knifegg",
        "Knife",
    ],
    "Grenades & Utility": [
        # Internal names CSDM/Source
        "hegrenade", "incgrenade", "molotov", "inferno",
        "flashbang", "smokegrenade", "decoy",
        # Variants with spaces
        "he grenade", "incendiary grenade", "decoy grenade",
        "smoke grenade", "flash",
        # Display names (capitalised)
        "HE Grenade", "Incendiary Grenade", "Molotov", "Decoy Grenade",
        "Flashbang", "Smoke Grenade",
        # Additional CS2 variants
        "weapon_hegrenade", "weapon_incgrenade", "weapon_molotov", "weapon_inferno",
        "weapon_flashbang", "weapon_smokegrenade", "weapon_decoy",
        "SmokeGrenade", "HeGrenade", "IncGrenade",
        "smoke_grenade", "he_grenade", "inc_grenade",
        "frag grenade", "fire bomb", "diversion device", "emp grenade",
    ],
    "C4 / World": [
        # Explosion C4, world damage (fall, trigger_hurt, etc.)
        "c4", "world", "suicide", "world_entity",
        "C4",
    ],
    "Misc": [
        # Zeus and special weapons — non-lethal by nature but can kill
        "taser",
        "Zeus x27",
    ],
}

WEAPON_ICONS = {'Pistols': '🔫', 'SMGs': '🔫', 'Rifles': '🎯', 'Snipers': '🎯', 'Heavy': '💥', 'Knives': '🔪', 'Grenades & Utility': '💣', 'C4 / World': '💥', 'Misc': '⚡', 'Other': '❓'}

def _weapon_category(weapon_name):
    return _WEAPON_LOOKUP.get(weapon_name.lower().strip(), "Other")

# Flat lookup built once at load time — O(1) instead of O(n²)
_WEAPON_LOOKUP: dict = {
    w.lower(): cat
    for cat, weapons in WEAPON_CATEGORIES.items()
    for w in weapons
}

# Delayed-effect weapons: DB tick = throw/impact, death may occur much later.
# We add extra BEFORE time for these weapons so the death is not clipped..
# inferno/molotov: victim can burn for ~7s after the throw.
# hegrenade: explosion ~1s after the throw.
# c4: variable timer, typically ~40s into the round.
DELAYED_EFFECT_WEAPONS = {
    "hegrenade", "incgrenade", "molotov", "inferno",
    "he grenade", "incendiary grenade",
}

DEFAULT_CONFIG = {
    "pg_host": "127.0.0.1", "pg_port": "5432",
    "pg_user": "postgres", "pg_pass": "", "pg_db": "csdm",
    "csdm_exe": r"C:\Users\Trois\AppData\Local\Programs\cs-demo-manager\csdm.CMD",
    "output_dir": r"H:\CS\CSVideos\Raws",
    "output_dir_clips":    r"H:\CS\CSVideos\Raws",   # raw clips per demo
    "output_dir_concat":   "",   # concatenated clips (empty = same as raw)
    "output_dir_assembled": "",  # final assembled file (empty = same as raw)
    "cs2_cfg_dir": "",
    "ui_window_w": 1600,
    "ui_window_h": 900,
    "ui_split_pct": 60,
    "ui_remember_layout": True,
    "theme_bg": "dark",      # background preset: dark | amoled | deepblue | white
    "theme_accent": "green", # accent preset or custom hex: green | blue | orange | purple | red | cyan | pink | yellow | #rrggbb
    "steam_id": "", "player_name": "",
    "events": ["Kills"], "weapons": [],
    "date_from": "", "date_to": "",
    "before": 3, "after": 5,
    "encoder": "FFmpeg", "recsys": "HLAE",
    "tickrate": 64,
    "use_config_file_mode": True, "close_game_after": True,
    "subfolder_per_demo": True,
    "width": 1920, "height": 1080, "framerate": 60,
    "crf": 18, "video_codec": "libx264", "audio_codec": "libmp3lame",
    "audio_bitrate": 256, "video_container": "mp4",
    "ffmpeg_input_params": "", "ffmpeg_output_params": "",
    "death_notices_duration": 5, "show_only_death_notices": True,
    "concatenate_sequences": False, "true_view": True,
    "tag_on_export": "", "tag_enabled": False,
    "retry_count": 2, "retry_delay": 15, "delay_between_demos": 3,
    # Final assembly of all clips after batch
    "assemble_after": False,      # concatenate all clips after batch
    "delete_after_assemble": False,  # delete source clips after assembly
    "assemble_output": "assembled.mp4",
    # Perspective / POV
    "perspective": "killer",   # "killer" | "victim" | "both"
    # In victim/both mode: duration (s) to follow killer before switching to victim
    "victim_pre_s": 2,
    # Clip recording order
    "clip_order": "chrono",    # "chrono" | "random"
    # Headshot filter — independent of kill-mod logic
    # "all" = include all kills  |  "only" = headshots only  |  "exclude" = non-headshots only
    "headshots_mode": "all",
    "teamkills_mode": "include",
    "include_suicides": True,   # include suicides (weapon world/suicide/world_entity)
    # Kill modifiers — logic mode per category
    # "any"   = OR  (at least one must match)
    # "all"   = AND (every checked filter must match)
    # "mixed" = required filters must all match AND at least one optional filter matches
    "kill_mod_logic_mods": "any",   # Mods section (DB boolean columns)
    "kill_mod_logic_dp2":  "any",   # demoparser2 modifiers
    "kill_mod_logic_db":   "any",   # DB post-filter modifiers (entry, ace, multi, bully, eco)
    # Per-filter "required" flags — only active when category logic == "mixed"
    "kill_mod_through_smoke_req":  False,
    "kill_mod_no_scope_req":       False,
    "kill_mod_wall_bang_req":      False,
    "kill_mod_airborne_req":       False,
    "kill_mod_assisted_flash_req": False,
    "kill_mod_collateral_req":     False,
    "kill_mod_attacker_blind_req": False,
    "kill_mod_trois_shot_req":     False,
    "kill_mod_no_trois_shot_req":  False,
    "kill_mod_trois_tap_req":      False,
    "kill_mod_one_tap_req":        False,
    "kill_mod_spray_transfer_req": False,
    "kill_mod_high_velocity_req":  False,
    "kill_mod_flick_req":          False,
    "kill_mod_sauveur_req":        False,
    "kill_mod_entry_frag_req":     False,
    "kill_mod_ace_req":            False,
    "kill_mod_multi_kill_req":     False,
    "kill_mod_bourreau_req":       False,
    "kill_mod_eco_frag_req":       False,

    # Kill modifiers (OR logic: checked = must match; none checked = no filter)
    
    "kill_mod_through_smoke": False,   # kill through smoke
    "kill_mod_no_scope": False,        # no-scope kill (sniper)
    "kill_mod_wall_bang": False,       # wallbang kill
    "kill_mod_airborne": False,        # killer airborne
    "kill_mod_assisted_flash": False,  # victim blinded (flash-assisted kill)
    "kill_mod_collateral": False,      # collateral kill (bullet through a victim)
    # TROIS SHOT modifier (v62) — lucky kills on precision weapons via demoparser2
    "kill_mod_trois_shot": False,
    # Inverse modifier: exclude lucky kills (v68)
    "kill_mod_no_trois_shot": False,
    # TROIS TAP modifier (v68) — lucky AND isolated one-tap headshot
    "kill_mod_trois_tap": False,
    # ONE TAP modifier (v66) — isolated single shot headshot, no shot within ±2s
    "kill_mod_one_tap": False,
    # SPRAY TRANSFER modifier (v87) — ≥2 kills in one continuous burst (auto weapons only)
    "kill_mod_spray_transfer": False,
    # DB-based modifiers (v91)
    "kill_mod_entry_frag":     False,  # first kill of the round
    "kill_mod_ace":            False,  # 5-kill round (all 5 opponents)
    "kill_mod_multi_kill":     False,  # ≥3 kills in the same round within N seconds
    "kill_mod_multi_kill_n":   3,      # minimum kills for multi-kill (3=triple, 4=quadra)
    "kill_mod_multi_kill_s":   12,     # max seconds between first and last kill
    "kill_mod_bourreau":       False,  # kills the same victim ≥3 times in the match
    "kill_mod_bourreau_n":     3,      # minimum repeat kills against same victim
    "kill_mod_eco_frag":       False,  # pistol kill vs full-buy opponent
    "kill_mod_attacker_blind": False,  # killer was blinded at shot time (attacker_blind)
    # dp2-based modifiers (v91)
    "kill_mod_high_velocity":  False,  # ferrari peek — one-shot + moving before + resumes after
    "kill_mod_hv_one_shot":    True,   # require isolated shot (no prior fire within ~0.75s)
    "kill_mod_high_vel_thr":   100,    # min approach speed (u/s) — walk=130, run=250
    "kill_mod_flick":          False,  # large view-angle change just before the kill
    "kill_mod_flick_deg":      50,     # minimum angle delta in degrees to qualify
    "kill_mod_sauveur":        False,  # killed an enemy who was hurting a teammate
    # Clutch mode (v82/v93) — player is last alive on team, kills remaining opponents
    "clutch_enabled":     False,
    # 1vX size filter — which opponent counts are included. All False = all included.
    "clutch_1v1":         False,
    "clutch_1v2":         False,
    "clutch_1v3":         False,
    "clutch_1v4":         False,
    "clutch_1v5":         False,
    "clutch_require_win": False,   # only include clutches where the player's team won the round
    "clutch_clip_mode":   "full",  # "full" = one clip per clutch (first→last kill) | "individual" = one clip per kill
    # Sequence options
    "show_xray": True,
    # Encoding preset (libx264/libx265/libsvtav1 only — no effect on GPU)
    "video_preset": "medium",
    # HLAE options (used when recsys == "HLAE")
    "hlae_fov": 90,
    "hlae_slow_motion": 100,   # game speed multiplier in % (100 = normal, 200 = 2x)
    "hlae_afx_stream": False,  # record separate HLAE AFX streams
    "hlae_no_spectator_ui": True,
    "hlae_fix_scope_fov": True,   # mirv_fov handleZoom enabled 1 — fixes scope FOV zoom override
    "hlae_extra_args": "",
    "hlae_workshop_download": False,
    # CS2 physics (injected as console commands via extraArgs)
    "phys_ragdoll_gravity": 600,       # cl_ragdoll_gravity (default 600, negative = float)
    "phys_ragdoll_scale": 1.0,         # ragdoll_gravity_scale (default 1.0)
    "phys_ragdoll_enable": True,       # cl_ragdoll_physics_enable
    "phys_sv_gravity": 800,            # sv_gravity (default 800)
    "phys_blood": True,                # violence_hblood
    "phys_dynamic_lighting": True,     # r_dynamic
    # CS2 window mode injected as Launch Option
    "cs2_window_mode": "none",   # "none" | "fullscreen" | "windowed" | "noborder"
    # Automatically minimize CS2 on launch (requires pywin32)
    "cs2_minimize": False,
    # demoparser2 performance
    "dp2_threads": 2,   # parallel threads for DP2 demo parsing (1–8)
}

PRESET_CATEGORIES = {
    "full": "All (full config)",
    "player": "Player + events + weapons",
    "video": "Video/encoding settings",
    "timing": "Timing + robustness",
}
PRESET_KEYS = {
    "full": None,
    "player": ["steam_id", "player_name", "events", "weapons", "date_from", "date_to",
               "perspective", "victim_pre_s", "headshots_mode", "include_suicides", "teamkills_mode",
               "kill_mod_logic_mods", "kill_mod_logic_dp2", "kill_mod_logic_db",
               "kill_mod_through_smoke", "kill_mod_no_scope", "kill_mod_wall_bang",
               "kill_mod_airborne", "kill_mod_assisted_flash", "kill_mod_collateral",
               "kill_mod_trois_shot", "kill_mod_no_trois_shot", "kill_mod_trois_tap",
               "kill_mod_one_tap", "kill_mod_spray_transfer",
               "kill_mod_entry_frag", "kill_mod_ace", "kill_mod_multi_kill",
               "kill_mod_multi_kill_n", "kill_mod_multi_kill_s",
               "kill_mod_bourreau", "kill_mod_bourreau_n",
               "kill_mod_eco_frag", "kill_mod_attacker_blind",
               "kill_mod_high_velocity", "kill_mod_hv_one_shot", "kill_mod_high_vel_thr",
               "kill_mod_flick", "kill_mod_flick_deg", "kill_mod_sauveur",
               # _req flags (mixed mode)
               "kill_mod_through_smoke_req", "kill_mod_no_scope_req",
               "kill_mod_wall_bang_req", "kill_mod_airborne_req",
               "kill_mod_assisted_flash_req", "kill_mod_collateral_req",
               "kill_mod_attacker_blind_req",
               "kill_mod_trois_shot_req", "kill_mod_no_trois_shot_req",
               "kill_mod_trois_tap_req", "kill_mod_one_tap_req",
               "kill_mod_spray_transfer_req", "kill_mod_high_velocity_req",
               "kill_mod_flick_req", "kill_mod_sauveur_req",
               "kill_mod_entry_frag_req", "kill_mod_ace_req",
               "kill_mod_multi_kill_req", "kill_mod_bourreau_req", "kill_mod_eco_frag_req",
               "clutch_enabled", "clutch_1v1", "clutch_1v2", "clutch_1v3",
               "clutch_1v4", "clutch_1v5",
               "clutch_require_win", "clutch_clip_mode",
               "clip_order", "show_xray"],
    "video": ["encoder", "recsys", "width", "height", "framerate",
              "crf", "video_codec", "video_preset", "audio_codec", "audio_bitrate",
              "video_container", "ffmpeg_input_params", "ffmpeg_output_params",
              "death_notices_duration", "show_only_death_notices", "concatenate_sequences",
              "subfolder_per_demo", "true_view",
              "hlae_fov", "hlae_slow_motion", "hlae_afx_stream",
              "hlae_no_spectator_ui", "hlae_fix_scope_fov", "hlae_workshop_download",
              "hlae_extra_args",
              "phys_ragdoll_gravity", "phys_ragdoll_scale", "phys_ragdoll_enable",
              "phys_sv_gravity", "phys_blood", "phys_dynamic_lighting"],
    "timing": ["before", "after", "close_game_after",
               "retry_count", "retry_delay", "delay_between_demos"],
}

# ═══════════════════════════════════════════════════════
#  Persistence
# ═══════════════════════════════════════════════════════
def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_presets(presets):
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_saved_players():
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_saved_players(players):
    try:
        with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
            json.dump(players, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_asm_names():
    if os.path.exists(ASM_NAMES_FILE):
        try:
            with open(ASM_NAMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_asm_names(names):
    try:
        with open(ASM_NAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(names, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(saved)
            # Backward compat: old headshots_only bool → headshots_mode
            if "headshots_only" in saved and "headshots_mode" not in saved:
                cfg["headshots_mode"] = "only" if saved["headshots_only"] else "all"
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════
#  Date helpers  DD-MM-YYYY <-> YYYY-MM-DD
# ═══════════════════════════════════════════════════════
def iso_to_display(iso_str):
    if not iso_str:
        return ""
    try:
        return datetime.strptime(iso_str.strip(), "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        try:
            datetime.strptime(iso_str.strip(), "%d-%m-%Y")
            return iso_str.strip()
        except ValueError:
            return iso_str

def display_to_iso(disp_str):
    if not disp_str or not disp_str.strip():
        return ""
    s = disp_str.strip()
    try:
        return datetime.strptime(s, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        except ValueError:
            return ""

# ═══════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════
def ensure_csdm_dirs():
    home = Path.home(); created = []
    for sub in ("", "virtualdub", "hlae", "ffmpeg"):
        d = home / ".csdm" / sub if sub else home / ".csdm"
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True); created.append(str(d))
    return created

def check_ffmpeg_available():
    w = shutil.which("ffmpeg")
    if w:
        return True, w
    for name in ("ffmpeg.exe", "ffmpeg"):
        c = Path.home() / ".csdm" / "ffmpeg" / name
        if c.exists():
            return True, str(c)
    return False, None

def fmt_duration(seconds):
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}:{s % 60:02d}"
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"

def safe_folder_name(name):
    name = Path(name).stem
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name[:100]

def build_camera_ticks(seq, tickrate):
    pre_offset = max(1, tickrate // 2)
    post_offset = max(1, tickrate // 8)
    ticks = {seq["start_tick"]}
    for e in seq["events"]:
        et = e["tick"]
        ticks.add(max(seq["start_tick"], et - pre_offset))
        ticks.add(min(seq["end_tick"], et + post_offset))
    return sorted(ticks)

def _generate_id_for_type(data_type):
    dt = (data_type or "").lower().strip()
    for it in ("bigint", "integer", "int", "int4", "int8", "smallint",
               "int2", "serial", "bigserial", "smallserial"):
        if it in dt:
            return random.randint(100_000_000, 9_999_999_999)
    if "uuid" in dt:
        return str(uuid.uuid4())
    if any(t in dt for t in ("text", "char", "varchar", "character")):
        return str(uuid.uuid4())
    return random.randint(100_000_000, 9_999_999_999)

def _contrast_fg(hex_color):
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"
    except Exception:
        return "#ffffff"

# ═══════════════════════════════════════════════════════
#  Calendar Popup
# ═══════════════════════════════════════════════════════

def _count_kills(events):
    """Count kill-type events in a list."""
    return sum(1 for e in events if e.get("type") == "kill")

class CalendarPopup(tk.Toplevel):
    def __init__(self, parent, callback, initial_date=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=BORDER)
        self.callback = callback
        self.attributes("-topmost", True)
        today = date.today()
        self._year = initial_date.year if initial_date else today.year
        self._month = initial_date.month if initial_date else today.month
        self._today = today
        inner = tk.Frame(self, bg=BG2, padx=6, pady=6)
        inner.pack(padx=1, pady=1)
        nav = tk.Frame(inner, bg=BG2)
        nav.pack(fill="x", pady=(0, 6))
        tk.Button(nav, text="◀", font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat",
                  bd=0, cursor="hand2", width=3, command=self._prev).pack(side="left")
        self._title = tk.Label(nav, text="", font=("Consolas", 9, "bold"), bg=BG2, fg=ORANGE)
        self._title.pack(side="left", fill="x", expand=True)
        tk.Button(nav, text="▶", font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat",
                  bd=0, cursor="hand2", width=3, command=self._next).pack(side="right")
        hdr = tk.Frame(inner, bg=BG2)
        hdr.pack(fill="x")
        for d in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"):
            tk.Label(hdr, text=d, font=FONT_DESC, fg=MUTED, bg=BG2, width=4).pack(side="left")
        self._grid = tk.Frame(inner, bg=BG2)
        self._grid.pack(fill="x")
        self._draw()
        qr = tk.Frame(inner, bg=BG2)
        qr.pack(fill="x", pady=(6, 0))
        tk.Button(qr, text="Today", font=FONT_DESC, bg=BG3, fg=GREEN, relief="flat",
                  bd=0, cursor="hand2", command=lambda: self._select(today)).pack(side="left", padx=2)
        tk.Button(qr, text="Clear", font=FONT_DESC, bg=BG3, fg=RED, relief="flat",
                  bd=0, cursor="hand2", command=lambda: self._select(None)).pack(side="right", padx=2)
        self.bind("<FocusOut>", lambda e: self.after(100, self._check_focus))
        self.focus_set()
        self.update_idletasks()
        self.geometry(f"+{parent.winfo_rootx()}+{parent.winfo_rooty() + parent.winfo_height()}")

    def _check_focus(self):
        try:
            if self.focus_get() is None or not str(self.focus_get()).startswith(str(self)):
                self.destroy()
        except Exception:
            pass

    def _prev(self):
        self._month -= 1
        if self._month < 1:
            self._month = 12; self._year -= 1
        self._draw()

    def _next(self):
        self._month += 1
        if self._month > 12:
            self._month = 1; self._year += 1
        self._draw()

    def _draw(self):
        for w in self._grid.winfo_children():
            w.destroy()
        MFR = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
        self._title.config(text=f"{MFR[self._month]} {self._year}")
        for ri, week in enumerate(cal_mod.monthcalendar(self._year, self._month)):
            for ci, day in enumerate(week):
                if day == 0:
                    tk.Label(self._grid, text="", width=4, bg=BG2).grid(row=ri, column=ci)
                else:
                    d = date(self._year, self._month, day)
                    is_t = d == self._today
                    tk.Button(self._grid, text=str(day), width=4, font=FONT_DESC,
                              bg=ORANGE if is_t else BG3, fg="white" if is_t else TEXT,
                              relief="flat", bd=0, cursor="hand2",
                              activebackground=ORANGE2, activeforeground="white",
                              command=lambda dd=d: self._select(dd)).grid(row=ri, column=ci, padx=1, pady=1)

    def _select(self, d):
        self.callback(d)
        self.destroy()

# ═══════════════════════════════════════════════════════
#  Color Picker Dialog
# ═══════════════════════════════════════════════════════
class ColorPickerDialog(tk.Toplevel):
    def __init__(self, parent, initial_color="#f97316"):
        super().__init__(parent)
        self.title("Choose a color")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._color = initial_color
        mlabel(self, "Quick colors").pack(anchor="w", padx=12, pady=(12, 4))
        gf = tk.Frame(self, bg=BG2)
        gf.pack(padx=12)
        for i, c in enumerate(TAG_PRESET_COLORS):
            tk.Button(gf, bg=c, width=3, height=1, relief="flat", bd=0, cursor="hand2",
                      activebackground=c, highlightthickness=2, highlightbackground=BG2,
                      command=lambda cc=c: self._pick(cc)).grid(row=i // 5, column=i % 5, padx=2, pady=2)
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x", padx=12, pady=8)
        pr = tk.Frame(self, bg=BG2)
        pr.pack(fill="x", padx=12)
        mlabel(pr, "Preview:").pack(side="left")
        self._preview = tk.Label(pr, text="  TAG  ", font=("Consolas", 10, "bold"),
                                 bg=initial_color, fg=_contrast_fg(initial_color), padx=12, pady=4)
        self._preview.pack(side="left", padx=(8, 0))
        self._hex_var = tk.StringVar(value=initial_color)
        self._hex_var.trace_add("write", self._on_hex)
        tk.Entry(pr, textvariable=self._hex_var, font=FONT_MONO, bg=BG3, fg=TEXT, width=10,
                 insertbackground=ORANGE, relief="flat", highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ORANGE).pack(side="left", padx=(8, 0), ipady=4)
        br = tk.Frame(self, bg=BG2)
        br.pack(fill="x", padx=12, pady=(10, 12))
        tk.Button(br, text="System picker...", font=FONT_SM, bg=BG3, fg=BLUE, relief="flat",
                  bd=0, cursor="hand2", command=self._sys).pack(side="left")
        tk.Button(br, text="  OK  ", font=FONT_SM, bg=ORANGE, fg="white", relief="flat",
                  bd=0, cursor="hand2", activebackground=ORANGE2,
                  command=self._ok).pack(side="right", ipady=4, ipadx=8)
        tk.Button(br, text="Cancel", font=FONT_SM, bg=BG3, fg=MUTED, relief="flat",
                  bd=0, cursor="hand2", command=self.destroy).pack(side="right", padx=(0, 8), ipady=4, ipadx=8)
        self.update_idletasks()
        self.geometry(
            f"+{parent.winfo_rootx() + parent.winfo_width() // 2 - self.winfo_width() // 2}+{parent.winfo_rooty() + 50}")
        self.wait_window()

    def _pick(self, c):
        self._color = c; self._hex_var.set(c); self._upd()

    def _on_hex(self, *_):
        v = self._hex_var.get().strip()
        if re.match(r'^#[0-9a-fA-F]{6}$', v):
            self._color = v; self._upd()

    def _upd(self):
        try:
            self._preview.config(bg=self._color, fg=_contrast_fg(self._color))
        except Exception:
            pass

    def _sys(self):
        r = colorchooser.askcolor(color=self._color, parent=self, title="Color")
        if r and r[1]:
            self._color = r[1]; self._hex_var.set(r[1]); self._upd()

    def _ok(self):
        self.result = self._color; self.destroy()

# ═══════════════════════════════════════════════════════
#  Widgets
# ═══════════════════════════════════════════════════════
class DateField(tk.Frame):
    def __init__(self, parent, label, var, **kw):
        super().__init__(parent, bg=BG2, **kw)
        mlabel(self, label).pack(fill="x")
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", pady=(3, 0))
        self._var = var
        self._entry = tk.Entry(row, textvariable=var, font=FONT_MONO, bg=BG3, fg=TEXT,
                               insertbackground=ORANGE, relief="flat", bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=ORANGE, width=14)
        self._entry.pack(side="left", ipady=5, ipadx=6)
        tk.Button(row, text="\U0001f4c5", font=FONT_SM, bg=BG3, fg=ORANGE, relief="flat",
                  bd=0, cursor="hand2", activebackground=BORDER, activeforeground=ORANGE,
                  highlightthickness=0, command=self._open).pack(side="left", padx=(4, 0), ipady=4, ipadx=4)

    def _open(self):
        init = None
        s = self._var.get().strip()
        if s:
            try:
                init = datetime.strptime(s, "%d-%m-%Y").date()
            except ValueError:
                pass
        CalendarPopup(self._entry, self._cb, initial_date=init)

    def _cb(self, d):
        self._var.set("" if d is None else d.strftime("%d-%m-%Y"))

class PlayerSearchWidget(tk.Frame):
    """
    Player system v26 — multi-selection:
    • Saved accounts are the source of truth.
    • Click an account to toggle it. Multiple accounts can be active
      simultaneously — all their kills/deaths are included in the query.
    • The DB list below is only for finding and registering players.
    """

    def __init__(self, parent, on_change=None, **kw):
        super().__init__(parent, bg=BG2, **kw)
        self._all_players   = []          # [(label, sid, name, last_seen), …] — base DB
        self._filtered      = []
        self._sort_key      = "name"      # "name" | "date"
        self._sort_rev      = False
        self._lb_sid        = ""
        self._lb_name       = ""
        self._lb_label      = ""
        self._saved_players = load_saved_players()
        self._active_sids   = set()       # source of truth (may contain multiple)
        self._active_names  = {}          # {sid: name}
        self._on_change     = on_change

        # Enable all saved accounts by default
        for p in self._saved_players:
            self._active_sids.add(p["steam_id"])
            self._active_names[p["steam_id"]] = p["name"]

        sp_frame = tk.LabelFrame(
            self,
            text="  ★ REGISTERED ACCOUNTS — click to enable/disable  ",
            bg=BG2, fg=ORANGE, font=("Consolas", 9, "bold"),
            relief="flat", bd=1, highlightthickness=1,
            highlightbackground=BORDER, padx=8, pady=6)
        sp_frame.pack(fill="x", pady=(0, 6))

        self._saved_frame = tk.Frame(sp_frame, bg=BG2)
        self._saved_frame.pack(fill="x")

        self._active_lbl = tk.Label(sp_frame, text="", font=FONT_DESC,
                                     fg=MUTED, bg=BG2, anchor="w")
        self._active_lbl.pack(fill="x", pady=(5, 0))

        sp_btns = tk.Frame(sp_frame, bg=BG2)
        sp_btns.pack(fill="x", pady=(4, 0))
        tk.Button(sp_btns,
                  text="★ Register selection below",
                  font=FONT_DESC, bg=BG3, fg=GREEN, relief="flat",
                  cursor="hand2", bd=0, highlightthickness=0,
                  activeforeground=ORANGE, activebackground=BG3,
                  command=self._save_lb_selection).pack(side="left")

        self._refresh_saved_display()

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(6, 4))
        tk.Label(self,
                 text="DB SEARCH  —  select then ★ to register",
                 font=FONT_DESC, fg=DESC_COLOR, bg=BG2, anchor="w").pack(fill="x")

        sr = tk.Frame(self, bg=BG2)
        sr.pack(fill="x", pady=(4, 0))
        self._placeholder = "Search by name or Steam ID…"
        self._search_entry = tk.Entry(
            sr, font=FONT_MONO, bg=BG3, fg=MUTED,
            insertbackground=ORANGE, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ORANGE)
        self._search_entry.pack(side="left", fill="x", expand=True, ipady=7, ipadx=8)
        self._search_entry.insert(0, self._placeholder)
        self._search_entry.bind("<FocusIn>",    self._on_search_focus_in)
        self._search_entry.bind("<FocusOut>",   self._on_search_focus_out)
        self._search_entry.bind("<KeyRelease>", self._on_search_key)
        self._count_lbl = tk.Label(sr, text="", font=FONT_DESC, bg=BG2, fg=MUTED)
        self._count_lbl.pack(side="right", padx=(6, 0))

        # Sort buttons
        sort_row = tk.Frame(self, bg=BG2)
        sort_row.pack(fill="x", pady=(3, 0))
        mlabel(sort_row, "Sort:").pack(side="left")
        self._sort_name_btn = tk.Button(
            sort_row, text="Name ↑", font=FONT_DESC, bg=BG3, fg=ORANGE,
            relief="flat", bd=0, cursor="hand2", highlightthickness=0,
            activebackground=BORDER, activeforeground=ORANGE,
            command=lambda: self._set_sort("name"))
        self._sort_name_btn.pack(side="left", padx=(4, 0), ipady=2, ipadx=4)
        self._sort_date_btn = tk.Button(
            sort_row, text="Date", font=FONT_DESC, bg=BG3, fg=MUTED,
            relief="flat", bd=0, cursor="hand2", highlightthickness=0,
            activebackground=BORDER, activeforeground=ORANGE,
            command=lambda: self._set_sort("date"))
        self._sort_date_btn.pack(side="left", padx=(4, 0), ipady=2, ipadx=4)
        add_tip(self._sort_date_btn, "Sort by last match date (most recent first).")

        lf = tk.Frame(self, bg=BG2)
        lf.pack(fill="both", expand=True, pady=(4, 0))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self._lb = tk.Listbox(
            lf, font=FONT_MONO, bg=BG3, fg=MUTED,
            selectbackground=BG3, selectforeground=TEXT,
            activestyle="none", relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER, height=4,
            exportselection=False)
        self._lb.grid(row=0, column=0, sticky="nsew")
        self._lb.bind("<<ListboxSelect>>", self._on_lb_select)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._lb.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._lb.configure(yscrollcommand=sb.set)

        self._lb_sel_lbl = tk.Label(
            self, text="", font=FONT_DESC, fg=MUTED, bg=BG2, anchor="w")
        self._lb_sel_lbl.pack(fill="x", pady=(4, 0))

    def _refresh_saved_display(self):
        for w in self._saved_frame.winfo_children():
            w.destroy()
        if not self._saved_players:
            tk.Label(self._saved_frame,
                     text="No registered account. Search below then ★",
                     font=FONT_DESC, fg=MUTED, bg=BG2).pack(anchor="w")
            self._update_active_lbl()
            return
        n = len(self._saved_players)
        for i, p in enumerate(self._saved_players):
            active = p["steam_id"] in self._active_sids
            row_bg = BG3 if active else BG2
            row = tk.Frame(self._saved_frame, bg=row_bg,
                           highlightthickness=1,
                           highlightbackground=ORANGE if active else BORDER)
            row.pack(fill="x", pady=2, ipadx=2, ipady=1)
            # ▲▼ buttons to reorder
            arr = tk.Frame(row, bg=row_bg)
            arr.pack(side="left", padx=(2, 0))
            tk.Button(arr, text="▲", font=FONT_DESC, bg=row_bg, fg=MUTED,
                      relief="flat", bd=0, cursor="hand2",
                      activebackground=BORDER, activeforeground=ORANGE,
                      state="normal" if i > 0 else "disabled",
                      command=lambda idx=i: self._move_saved(idx, -1)
                      ).pack(side="top", pady=(0, 1))
            tk.Button(arr, text="▼", font=FONT_DESC, bg=row_bg, fg=MUTED,
                      relief="flat", bd=0, cursor="hand2",
                      activebackground=BORDER, activeforeground=ORANGE,
                      state="normal" if i < n - 1 else "disabled",
                      command=lambda idx=i: self._move_saved(idx, +1)
                      ).pack(side="top")
            prefix = "✓  " if active else "○  "
            tk.Button(
                row,
                text=f"{prefix}{p['name']}  ({p['steam_id']})",
                font=("Consolas", 9, "bold" if active else "normal"),
                bg=row_bg, fg=ORANGE if active else TEXT,
                relief="flat", cursor="hand2", bd=0, anchor="w",
                activebackground=BG3, activeforeground=ORANGE,
                command=lambda pp=p: self._toggle_saved(pp)
            ).pack(side="left", fill="x", expand=True, ipady=4, ipadx=6)
            tk.Button(
                row, text="✕", font=FONT_DESC,
                bg=row_bg, fg=RED, relief="flat", bd=0, cursor="hand2",
                activebackground=BORDER, activeforeground=RED,
                command=lambda idx=i: self._remove_saved(idx)
            ).pack(side="right", padx=(4, 2))
        self._update_active_lbl()

    def _update_active_lbl(self):
        n = len(self._active_sids)
        if n == 0:
            text = "⚠  No active account — check a player above."
            fg   = RED
        elif n == 1:
            sid  = next(iter(self._active_sids))
            name = self._active_names.get(sid, sid)
            text = f"Active: {name}  ({sid})"
            fg   = GREEN
        else:
            names = ", ".join(self._active_names.get(s, s) for s in sorted(self._active_sids))
            text  = f"{n} active: {names}"
            fg    = GREEN

        self._active_lbl.config(text=text, fg=fg)

        # Mirror the exact same text to the header label
        try:
            app = self.winfo_toplevel()
            app._hdr_player_lbl.config(
                text=text if n > 0 else "",
                fg=fg)
        except Exception:
            pass

    def _toggle_saved(self, p):
        sid = p["steam_id"]
        if sid in self._active_sids:
            self._active_sids.discard(sid)
        else:
            self._active_sids.add(sid)
            self._active_names[sid] = p["name"]
        self._refresh_saved_display()
        if self._on_change:
            self._on_change(p["name"], sid)

    def _save_lb_selection(self):
        if not self._lb_sid:
            messagebox.showinfo("Players",
                "Select a player from the search list first.")
            return
        for p in self._saved_players:
            if p["steam_id"] == self._lb_sid:
                messagebox.showinfo("Players", "This player is already registered.")
                return
        self._saved_players.append({
            "steam_id": self._lb_sid,
            "name":     self._lb_name,
            "label":    self._lb_label,
        })
        save_saved_players(self._saved_players)
        # Auto-activate if it's the first
        if len(self._saved_players) == 1:
            self._active_sids.add(self._lb_sid)
            self._active_names[self._lb_sid] = self._lb_name
            if self._on_change:
                self._on_change(self._lb_name, self._lb_sid)
        self._refresh_saved_display()

    def _remove_saved(self, idx):
        if not (0 <= idx < len(self._saved_players)):
            return
        removed_sid = self._saved_players[idx]["steam_id"]
        self._saved_players.pop(idx)
        save_saved_players(self._saved_players)
        self._active_sids.discard(removed_sid)
        self._active_names.pop(removed_sid, None)
        self._refresh_saved_display()
        if self._on_change:
            self._on_change("", removed_sid)

    def _move_saved(self, idx, direction):
        new_idx = idx + direction
        if not (0 <= new_idx < len(self._saved_players)):
            return
        lst = self._saved_players
        lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
        save_saved_players(lst)
        self._refresh_saved_display()

    def _is_placeholder(self):
        return self._search_entry.cget("fg") == MUTED

    def _on_search_focus_in(self, *_):
        if self._is_placeholder():
            self._search_entry.delete(0, "end")
            self._search_entry.config(fg=TEXT)

    def _on_search_focus_out(self, *_):
        if self._search_entry.get().strip() == "":
            self._search_entry.delete(0, "end")
            self._search_entry.insert(0, self._placeholder)
            self._search_entry.config(fg=MUTED)

    def _on_search_key(self, *_):
        q = "" if self._is_placeholder() else self._search_entry.get()
        self._refresh(q)

    def set_players(self, data, restore_steam_id=""):
        # data: [(label, sid, name, last_seen), ...] — last_seen may be None
        self._all_players = data
        self._refresh("")
        self._count_lbl.config(text=f"{len(data)} players")
        if restore_steam_id:
            for p in self._saved_players:
                if p["steam_id"] == restore_steam_id:
                    if restore_steam_id not in self._active_sids:
                        self._active_sids.add(restore_steam_id)
                        self._active_names[restore_steam_id] = p["name"]
                    self._refresh_saved_display()
                    return

    def _set_sort(self, key):
        if self._sort_key == key:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_key = key
            self._sort_rev = (key == "date")  # date defaults to newest first
        self._update_sort_buttons()
        q = "" if self._is_placeholder() else self._search_entry.get()
        self._refresh(q)

    def _update_sort_buttons(self):
        arrow = "↓" if self._sort_rev else "↑"
        try:
            self._sort_name_btn.config(
                text=f"Name {arrow if self._sort_key == 'name' else ''}".strip(),
                fg=ORANGE if self._sort_key == "name" else MUTED)
            self._sort_date_btn.config(
                text=f"Date {arrow if self._sort_key == 'date' else ''}".strip(),
                fg=ORANGE if self._sort_key == "date" else MUTED)
        except Exception:
            pass

    def _refresh(self, query=""):
        q = query.strip().lower()
        self._lb.delete(0, "end")
        self._filtered = []

        def _last_seen(entry):
            last = entry[3] if len(entry) > 3 else None
            if last is None:
                return 0
            try:
                if hasattr(last, "timestamp"):
                    return last.timestamp()
                if isinstance(last, (int, float)):
                    v = int(last)
                    return v / 1000 if v > 4_000_000_000 else v
                s = str(last).strip()
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(s[:len(fmt)], fmt).timestamp()
                    except ValueError:
                        continue
            except Exception:
                pass
            return 0

        candidates = [
            e for e in self._all_players
            if not q or q in e[0].lower() or q in e[1].lower()
        ]

        if self._sort_key == "date":
            candidates.sort(key=_last_seen, reverse=self._sort_rev)
        else:
            candidates.sort(key=lambda e: e[2].lower(), reverse=self._sort_rev)

        for entry in candidates:
            self._lb.insert("end", entry[0])
            self._filtered.append(entry)

    def _on_lb_select(self, *_):
        sel = self._lb.curselection()
        if not sel or sel[0] >= len(self._filtered):
            return
        entry = self._filtered[sel[0]]
        label, sid, name = entry[0], entry[1], entry[2]
        self._lb_label, self._lb_sid, self._lb_name = label, sid, name
        self._lb_sel_lbl.config(
            text=f"Selected: {name}  ({sid})  ← ★ to register",
            fg=YELLOW)

    def _select_by_label(self, label):
        for i, entry in enumerate(self._filtered):
            if entry[0] == label:
                self._lb.selection_clear(0, "end")
                self._lb.selection_set(i)
                self._lb.see(i)
                self._lb_label, self._lb_sid, self._lb_name = entry[0], entry[1], entry[2]
                break

    def get_steam_ids(self):
        return list(self._active_sids)

    def get_steam_id(self):
        if not self._active_sids:
            return ""
        # Priority: registration order
        for p in self._saved_players:
            if p["steam_id"] in self._active_sids:
                return p["steam_id"]
        return next(iter(self._active_sids))

    def get_name(self):
        sid = self.get_steam_id()
        return self._active_names.get(sid, "")

    def get_label(self):
        sid = self.get_steam_id()
        for p in self._saved_players:
            if p["steam_id"] == sid:
                return p.get("label", f"{p['name']}  ({sid})")
        return f"{self._active_names.get(sid, '')}  ({sid})" if sid else ""

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._c = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self._c.yview)
        self.inner = tk.Frame(self._c, bg=BG)
        self.inner.bind("<Configure>", lambda e: self._c.configure(scrollregion=self._c.bbox("all")))
        self._c.create_window((0, 0), window=self.inner, anchor="nw")
        self._c.configure(yscrollcommand=sb.set)
        self._c.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._c.bind("<Enter>", lambda e: self._c.bind_all("<MouseWheel>",
                                                            lambda ev: self._c.yview_scroll(-1 * (ev.delta // 120),
                                                                                            "units")))
        self._c.bind("<Leave>", lambda e: self._c.unbind_all("<MouseWheel>"))

class Sec(tk.LabelFrame):
    def __init__(self, parent, title, **kw):
        super().__init__(parent, text=f"  {title}  ", bg=BG2, fg=ORANGE,
                         font=("Consolas", 9, "bold"), relief="flat", bd=1,
                         highlightthickness=1, highlightbackground=BORDER, padx=14, pady=10, **kw)

class PathField(tk.Frame):
    def __init__(self, parent, label, desc, var, mode="file"):
        super().__init__(parent, bg=BG2)
        mlabel(self, label, anchor="w").pack(fill="x")
        if desc:
            tk.Label(self, text=desc, font=FONT_DESC, fg=DESC_COLOR, bg=BG2, anchor="w").pack(fill="x")
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", pady=(3, 0))
        tk.Entry(row, textvariable=var, font=FONT_MONO, bg=BG3, fg=TEXT, insertbackground=ORANGE,
                 relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ORANGE).pack(side="left", fill="x", expand=True, ipady=6, ipadx=8)

        def browse():
            p = (filedialog.askopenfilename(filetypes=[("Exe", "*.exe;*.cmd"), ("All files", "*.*")])
                 if mode == "file" else filedialog.askdirectory())
            if p:
                var.set(p)

        tk.Button(row, text=" ... ", command=browse, font=FONT_SM, bg=BG3, fg=MUTED, relief="flat",
                  cursor="hand2", activebackground=BORDER, activeforeground=ORANGE,
                  highlightthickness=0, bd=0).pack(side="left", padx=(4, 0), ipady=6, ipadx=4)

def sentry(parent, var, **kw):
    return tk.Entry(parent, textvariable=var, font=FONT_MONO, bg=BG3, fg=TEXT,
                    insertbackground=ORANGE, relief="flat", bd=0, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ORANGE, **kw)

def scombo(parent, var, values, width=15):
    return ttk.Combobox(parent, textvariable=var, values=values, font=FONT_SM, state="readonly", width=width)

def mlabel(parent, text, **kw):
    return tk.Label(parent, text=text, font=FONT_SM, fg=MUTED, bg=BG2, **kw)

def hchk(parent, text, var, **kw):
    cb_kw = dict(font=FONT_SM, relief="flat", bd=0, cursor="hand2",
                 highlightthickness=0, padx=8, pady=3)
    cb_kw.update(kw)
    cb = tk.Checkbutton(parent, text=text, variable=var, **cb_kw)

    def _update(*_):
        if var.get():
            cb.config(bg=_t("ORANGE2"), fg="white",
                      activebackground=_t("ORANGE"), activeforeground="white",
                      selectcolor=_t("ORANGE2"))
        else:
            cb.config(bg=_t("BG3"), fg=_t("MUTED"),
                      activebackground=_t("BG3"), activeforeground=_t("ORANGE"),
                      selectcolor=_t("BG3"))
    var.trace_add("write", _update)
    _update()
    return cb


def hradio(parent, text, var, value, **kw):
    """Radiobutton with highlight when selected."""
    rb_kw = dict(font=FONT_SM, relief="flat", bd=0, cursor="hand2",
                 highlightthickness=0, padx=8, pady=3)
    rb_kw.update(kw)
    rb = tk.Radiobutton(parent, text=text, variable=var, value=value, **rb_kw)

    def _update(*_):
        if var.get() == value:
            rb.config(bg=_t("ORANGE2"), fg="white",
                      activebackground=_t("ORANGE"), activeforeground="white",
                      selectcolor=_t("ORANGE2"))
        else:
            rb.config(bg=_t("BG3"), fg=_t("MUTED"),
                      activebackground=_t("BG3"), activeforeground=_t("ORANGE"),
                      selectcolor=_t("BG3"))
    var.trace_add("write", _update)
    _update()
    return rb

def desc_label(parent, text):
    return tk.Label(parent, text=text, font=FONT_DESC, fg=DESC_COLOR, bg=BG2, anchor="w",
                    justify="left", wraplength=700)

# ═══════════════════════════════════════════════════════
#  Lightweight tooltip — replaces inline desc_labels
# ═══════════════════════════════════════════════════════
class Tooltip:
    """Hover tooltip widget. Use add_tip(widget, text)."""
    def __init__(self, widget, text):
        self._widget = widget
        self._text   = text
        self._tip    = None
        widget.bind("<Enter>",  self._show, add="+")
        widget.bind("<Leave>",  self._hide, add="+")
        widget.bind("<Destroy>", lambda e: self._hide(), add="+")

    def _show(self, event=None):
        if self._tip or not self._text:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() + 4
        y = self._widget.winfo_rooty()
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self._text, font=("Consolas", 8), fg=TEXT,
                 bg="#2a2a2a", relief="flat", bd=0,
                 padx=8, pady=4, wraplength=340, justify="left").pack()

    def _hide(self, event=None):
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

def add_tip(widget, text):
    """Attach a tooltip to widget if text is non-empty."""
    if text:
        Tooltip(widget, text)

def dp2_badge(parent):
    """Blue 'demoparser2' label with a shared tooltip — attach with .pack()."""
    lbl = tk.Label(parent, text="demoparser2", font=FONT_DESC, fg=BLUE, bg=BG2)
    add_tip(lbl, "Requires: pip install demoparser2")
    return lbl

# ═══════════════════════════════════════════════════════
#  App
# ═══════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        # Apply theme from config before building any widgets
        _apply_theme_globals(
            self.cfg.get("theme_bg", "dark"),
            self.cfg.get("theme_accent", "green")
        )
        self.title(f"CSDM Batch {APP_VERSION}")
        self.configure(bg=BG)
        _w = int(self.cfg.get("ui_window_w", 1600) or 1600)
        _h = int(self.cfg.get("ui_window_h", 900) or 900)
        _w = max(1000, min(3840, _w))
        _h = max(600, min(2160, _h))
        self.geometry(f"{_w}x{_h}")
        self.minsize(1000, 600)
        self.option_add('*TCombobox*Listbox.background', BG3)
        self.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.option_add('*TCombobox*Listbox.selectBackground', ORANGE)
        self.option_add('*TCombobox*Listbox.selectForeground', "white")
        self.option_add('*TCombobox*Listbox.font', FONT_SM)

        self.presets = load_presets()
        self._player_names = {}
        self._tags_list = []
        self._tags_active = set()   # IDs of currently selected tags
        self._tags_schema = {}
        self._demo_checksums = {}  # {demo_path: checksum} — populated by _query_events
        self._demo_dates     = {}  # {demo_path: date_val} — populated by _query_events
        self._ts_cache       = {}  # {demo_path: int|None} — cached _get_demo_ts results
        self._col_cache      = {}  # {(table, tuple(candidates)): col} — cached _find_col results
        self._db_conn        = None  # persistent psycopg2 connection — reused across calls
        self._dp2_verbose    = False  # per-kill dp2 filter logging (debug only — expensive)
        self._tag_search_results = {}
        self._warned_missing_mods: set = set()  # suppress repeat warnings for same absent cols

        self.v = {}
        str_keys = ["pg_host", "pg_port", "pg_user", "pg_pass", "pg_db", "csdm_exe", "output_dir",
                     "date_from", "date_to", "encoder", "recsys", "video_codec",
                     "audio_codec", "video_container", "ffmpeg_input_params", "ffmpeg_output_params",
                     "tag_on_export", "perspective", "hlae_extra_args", "clip_order",
                     "cs2_window_mode",
                     "output_dir_clips", "output_dir_concat", "output_dir_assembled",
                     "assemble_output", "video_preset", "teamkills_mode", "phys_ragdoll_scale",
                     "cs2_cfg_dir",
                     "clutch_clip_mode",
                     "kill_mod_logic_mods", "kill_mod_logic_dp2", "kill_mod_logic_db",
                     "headshots_mode",
                     "theme_bg", "theme_accent"]
        int_keys = ["before", "after", "tickrate", "width", "height", "framerate", "crf", "audio_bitrate",
                     "death_notices_duration", "retry_count", "retry_delay", "delay_between_demos",
                     "hlae_fov", "hlae_slow_motion",
                     "phys_ragdoll_gravity", "phys_sv_gravity",
                     "ui_window_w", "ui_window_h", "ui_split_pct",
                     "victim_pre_s", "dp2_threads",
                     "kill_mod_multi_kill_n", "kill_mod_multi_kill_s",
                     "kill_mod_bourreau_n", "kill_mod_high_vel_thr", "kill_mod_flick_deg"]
        bool_keys = ["use_config_file_mode", "close_game_after", "show_only_death_notices",
                      "concatenate_sequences", "subfolder_per_demo", "true_view", "tag_enabled",
                      "hlae_afx_stream", "hlae_no_spectator_ui",
                      "hlae_fix_scope_fov", "hlae_workshop_download",
                      "include_suicides", "show_xray",
                      "kill_mod_through_smoke", "kill_mod_no_scope", "kill_mod_wall_bang",
                      "kill_mod_airborne", "kill_mod_assisted_flash", "kill_mod_collateral",
                      "kill_mod_trois_shot", "kill_mod_no_trois_shot", "kill_mod_trois_tap",
                      "kill_mod_one_tap", "kill_mod_spray_transfer",
                      "kill_mod_entry_frag", "kill_mod_ace", "kill_mod_multi_kill",
                      "kill_mod_bourreau", "kill_mod_eco_frag", "kill_mod_attacker_blind",
                      "kill_mod_high_velocity", "kill_mod_hv_one_shot", "kill_mod_flick", "kill_mod_sauveur",
                      # Per-filter "required" flags (mixed mode)
                      "kill_mod_through_smoke_req", "kill_mod_no_scope_req",
                      "kill_mod_wall_bang_req", "kill_mod_airborne_req",
                      "kill_mod_assisted_flash_req", "kill_mod_collateral_req",
                      "kill_mod_attacker_blind_req",
                      "kill_mod_trois_shot_req", "kill_mod_no_trois_shot_req",
                      "kill_mod_trois_tap_req", "kill_mod_one_tap_req",
                      "kill_mod_spray_transfer_req", "kill_mod_high_velocity_req",
                      "kill_mod_flick_req", "kill_mod_sauveur_req",
                      "kill_mod_entry_frag_req", "kill_mod_ace_req",
                      "kill_mod_multi_kill_req", "kill_mod_bourreau_req", "kill_mod_eco_frag_req",
                      "assemble_after", "delete_after_assemble",
                      "phys_ragdoll_enable", "phys_blood", "phys_dynamic_lighting",
                      "cs2_minimize",
                     "ui_remember_layout",
                      "clutch_enabled", "clutch_1v1", "clutch_1v2", "clutch_1v3",
                      "clutch_1v4", "clutch_1v5",
                      "clutch_require_win",]
        for k in str_keys:
            val = str(self.cfg.get(k, DEFAULT_CONFIG.get(k, "")))
            if k in ("date_from", "date_to"):
                val = iso_to_display(val)
            self.v[k] = tk.StringVar(value=val)
        for k in int_keys:
            self.v[k] = tk.IntVar(value=self.cfg.get(k, DEFAULT_CONFIG.get(k, 0)))
        for k in bool_keys:
            self.v[k] = tk.BooleanVar(value=self.cfg.get(k, DEFAULT_CONFIG.get(k, False)))
        self.v["resolution"] = tk.StringVar(value=f"{self.v['width'].get()}x{self.v['height'].get()}")

        # Structured resolution selectors (v60)
        # Infer definition from current height
        _h0 = self.v["height"].get()
        _def0 = next((lbl for lbl, h in DEFINITIONS if h == _h0), "1080p")
        self.v["res_definition"] = tk.StringVar(value=_def0)
        # Infer ratio from current width/height
        _w0 = self.v["width"].get()
        _ratio0 = "16:9"
        for _lbl, _rw, _rh in ASPECT_RATIOS:
            if _h0 > 0 and abs(_w0 / _h0 - _rw / _rh) < 0.01:
                _ratio0 = _lbl
                break
        self.v["res_aspect"] = tk.StringVar(value=_ratio0)
        # Custom mode: active if width/height do not match a known preset
        _known = any(
            abs(_w0 / _h0 - rw / rh) < 0.01
            for _, rw, rh in ASPECT_RATIOS
        ) and any(h == _h0 for _, h in DEFINITIONS)
        self.v["res_custom"] = tk.BooleanVar(value=not _known)
        self.db_status = tk.StringVar(value="Not connected")
        self.sel_events = {e: tk.BooleanVar(value=(e in self.cfg.get("events", []))) for e in EVENTS}
        self.sel_weapons = {}
        for w in self.cfg.get("weapons", []):
            self.sel_weapons[w] = tk.BooleanVar(value=True)
        self._running = False
        self._stop_after_current = False
        self._kill_triggered = False
        self._tagged_this_batch = []   # [(demo_path, tag_name)] — for rollback on kill
        self._proc = None
        self._dp2_cache      = {}                  # {demo_path: {"fire_detail": …, "fire_ticks": …}}
        self._dp2_cache_lock = threading.Lock()    # protects _dp2_cache during parallel pre-parse
        self._db_schema = {}
        self._db_col_types = {}
        self._date_col = None
        self._date_col_type = ""      # actual SQL type of the date column
        self._pending_restore_sid  = None   # steam_id to restore once DB is ready
        self._pending_restore_tags = []     # tag names to restore once DB is ready
        self._speed_feedback = None
        self._game_speed_trace_busy = False
        self._log_badges_enabled = tk.BooleanVar(value=True)
        self._log_badges_btn = None
        self._outer_paned = None
        self._layout_cfg_job = None
        # Async log buffer — background threads append here; main thread drains
        # in a single batch every _LOG_PUMP_MS ms instead of one after(0) per line.
        self._log_buf: deque = deque()
        self._log_buf_lock = threading.Lock()

        self.v["hlae_slow_motion"].trace_add("write", self._on_game_speed_var)
        self._build_ui()
        self.after(50, self._log_pump)   # start the async log drain pump

        # PlayerSearchWidget enables all accounts by default; override
        # with the exact saved list if it exists.
        saved_ids = self.cfg.get("steam_ids", [])
        if saved_ids:
            self.player_search._active_sids.clear()
            for sid in saved_ids:
                for p in self.player_search._saved_players:
                    if p["steam_id"] == sid:
                        self.player_search._active_sids.add(sid)
                        self.player_search._active_names[sid] = p["name"]
                        break
            self.player_search._refresh_saved_display()

        # Track width/height → auto-update the resolution combo
        def _sync_res(*_):
            try:
                self.v["resolution"].set(f"{self.v['width'].get()}x{self.v['height'].get()}")
            except Exception:
                pass
        self.v["width"].trace_add("write", _sync_res)
        self.v["height"].trace_add("write", _sync_res)

        # Init structured resolution selectors state (v60)
        self.after(50, self._on_res_custom_toggle)
        self.bind("<Configure>", self._on_window_configure, add="+")
        self.after(60, self._update_res_preview)

        self._auto_save()
        self.after(200, self._preflight)
        if HAS_PG:
            self.after(500, self._connect_and_load)

    def _on_player_change(self, name, sid):
        """Called when the DB search list selection changes.
        Delegate to the player widget's _update_active_lbl so the header
        always shows the same text as the active label in the Capture tab."""
        try:
            self.player_search._update_active_lbl()
        except Exception:
            pass

    def _preflight(self):
        for d in ensure_csdm_dirs():
            self._log(f"[PRE] Created: {d}", "ok")
        ok, p = check_ffmpeg_available()
        self._log(f"[PRE] FFmpeg: {p}" if ok else "[PRE] FFmpeg NON TROUVE", "ok" if ok else "err")
        cli = self._resolve_cli(self.v["csdm_exe"].get())
        self._log(f"[PRE] CLI: {cli}" if os.path.isfile(cli) else f"[PRE] CLI not found: {cli}",
                  "ok" if os.path.isfile(cli) else "err")
        out = self.v["output_dir"].get().strip()
        if out:
            os.makedirs(out, exist_ok=True)
        self._log("[PRE] OK\n", "ok")

    def _collect_config(self):
        cfg = {}
        for k, var in self.v.items():
            if k == "resolution":
                continue
            try:
                val = var.get()
            except Exception:
                # IntVar/BooleanVar raises TclError if the entry field was cleared
                val = DEFAULT_CONFIG.get(k, 0)
            if k in ("date_from", "date_to"):
                val = display_to_iso(val)
            cfg[k] = val
        if cfg.get("encoder") not in ENCODER_OPTIONS:
            cfg["encoder"] = "FFmpeg"
        cfg["events"] = [e for e, v in self.sel_events.items() if v.get()]
        cfg["weapons"] = [w for w, v in self.sel_weapons.items() if v.get()]
        # Compat: output_dir mirrors output_dir_clips
        if cfg.get("output_dir_clips"):
            cfg["output_dir"] = cfg["output_dir_clips"]
        cfg["steam_ids"]   = self.player_search.get_steam_ids()
        cfg["steam_id"]    = self.player_search.get_steam_id()    # compat
        cfg["player_name"] = self.player_search.get_name()
        cfg["active_tags"] = self._get_active_tag_names()         # names of checked tags
        return cfg

    def _auto_save(self):
        save_config(self._collect_config())
        self.after(5000, self._auto_save)

    def _apply_config(self, cfg, keys=None):
        for k, val in cfg.items():
            if keys and k not in keys:
                continue
            # Backward compat: old bool headshots_only → headshots_mode
            if k == "headshots_only":
                if val and "headshots_mode" not in cfg:
                    if "headshots_mode" in self.v:
                        self.v["headshots_mode"].set("only")
                continue
            if k in self.v:
                if k == "encoder" and val not in ENCODER_OPTIONS:
                    val = "FFmpeg"
                self.v[k].set(iso_to_display(str(val)) if k in ("date_from", "date_to") else val)
            elif k == "events":
                for e in EVENTS:
                    self.sel_events[e].set(e in val)
            elif k == "weapons":
                for w, v in self.sel_weapons.items():
                    v.set(w in val)
            elif k == "steam_ids" and isinstance(val, list):
                self.player_search._active_sids.clear()
                for sid in val:
                    for p in self.player_search._saved_players:
                        if p["steam_id"] == sid:
                            self.player_search._active_sids.add(sid)
                            self.player_search._active_names[sid] = p["name"]
                            break
                self.player_search._refresh_saved_display()
            elif k == "steam_id" and val and not cfg.get("steam_ids"):
                # Compat legacy single-player config
                for p in self.player_search._saved_players:
                    if p["steam_id"] == val:
                        self.player_search._active_sids.add(val)
                        self.player_search._active_names[val] = p["name"]
                        self.player_search._refresh_saved_display()
                        break
                else:
                    self._pending_restore_sid = val
            elif k == "active_tags" and isinstance(val, list) and val:
                # Restore checked tags — deferred if DB not yet ready
                self._restore_active_tags(val)

    def _restore_active_tags(self, tag_names):
        """Restore the set of active (checked) tags from a list of names.
        If _tags_list is not yet populated (DB not connected), stores the names
        in _pending_restore_tags for deferred restoration on _on_load_success."""
        if self._tags_list:
            self._tags_active.clear()
            for tid, tn, _ in self._tags_list:
                if tn in tag_names:
                    self._tags_active.add(tid)
            try:
                self._refresh_tags_list_display()
            except Exception:
                pass
        else:
            self._pending_restore_tags = list(tag_names)


    def _pg(self):
        """Return a live psycopg2 connection, reusing the existing one when possible.
        Creates a new connection on first call or if the existing one is closed/broken.
        The _connect_and_load thread always opens its own connection (thread safety).
        """
        if self._db_conn is not None:
            try:
                # Quick liveness check — closed attribute is False when open
                if not self._db_conn.closed:
                    return self._db_conn
            except Exception:
                pass
        self._db_conn = psycopg2.connect(
            host=self.v["pg_host"].get(), port=int(self.v["pg_port"].get()),
            user=self.v["pg_user"].get(), password=self.v["pg_pass"].get(),
            dbname=self.v["pg_db"].get(), connect_timeout=5)
        return self._db_conn

    def _pg_fresh(self):
        """Always create a new connection (used by background threads that must
        not share the main-thread connection)."""
        return psycopg2.connect(
            host=self.v["pg_host"].get(), port=int(self.v["pg_port"].get()),
            user=self.v["pg_user"].get(), password=self.v["pg_pass"].get(),
            dbname=self.v["pg_db"].get(), connect_timeout=5)

    def _connect_and_load(self):
        self.db_status.set("Connecting...")
        self.db_status_lbl.config(fg=YELLOW)

        def task():
            try:
                conn = self._pg_fresh()
                with conn.cursor() as cur:
                    schema = {}
                    col_types = {}
                    for t in ["kills", "matches", "rounds", "players", "tags",
                              "checksum_tags", "match_tags"]:
                        cur.execute(
                            "SELECT column_name, data_type FROM information_schema.columns "
                            "WHERE table_name=%s ORDER BY ordinal_position", (t,))
                        ri = cur.fetchall()
                        cols = [r[0] for r in ri]
                        types = {r[0]: r[1] for r in ri}
                        if cols:
                            schema[t] = cols
                            col_types[t] = types

                    # Fetch players with their last-seen match date for sorting
                    _m_cols_check = schema.get("matches", [])
                    _date_col_for_players = next(
                        (c for c in _m_cols_check
                         if col_types.get("matches", {}).get(c, "").lower()
                         in {"date","timestamp","timestamp with time zone",
                             "timestamp without time zone","timestamptz","bigint","integer","int","int4","int8"}
                         and "analyze" not in c.lower()),
                        None)
                    _pmk_col = next(
                        (c for c in schema.get("players", [])
                         if c.lower() in ("match_checksum","match_id","checksum")),
                        None)
                    _mmk_col = next(
                        (c for c in schema.get("matches", [])
                         if c.lower() in ("checksum","id","match_id")),
                        None)
                    if _date_col_for_players and _pmk_col and _mmk_col:
                        try:
                            cur.execute(
                                f'SELECT DISTINCT p.name, p.steam_id, '
                                f'MAX(m."{_date_col_for_players}") as last_seen '
                                f'FROM players p '
                                f'LEFT JOIN matches m ON m."{_mmk_col}" = p."{_pmk_col}" '
                                f'WHERE p.name IS NOT NULL AND p.steam_id IS NOT NULL '
                                f"AND p.name!='' AND p.steam_id!='' "
                                f'GROUP BY p.name, p.steam_id ORDER BY p.name')
                            rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
                        except Exception:
                            cur.execute(
                                "SELECT DISTINCT p.name, p.steam_id FROM players p "
                                "WHERE p.name IS NOT NULL AND p.steam_id IS NOT NULL "
                                "AND p.name!='' AND p.steam_id!='' ORDER BY p.name")
                            rows = [(r[0], r[1], None) for r in cur.fetchall()]
                    else:
                        cur.execute(
                            "SELECT DISTINCT p.name, p.steam_id FROM players p "
                            "WHERE p.name IS NOT NULL AND p.steam_id IS NOT NULL "
                            "AND p.name!='' AND p.steam_id!='' ORDER BY p.name")
                        rows = [(r[0], r[1], None) for r in cur.fetchall()]

                    _m_types = col_types.get("matches", {})
                    _m_cols  = schema.get("matches", [])
                    _DATE_TYPES = {
                        "date", "timestamp", "timestamp with time zone",
                        "timestamp without time zone", "timestamptz",
                    }
                    _INT_TYPES = {"bigint", "integer", "int", "int4", "int8",
                                  "smallint", "int2", "numeric"}

                    # Candidate columns: date/timestamp type, OR bigint with date-like name,
                    # OR text with 'date'/'time' in name
                    _candidates = []
                    for c in _m_cols:
                        t = _m_types.get(c, "").lower()
                        clow = c.lower()
                        if t in _DATE_TYPES:
                            _candidates.append(c)
                        elif any(it in t for it in _INT_TYPES) and (
                                "date" in clow or "time" in clow or "played" in clow):
                            _candidates.append(c)
                        elif "text" in t and ("date" in clow or "time" in clow):
                            _candidates.append(c)

                    _SUSPECT = ("analyze", "created", "import", "added", "updated")
                    best_col, best_score = None, -1
                    for c in _candidates:
                        try:
                            cur.execute(
                                f'SELECT COUNT(DISTINCT "{c}") FROM '
                                f'(SELECT "{c}" FROM matches '
                                f' WHERE "{c}" IS NOT NULL LIMIT 30) sub')
                            n_distinct = cur.fetchone()[0] or 0
                        except Exception:
                            n_distinct = 0
                        penalty = 5 if any(s in c.lower() for s in _SUSPECT) else 0
                        score = n_distinct - penalty
                        if score > best_score:
                            best_score = score
                            best_col = c

                    dc = best_col
                    dc_type = _m_types.get(dc, "").lower() if dc else ""

                    cur.execute(
                        "SELECT DISTINCT weapon_name FROM kills "
                        "WHERE weapon_name IS NOT NULL AND weapon_name!='' ORDER BY weapon_name")
                    weapons = [r[0] for r in cur.fetchall()]

                    tags_data = []
                    tags_schema_info = {}
                    if "tags" in schema:
                        tc = schema["tags"]
                        tt = col_types.get("tags", {})
                        id_col = next((c for c in tc if c in ("id", "tag_id")), tc[0] if tc else None)
                        id_col_type = tt.get(id_col, "bigint")
                        name_col = next((c for c in tc if c in ("name", "tag_name")), None)
                        color_col = next((c for c in tc if c in ("color", "tag_color")), None)

                        jt = None
                        jt_tag_col = None
                        jt_match_col = None
                        jt_col_types = {}

                        for jtable in ("checksum_tags", "match_tags"):
                            if jtable in schema:
                                jcols = schema[jtable]
                                jtypes = col_types.get(jtable, {})
                                candidate_tag = None
                                candidate_match = None
                                for c in jcols:
                                    cl = c.lower()
                                    if "tag" in cl and "checksum" not in cl and "match" not in cl:
                                        candidate_tag = c
                                    elif any(k in cl for k in ("checksum", "match", "demo")):
                                        candidate_match = c
                                if candidate_tag and candidate_match:
                                    jt = jtable
                                    jt_tag_col = candidate_tag
                                    jt_match_col = candidate_match
                                    jt_col_types = jtypes
                                    break

                        if not jt:
                            for jtable in ("checksum_tags", "match_tags"):
                                if jtable in schema:
                                    jcols = schema[jtable]
                                    if len(jcols) >= 2:
                                        jt = jtable
                                        jt_match_col = jcols[0]
                                        jt_tag_col = jcols[1]
                                        jt_col_types = col_types.get(jtable, {})
                                        break

                        tags_schema_info = {
                            "table": "tags",
                            "id_col": id_col,
                            "id_col_type": id_col_type,
                            "name_col": name_col,
                            "color_col": color_col,
                            "junction_table": jt,
                            "jt_tag_col": jt_tag_col,
                            "jt_match_col": jt_match_col,
                            "jt_col_types": jt_col_types,
                        }

                        if name_col and id_col:
                            sel = f'"{id_col}","{name_col}"'
                            if color_col:
                                sel += f',"{color_col}"'
                            cur.execute(f'SELECT {sel} FROM tags ORDER BY "{name_col}"')
                            for r in cur.fetchall():
                                tags_data.append(
                                    (r[0], r[1] if len(r) > 1 else str(r[0]),
                                     r[2] if len(r) > 2 and color_col else ""))

                conn.close()
                players = [(f"{n}  ({s})", s, n, d) for n, s, d in rows]
                names = {s: n for n, s, *_ in rows}
                self.after(0, lambda: self._on_load_ok(players, dc, dc_type, weapons, schema,
                                                        col_types, names, tags_data, tags_schema_info))
            except Exception as e:
                self.after(0, lambda err=e: self._on_load_fail(err))

        threading.Thread(target=task, daemon=True).start()

    def _on_load_ok(self, players, dc, dc_type, weapons, schema, col_types, names,
                    tags_data, tags_schema):
        self._date_col      = dc
        self._date_col_type = dc_type   # actual SQL type: bigint, timestamp, date, text…
        self._db_schema     = schema
        self._db_col_types  = col_types
        self._player_names  = names
        self._tags_list     = tags_data
        self._tags_schema   = tags_schema
        self._demo_checksums = {}
        self._demo_dates     = {}
        self._ts_cache       = {}
        self._col_cache      = {}
        self._warned_missing_mods = set()  # reset so re-connect re-checks column presence

        # Warn (log only) if the date column was not detected
        if not dc:
            self._alog("⚠ Date column not detected in matches — date filter disabled", "warn")

        self.db_status.set(
            f"OK — {len(players)} players, {len(tags_data)} tags"
            + ("" if dc else "  ⚠ date ?"))
        self.db_status_lbl.config(fg=GREEN)

        # Deferred restoration (preset loaded before DB was ready)
        restore_sid = self._pending_restore_sid or ""
        self._pending_restore_sid = None
        self.player_search.set_players(players, restore_steam_id=restore_sid)

        self._build_weapons(weapons)
        self._refresh_tag_combo()
        self._refresh_tags_list_display()

        # Deferred tag restoration (config loaded before DB was ready)
        if self._pending_restore_tags:
            self._restore_active_tags(self._pending_restore_tags)
            self._pending_restore_tags = []

    def _on_load_fail(self, err):
        self.db_status.set(f"Error: {err}")
        self.db_status_lbl.config(fg=RED)

    # ═══════════════════════════════════════════════════
    #  Weapons grouped by category
    # ═══════════════════════════════════════════════════
    def _build_weapons(self, weapons):
        saved = self.cfg.get("weapons", [])

        # Grenades always present regardless of whether they have kills in DB
        _FORCED_GRENADES = [
            "HE Grenade", "Flashbang", "Smoke Grenade",
            "Incendiary Grenade", "Molotov", "Decoy Grenade",
        ]
        weapons = list(weapons)
        for g in _FORCED_GRENADES:
            if g not in weapons:
                weapons.append(g)

        for w in weapons:
            if w not in self.sel_weapons:
                self.sel_weapons[w] = tk.BooleanVar(value=(w in saved))

        if self._wg_frame:
            self._wg_frame.destroy()
        self._wg_lbl.config(text=f"{len(weapons)} weapons")

        self._wg_frame = tk.Frame(self._sec_w, bg=BG2)
        self._wg_frame.pack(fill="x", pady=(4, 0))

        categorized = {}
        for w in weapons:
            cat = _weapon_category(w)
            categorized.setdefault(cat, []).append(w)

        self._cat_vars = {}

        for cat in sorted(categorized.keys(), key=lambda c: list(WEAPON_CATEGORIES.keys()).index(c)
                          if c in WEAPON_CATEGORIES else 999):
            cat_weapons = categorized[cat]
            cat_frame = tk.Frame(self._wg_frame, bg=BG2)
            cat_frame.pack(fill="x", pady=(4, 0))

            cat_var = tk.BooleanVar(value=all(
                self.sel_weapons.get(w, tk.BooleanVar(value=False)).get() for w in cat_weapons))
            self._cat_vars[cat] = (cat_var, cat_weapons)

            hdr = tk.Frame(cat_frame, bg=BG2)
            hdr.pack(fill="x")
            _icon = WEAPON_ICONS.get(cat, "")
            _cat_cb = tk.Checkbutton(hdr, text=f"{_icon} {cat}  ({len(cat_weapons)})", variable=cat_var,
                           **{**_CHK_KW, "font": ("Consolas", 9, "bold"), "fg": ORANGE},
                           command=lambda c=cat: self._toggle_category(c))
            _cat_cb.pack(side="left")

            wf = tk.Frame(cat_frame, bg=BG2, padx=16)
            wf.pack(fill="x")
            for i, w in enumerate(cat_weapons):
                cb = hchk(wf, w, self.sel_weapons[w],
                          command=lambda c=cat: self._update_cat_var(c))
                cb.grid(row=i // 4, column=i % 4, sticky="w", padx=4, pady=1)

    def _weapons_select_all(self):
        for v in self.sel_weapons.values():
            v.set(True)
        for cat in self._cat_vars:
            self._update_cat_var(cat)

    def _weapons_deselect_all(self):
        for v in self.sel_weapons.values():
            v.set(False)
        for cat in self._cat_vars:
            self._update_cat_var(cat)

    def _toggle_category(self, cat):
        cat_var, weapons = self._cat_vars[cat]
        val = cat_var.get()
        for w in weapons:
            if w in self.sel_weapons:
                self.sel_weapons[w].set(val)

    def _update_cat_var(self, cat):
        cat_var, weapons = self._cat_vars[cat]
        all_on = all(self.sel_weapons.get(w, tk.BooleanVar(value=False)).get() for w in weapons)
        cat_var.set(all_on)

    # ═══════════════════════════════════════════════════
    #  Tags DB
    # ═══════════════════════════════════════════════════
    def _refresh_tag_combo(self):
        # Combo removed — auto-tag managed via tag selection in Tags tab.
        # Method kept for _connect_and_load compatibility.
        pass

    def _on_tag_selected(self, e=None):
        pass  # Obsolete — kept for compat

    def _create_new_tag_dialog(self, from_combo=True):
        ts = self._tags_schema
        if not ts.get("name_col"):
            messagebox.showerror("Tags", "Tags schema not detected.")
            return None
        name = simpledialog.askstring("New tag", "Tag name:", parent=self)
        if not name or not name.strip():
            return None
        name = name.strip()
        color = "#f97316"
        if ts.get("color_col"):
            dlg = ColorPickerDialog(self, initial_color="#f97316")
            if dlg.result:
                color = dlg.result
            else:
                return None
        try:
            conn = self._pg_fresh()
            with conn.cursor() as cur:
                new_id = _generate_id_for_type(ts.get("id_col_type", "bigint"))
                cols_sql = f'"{ts["id_col"]}","{ts["name_col"]}"'
                vals = [new_id, name]
                if ts.get("color_col"):
                    cols_sql += f',"{ts["color_col"]}"'
                    vals.append(color)
                cur.execute(f'INSERT INTO tags ({cols_sql}) VALUES ({",".join(["%s"] * len(vals))})', vals)
                conn.commit()
            conn.close()
            self._tags_list.append((new_id, name, color))
            self._refresh_tag_combo()
            self._refresh_tags_list_display()
            self._log(f"Tag '{name}' created (id={new_id})", "ok")
            return name
        except Exception as e:
            messagebox.showerror("Tags", f"Error:\n{e}")
            return None

    def _delete_tag_from_db(self, tag_id, tag_name):
        ts = self._tags_schema
        if not ts.get("id_col"):
            return False, "Unknown schema"
        try:
            conn = self._pg_fresh()
            with conn.cursor() as cur:
                jt = ts.get("junction_table")
                jt_tag = ts.get("jt_tag_col")
                if jt and jt_tag:
                    cur.execute(f'DELETE FROM "{jt}" WHERE "{jt_tag}"=%s', (tag_id,))
                cur.execute(f'DELETE FROM tags WHERE "{ts["id_col"]}"=%s', (tag_id,))
                conn.commit()
            conn.close()
            self._tags_list = [t for t in self._tags_list if t[0] != tag_id]
            return True, ""
        except Exception as e:
            return False, str(e)

    def _get_demo_checksum(self, demo_path):
        """Return the matches checksum for a demo path.

        v19: Priority: cache populated by _query_events (no re-query).
        Fallback: direct query with extended candidates.
        """
        # 1. Cache populated by _query_events — primary path
        if demo_path in self._demo_checksums:
            return self._demo_checksums[demo_path]

        # 2. Fallback: direct query
        dc = self._find_col("matches", [
            "demo_path", "demo_file_path", "demo_filepath",
            "share_code", "file_path", "path",
        ])
        mkm = self._find_col("matches", ["checksum", "id", "match_id"])

        if not dc or not mkm:
            self._tag_log_line(
                f"[CHK] ERREUR: colonnes non trouvees (dc={dc}, mkm={mkm})\n"
                f"      Colonnes matches: {self._db_schema.get('matches', [])}")
            return None

        candidates = [demo_path]
        abs_path = os.path.abspath(demo_path)
        candidates.append(abs_path)
        candidates.append(abs_path.replace("\\", "/"))
        candidates.append(abs_path.replace("/", "\\"))
        basename = os.path.basename(demo_path)

        try:
            conn = self._pg_fresh()
            with conn.cursor() as cur:
                for sp in candidates:
                    cur.execute(
                        f'SELECT "{mkm}" FROM matches WHERE "{dc}"=%s LIMIT 1', (sp,))
                    r = cur.fetchone()
                    if r:
                        self._demo_checksums[demo_path] = r[0]
                        conn.close()
                        return r[0]

                # LIKE on the filename
                cur.execute(
                    f'SELECT "{mkm}" FROM matches WHERE "{dc}" LIKE %s LIMIT 1',
                    (f"%{basename}",))
                r = cur.fetchone()
                if r:
                    self._demo_checksums[demo_path] = r[0]
                    conn.close()
                    return r[0]

                # Debug: show what is in the table
                cur.execute(f'SELECT "{dc}","{mkm}" FROM matches LIMIT 5')
                samples = cur.fetchall()
                self._tag_log_line(
                    f"[CHK] Not found: {demo_path!r}\n"
                    f"      col_demo={dc!r}, col_chk={mkm!r}")
                for s in samples:
                    self._tag_log_line(f"      sample DB: demo={s[0]!r}  chk={s[1]!r}")
            conn.close()
        except Exception as e:
            self._tag_log_line(f"[CHK] Exception: {e}")
        return None

    def _tag_demo(self, demo_path, tag_name):
        ts = self._tags_schema
        jt = ts.get("junction_table")
        jt_tag = ts.get("jt_tag_col")
        jt_match = ts.get("jt_match_col")
        if not jt or not jt_tag or not jt_match:
            return False, f"Junction table not found (jt={jt}, tag={jt_tag}, match={jt_match})"

        tag_id = next((tid for tid, tn, _ in self._tags_list if tn == tag_name), None)
        if tag_id is None:
            return False, f"Tag '{tag_name}' not found in self._tags_list"

        checksum = self._get_demo_checksum(demo_path)
        if not checksum:
            return False, f"Checksum not found for {os.path.basename(demo_path)}"

        try:
            conn = self._pg_fresh()
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT 1 FROM "{jt}" WHERE "{jt_match}"=%s AND "{jt_tag}"=%s LIMIT 1',
                    (checksum, tag_id))
                if not cur.fetchone():
                    cur.execute(
                        f'INSERT INTO "{jt}" ("{jt_match}","{jt_tag}") VALUES (%s,%s)',
                        (checksum, tag_id))
                    conn.commit()
                    self._tag_log_line(
                        f"   INSERT {jt}({jt_match}={checksum!r}, {jt_tag}={tag_id}) OK")
                else:
                    conn.commit()
                    self._tag_log_line(
                        f"   Relation deja existante: {jt_match}={checksum!r}, {jt_tag}={tag_id}")
            conn.close()
            return True, ""
        except Exception as e:
            return False, str(e)

    def _untag_demo(self, demo_path, tag_name):
        ts = self._tags_schema
        jt = ts.get("junction_table")
        jt_tag = ts.get("jt_tag_col")
        jt_match = ts.get("jt_match_col")
        if not jt or not jt_tag or not jt_match:
            return False, "Junction table not found"

        tag_id = next((tid for tid, tn, _ in self._tags_list if tn == tag_name), None)
        if tag_id is None:
            return False, f"Tag '{tag_name}' not found"

        checksum = self._get_demo_checksum(demo_path)
        if not checksum:
            # Last resort: direct query bypassing cache
            dc = self._find_col("matches", ["demo_path", "demo_file_path", "demo_filepath",
                                             "share_code", "file_path", "path"])
            mkm = self._find_col("matches", ["checksum", "id", "match_id"])
            if dc and mkm:
                try:
                    conn = self._pg_fresh()
                    with conn.cursor() as cur:
                        name = os.path.basename(demo_path)
                        cur.execute(f'SELECT "{mkm}" FROM matches WHERE "{dc}" LIKE %s LIMIT 1',
                                    (f"%{name}",))
                        r = cur.fetchone()
                        if r:
                            checksum = r[0]
                            self._demo_checksums[demo_path] = checksum
                    conn.close()
                except Exception:
                    pass
        if not checksum:
            return False, f"Checksum not found for {os.path.basename(demo_path)}"

        try:
            conn = self._pg_fresh()
            with conn.cursor() as cur:
                cur.execute(
                    f'DELETE FROM "{jt}" WHERE "{jt_match}"=%s AND "{jt_tag}"=%s',
                    (checksum, tag_id))
                conn.commit()
            conn.close()
            return True, ""
        except Exception as e:
            return False, str(e)

    def _tag_log_line(self, msg):
        self._alog(msg, "dim")

    def _do_tag_demos(self, demos, tag_name):

        self._tag_log_line(f"=== Tag '{tag_name}' on {len(demos)} demo(s) ===")

        def task():
            ok = 0
            err_first = ""
            for dp in demos:
                self._tag_log_line(f"\n-> {os.path.basename(dp)}")
                cached = dp in self._demo_checksums
                self._tag_log_line(f"   checksum cache: {'OUI' if cached else 'NON'}")
                success, err = self._tag_demo(dp, tag_name)
                if success:
                    ok += 1
                else:
                    self._tag_log_line(f"   FAILED: {err}")
                    if not err_first:
                        err_first = err

            def finish():
                if ok == len(demos):
                    self._alog(f"Tags ✓ '{tag_name}' assigned to {ok}/{len(demos)} demo(s).", "ok")
                    self._tag_search_status.config(text=f"✓ {ok}/{len(demos)}", fg=GREEN)
                elif ok > 0:
                    self._alog(f"Tags ⚠ {ok}/{len(demos)} OK — {err_first}", "warn")
                    self._tag_search_status.config(text=f"⚠ {ok}/{len(demos)}", fg=YELLOW)
                else:
                    self._alog(f"Tags ✗ failed: {err_first}", "err")
                    self._tag_search_status.config(text="✗ failed", fg=RED)

            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    # ═══════════════════════════════════════════════════
    #  UI
    # ═══════════════════════════════════════════════════
    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=20, pady=(10, 6))
        tk.Label(hdr, text=" >> ", font=("Consolas", 11, "bold"), bg=ORANGE2, fg="white",
                 padx=6, pady=2).pack(side="left")
        tk.Label(hdr, text="  CSDM ", font=("Consolas", 14, "bold"), bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text=f"Batch {APP_VERSION}", font=("Consolas", 14, "bold"), bg=BG, fg=ORANGE).pack(side="left")

        self._hdr_player_lbl = tk.Label(hdr, text="", font=FONT_SM, bg=BG, fg=MUTED)
        self._hdr_player_lbl.pack(side="left", padx=(16, 0))

        sf = tk.Frame(hdr, bg=BG)
        sf.pack(side="right")
        tk.Label(sf, text="DB: ", font=FONT_SM, bg=BG, fg=MUTED).pack(side="left")
        self.db_status_lbl = tk.Label(sf, textvariable=self.db_status,
                                      font=("Consolas", 9, "bold"), bg=BG, fg=YELLOW)
        self.db_status_lbl.pack(side="left")
        tk.Button(sf, text="↺", font=FONT_SM, bg=BG, fg=MUTED, relief="flat", bd=0,
                  cursor="hand2", highlightthickness=0, activeforeground=ORANGE,
                  command=self._connect_and_load).pack(side="left", padx=(6, 0))

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x")

        s = ttk.Style()
        s.theme_use("default")
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=MUTED,
                    font=("Consolas", 9, "bold"), padding=[12, 7], borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", BG2)], foreground=[("selected", ORANGE)])
        s.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=TEXT,
                    arrowcolor=ORANGE, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    selectbackground=ORANGE, selectforeground="white")
        s.map("TCombobox", fieldbackground=[("readonly", BG3), ("disabled", BG)],
              foreground=[("readonly", TEXT), ("disabled", MUTED)],
              background=[("readonly", BG3)], arrowcolor=[("readonly", ORANGE)])
        s.configure("TPanedwindow", background=BORDER)
        s.configure("Vertical.TPanedwindow", background=BORDER)

        # Gauche : notebook config (poids 5)
        # Right: run bar + vertical PanedWindow (notebook | log)
        outer = ttk.PanedWindow(self, orient="horizontal")
        outer.pack(fill="both", expand=True)
        self._outer_paned = outer

        left_frame = tk.Frame(outer, bg=BG)
        outer.add(left_frame, weight=3)

        nb = ttk.Notebook(left_frame)
        nb.pack(fill="both", expand=True)
        for title, builder in [("Capture", self._tab_capturer), ("Tags", self._tab_tags),
                                ("Video", self._tab_video), ("Tools", self._tab_outils)]:
            f = tk.Frame(nb, bg=BG)
            nb.add(f, text=f"  {title}  ")
            builder(f)

        right_frame = tk.Frame(outer, bg=BG)
        outer.add(right_frame, weight=2)
        right_frame.rowconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # Run bar (top of right panel)
        run_bar = tk.Frame(right_frame, bg=BG2, pady=6)
        run_bar.grid(row=0, column=0, sticky="ew")

        ctrl = tk.Frame(run_bar, bg=BG2)
        ctrl.pack(fill="x", padx=12)

        self.run_btn = tk.Button(ctrl, text="  ▶  RUN  ", font=("Consolas", 10, "bold"),
                                  bg=ORANGE, fg="white", relief="flat", cursor="hand2", bd=0,
                                  highlightthickness=0, activebackground=ORANGE2,
                                  command=self._run)
        self.run_btn.pack(side="left", ipady=6, ipadx=4)

        self.stop_btn = tk.Button(ctrl, text="  ⏸ STOP  ", font=("Consolas", 9, "bold"),
                                   bg=BG3, fg=RED, relief="flat", cursor="hand2", bd=0,
                                   state="disabled", command=self._stop_graceful)
        self.stop_btn.pack(side="left", padx=(6, 0), ipady=6, ipadx=4)

        self.kill_btn = tk.Button(ctrl, text="  ⛔ KILL  ", font=("Consolas", 9, "bold"),
                                   bg=BG3, fg=RED, relief="flat", cursor="hand2", bd=0,
                                   state="disabled", command=self._kill_now)
        self.kill_btn.pack(side="left", padx=(6, 0), ipady=6, ipadx=4)

        tk.Button(ctrl, text="  🔍 Preview  ", font=("Consolas", 9, "bold"), bg=BG3, fg=BLUE,
                  relief="flat", cursor="hand2", bd=0, highlightthickness=0,
                  command=self._dry_run).pack(side="left", padx=(6, 0), ipady=6, ipadx=4)

        tk.Label(ctrl, text="F5  F6  Esc", font=FONT_DESC, bg=BG2, fg=DESC_COLOR
                 ).pack(side="left", padx=(12, 0))

        self.progress_lbl = tk.Label(ctrl, text="", font=FONT_SM, bg=BG2, fg=MUTED)
        self.progress_lbl.pack(side="right")

        self._summary_lbl = tk.Label(run_bar, text="", font=FONT_SM,
                                     bg=BG2, fg=MUTED, anchor="w", pady=2)
        self._summary_lbl.pack(fill="x", padx=12)

        # Log
        log_frame = tk.Frame(right_frame, bg=BG)
        log_frame.grid(row=1, column=0, sticky="nsew")
        self._build_log_panel(log_frame)

        self.bind("<F5>",     lambda e: self._run())
        self.bind("<F6>",     lambda e: self._dry_run())
        self.bind("<Escape>", lambda e: self._stop_graceful() if self._running else None)
        self.bind("<Control-b>", self._toggle_log_badges)

        # Position the sash once the window is actually visible
        # Wait for <Map> event then force geometry
        def _set_sash(event=None):
            self.update_idletasks()
            w = self.winfo_width()
            if w > 100:
                try:
                    pct = self._clamp_layout_values(
                        self.v["ui_window_w"].get(),
                        self.v["ui_window_h"].get(),
                        self.v["ui_split_pct"].get(),
                    )[2]
                    outer.sashpos(0, int(w * (pct / 100.0)))
                except Exception:
                    pass
        self.bind("<Map>", _set_sash)
        outer.bind("<ButtonRelease-1>", self._on_splitter_release, add="+")

    def _build_log_panel(self, parent):
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        top = tk.Frame(parent, bg=BG2)
        top.grid(row=0, column=0, sticky="ew")

        tk.Label(top, text="LOG", font=("Consolas", 9, "bold"),
                 fg=ORANGE, bg=BG2).pack(side="left", padx=(10, 0), pady=5)

        self._log_filter = tk.StringVar(value="All")
        filter_frame = tk.Frame(top, bg=BG2)
        filter_frame.pack(side="left", padx=(10, 0))
        for lvl, col in [("All", TEXT), ("OK", GREEN), ("Err", RED), ("Warn", YELLOW), ("Info", ORANGE)]:
            tk.Radiobutton(filter_frame, text=lvl, variable=self._log_filter, value=lvl,
                           **{**_CHK_KW, "font": FONT_DESC, "fg": col, "activeforeground": col},
                           command=self._apply_log_filter).pack(side="left", padx=(0, 4))

        self._log_autoscroll = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="↓auto", variable=self._log_autoscroll,
                       **{**_CHK_KW, "font": FONT_DESC}).pack(side="right", padx=(0, 8))
        self._log_badges_btn = tk.Button(
            top, text="Badges: ON", font=FONT_DESC, bg=BG3, fg=GREEN,
            relief="flat", bd=0, cursor="hand2",
            activebackground=BORDER, activeforeground=ORANGE,
            highlightthickness=0, command=self._toggle_log_badges
        )
        self._log_badges_btn.pack(side="right", padx=(0, 8), pady=3, ipady=2, ipadx=4)
        add_tip(self._log_badges_btn,
                "Toggle inline clip badges in log entries.\n"
                "Keyboard: Ctrl+B")

        btn_bar = tk.Frame(parent, bg=BG3)
        btn_bar.grid(row=1, column=0, sticky="ew")

        def _btn(text, cmd, fg=MUTED):
            return tk.Button(btn_bar, text=text, font=FONT_DESC, bg=BG3, fg=fg,
                             relief="flat", bd=0, cursor="hand2",
                             activebackground=BORDER, activeforeground=ORANGE,
                             highlightthickness=0, command=cmd)

        _btn("📋 Copy all",      self._log_copy_all).pack(side="left", padx=(8, 4), pady=3, ipady=2)
        _btn("📋 Copy sel.",      self._log_copy_sel).pack(side="left", padx=(0, 4), pady=3, ipady=2)
        _btn("💾 Save",      self._log_save, fg=BLUE).pack(side="left", padx=(0, 4), pady=3, ipady=2)
        _btn("🔍 Search",         self._log_search_open).pack(side="left", padx=(0, 4), pady=3, ipady=2)
        _btn("🗑 Clear",          self._clear_log, fg=RED).pack(side="right", padx=(0, 8), pady=3, ipady=2)

        log_frame = tk.Frame(parent, bg=BG)
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, font=("Consolas", 9), bg="#090909", fg=TEXT,
                           relief="flat", bd=0, insertbackground=ORANGE,
                           highlightthickness=0, state="disabled", wrap="word",
                           selectbackground=ORANGE2, selectforeground="white")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)

        for tag, c in [("ok", GREEN), ("err", RED), ("info", ORANGE), ("dim", MUTED),
                        ("warn", YELLOW), ("blue", BLUE)]:
            self.log.tag_configure(tag, foreground=c)

        self._search_bar = tk.Frame(parent, bg=BG2)
        self._search_bar.grid(row=3, column=0, sticky="ew")
        parent.rowconfigure(3, weight=0)
        self._search_bar.grid_remove()

        tk.Label(self._search_bar, text="Search:", font=FONT_DESC,
                 fg=MUTED, bg=BG2).pack(side="left", padx=(8, 4), pady=4)
        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(self._search_bar, textvariable=self._search_var,
                                      font=FONT_MONO, bg=BG3, fg=TEXT, insertbackground=ORANGE,
                                      relief="flat", bd=0, highlightthickness=1,
                                      highlightbackground=BORDER, highlightcolor=ORANGE, width=20)
        self._search_entry.pack(side="left", ipady=3)
        self._search_entry.bind("<Return>",  lambda e: self._log_search_next())
        self._search_entry.bind("<Escape>",  lambda e: self._log_search_close())
        self._search_count = tk.Label(self._search_bar, text="", font=FONT_DESC, fg=MUTED, bg=BG2)
        self._search_count.pack(side="left", padx=(6, 0))
        tk.Button(self._search_bar, text="▲", font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat",
                  bd=0, cursor="hand2", command=self._log_search_prev).pack(side="left", padx=(6, 0))
        tk.Button(self._search_bar, text="▼", font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat",
                  bd=0, cursor="hand2", command=self._log_search_next).pack(side="left", padx=(2, 0))
        tk.Button(self._search_bar, text="✕", font=FONT_DESC, bg=BG3, fg=RED, relief="flat",
                  bd=0, cursor="hand2", command=self._log_search_close).pack(side="left", padx=(6, 0))
        self._search_var.trace_add("write", lambda *_: self._log_search_highlight())
        self._search_idx = 0
        self.log.tag_configure("search_hi",  background=ORANGE2, foreground="white")
        self.log.tag_configure("search_cur", background=ORANGE,  foreground="white")
        self.log.tag_configure("badge_kill",   foreground=RED)
        self.log.tag_configure("badge_warn",   foreground=YELLOW)
        self.log.tag_configure("badge_safe",   foreground=GREEN)
        self.log.tag_configure("badge_filter", foreground=BLUE)

    def _log_get_text(self):
        return self.log.get("1.0", "end-1c")

    def _log_copy_all(self):
        txt = self._log_get_text()
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self._log_flash("  ✓ All copied to clipboard.")

    def _log_copy_sel(self):
        try:
            txt = self.log.get(tk.SEL_FIRST, tk.SEL_LAST)
            if txt:
                self.clipboard_clear()
                self.clipboard_append(txt)
                self._log_flash("  ✓ Selection copied.")
        except tk.TclError:
            self._log_flash("  ⚠ No selection.", "warn")

    def _log_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            title="Save log")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log_get_text())
            self._log_flash(f"  ✓ Log saved: {path}")
        except Exception as e:
            self._log_flash(f"  ✗ Error: {e}", "err")

    def _log_flash(self, msg, tag="ok"):
        marker = f"__flash_{id(msg)}__"
        self._log(msg, tag)
        self.log.configure(state="normal")
        self.log.mark_set(marker, "end-1l linestart")
        self.log.mark_gravity(marker, "left")
        self.log.configure(state="disabled")
        def _remove():
            try:
                self.log.configure(state="normal")
                self.log.delete(marker, f"{marker} lineend +1c")
                self.log.configure(state="disabled")
            except Exception:
                pass
        self.after(3000, _remove)

    def _apply_log_filter(self):
        lvl = self._log_filter.get()
        tag_map = {"OK": "ok", "Err": "err", "Warn": "warn", "Info": "info"}
        # Remet tout visible
        self.log.configure(state="normal")
        self.log.tag_configure("hidden", elide=False)
        if lvl == "All":
            self.log.configure(state="disabled")
            return
        # Filter by elision: hide lines that do not carry the target tag
        target = tag_map.get(lvl, "")
        # Strategy: elide lines that do NOT have the target tag
        # (Tk elide on tags: hide items carrying the "hidden" tag)
        self.log.tag_remove("hidden", "1.0", "end")
        if target:
            all_ranges = set()
            # Lines carrying the target tag
            idx = "1.0"
            while True:
                r = self.log.tag_nextrange(target, idx, "end")
                if not r:
                    break
                # Convert to line numbers
                l1 = int(self.log.index(r[0]).split(".")[0])
                l2 = int(self.log.index(r[1]).split(".")[0])
                for ln in range(l1, l2 + 1):
                    all_ranges.add(ln)
                idx = r[1]
            total = int(self.log.index("end").split(".")[0])
            for ln in range(1, total):
                if ln not in all_ranges:
                    self.log.tag_add("hidden", f"{ln}.0", f"{ln}.0 lineend +1c")
        self.log.tag_configure("hidden", elide=True)
        self.log.configure(state="disabled")

    def _log_search_open(self):
        self._search_bar.grid()
        self._search_entry.focus_set()

    def _log_search_close(self):
        self._search_bar.grid_remove()
        self.log.tag_remove("search_hi",  "1.0", "end")
        self.log.tag_remove("search_cur", "1.0", "end")
        self._search_count.config(text="")

    def _log_search_highlight(self):
        self.log.tag_remove("search_hi",  "1.0", "end")
        self.log.tag_remove("search_cur", "1.0", "end")
        q = self._search_var.get()
        if not q:
            self._search_count.config(text="")
            self._search_idx = 0
            return
        count = 0
        idx = "1.0"
        while True:
            pos = self.log.search(q, idx, nocase=True, stopindex="end")
            if not pos:
                break
            end = f"{pos}+{len(q)}c"
            self.log.tag_add("search_hi", pos, end)
            count += 1
            idx = end
        self._search_count.config(text=f"{count} result{'s' if count != 1 else ''}")
        self._search_idx = 0
        if count:
            self._log_search_goto(0)

    def _log_search_goto(self, n):
        q = self._search_var.get()
        if not q:
            return
        ranges = self.log.tag_ranges("search_hi")
        # tag_ranges returns flat list of (start, end, start, end, ...)
        pairs = [(ranges[i], ranges[i+1]) for i in range(0, len(ranges), 2)]
        if not pairs:
            return
        n = n % len(pairs)
        self._search_idx = n
        self.log.tag_remove("search_cur", "1.0", "end")
        s, e = pairs[n]
        self.log.tag_add("search_cur", s, e)
        self.log.see(s)

    def _log_search_next(self):
        self._log_search_goto(self._search_idx + 1)

    def _log_search_prev(self):
        self._log_search_goto(self._search_idx - 1)

    # ── TAB CAPTURE ──
    def _make_tab_scroll(self, parent):
        sf = ScrollableFrame(parent, bg=BG)
        sf.pack(fill="both", expand=True)
        p = sf.inner
        p.configure(padx=20, pady=16)
        p.columnconfigure(0, weight=1)
        return p

    def _tab_capturer(self, parent):
        p = self._make_tab_scroll(parent)
        # must_widgets: {category: [hchk_widget, ...]} for MIXED mode show/hide
        self._must_widgets: dict = {"mods": [], "dp2": [], "db": []}

        sec = Sec(p, "PLAYER")
        sec.pack(fill="x", pady=(0, 10))
        self.player_search = PlayerSearchWidget(sec, on_change=self._on_player_change)
        self.player_search.pack(fill="x")

        sec = Sec(p, "CAPTURE")
        sec.pack(fill="x", pady=(0, 10))

        ev_row = tk.Frame(sec, bg=BG2)
        ev_row.pack(fill="x")
        mlabel(ev_row, "Capture:").pack(side="left")

        def _make_event_toggle(parent, label, var, tip):
            """Styled toggle button for event types."""
            btn = tk.Button(parent, text=f"  {label}  ", font=("Consolas", 9, "bold"),
                            relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                            padx=6, pady=3)
            def _refresh(*_):
                on = var.get()
                btn.config(bg=ORANGE if on else BG3, fg="white" if on else MUTED,
                           activebackground=ORANGE2 if on else BORDER,
                           activeforeground="white")
            def _toggle():
                var.set(not var.get())
                _refresh()
            btn.config(command=_toggle)
            var.trace_add("write", _refresh)
            _refresh()
            add_tip(btn, tip)
            return btn

        _make_event_toggle(ev_row, "KILLS",
                           self.sel_events["Kills"],
                           "Capture kills made by the player.").pack(side="left", padx=(10, 0))
        _make_event_toggle(ev_row, "DEATHS BY",
                           self.sel_events["Deaths"],
                           "Capture deaths of the selected player(s).\n"
                           "Uses the same active weapon / kill-filter / situation-filter logic as KILLS;\n"
                           "the difference is that matching events are those where the selected player dies.").pack(side="left", padx=(4, 0))
        _make_event_toggle(ev_row, "ROUNDS",
                           self.sel_events["Rounds"],
                           "One clip per round the player participated in, starting at round start tick.\n"
                           "Clips every round regardless of kills — useful for full-round montages.\n"
                           "Requires a 'rounds' table in the CSDM database.").pack(side="left", padx=(4, 0))


        # ── PERSPECTIVE ───────────────────────────────────────────────────────
        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(6, 4))
        persp_row = tk.Frame(sec, bg=BG2)
        persp_row.pack(fill="x")
        mlabel(persp_row, "Perspective:").pack(side="left")
        for lbl, val, tip in [
            ("POV Killer", "killer", "Camera on the killer throughout the clip"),
            ("POV Victim", "victim", "Camera on the victim throughout the clip"),
            ("Both",       "both",   "Starts on the killer, then switches to the victim before the kill"),
        ]:
            _rb = hradio(persp_row, lbl, self.v["perspective"], val,
                         command=self._on_perspective_change)
            _rb.pack(side="left", padx=(4, 0))
            add_tip(_rb, tip)

        # Switch delay slider — visible only in both mode
        self._victim_pre_row = tk.Frame(sec, bg=BG2)
        self._victim_pre_row.pack(fill="x", pady=(4, 0))
        _vp_lbl = mlabel(self._victim_pre_row, "Switch delay (s):")
        _vp_lbl.pack(side="left")
        add_tip(_vp_lbl,
                "Seconds before the kill tick at which the camera switches from killer to victim.\n"
                "0 = switch exactly at the kill. Capped at BEFORE seconds.")
        _vp_val_lbl = tk.Label(self._victim_pre_row, text=f"{self.v['victim_pre_s'].get()}s",
                               font=FONT_SM, fg=ORANGE, bg=BG2)
        _vp_val_lbl.pack(side="right")
        tk.Scale(self._victim_pre_row, from_=0, to=10, variable=self.v["victim_pre_s"],
                 orient="horizontal", bg=BG2, fg=TEXT, troughcolor=BG3,
                 activebackground=ORANGE, highlightthickness=0, bd=0,
                 showvalue=False, cursor="hand2",
                 command=lambda v: _vp_val_lbl.config(text=f"{int(float(v))}s")
                 ).pack(side="left", fill="x", expand=True, pady=(2, 0))
        self.after(50, self._on_perspective_change)

        # ══════════════════════════════════════════════════════════════════════
        sec = Sec(p, "KILL FILTERS")
        sec.pack(fill="x", pady=(0, 10))

        # ── SUICIDES / TK / HS ───────────────────────────────────────────────
        tk_row = tk.Frame(sec, bg=BG2)
        tk_row.pack(fill="x")
        _sui_cb = hchk(tk_row, "Suicides", self.v["include_suicides"])
        _sui_cb.pack(side="left")
        add_tip(_sui_cb, "Include world / fall / suicide deaths in clips.")
        mlabel(tk_row, "   TK:").pack(side="left", padx=(8, 0))
        for lbl, val, tip in [
            ("Include", "include", "All kills, including teamkills"),
            ("Exclude", "exclude", "Exclude teamkill frags"),
            ("Only",    "only",    "Only kills on teammates"),
        ]:
            _rb = hradio(tk_row, lbl, self.v["teamkills_mode"], val)
            _rb.pack(side="left", padx=(4, 0))
            add_tip(_rb, tip)

        # HS filter — its own row, independent of the Mods ANY/ALL logic
        hs_row = tk.Frame(sec, bg=BG2)
        hs_row.pack(fill="x", pady=(4, 0))
        _hs_lbl = mlabel(hs_row, "🎯 Headshots:")
        _hs_lbl.pack(side="left")
        add_tip(_hs_lbl,
                "All = include all kills regardless of headshot status.\n"
                "Only = keep headshot kills only (is_headshot column).\n"
                "Exclude = keep non-headshot kills only.\n"
                "⚠ HS is auto-forced only when active filter logic guarantees HS-only output.")
        for lbl, val in [("All", "all"), ("Only", "only"), ("Exclude", "exclude")]:
            _rb = hradio(hs_row, lbl, self.v["headshots_mode"], val,
                         command=self._on_headshots_mode_change)
            _rb.pack(side="left", padx=(8 if val == "all" else 4, 0))
        # Store the radio buttons container so ONE TAP / TROIS TAP can disable it
        self._hs_row = hs_row

        # ── KILL FILTERS LOGIC (shared for Mods + demoparser2) ───────────────
        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(6, 4))
        _kill_logic_hdr = tk.Frame(sec, bg=BG2)
        _kill_logic_hdr.pack(fill="x", pady=(0, 4))
        mlabel(_kill_logic_hdr, "Kill filters logic (Mods + demoparser2):").pack(side="left")
        _logic_tip_kill = (
            "AT LEAST ONE (OR): keep kills matching at least one enabled kill filter.\n"
            "ALL AT ONCE (AND): keep kills matching every enabled kill filter.\n"
            "MIXED: ★ Must filters must all match, plus at least one optional filter.")
        for _lv, _ll in (("any", "AT LEAST ONE"), ("all", "ALL AT ONCE"), ("mixed", "MIXED")):
            _rb = hradio(_kill_logic_hdr, _ll, self.v["kill_mod_logic_dp2"], _lv,
                         command=self._on_kill_logic_change)
            _rb.pack(side="left", padx=(10 if _lv == "any" else 4, 0))
            add_tip(_rb, _logic_tip_kill)
        _clear_kf_btn = tk.Button(
            _kill_logic_hdr, text="Unselect all", command=self._clear_kill_filters,
            font=FONT_SM, bg=BG3, fg=MUTED, activebackground=BORDER, activeforeground=TEXT,
            relief="flat", bd=0, padx=8, pady=2, cursor="hand2"
        )
        _clear_kf_btn.pack(side="right")
        add_tip(_clear_kf_btn, "Disable all kill/situation modifiers and clear all ★ Must flags.")
        self._on_kill_logic_change()

        _MODS = [
            ("kill_mod_through_smoke",  "💨 SMOKE:",          "kill_mod_through_smoke",
             "Kill through a smoke grenade (DB column — fast, no demoparser2 needed)."),
            ("kill_mod_no_scope",       "🔭 NO-SCOPE:",       "kill_mod_no_scope",
             "No-scope kill — sniper only (DB column)."),
            ("kill_mod_assisted_flash", "⚡ VICTIM FLASHED:", "kill_mod_assisted_flash",
             "Victim was blinded by a flashbang (DB column)."),
        ]
        self._must_widgets["mods"] = []
        for i, (key, label, _ck, tip) in enumerate(_MODS):
            row = tk.Frame(sec, bg=BG2)
            row.pack(fill="x", pady=(2 if i > 0 else 0, 0))
            _lbl = mlabel(row, label)
            _lbl.pack(side="left")
            add_tip(_lbl, tip)
            _cb = hchk(row, "Enable", self.v[key])
            _cb.pack(side="left", padx=(4, 0))
            add_tip(_cb, tip)
            _must_cb = hchk(row, "★ Must", self.v[f"{key}_req"])
            self._must_widgets["mods"].append(_must_cb)
            add_tip(_must_cb, "In MIXED mode: this filter is required (must match).\nOthers without ★ are optional (at least one must match).")
            self._wire_enable_must(self.v[key], self.v[f"{key}_req"])
        self.after(50, lambda: self._on_logic_mode_change("mods"))

        # ── Mods ───────────────────────────────────────────────────────────────
        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(6, 4))
        _mods_hdr = tk.Frame(sec, bg=BG2)
        _mods_hdr.pack(fill="x", pady=(0, 4))
        mlabel(_mods_hdr, "Mods — none checked = all kills:").pack(side="left")

        # ── demoparser2 modifiers ─────────────────────────────────────────────
        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(6, 4))
        _dp2_hdr = tk.Frame(sec, bg=BG2)
        _dp2_hdr.pack(fill="x", pady=(0, 4))
        mlabel(_dp2_hdr, "demoparser2 modifiers:").pack(side="left")
        mlabel(_dp2_hdr, "  (uses shared kill logic above)").pack(side="left", padx=(8, 0))

        # ── player_death flag modifiers (dp2) ─────────────────────────────────
        self._must_widgets["dp2"] = []
        _DP2_FLAG_MODS = [
            ("kill_mod_wall_bang",      "🧱 WALLBANG:",
             "Kill by shooting through a wall or object.\n"
             "Uses player_death.penetrated > 0 from the demo file via demoparser2."),
            ("kill_mod_airborne",       "🪂 AIRBORNE:",
             "Killer was in the air at time of shot.\n"
             "Uses player_death.attackerinair from the demo file via demoparser2."),
            ("kill_mod_collateral",     "🎯 COLLATERAL:",
             "Bullet passed through a first victim.\n"
             "Uses player_death.penetrated > 0 from the demo file via demoparser2."),
            ("kill_mod_attacker_blind", "😵 BLIND FIRE:",
             "Killer was blinded by a flashbang at shot time.\n"
             "Uses player_death.attackerblind from the demo file via demoparser2."),
        ]
        for key, label, tip in _DP2_FLAG_MODS:
            row = tk.Frame(sec, bg=BG2)
            row.pack(fill="x", pady=(2, 0))
            _lbl = mlabel(row, label)
            _lbl.pack(side="left")
            add_tip(_lbl, tip)
            _cb = hchk(row, "Enable", self.v[key])
            _cb.pack(side="left", padx=(4, 0))
            add_tip(_cb, tip)
            _must_cb = hchk(row, "★ Must", self.v[f"{key}_req"])
            self._must_widgets["dp2"].append(_must_cb)
            add_tip(_must_cb, "In MIXED mode: this filter is required (must match).")
            self._wire_enable_must(self.v[key], self.v[f"{key}_req"])
            dp2_badge(row).pack(side="left", padx=(8, 0))

        # ── TROIS SHOT ────────────────────────────────────────────────────────
        trois_row = tk.Frame(sec, bg=BG2)
        trois_row.pack(fill="x", pady=(2, 0))
        _ts_lbl = mlabel(trois_row, "🎲 TROIS SHOT:")
        _ts_lbl.pack(side="left")
        add_tip(_ts_lbl,
                "Lucky kills on precision weapons — detected via demoparser2.\n\n"
                "Per-weapon logic:\n"
                "  Deagle / R8   bloom > 0.015 (not a stationary aimed shot)\n"
                "  AWP / SSG 08  unscoped at shot time\n"
                "  SCAR-20 / G3SG1  unscoped OR bloom > 0.010 OR moving\n\n"
                "Enable = keep only lucky kills.\n"
                "Exclude = keep only precise kills on these weapons.\n"
                "⚠ Enable and Exclude are mutually exclusive.")
        _ts_cb = hchk(trois_row, "Enable", self.v["kill_mod_trois_shot"],
                      command=self._on_trois_shot_toggle)
        _ts_cb.pack(side="left", padx=(4, 0))
        _ts_must = hchk(trois_row, "★ Must", self.v["kill_mod_trois_shot_req"])
        self._must_widgets["dp2"].append(_ts_must)
        add_tip(_ts_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_trois_shot"], self.v["kill_mod_trois_shot_req"])
        _nts_cb = hchk(trois_row, "Exclude", self.v["kill_mod_no_trois_shot"],
                       command=self._on_no_trois_shot_toggle)
        _nts_cb.pack(side="left", padx=(12, 0))
        add_tip(_nts_cb,
                "Inverse of TROIS SHOT — removes lucky kills on these weapons.\n"
                "When combined with other dp2 filters, it acts as an exclusion gate first.")
        dp2_badge(trois_row).pack(side="left", padx=(8, 0))

        # ── TROIS TAP ─────────────────────────────────────────────────────────
        tt_row = tk.Frame(sec, bg=BG2)
        tt_row.pack(fill="x", pady=(4, 0))
        _tt_lbl = mlabel(tt_row, "🎯🎲 TROIS TAP:")
        _tt_lbl.pack(side="left")
        add_tip(_tt_lbl,
                "TROIS SHOT + ONE TAP combined: lucky isolated headshot.\n"
                "Must be a headshot, qualify as lucky (TROIS SHOT), and have no other\n"
                "shot within 2s before or after.\n"
                "HS is auto-forced only when active logic guarantees HS-only output.")
        _tt_cb = hchk(tt_row, "Enable", self.v["kill_mod_trois_tap"],
                      command=self._on_trois_tap_toggle)
        _tt_cb.pack(side="left", padx=(4, 0))
        _tt_must = hchk(tt_row, "★ Must", self.v["kill_mod_trois_tap_req"])
        self._must_widgets["dp2"].append(_tt_must)
        add_tip(_tt_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_trois_tap"], self.v["kill_mod_trois_tap_req"])
        dp2_badge(tt_row).pack(side="left", padx=(8, 0))

        # ── ONE TAP ───────────────────────────────────────────────────────────
        ot_row = tk.Frame(sec, bg=BG2)
        ot_row.pack(fill="x", pady=(4, 0))
        _ot_lbl = mlabel(ot_row, "🎯 ONE TAP:")
        _ot_lbl.pack(side="left")
        add_tip(_ot_lbl,
                "Isolated single-shot headshot — no other shot within 2s before or after.\n"
                "HS is auto-forced only when active logic guarantees HS-only output.")
        _ot_cb = hchk(ot_row, "Enable", self.v["kill_mod_one_tap"],
                      command=self._on_one_tap_toggle)
        _ot_cb.pack(side="left", padx=(4, 0))
        _ot_must = hchk(ot_row, "★ Must", self.v["kill_mod_one_tap_req"])
        self._must_widgets["dp2"].append(_ot_must)
        add_tip(_ot_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_one_tap"], self.v["kill_mod_one_tap_req"])
        dp2_badge(ot_row).pack(side="left", padx=(8, 0))

        # ── SPRAY TRANSFER ────────────────────────────────────────────────────
        st_row = tk.Frame(sec, bg=BG2)
        st_row.pack(fill="x", pady=(4, 0))
        _st_lbl = mlabel(st_row, "🔫 SPRAY TRANSFER:")
        _st_lbl.pack(side="left")
        add_tip(_st_lbl,
                "≥2 enemies killed in one continuous spray (no trigger release).\n"
                "Auto weapons only: rifles (AK-47, M4A4/M4A1-S, Galil AR, FAMAS, SG 553, AUG),\n"
                "SMGs, M249, Negev, and CZ75-Auto (the only full-auto pistol).\n"
                "Excluded: AWP, SSG 08, SCAR-20, G3SG1, shotguns, other pistols.")
        _st_cb = hchk(st_row, "Enable", self.v["kill_mod_spray_transfer"])
        _st_cb.pack(side="left", padx=(4, 0))
        _st_must = hchk(st_row, "★ Must", self.v["kill_mod_spray_transfer_req"])
        self._must_widgets["dp2"].append(_st_must)
        add_tip(_st_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_spray_transfer"], self.v["kill_mod_spray_transfer_req"])
        dp2_badge(st_row).pack(side="left", padx=(8, 0))

        # ── FERRARI PEEK ──────────────────────────────────────────────────────
        hv_row = tk.Frame(sec, bg=BG2)
        hv_row.pack(fill="x", pady=(4, 0))
        _hv_lbl = mlabel(hv_row, "🏎 FERRARI PEEK:")
        _hv_lbl.pack(side="left")
        add_tip(_hv_lbl,
                "Kill faster than the opponent can react.\n\n"
                "The player peeks at speed, fires once, and retreats immediately —\n"
                "the entire exposure window is shorter than human reaction time (~150-250ms).\n\n"
                "Three conditions:\n"
                "  1. One-shot (optional) — no prior fire within ~0.75s before the kill\n"
                "  2. Moving before — approach speed ≥ threshold within the last 1s before the shot,\n"
                "     OR the kill shot itself was fired while still running\n"
                "  3. Resumes after — fires again within 2s of the kill while moving\n\n"
                "CS2 run speeds: knife 250 · pistols 240 · Deagle 230 · AK-47 215 · AWP 200 u/s\n"
                "Default 100 u/s — catches any active peek above walking speed.")

        _hv_inner = tk.Frame(hv_row, bg=BG2)

        def _on_hv_toggle(*_):
            if self.v["kill_mod_high_velocity"].get():
                _hv_inner.pack(side="left", fill="x")
            else:
                _hv_inner.pack_forget()

        _hv_enable = hchk(hv_row, "Enable", self.v["kill_mod_high_velocity"],
                          command=_on_hv_toggle)
        _hv_enable.pack(side="left", padx=(4, 0))
        _hv_must = hchk(hv_row, "★ Must", self.v["kill_mod_high_velocity_req"])
        self._must_widgets["dp2"].append(_hv_must)
        add_tip(_hv_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_high_velocity"], self.v["kill_mod_high_velocity_req"])

        _os_cb = hchk(_hv_inner, "One-shot", self.v["kill_mod_hv_one_shot"])
        _os_cb.pack(side="left", padx=(8, 0))
        add_tip(_os_cb, "Require no prior fire within ~0.75s before the kill.\n"
                        "Uncheck to allow spray finishers as long as the approach and resume conditions hold.")
        mlabel(_hv_inner, "  Min approach:").pack(side="left", padx=(8, 0))
        sentry(_hv_inner, self.v["kill_mod_high_vel_thr"], width=5).pack(side="left", padx=(4, 0), ipady=4)
        mlabel(_hv_inner, "u/s").pack(side="left", padx=(2, 0))
        dp2_badge(_hv_inner).pack(side="left", padx=(8, 0))

        self.after(50, _on_hv_toggle)

        # ── FLICK ─────────────────────────────────────────────────────────────
        fl_row = tk.Frame(sec, bg=BG2)
        fl_row.pack(fill="x", pady=(4, 0))
        _fl_lbl = mlabel(fl_row, "↩ FLICK:")
        _fl_lbl.pack(side="left")
        add_tip(_fl_lbl,
                "Kill preceded by a large view-angle change (~0.5s before kill tick).\n"
                "Default: 50°. Lower = catch smaller corrections, raise = extreme flicks only.")
        hchk(fl_row, "Enable", self.v["kill_mod_flick"]).pack(side="left", padx=(4, 0))
        _fl_must = hchk(fl_row, "★ Must", self.v["kill_mod_flick_req"])
        self._must_widgets["dp2"].append(_fl_must)
        add_tip(_fl_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_flick"], self.v["kill_mod_flick_req"])
        mlabel(fl_row, "  Min angle:").pack(side="left", padx=(8, 0))
        sentry(fl_row, self.v["kill_mod_flick_deg"], width=4).pack(side="left", padx=(4, 0), ipady=4)
        mlabel(fl_row, "°").pack(side="left", padx=(2, 0))
        dp2_badge(fl_row).pack(side="left", padx=(8, 0))

        # ── SAVIOR ────────────────────────────────────────────────────────────
        sv_row = tk.Frame(sec, bg=BG2)
        sv_row.pack(fill="x", pady=(4, 0))
        _sv_lbl = mlabel(sv_row, "🛡 SAVIOR:")
        _sv_lbl.pack(side="left")
        add_tip(_sv_lbl,
                "Kill an enemy who was actively damaging a teammate in the ~2s prior.\n"
                "Captures clutch saves and last-second rescues.")
        hchk(sv_row, "Enable", self.v["kill_mod_sauveur"]).pack(side="left", padx=(4, 0))
        _sv_must = hchk(sv_row, "★ Must", self.v["kill_mod_sauveur_req"])
        self._must_widgets["dp2"].append(_sv_must)
        add_tip(_sv_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_sauveur"], self.v["kill_mod_sauveur_req"])
        dp2_badge(sv_row).pack(side="left", padx=(8, 0))
        self.after(50, lambda: self._on_logic_mode_change("dp2"))

        # ── SITUATION ─────────────────────────────────────────────────────────
        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(8, 4))
        _sit_hdr = tk.Frame(sec, bg=BG2)
        _sit_hdr.pack(fill="x", pady=(0, 4))
        mlabel(_sit_hdr, "Situation (DB + Clutch):").pack(side="left")
        _logic_tip_db = (
            "Applied after kill filters.\n"
            "AT LEAST ONE (OR): keep kills matching at least one enabled situation modifier.\n"
            "ALL AT ONCE (AND): keep kills matching every enabled situation modifier.\n"
            "MIXED: ★ Must situation modifiers must all match, plus at least one optional matches.")
        for _lv, _ll in (("any", "AT LEAST ONE"), ("all", "ALL AT ONCE"), ("mixed", "MIXED")):
            _rb = hradio(_sit_hdr, _ll, self.v["kill_mod_logic_db"], _lv,
                         command=lambda *_, cat="db": self._on_logic_mode_change(cat))
            _rb.pack(side="left", padx=(10 if _lv == "any" else 4, 0))
            add_tip(_rb, _logic_tip_db)
        self._must_widgets["db"] = []

        # ── ENTRY FRAG ────────────────────────────────────────────────────────
        ef_row = tk.Frame(sec, bg=BG2)
        ef_row.pack(fill="x", pady=(2, 0))
        _ef_lbl = mlabel(ef_row, "🚀 ENTRY FRAG:")
        _ef_lbl.pack(side="left")
        add_tip(_ef_lbl, "First kill of the round (earliest tick), regardless of side.")
        hchk(ef_row, "Enable", self.v["kill_mod_entry_frag"]).pack(side="left", padx=(4, 0))
        _ef_must = hchk(ef_row, "★ Must", self.v["kill_mod_entry_frag_req"])
        self._must_widgets["db"].append(_ef_must)
        add_tip(_ef_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_entry_frag"], self.v["kill_mod_entry_frag_req"])

        # ── ACE ───────────────────────────────────────────────────────────────
        ac_row = tk.Frame(sec, bg=BG2)
        ac_row.pack(fill="x", pady=(4, 0))
        _ac_lbl = mlabel(ac_row, "🃏 ACE:")
        _ac_lbl.pack(side="left")
        add_tip(_ac_lbl, "Rounds where the player eliminated all 5 opponents alone.")
        hchk(ac_row, "Enable", self.v["kill_mod_ace"]).pack(side="left", padx=(4, 0))
        _ac_must = hchk(ac_row, "★ Must", self.v["kill_mod_ace_req"])
        self._must_widgets["db"].append(_ac_must)
        add_tip(_ac_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_ace"], self.v["kill_mod_ace_req"])

        # ── MULTI-KILL ────────────────────────────────────────────────────────
        mk_row = tk.Frame(sec, bg=BG2)
        mk_row.pack(fill="x", pady=(4, 0))
        _mk_lbl = mlabel(mk_row, "⚡ MULTI-KILL:")
        _mk_lbl.pack(side="left")
        add_tip(_mk_lbl, "N or more kills in one round within the time window.")
        hchk(mk_row, "Enable", self.v["kill_mod_multi_kill"]).pack(side="left", padx=(4, 0))
        _mk_must = hchk(mk_row, "★ Must", self.v["kill_mod_multi_kill_req"])
        self._must_widgets["db"].append(_mk_must)
        add_tip(_mk_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_multi_kill"], self.v["kill_mod_multi_kill_req"])
        mlabel(mk_row, "  Min kills:").pack(side="left", padx=(8, 0))
        scombo(mk_row, self.v["kill_mod_multi_kill_n"], [2, 3, 4, 5], 3).pack(side="left", padx=(4, 0))
        add_tip(mk_row.winfo_children()[-1], "2 = double, 3 = triple, 4 = quadra, 5 = ace")
        mlabel(mk_row, "  within:").pack(side="left", padx=(8, 0))
        sentry(mk_row, self.v["kill_mod_multi_kill_s"], width=3).pack(side="left", padx=(4, 0), ipady=4)
        mlabel(mk_row, "s").pack(side="left", padx=(2, 0))

        # ── BULLY ─────────────────────────────────────────────────────────────
        bo_row = tk.Frame(sec, bg=BG2)
        bo_row.pack(fill="x", pady=(4, 0))
        _bo_lbl = mlabel(bo_row, "💀 BULLY:")
        _bo_lbl.pack(side="left")
        add_tip(_bo_lbl,
                "Kill the same opponent for the Nth time in the match.\n"
                "e.g. From kill #3 = captured from the 3rd time you kill the same player.")
        hchk(bo_row, "Enable", self.v["kill_mod_bourreau"]).pack(side="left", padx=(4, 0))
        _bo_must = hchk(bo_row, "★ Must", self.v["kill_mod_bourreau_req"])
        self._must_widgets["db"].append(_bo_must)
        add_tip(_bo_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_bourreau"], self.v["kill_mod_bourreau_req"])
        mlabel(bo_row, "  From kill #:").pack(side="left", padx=(8, 0))
        scombo(bo_row, self.v["kill_mod_bourreau_n"], [2, 3, 4, 5], 3).pack(side="left", padx=(4, 0))
        add_tip(bo_row.winfo_children()[-1], "2 = from 2nd kill of same victim, 3 = from 3rd, etc.")

        # ── ECO FRAG ──────────────────────────────────────────────────────────
        eco_row = tk.Frame(sec, bg=BG2)
        eco_row.pack(fill="x", pady=(4, 0))
        _eco_lbl = mlabel(eco_row, "💰 ECO FRAG:")
        _eco_lbl.pack(side="left")
        add_tip(_eco_lbl,
                "Pistol kill against a full-buy opponent (rifle / sniper / LMG).\n"
                "Falls back to all pistol kills if victim_weapon column is missing.")
        hchk(eco_row, "Enable", self.v["kill_mod_eco_frag"]).pack(side="left", padx=(4, 0))
        _eco_must = hchk(eco_row, "★ Must", self.v["kill_mod_eco_frag_req"])
        self._must_widgets["db"].append(_eco_must)
        add_tip(_eco_must, "In MIXED mode: this filter is required (must match).")
        self._wire_enable_must(self.v["kill_mod_eco_frag"], self.v["kill_mod_eco_frag_req"])
        self.after(50, lambda: self._on_logic_mode_change("db"))
        self._install_hs_lock_watchers()

        # ── CLUTCH ────────────────────────────────────────────────────────────
        clutch_hdr = tk.Frame(sec, bg=BG2)
        clutch_hdr.pack(fill="x")
        _cl_lbl = mlabel(clutch_hdr, "🤝 CLUTCH:")
        _cl_lbl.pack(side="left")
        add_tip(_cl_lbl,
                "Player is last alive on their team and kills the remaining opponents.\n"
                "1vX filters: check which sizes to include (none = all included).\n"
                "Full = one clip per clutch. Per kill = one clip per kill.\n"
                "Can be combined with Kills / Deaths / Rounds.")
        _cl_cb = hchk(clutch_hdr, "Enable", self.v["clutch_enabled"],
                      command=self._on_clutch_toggle)
        _cl_cb.pack(side="left", padx=(4, 0))

        # Always-packed container — inner content shown/hidden by _on_clutch_toggle
        self._clutch_opts_row = tk.Frame(sec, bg=BG2)
        self._clutch_opts_row.pack(fill="x")

        # Inner frame — this is what gets shown/hidden
        self._clutch_opts_inner = tk.Frame(self._clutch_opts_row, bg=BG2)

        # 1vX checkboxes
        _sizes_row = tk.Frame(self._clutch_opts_inner, bg=BG2)
        _sizes_row.pack(fill="x", pady=(4, 0))
        mlabel(_sizes_row, "Sizes:").pack(side="left")
        add_tip(_sizes_row.winfo_children()[-1],
                "No box checked = all sizes included (1v1 through 1v5).")
        for n in range(1, 6):
            _cb = hchk(_sizes_row, f"1v{n}", self.v[f"clutch_1v{n}"])
            _cb.pack(side="left", padx=(6, 0))

        # Clip mode + win only
        _clip_row = tk.Frame(self._clutch_opts_inner, bg=BG2)
        _clip_row.pack(fill="x", pady=(4, 0))
        mlabel(_clip_row, "Clip:").pack(side="left")
        for lbl, val, tip in [
            ("Full clutch", "full",       "One clip from the first to the last kill of the clutch."),
            ("Per kill",    "individual", "One clip per kill (standard BEFORE/AFTER padding)."),
        ]:
            _rb = hradio(_clip_row, lbl, self.v["clutch_clip_mode"], val)
            _rb.pack(side="left", padx=(4, 0))
            add_tip(_rb, tip)
        _req_win = hchk(_clip_row, "Win only", self.v["clutch_require_win"])
        _req_win.pack(side="left", padx=(12, 0))
        add_tip(_req_win, "Only capture clutches where the player's team won the round.")

        self.after(50, self._on_clutch_toggle)

        sec = Sec(p, "TIMING")
        sec.pack(fill="x", pady=(0, 6))

        tg = tk.Frame(sec, bg=BG2)
        tg.pack(fill="x")
        tg.columnconfigure(0, weight=1)
        tg.columnconfigure(1, weight=1)
        _sb = self._slider(tg, "Seconds BEFORE", self.v["before"], 1, 15, 0, 0)
        add_tip(_sb, "Seconds of footage recorded before the event tick.\n"
                     "In 'Both' mode, victim_pre_s is added on top of this value.")
        _sa = self._slider(tg, "Seconds AFTER", self.v["after"],  1, 15, 0, 1)
        add_tip(_sa, "Seconds of footage recorded after the event tick.")

        tr = tk.Frame(sec, bg=BG2)
        tr.pack(fill="x", pady=(4, 0))
        _cs2_cb = hchk(tr, "Close CS2 after demo", self.v["close_game_after"])
        _cs2_cb.pack(side="left")
        add_tip(_cs2_cb, "closeGameAfterRecording — closes CS2 after each recorded demo.\n"
                         "Recommended: ON. Leaving CS2 open between demos can cause\n"
                         "instability on long batches.")

        rg = tk.Frame(sec, bg=BG2)
        rg.pack(fill="x", pady=(6, 0))
        _ret_lbl = mlabel(rg, "Retries:")
        _ret_lbl.pack(side="left")
        add_tip(_ret_lbl, "Number of times to retry a demo if CSDM reports 'Game error'\n"
                          "or a crash. Each retry re-launches CS2 from scratch.\n"
                          "Recommended: 2.")
        sentry(rg, self.v["retry_count"], width=3).pack(side="left", padx=(4, 0), ipady=4)
        _del_lbl = mlabel(rg, "  Delay (s):")
        _del_lbl.pack(side="left", padx=(8, 0))
        add_tip(_del_lbl, "Seconds to wait between retries.\n"
                          "Give CS2 time to fully close before re-launching.\n"
                          "Recommended: 15.")
        sentry(rg, self.v["retry_delay"], width=3).pack(side="left", padx=(4, 0), ipady=4)
        _pause_lbl = mlabel(rg, "  Demo pause (s):")
        _pause_lbl.pack(side="left", padx=(8, 0))
        add_tip(_pause_lbl, "Seconds to wait between demos (successful or failed).\n"
                            "Helps CS2 fully release resources before the next launch.\n"
                            "Recommended: 3–5.")
        sentry(rg, self.v["delay_between_demos"], width=3).pack(side="left", padx=(4, 0), ipady=4)
        _ord_lbl = mlabel(rg, "  Order:")
        _ord_lbl.pack(side="left", padx=(16, 0))
        add_tip(_ord_lbl, "Chronological: demos processed oldest-to-newest.\n"
                          "Random: demos shuffled before the batch starts.")
        for lbl, val in [("Chrono","chrono"),("Random 🎲","random")]:
            hradio(rg, lbl, self.v["clip_order"], val).pack(side="left", padx=(4, 0))

        sec = Sec(p, "DEMO SELECTION")
        sec.pack(fill="x", pady=(0, 6))

        # ── Date range row ────────────────────────────────────────────────────
        dr1 = tk.Frame(sec, bg=BG2)
        dr1.pack(fill="x")
        mlabel(dr1, "From:").pack(side="left")
        tk.Entry(dr1, textvariable=self.v["date_from"], font=FONT_MONO, bg=BG3, fg=TEXT,
                 insertbackground=ORANGE, relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ORANGE, width=12
                 ).pack(side="left", padx=(4, 0), ipady=4, ipadx=4)
        _btn_from = tk.Button(dr1, text="📅", font=FONT_SM, bg=BG3, fg=ORANGE, relief="flat",
                  bd=0, cursor="hand2", highlightthickness=0,
                  activebackground=BORDER, activeforeground=ORANGE)
        _btn_from.configure(command=lambda b=_btn_from: self._open_cal(self.v["date_from"], b))
        _btn_from.pack(side="left", padx=(2, 0), ipady=4, ipadx=4)
        mlabel(dr1, "  To:").pack(side="left", padx=(10, 0))
        tk.Entry(dr1, textvariable=self.v["date_to"], font=FONT_MONO, bg=BG3, fg=TEXT,
                 insertbackground=ORANGE, relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ORANGE, width=12
                 ).pack(side="left", padx=(4, 0), ipady=4, ipadx=4)
        _btn_to = tk.Button(dr1, text="📅", font=FONT_SM, bg=BG3, fg=ORANGE, relief="flat",
                  bd=0, cursor="hand2", highlightthickness=0,
                  activebackground=BORDER, activeforeground=ORANGE)
        _btn_to.configure(command=lambda b=_btn_to: self._open_cal(self.v["date_to"], b))
        _btn_to.pack(side="left", padx=(2, 0), ipady=4, ipadx=4)
        tk.Button(dr1, text="Today", font=FONT_DESC, bg=BG3, fg=GREEN,
                  relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  activebackground=BORDER, activeforeground=GREEN,
                  command=lambda: self.v["date_to"].set(date.today().strftime("%d-%m-%Y"))
                  ).pack(side="left", padx=(6, 0), ipady=4, ipadx=5)
        tk.Button(dr1, text="Clear all", font=FONT_DESC, bg=BG3, fg=MUTED,
                  relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  activebackground=BORDER, activeforeground=MUTED,
                  command=lambda: [self.v["date_from"].set(""), self.v["date_to"].set(""),
                                   self._demo_picker_clear()]
                  ).pack(side="left", padx=(4, 0), ipady=4, ipadx=5)

        qr = tk.Frame(sec, bg=BG2)
        qr.pack(fill="x", pady=(4, 0))
        tk.Label(qr, text="Shortcuts:", font=FONT_DESC, fg=MUTED, bg=BG2).pack(side="left")
        for lbl, key in [("Yesterday","yesterday"),("7d",7),("30d",30),
                         ("This month","month"),("3m",90),("6m",180),("Year","year"),("All",0)]:
            tk.Button(qr, text=lbl, font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat", bd=0,
                      cursor="hand2", activebackground=ORANGE, activeforeground="white",
                      highlightthickness=0,
                      command=lambda k=key: self._set_date_range(k)).pack(
                side="left", padx=(4, 0), ipady=2, ipadx=4)

        # ── Demo picker ───────────────────────────────────────────────────────
        picker_hdr = tk.Frame(sec, bg=BG2)
        picker_hdr.pack(fill="x", pady=(10, 0))
        mlabel(picker_hdr, "Demo selection:").pack(side="left")
        add_tip(picker_hdr.winfo_children()[-1],
                "After Preview, demos in the date range are shown here.\n"
                "Uncheck any demo to exclude it from the batch.\n"
                "Enable 'Manual mode' to see all demos from the DB\n"
                "and add/remove them individually.")
        self._picker_manual_var = tk.BooleanVar(value=False)
        _pm_cb = hchk(picker_hdr, "Manual mode", self._picker_manual_var,
                      command=self._on_picker_mode_change)
        _pm_cb.pack(side="left", padx=(12, 0))
        add_tip(_pm_cb,
                "Off: shows only demos found by the date range (after Preview).\n"
                "On: loads all demos from DB so you can pick or exclude individually.")
        self._picker_count_lbl = tk.Label(picker_hdr, text="", font=FONT_DESC,
                                          fg=MUTED, bg=BG2)
        self._picker_count_lbl.pack(side="right")

        # Treeview: columns = checkbox-state (not real col) + date + name
        tree_frame = tk.Frame(sec, bg=BG2)
        tree_frame.pack(fill="x", pady=(4, 0))
        style = ttk.Style()
        style.configure("DemoPicker.Treeview",
                        background=BG3, fieldbackground=BG3,
                        foreground=TEXT, rowheight=18,
                        font=FONT_SM)
        style.configure("DemoPicker.Treeview.Heading",
                        background=BG2, foreground=MUTED,
                        font=FONT_DESC, relief="flat")
        style.map("DemoPicker.Treeview",
                  background=[("selected", BORDER)],
                  foreground=[("selected", ORANGE)])
        self._demo_tree = ttk.Treeview(
            tree_frame, style="DemoPicker.Treeview",
            columns=("sel", "date", "name"), show="headings", height=7,
            selectmode="extended")
        self._demo_tree.heading("sel",  text="✓",         anchor="center")
        self._demo_tree.heading("date", text="Date",       anchor="w")
        self._demo_tree.heading("name", text="Demo",       anchor="w")
        self._demo_tree.column("sel",  width=24, minwidth=24, stretch=False, anchor="center")
        self._demo_tree.column("date", width=120, minwidth=100, stretch=False)
        self._demo_tree.column("name", width=340, minwidth=200, stretch=True)
        _tree_sb = ttk.Scrollbar(tree_frame, orient="vertical",
                                 command=self._demo_tree.yview)
        self._demo_tree.configure(yscrollcommand=_tree_sb.set)
        self._demo_tree.pack(side="left", fill="x", expand=True)
        _tree_sb.pack(side="right", fill="y")
        self._demo_tree.bind("<Button-1>", self._on_demo_tree_click)

        # Per-row toggle buttons row
        pick_btns = tk.Frame(sec, bg=BG2)
        pick_btns.pack(fill="x", pady=(4, 0))
        tk.Button(pick_btns, text="✓ Check all", font=FONT_DESC, bg=BG3, fg=GREEN,
                  relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  activeforeground=GREEN, activebackground=BG3,
                  command=lambda: self._demo_picker_set_all(True)
                  ).pack(side="left", padx=(0, 6))
        tk.Button(pick_btns, text="✕ Uncheck all", font=FONT_DESC, bg=BG3, fg=RED,
                  relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  activeforeground=RED, activebackground=BG3,
                  command=lambda: self._demo_picker_set_all(False)
                  ).pack(side="left")
        tk.Button(pick_btns, text="↕ Toggle selected", font=FONT_DESC, bg=BG3, fg=MUTED,
                  relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                  activeforeground=ORANGE, activebackground=BG3,
                  command=self._demo_picker_toggle_selected
                  ).pack(side="left", padx=(6, 0))

        # Internal state: {demo_path: bool} — True = included
        self._demo_picker_state: dict = {}

        self._sec_w = Sec(p, "WEAPON FILTER  (empty = all)")
        self._sec_w.pack(fill="x", pady=(0, 6))
        self._wg_lbl = tk.Label(self._sec_w, text="Waiting for DB…", font=FONT_DESC, fg=MUTED, bg=BG2)
        self._wg_lbl.pack(anchor="w")
        self._wg_frame = None
        br = tk.Frame(self._sec_w, bg=BG2)
        br.pack(fill="x", pady=(4, 0))
        tk.Button(br, text="Select all", font=FONT_DESC, bg=BG3, fg=GREEN, relief="flat",
                  cursor="hand2", bd=0, highlightthickness=0, activeforeground=GREEN,
                  command=self._weapons_select_all).pack(side="left", padx=(0, 6))
        tk.Button(br, text="Deselect all", font=FONT_DESC, bg=BG3, fg=RED, relief="flat",
                  cursor="hand2", bd=0, highlightthickness=0, activeforeground=RED,
                  command=self._weapons_deselect_all).pack(side="left")

        # Auto-tag managed from the Tags tab (active selection)

    def _open_cal(self, var, anchor=None):
        init = None
        s = var.get().strip()
        if s:
            try:
                init = datetime.strptime(s, "%d-%m-%Y").date()
            except ValueError:
                pass
        CalendarPopup(anchor if anchor else self,
                      lambda d: var.set("" if d is None else d.strftime("%d-%m-%Y")),
                      initial_date=init)

    def _set_date_range(self, key):
        today = date.today()
        today_str = today.strftime("%d-%m-%Y")
        if key == 0:
            # All: clear both fields
            self.v["date_from"].set("")
            self.v["date_to"].set("")
        elif key == "yesterday":
            yesterday = today - timedelta(days=1)
            self.v["date_from"].set(yesterday.strftime("%d-%m-%Y"))
            self.v["date_to"].set(yesterday.strftime("%d-%m-%Y"))
        elif key == "month":
            # From the 1st of the current month
            start = today.replace(day=1)
            self.v["date_from"].set(start.strftime("%d-%m-%Y"))
            self.v["date_to"].set(today_str)
        elif key == "year":
            # From January 1st
            start = today.replace(month=1, day=1)
            self.v["date_from"].set(start.strftime("%d-%m-%Y"))
            self.v["date_to"].set(today_str)
        elif isinstance(key, int) and key > 0:
            start = today - timedelta(days=key)
            self.v["date_from"].set(start.strftime("%d-%m-%Y"))
            self.v["date_to"].set(today_str)

    # ── Demo picker helpers ─────────────────────────────────────────────────
    def _demo_picker_fmt_name(self, demo_path):
        """Shorten long demo filenames for display: keep last ~40 chars, prefix …"""
        name = Path(demo_path).name
        if len(name) > 44:
            return "…" + name[-43:]
        return name

    def _demo_picker_fmt_date(self, demo_path):
        """Return dd-mm-yyyy hh:mm for a demo path."""
        ts = self._get_demo_ts(demo_path)
        if ts is not None:
            try:
                return datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M")
            except Exception:
                pass
        raw = self._demo_dates.get(demo_path)
        if raw is None:
            return "??-??-???? ??:??"
        try:
            if hasattr(raw, "strftime"):
                return raw.strftime("%d-%m-%Y %H:%M")
            if isinstance(raw, (int, float)):
                t = int(raw)
                if t > 4_000_000_000:
                    t //= 1000
                return datetime.fromtimestamp(t).strftime("%d-%m-%Y %H:%M")
            s = str(raw).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s[:len(fmt)], fmt).strftime("%d-%m-%Y %H:%M")
                except ValueError:
                    continue
        except Exception:
            pass
        return "??-??-???? ??:??"

    def _demo_picker_populate(self, demo_paths, keep_existing=False):
        """Populate the demo picker treeview with the given paths.

        demo_paths: list of demo file paths to show.
        keep_existing: if True, preserve checked state for paths already present.
        After Preview, called with just the range-filtered demos.
        In Manual mode, called with all demos from DB.
        """
        # Preserve existing state for known paths if requested
        prev_state = dict(self._demo_picker_state) if keep_existing else {}

        self._demo_picker_state = {}
        try:
            self._demo_tree.delete(*self._demo_tree.get_children())
        except Exception:
            return

        sorted_paths = sorted(demo_paths, key=self._demo_sort_key)
        for dp in sorted_paths:
            checked = prev_state.get(dp, True)
            self._demo_picker_state[dp] = checked
            sym = "✓" if checked else "✕"
            date_str = self._demo_picker_fmt_date(dp)
            name_str = self._demo_picker_fmt_name(dp)
            tag = "ok" if checked else "off"
            iid = self._demo_tree.insert("", "end",
                values=(sym, date_str, name_str),
                tags=(tag,), iid=dp)

        self._demo_tree.tag_configure("ok",  foreground=TEXT)
        self._demo_tree.tag_configure("off", foreground=MUTED)

        n_on  = sum(1 for v in self._demo_picker_state.values() if v)
        n_tot = len(self._demo_picker_state)
        try:
            self._picker_count_lbl.config(
                text=f"{n_on}/{n_tot} selected",
                fg=ORANGE if n_on < n_tot else MUTED)
        except Exception:
            pass

    def _demo_picker_clear(self):
        """Clear the picker when dates are cleared."""
        self._demo_picker_state = {}
        try:
            self._demo_tree.delete(*self._demo_tree.get_children())
            self._picker_count_lbl.config(text="")
        except Exception:
            pass

    def _on_demo_tree_click(self, event):
        """Toggle checked state on click. Return 'break' to suppress native selection
        highlight which would otherwise fight with our tag-based coloring."""
        region = self._demo_tree.identify_region(event.x, event.y)
        iid    = self._demo_tree.identify_row(event.y)
        if not iid or region not in ("cell", "tree"):
            return "break"
        dp = iid  # iid == demo_path
        cur = self._demo_picker_state.get(dp, True)
        new = not cur
        self._demo_picker_state[dp] = new
        sym = "✓" if new else "✕"
        tag = "ok" if new else "off"
        vals = self._demo_tree.item(iid, "values")
        self._demo_tree.item(iid, values=(sym, vals[1], vals[2]), tags=(tag,))
        self._demo_tree.selection_remove(iid)  # no native highlight
        n_on  = sum(1 for v in self._demo_picker_state.values() if v)
        n_tot = len(self._demo_picker_state)
        try:
            self._picker_count_lbl.config(
                text=f"{n_on}/{n_tot} selected",
                fg=ORANGE if n_on < n_tot else MUTED)
        except Exception:
            pass
        return "break"

    def _demo_picker_set_all(self, value):
        for dp in list(self._demo_picker_state.keys()):
            self._demo_picker_state[dp] = value
            iid = dp
            try:
                sym = "✓" if value else "✕"
                tag = "ok" if value else "off"
                old_vals = self._demo_tree.item(iid, "values")
                self._demo_tree.item(iid, values=(sym, old_vals[1], old_vals[2]), tags=(tag,))
            except Exception:
                pass
        n_on  = sum(1 for v in self._demo_picker_state.values() if v)
        n_tot = len(self._demo_picker_state)
        try:
            self._picker_count_lbl.config(
                text=f"{n_on}/{n_tot} selected",
                fg=ORANGE if n_on < n_tot else MUTED)
        except Exception:
            pass

    def _demo_picker_toggle_selected(self):
        sel = self._demo_tree.selection()
        for iid in sel:
            dp = iid
            cur = self._demo_picker_state.get(dp, True)
            new = not cur
            self._demo_picker_state[dp] = new
            sym = "✓" if new else "✕"
            tag = "ok" if new else "off"
            old_vals = self._demo_tree.item(iid, "values")
            self._demo_tree.item(iid, values=(sym, old_vals[1], old_vals[2]), tags=(tag,))
        n_on  = sum(1 for v in self._demo_picker_state.values() if v)
        n_tot = len(self._demo_picker_state)
        try:
            self._picker_count_lbl.config(
                text=f"{n_on}/{n_tot} selected",
                fg=ORANGE if n_on < n_tot else MUTED)
        except Exception:
            pass

    def _on_picker_mode_change(self, *_):
        """Switch between range-only and manual (all demos) mode."""
        manual = self._picker_manual_var.get()
        if not manual:
            # Back to range mode — preserve current list
            return
        # Manual mode: load all demos from DB
        def _bg():
            try:
                conn = self._pg_fresh()
                dc   = self._find_col("matches", ["demo_path", "demo_file_path",
                                                    "demo_filepath", "share_code"])
                mkm  = self._find_col("matches", ["checksum", "id", "match_id"])
                date_col = self._date_col
                if not dc:
                    return
                with conn.cursor() as cur:
                    if date_col:
                        cur.execute(f'SELECT "{dc}","{mkm}","{date_col}" FROM matches '
                                    f'ORDER BY "{date_col}" DESC')
                    else:
                        cur.execute(f'SELECT "{dc}","{mkm}" FROM matches')
                    rows = cur.fetchall()
                conn.close()
                all_paths = []
                for row in rows:
                    dp = row[0]
                    if not dp:
                        continue
                    chk = row[1]
                    if chk and dp not in self._demo_checksums:
                        self._demo_checksums[dp] = chk
                    if date_col and len(row) > 2 and row[2] and dp not in self._demo_dates:
                        self._demo_dates[dp] = row[2]
                    all_paths.append(dp)
                self.after(0, lambda: self._demo_picker_populate(all_paths, keep_existing=True))
            except Exception as e:
                self._alog(f"  ⚠ Demo picker (manual mode): {e}", "warn")
        threading.Thread(target=_bg, daemon=True).start()

    def _demo_picker_get_active(self):
        """Return list of demo paths that are checked in the picker.
        If picker is empty (no preview run yet), returns None (= no filter)."""
        if not self._demo_picker_state:
            return None
        return [dp for dp, ok in self._demo_picker_state.items() if ok]

    # ── TAB VIDEO ──
    def _tab_video(self, parent):
        p = self._make_tab_scroll(parent)

        sec = Sec(p, "RECORDING SYSTEM")
        sec.pack(fill="x", pady=(0, 12))
        rg = tk.Frame(sec, bg=BG2)
        rg.pack(fill="x")
        rg.columnconfigure(0, weight=1)
        rg.columnconfigure(1, weight=1)
        for col, (title, opts, key, tip) in enumerate([
            ("Encoder", ENCODER_OPTIONS, "encoder", "FFmpeg only."),
            ("System",  RECSYS_OPTIONS,  "recsys",
             "HLAE = injects via HLAE into CS2 (recommended — full options).\n"
             "CS = native CSDM recording via CS2's startmovie command.\n\n"
             "⚠ HLAE-exclusive features not available in CS mode:\n"
             "  custom FOV (mirv_fov), AFX streams, No spectator UI,\n"
             "  Fix scope FOV, and other mirv_* commands.\n"
             "ℹ Vanilla CS2 effects (physics, gravity, blood) are injected in both modes:\n"
             "  HLAE via extraArgs, CS via autoexec + runtime cfg injection."),
        ]):
            f = tk.Frame(rg, bg=BG2)
            f.grid(row=0, column=col, sticky="new", padx=(0, 12 if col < 1 else 0))
            mlabel(f, title).pack(anchor="w")
            for o in opts:
                hradio(f, o, self.v[key], o).pack(anchor="w")
            desc_label(f, tip).pack(anchor="w", pady=(4, 0))

        sec = Sec(p, "RESOLUTION & FRAMERATE")
        sec.pack(fill="x", pady=(0, 10))

        # ── Row 1: Definition + Ratio + Custom ───────────────────────────────
        top_row = tk.Frame(sec, bg=BG2)
        top_row.pack(fill="x", pady=(4, 0))

        # -- Definition block --
        def_frm = tk.Frame(top_row, bg=BG2)
        def_frm.pack(side="left", padx=(0, 20))
        mlabel(def_frm, "Definition").pack(anchor="w")
        self._def_radios = []
        for lbl, _ in DEFINITIONS:
            rb = hradio(def_frm, lbl, self.v["res_definition"], lbl,
                        command=self._on_res_structured)
            rb.pack(anchor="w", pady=(2, 0))
            self._def_radios.append(rb)

        # -- Vertical separator --
        tk.Frame(top_row, bg=BORDER, width=1).pack(side="left", fill="y", padx=(0, 20))

        # -- Aspect Ratio block --
        ratio_frm = tk.Frame(top_row, bg=BG2)
        ratio_frm.pack(side="left", padx=(0, 20))
        mlabel(ratio_frm, "Aspect ratio").pack(anchor="w")
        self._ratio_radios = []
        for lbl, _, _ in ASPECT_RATIOS:
            rb = hradio(ratio_frm, lbl, self.v["res_aspect"], lbl,
                        command=self._on_res_structured)
            rb.pack(anchor="w", pady=(2, 0))
            self._ratio_radios.append(rb)

        # -- Vertical separator --
        tk.Frame(top_row, bg=BORDER, width=1).pack(side="left", fill="y", padx=(0, 20))

        # -- Custom block --
        custom_frm = tk.Frame(top_row, bg=BG2)
        custom_frm.pack(side="left", padx=(0, 20))
        mlabel(custom_frm, "Custom").pack(anchor="w")
        self._res_custom_chk = hchk(custom_frm, "Free dimensions", self.v["res_custom"],
                                    command=self._on_res_custom_toggle)
        self._res_custom_chk.pack(anchor="w", pady=(4, 0))
        # Width × height fields (active only in custom mode)
        wh_frm = tk.Frame(custom_frm, bg=BG2)
        wh_frm.pack(anchor="w", pady=(6, 0))
        self._res_w_entry = sentry(wh_frm, self.v["width"], width=6)
        self._res_w_entry.pack(side="left", ipady=4)
        mlabel(wh_frm, "×").pack(side="left", padx=4)
        self._res_h_entry = sentry(wh_frm, self.v["height"], width=6)
        self._res_h_entry.pack(side="left", ipady=4)
        desc_label(custom_frm, "Calculated resolution:").pack(anchor="w", pady=(4, 0))
        self._res_preview_lbl = tk.Label(custom_frm, text="", font=FONT_SM,
                                         fg=ORANGE, bg=BG2)
        self._res_preview_lbl.pack(anchor="w")

        # ── Row 2: FPS ───────────────────────────────────────────────────────
        bot_row = tk.Frame(sec, bg=BG2)
        bot_row.pack(fill="x", pady=(12, 0))

        fps_frm = tk.Frame(bot_row, bg=BG2)
        fps_frm.pack(side="left", padx=(0, 20))
        mlabel(fps_frm, "FPS").pack(anchor="w")
        scombo(fps_frm, self.v["framerate"], FRAMERATES, 6).pack(anchor="w", pady=(4, 0))

        sec = Sec(p, "VIDEO CODEC")
        sec.pack(fill="x", pady=(0, 10))
        vc = tk.Frame(sec, bg=BG2)
        vc.pack(fill="x", pady=(4, 0))
        mlabel(vc, "Codec:").pack(side="left")
        self._vcodec_cb = scombo(vc, self.v["video_codec"], VIDEO_CODECS, 16)
        self._vcodec_cb.pack(side="left", padx=(6, 0))
        self._vcodec_cb.bind("<<ComboboxSelected>>", self._on_vcodec)
        mlabel(vc, "CRF:").pack(side="left", padx=(16, 0))
        sentry(vc, self.v["crf"], width=4).pack(side="left", padx=(6, 0), ipady=4)
        desc_label(vc, "  0=lossless  18=very good  23=default").pack(side="left", padx=(6, 0))
        self._vcodec_desc = tk.Label(sec, text="", font=FONT_DESC, fg=BLUE, bg=BG2, anchor="w", wraplength=700)
        self._vcodec_desc.pack(fill="x", pady=(4, 0))
        self._on_vcodec()

        pr = tk.Frame(sec, bg=BG2)
        pr.pack(fill="x", pady=(8, 0))
        mlabel(pr, "Preset:").pack(side="left")
        PRESETS_CPU = ["ultrafast", "superfast", "veryfast", "faster", "fast",
                       "medium", "slow", "slower", "veryslow"]
        scombo(pr, self.v["video_preset"], PRESETS_CPU, 10).pack(side="left", padx=(6, 0))
        desc_label(pr, "  Slow = better compression at equal quality."
                       "  No effect on GPU codecs (NVENC/AMF).").pack(side="left", padx=(8, 0))

        ct = tk.Frame(sec, bg=BG2)
        ct.pack(fill="x", pady=(8, 0))
        mlabel(ct, "Container:").pack(side="left")
        scombo(ct, self.v["video_container"], VIDEO_CONTAINERS, 8).pack(side="left", padx=(6, 0))

        sec = Sec(p, "AUDIO CODEC")
        sec.pack(fill="x", pady=(0, 10))
        ac = tk.Frame(sec, bg=BG2)
        ac.pack(fill="x")
        mlabel(ac, "Codec:").pack(side="left")
        self._acodec_cb = scombo(ac, self.v["audio_codec"], AUDIO_CODECS, 14)
        self._acodec_cb.pack(side="left", padx=(6, 0))
        self._acodec_cb.bind("<<ComboboxSelected>>", self._on_acodec)
        mlabel(ac, "Bitrate (kbps):").pack(side="left", padx=(16, 0))
        sentry(ac, self.v["audio_bitrate"], width=5).pack(side="left", padx=(6, 0), ipady=4)
        self._acodec_desc = tk.Label(sec, text="", font=FONT_DESC, fg=BLUE, bg=BG2, anchor="w", wraplength=700)
        self._acodec_desc.pack(fill="x", pady=(4, 0))
        self._on_acodec()

        sec = Sec(p, "ADVANCED FFMPEG PARAMS")
        sec.pack(fill="x", pady=(0, 10))
        for lbl, key in [("Input :", "ffmpeg_input_params"), ("Output :", "ffmpeg_output_params")]:
            row = tk.Frame(sec, bg=BG2)
            row.pack(fill="x", pady=(4, 0))
            mlabel(row, lbl, width=8, anchor="w").pack(side="left")
            sentry(row, self.v[key]).pack(side="left", fill="x", expand=True, ipady=4)

        sec = Sec(p, "IN-GAME OPTIONS")
        sec.pack(fill="x", pady=(0, 10))
        for txt, key, tip in [
            ("TrueView",            "true_view",               "Client perspective (recommended) — FPS render instead of spectator camera."),
            ("Death notices only", "show_only_death_notices", "Show only death notices on screen."),
            ("X-Ray",               "show_xray",               "Skeletons visible through walls (showXRay)."),
        ]:
            _cb = hchk(sec, txt, self.v[key])
            _cb.pack(anchor="w", pady=2)
            add_tip(_cb, tip)
        dr = tk.Frame(sec, bg=BG2)
        dr.pack(fill="x", pady=(6, 0))
        _dn_lbl = mlabel(dr, "Death notices (s):")
        _dn_lbl.pack(side="left")
        add_tip(_dn_lbl, "Duration death notices are shown on screen (seconds).")
        sentry(dr, self.v["death_notices_duration"], width=4).pack(side="left", padx=(6, 0), ipady=4)

        sec_asm = Sec(p, "FINAL ASSEMBLY")
        sec_asm.pack(fill="x", pady=(0, 10))
        _asm_cb1 = hchk(sec_asm, "Assemble all clips at the end",
             self.v["assemble_after"])
        _asm_cb1.pack(anchor="w", pady=(4, 2))
        add_tip(_asm_cb1, "After batch, concatenate all clips into a single file.\n"
                          "Video copied without re-encoding (-c:v copy) — fast, lossless.\n"
                          "Audio re-encoded to AAC to fix drift.\n"
                          "Requires the same codec and resolution on all clips.")
        _asm_cb2 = hchk(sec_asm, "Delete source clips after assembly",
             self.v["delete_after_assemble"])
        _asm_cb2.pack(anchor="w", pady=2)
        add_tip(_asm_cb2, "Deletes source files (and their folders) after successful assembly.\n"
                          "⚠ Incompatible with Concatenate sequences — automatically disables that option.")
        _asm_cb3 = hchk(sec_asm, "Concatenate sequences",
             self.v["concatenate_sequences"])
        _asm_cb3.pack(anchor="w", pady=2)
        add_tip(_asm_cb3,
                "Merge all sequences from the same demo into a single clip (CSDM side, before FFmpeg).\n"
                "⚠ Useless if 'Assemble all clips' is active — final assembly already does this.\n"
                "⛔ Automatically disabled if 'Delete source clips' is checked.")

        def _sync_concat_state(*_):
            del_active = self.v["delete_after_assemble"].get()
            if del_active:
                self.v["concatenate_sequences"].set(False)
                _asm_cb3.config(state="disabled")
            else:
                _asm_cb3.config(state="normal")
        self.v["delete_after_assemble"].trace_add("write", _sync_concat_state)
        _sync_concat_state()

        asm_row = tk.Frame(sec_asm, bg=BG2)
        asm_row.pack(fill="x", pady=(8, 0))
        mlabel(asm_row, "Output filename:").pack(side="left")
        asm_entry = sentry(asm_row, self.v["assemble_output"])
        asm_entry.pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=4)
        desc_label(asm_row, "  (extension .mp4/.mkv… auto-added if missing)").pack(
            side="left", padx=(6, 0))

        saved_names_frame = tk.Frame(sec_asm, bg=BG2)
        saved_names_frame.pack(fill="x", pady=(10, 0))

        names_hdr = tk.Frame(saved_names_frame, bg=BG2)
        names_hdr.pack(fill="x")
        mlabel(names_hdr, "Saved names:").pack(side="left")
        tk.Button(names_hdr, text="+ Save current name", font=FONT_DESC,
                  bg=BG3, fg=GREEN, relief="flat", bd=0, cursor="hand2",
                  activeforeground=GREEN, activebackground=BG3,
                  command=self._asm_save_current_name).pack(side="left", padx=(10, 0))

        self._asm_names_frame = tk.Frame(saved_names_frame, bg=BG2)
        self._asm_names_frame.pack(fill="x", pady=(6, 0))
        self._asm_names = load_asm_names()
        self._refresh_asm_names()

        self._hlae_sec = Sec(p, "⚡ HLAE OPTIONS  —  HLAE mode only")
        self._hlae_sec.pack(fill="x", pady=(0, 10))
        desc_label(self._hlae_sec,
                   "Passed to HLAE via CSDM. Not available in CS recording mode.\n"
                   "ℹ Audio captured directly by HLAE (bypasses Windows mixer).\n"
                   "⚠ CS2 console may briefly appear during recording: this is normal.").pack(fill="x")

        # FOV
        fov_row = tk.Frame(self._hlae_sec, bg=BG2)
        fov_row.pack(fill="x", pady=(8, 0))
        mlabel(fov_row, "FOV:").pack(side="left")
        sentry(fov_row, self.v["hlae_fov"], width=5).pack(side="left", padx=(6, 0), ipady=4)
        desc_label(fov_row, "  90 = default  |  100–110 = cinematic wide  |  60 = zoomed").pack(
            side="left", padx=(8, 0))

        # Game speed
        sm_row = tk.Frame(self._hlae_sec, bg=BG2)
        sm_row.pack(fill="x", pady=(6, 0))
        _gs_lbl = mlabel(sm_row, "Game Speed (%):")
        _gs_lbl.pack(side="left")
        _gs_entry = sentry(sm_row, self.v["hlae_slow_motion"], width=7)
        _gs_entry.pack(side="left", padx=(6, 0), ipady=4)
        add_tip(_gs_lbl,
                "Simulation speed multiplier.\n"
                "100 = normal | 125 = 1.25x | 200 = 2x | max 1000.")
        add_tip(_gs_entry,
                "Direct numeric input.\n"
                "Allowed range: 1..1000 (%).")
        self._speed_feedback = tk.Label(sm_row, text="", font=FONT_SM, fg=ORANGE, bg=BG2)
        self._speed_feedback.pack(side="left", padx=(8, 0))
        for pv in ("50", "75", "100", "125", "150", "200", "500", "1000"):
            tk.Button(sm_row, text=pv, font=FONT_DESC, bg=BG3, fg=TEXT,
                      relief="flat", bd=0, cursor="hand2",
                      activebackground=BORDER, activeforeground=ORANGE,
                      command=lambda v=pv: self.v["hlae_slow_motion"].set(int(v))
                      ).pack(side="left", padx=(4, 0), ipady=2, ipadx=3)
        self._on_game_speed_var()

        # Bool options
        bool_opts = tk.Frame(self._hlae_sec, bg=BG2)
        bool_opts.pack(fill="x", pady=(8, 0))
        for txt, key, tip in [
            ("AFX Stream",      "hlae_afx_stream",
             "Records separate passes (color, depth, stencil) for compositing."),
            ("No spectator UI", "hlae_no_spectator_ui",
             "Hides spectator HUD — injects +cl_draw_only_deathnotices 1."),
            ("Fix scope FOV",   "hlae_fix_scope_fov",
             "Injects: mirv_fov handleZoom enabled 1\n"
             "Prevents mirv_fov from overriding the zoomed FOV on scoped weapons.\n"
             "Recommended: ON."),
            ("Auto Workshop DL", "hlae_workshop_download",
             "Injects +cl_downloadfilter all — allows CS2 to download old Workshop map versions."),
        ]:
            _cb = hchk(bool_opts, txt, self.v[key])
            _cb.pack(side="left", padx=(0, 6))
            add_tip(_cb, tip)

        # Extra args
        _ea_lbl = tk.Label(self._hlae_sec, text="Additional HLAE args:",
                 font=FONT_SM, fg=MUTED, bg=BG2)
        _ea_lbl.pack(anchor="w", pady=(8, 0))
        add_tip(_ea_lbl,
                "Arguments passed directly to the HLAE session.\n"
                "⚠ If CS2 gets stuck on an old Workshop map: add "
                "+cl_downloadfilter all in Steam Launch Options, not here.")
        sentry(self._hlae_sec, self.v["hlae_extra_args"]).pack(fill="x", ipady=4, pady=(2, 0))

        # ── CS2 EFFECTS (available in both modes) ────────────────────────────
        self._cs2_sec = Sec(p, "🎮 CS2 EFFECTS  —  both HLAE and CS modes")
        self._cs2_sec.pack(fill="x", pady=(0, 10))
        desc_label(self._cs2_sec,
                   "Vanilla CS2 commands shared by both recording modes.\n"
                   "HLAE: injected via extraArgs | CS: injected via autoexec + runtime cfg.").pack(fill="x")

        # CS2 window mode + minimize
        win_row = tk.Frame(self._cs2_sec, bg=BG2)
        win_row.pack(fill="x", pady=(8, 0))
        _wm_lbl = mlabel(win_row, "Window mode:")
        _wm_lbl.pack(side="left")
        add_tip(_wm_lbl,
                "Launch flags: -fullscreen / -windowed / -noborder.\n"
                "Applied in HLAE mode via extraArgs.\n"
                "In CS mode, CSDM JSON has no launch-args field (warning shown in log).")
        for lbl, val in [("None","none"),("Fullscreen","fullscreen"),
                         ("Windowed","windowed"),("Borderless","noborder")]:
            hradio(win_row, lbl, self.v["cs2_window_mode"], val).pack(side="left", padx=(4, 0))
        _min_cb = hchk(win_row, "Minimize on launch", self.v["cs2_minimize"])
        _min_cb.pack(side="left", padx=(16, 0))
        add_tip(_min_cb,
                "Automatically minimizes CS2 as soon as it appears.\n"
                "Requires pywin32 (pip install pywin32). Silently ignored otherwise.")

        # Physics grid
        tk.Frame(self._cs2_sec, height=1, bg=BORDER).pack(fill="x", pady=(10, 6))
        mlabel(self._cs2_sec, "Physics & visuals:").pack(anchor="w")
        desc_label(self._cs2_sec,
                   "Non-default values are injected as CS2 console commands on startup.").pack(
            anchor="w")

        phys_grid = tk.Frame(self._cs2_sec, bg=BG2)
        phys_grid.pack(fill="x", pady=(6, 0))
        phys_grid.columnconfigure(0, weight=2)
        phys_grid.columnconfigure(1, weight=1)

        col_l = tk.Frame(phys_grid, bg=BG2)
        col_l.grid(row=0, column=0, sticky="new", padx=(0, 16))
        for lbl, key, tip, presets in [
            ("cl_ragdoll_gravity", "phys_ragdoll_gravity",
             "Ragdoll gravity.\nDefault 600 | 0 or negative = float | 5000 = slam hard.",
             ["600", "200", "0", "-200", "-500", "2000", "5000"]),
            ("ragdoll_gravity_scale", "phys_ragdoll_scale",
             "Ragdoll gravity scale.\nDefault 1.0 | 0.1 = slow | 3.0 = fast.",
             ["1.0", "0.5", "0.1", "0.0", "2.0", "3.0"]),
            ("sv_gravity", "phys_sv_gravity",
             "World gravity.\nDefault 800 | 200 = moon | 2000 = very heavy.",
             ["800", "400", "200", "100", "1200", "2000"]),
        ]:
            f = tk.Frame(col_l, bg=BG2)
            f.pack(fill="x", pady=(0, 6))
            _fl = mlabel(f, lbl)
            _fl.pack(anchor="w")
            add_tip(_fl, tip)
            row = tk.Frame(f, bg=BG2)
            row.pack(fill="x", pady=(2, 0))
            sentry(row, self.v[key], width=7).pack(side="left", ipady=4)
            for pv in presets:
                tk.Button(row, text=pv, font=FONT_DESC, bg=BG3, fg=TEXT,
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=BORDER, activeforeground=ORANGE,
                          command=lambda v=pv, k=key: self.v[k].set(v)
                          ).pack(side="left", padx=(4, 0), ipady=2, ipadx=3)

        col_r = tk.Frame(phys_grid, bg=BG2)
        col_r.grid(row=0, column=1, sticky="new")
        for txt, key, tip in [
            ("Ragdoll physics",  "phys_ragdoll_enable",
             "cl_ragdoll_physics_enable — disable for frozen corpses."),
            ("Blood on walls",   "phys_blood",
             "violence_hblood — disable for a cleaner render."),
            ("Dynamic lighting", "phys_dynamic_lighting",
             "r_dynamic — disable to remove explosion flashes."),
        ]:
            f = tk.Frame(col_r, bg=BG2)
            f.pack(fill="x", pady=(0, 6))
            _cb = hchk(f, txt, self.v[key])
            _cb.pack(anchor="w")
            add_tip(_cb, tip)

        # Trace recsys to show/hide HLAE-exclusive section
        self.v["recsys"].trace_add("write", self._on_recsys_change)
        self._on_recsys_change()

    def _asm_save_current_name(self):
        name = self.v["assemble_output"].get().strip()
        if not name:
            messagebox.showinfo("Assembly names", "Name field is empty.")
            return
        if name in self._asm_names:
            messagebox.showinfo("Assembly names", f"'{name}' is already registered.")
            return
        self._asm_names.append(name)
        save_asm_names(self._asm_names)
        self._refresh_asm_names()

    def _asm_delete_name(self, name):
        if name in self._asm_names:
            self._asm_names.remove(name)
            save_asm_names(self._asm_names)
            self._refresh_asm_names()

    def _refresh_asm_names(self):
        for w in self._asm_names_frame.winfo_children():
            w.destroy()
        if not self._asm_names:
            tk.Label(self._asm_names_frame,
                     text="No saved names — enter a name above then '+ Save'.",
                     font=FONT_DESC, fg=MUTED, bg=BG2).pack(anchor="w")
            return
        for n in self._asm_names:
            row = tk.Frame(self._asm_names_frame, bg=BG2)
            row.pack(fill="x", pady=1)
            tk.Button(row, text=n, font=FONT_SM, bg=BG3, fg=TEXT,
                      relief="flat", bd=0, cursor="hand2", anchor="w",
                      activebackground=BORDER, activeforeground=ORANGE,
                      command=lambda v=n: self.v["assemble_output"].set(v)
                      ).pack(side="left", ipady=3, ipadx=8)
            tk.Button(row, text="✕", font=FONT_DESC, bg=BG2, fg=RED,
                      relief="flat", bd=0, cursor="hand2",
                      activebackground=BORDER, activeforeground=RED,
                      command=lambda v=n: self._asm_delete_name(v)
                      ).pack(side="left", padx=(4, 0))

    def _on_game_speed_var(self, *_):
        if self._game_speed_trace_busy:
            return
        self._game_speed_trace_busy = True
        try:
            val = self._cfg_int({"v": self.v["hlae_slow_motion"].get()}, "v", 100, 1, 1000)
            try:
                current = int(self.v["hlae_slow_motion"].get())
            except Exception:
                current = None
            if current != val:
                self.v["hlae_slow_motion"].set(val)
            if self._speed_feedback is not None and self._speed_feedback.winfo_exists():
                self._speed_feedback.config(text=f"{val}%  ({val / 100:.2f}x)")
        finally:
            self._game_speed_trace_busy = False

    def _clamp_layout_values(self, w, h, split):
        try:
            w = int(float(w))
        except Exception:
            w = 1600
        try:
            h = int(float(h))
        except Exception:
            h = 900
        try:
            split = int(float(split))
        except Exception:
            split = 60
        w = max(1000, min(3840, w))
        h = max(600, min(2160, h))
        split = max(30, min(85, split))
        return w, h, split

    def _apply_layout_vars(self):
        w, h, split = self._clamp_layout_values(
            self.v["ui_window_w"].get(),
            self.v["ui_window_h"].get(),
            self.v["ui_split_pct"].get(),
        )
        self.v["ui_window_w"].set(w)
        self.v["ui_window_h"].set(h)
        self.v["ui_split_pct"].set(split)
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        if self._outer_paned is not None:
            try:
                self._outer_paned.sashpos(0, int(self.winfo_width() * (split / 100.0)))
            except Exception:
                pass
        self._log_flash(f"  ✓ UI layout applied: {w}x{h} | split {split}%", "ok")

    def _auto_layout(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = max(1000, min(3840, int(sw * 0.86)))
        h = max(600, min(2160, int(sh * 0.84)))
        self.v["ui_window_w"].set(w)
        self.v["ui_window_h"].set(h)
        self.v["ui_split_pct"].set(60)
        self._apply_layout_vars()

    def _reset_layout_defaults(self):
        self.v["ui_window_w"].set(1600)
        self.v["ui_window_h"].set(900)
        self.v["ui_split_pct"].set(60)
        self._apply_layout_vars()

    def _on_splitter_release(self, event=None):
        if self._outer_paned is None:
            return
        try:
            total = max(1, self.winfo_width())
            split = int(round(self._outer_paned.sashpos(0) * 100 / total))
            split = self._clamp_layout_values(1600, 900, split)[2]
            self.v["ui_split_pct"].set(split)
        except Exception:
            pass

    def _on_window_configure(self, event=None):
        if not self.v["ui_remember_layout"].get():
            return
        if self.state() != "normal":
            return
        if self._layout_cfg_job is not None:
            try:
                self.after_cancel(self._layout_cfg_job)
            except Exception:
                pass
        self._layout_cfg_job = self.after(250, self._remember_layout_state)

    def _remember_layout_state(self):
        self._layout_cfg_job = None
        if not self.v["ui_remember_layout"].get():
            return
        if self.state() != "normal":
            return
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            w, h, _ = self._clamp_layout_values(w, h, self.v["ui_split_pct"].get())
            self.v["ui_window_w"].set(w)
            self.v["ui_window_h"].set(h)
            self._on_splitter_release()
        except Exception:
            pass

    def _on_recsys_change(self, *_):
        try:
            is_hlae = self.v["recsys"].get() == "HLAE"
            if is_hlae:
                self._hlae_sec.pack(fill="x", pady=(0, 10))
            else:
                self._hlae_sec.pack_forget()
            # CS2 EFFECTS section is always visible (both modes)
        except Exception:
            pass

    def _on_res(self, e=None):
        for l, w, h in RESOLUTIONS:
            if l == self.v["resolution"].get():
                self.v["width"].set(w)
                self.v["height"].set(h)
                break

    # ── v60: structured resolution selectors ─────────────────────────────────
    def _on_perspective_change(self, *_):
        """Show/hide the 'Switch delay' slider based on the perspective mode."""
        try:
            persp = self.v["perspective"].get()
            if persp == "both":
                self._victim_pre_row.pack(fill="x", pady=(4, 0))
            else:
                self._victim_pre_row.pack_forget()
        except Exception:
            pass

    def _on_res_structured(self, *_):
        """Compute width × height from (definition × ratio) and update vars."""
        if self.v["res_custom"].get():
            return
        def_lbl = self.v["res_definition"].get()
        ratio_lbl = self.v["res_aspect"].get()
        height = next((h for lbl, h in DEFINITIONS if lbl == def_lbl), 1080)
        rw, rh = next(((rw, rh) for lbl, rw, rh in ASPECT_RATIOS if lbl == ratio_lbl), (16, 9))
        # Round width to nearest multiple of 2 (required by most codecs)
        width = round(height * rw / rh / 2) * 2
        self.v["width"].set(width)
        self.v["height"].set(height)
        self._update_res_preview()

    def _on_res_custom_toggle(self, *_):
        """Enable/disable structured selectors and manual input fields."""
        custom = self.v["res_custom"].get()
        state_struct = "disabled" if custom else "normal"
        state_manual = "normal" if custom else "disabled"
        # Enable/disable definition and ratio radio buttons
        try:
            for w in self._def_radios:
                w.config(state=state_struct)
        except Exception:
            pass
        try:
            for w in self._ratio_radios:
                w.config(state=state_struct)
        except Exception:
            pass
        # Enable/disable manual input fields
        try:
            self._res_w_entry.config(state=state_manual)
            self._res_h_entry.config(state=state_manual)
        except Exception:
            pass
        if not custom:
            # Recompute from selectors
            self._on_res_structured()
        self._update_res_preview()

    def _update_res_preview(self):
        """Refresh the computed resolution label."""
        try:
            w = self.v["width"].get()
            h = self.v["height"].get()
            self._res_preview_lbl.config(text=f"{w} × {h} px")
            self.v["resolution"].set(f"{w}x{h}")
        except Exception:
            pass

    def _on_vcodec(self, e=None):
        self._vcodec_desc.config(text=VIDEO_CODECS_INFO.get(self.v["video_codec"].get(), ""))

    def _on_acodec(self, e=None):
        self._acodec_desc.config(text=AUDIO_CODECS_INFO.get(self.v["audio_codec"].get(), ""))

    # ── TROIS SHOT (v62) ──────────────────────────────────────────────────
    def _on_trois_shot_toggle(self, *_):
        """Toggle TROIS SHOT. Mutually exclusive with Exclude and TROIS TAP.
        If both TROIS SHOT + ONE TAP are now checked → auto-enable TROIS TAP."""
        active = self.v["kill_mod_trois_shot"].get()
        if active and self.v["kill_mod_no_trois_shot"].get():
            self.v["kill_mod_no_trois_shot"].set(False)
        if active and self.v["kill_mod_trois_tap"].get():
            self.v["kill_mod_trois_tap"].set(False)
            self._disengage_trois_tap()
        if active and self.v["kill_mod_one_tap"].get():
            self.v["kill_mod_trois_shot"].set(False)
            self.v["kill_mod_one_tap"].set(False)
            self.v["kill_mod_trois_tap"].set(True)
            self._engage_trois_tap()

    def _on_no_trois_shot_toggle(self, *_):
        """Toggle Exclude (inverse TROIS SHOT).
        Mutually exclusive with TROIS SHOT and TROIS TAP only."""
        active = self.v["kill_mod_no_trois_shot"].get()
        if active:
            if self.v["kill_mod_trois_shot"].get():
                self.v["kill_mod_trois_shot"].set(False)
            if self.v["kill_mod_trois_tap"].get():
                self.v["kill_mod_trois_tap"].set(False)
                self._disengage_trois_tap()

    def _on_one_tap_toggle(self, *_):
        """Toggle ONE TAP.
        If both TROIS SHOT + ONE TAP are now checked → auto-enable TROIS TAP."""
        active = self.v["kill_mod_one_tap"].get()
        # Mutually exclusive with TROIS TAP
        if active and self.v["kill_mod_trois_tap"].get():
            self.v["kill_mod_trois_tap"].set(False)
            self._disengage_trois_tap()
        # Auto TROIS TAP: if both TROIS SHOT + ONE TAP active → engage TROIS TAP
        if active and self.v["kill_mod_trois_shot"].get():
            self.v["kill_mod_trois_shot"].set(False)
            self.v["kill_mod_one_tap"].set(False)
            self.v["kill_mod_trois_tap"].set(True)
            self._engage_trois_tap()
            return
        self._refresh_hs_lock_state()

    def _on_headshots_mode_change(self, *_):
        """Called when the user manually changes the HS radio — no-op if locked."""
        pass  # The radio var updates itself; lock is enforced by widget state

    def _lock_hs_to_only(self):
        """Force headshots_mode to 'only' and disable the HS radio buttons."""
        try:
            self.v["headshots_mode"].set("only")
            for w in self._hs_row.winfo_children():
                if isinstance(w, tk.Radiobutton):
                    w.config(state="disabled")
        except Exception:
            pass

    def _unlock_hs(self):
        """Re-enable the HS radio buttons."""
        try:
            for w in self._hs_row.winfo_children():
                if isinstance(w, tk.Radiobutton):
                    w.config(state="normal")
        except Exception:
            pass

    def _on_trois_tap_toggle(self, *_):
        """Toggle TROIS TAP checkbox — called by the UI widget only."""
        if self.v["kill_mod_trois_tap"].get():
            # Clear individual modifiers, engage locks
            self.v["kill_mod_trois_shot"].set(False)
            self.v["kill_mod_one_tap"].set(False)
            self.v["kill_mod_no_trois_shot"].set(False)
            self._engage_trois_tap()
        else:
            # User manually unchecked → simply disengage, do NOT restore sub-modifiers
            self._disengage_trois_tap()
        self._refresh_hs_lock_state()

    def _on_logic_mode_change(self, category: str, *_):
        """Show ★ Must toggles only when the category's logic mode is 'mixed'.

        Called by each logic radio command and at tab-build time (after(50,...)).
        DRY: one method handles all three categories via the _must_widgets dict.
        """
        logic_key = f"kill_mod_logic_{category}"
        is_mixed = self.v.get(logic_key, tk.StringVar()).get() == "mixed"
        for widget in self._must_widgets.get(category, []):
            try:
                if is_mixed:
                    widget.pack(side="left", padx=(8, 0))
                else:
                    widget.pack_forget()
            except Exception:
                pass
        if category in ("mods", "dp2"):
            self._refresh_hs_lock_state()

    def _on_kill_logic_change(self, *_):
        logic = self.v["kill_mod_logic_dp2"].get()
        self.v["kill_mod_logic_mods"].set(logic)
        self._on_logic_mode_change("mods")
        self._on_logic_mode_change("dp2")
        self._refresh_hs_lock_state()

    def _clear_kill_filters(self):
        keys = [k for k, *_ in self._FILTER_BADGE_DEFS]
        for k in keys:
            v = self.v.get(k)
            if v is not None:
                v.set(False)
            rv = self.v.get(f"{k}_req")
            if rv is not None:
                rv.set(False)
        self._refresh_hs_lock_state()
        self._log_flash("  ✓ All kill/situation filters unselected.", "ok")

    @staticmethod
    def _cfg_scalar(cfg, key, default=None):
        v = cfg.get(key, default)
        if hasattr(v, "get") and callable(v.get):
            try:
                return v.get()
            except Exception:
                return default
        return v

    def _hs_only_is_required(self, cfg) -> bool:
        if bool(self._cfg_scalar(cfg, "kill_mod_trois_tap", False)):
            return True
        if not bool(self._cfg_scalar(cfg, "kill_mod_one_tap", False)):
            return False

        active_dp2 = [k for k, *_ in self._DP2_FILTER_DEFS if bool(self._cfg_scalar(cfg, k, False))]
        if "kill_mod_one_tap" not in active_dp2:
            return False

        logic = str(self._cfg_scalar(cfg, "kill_mod_logic_dp2", "any") or "any")
        if logic == "all":
            return True

        if logic == "mixed":
            req = [k for k in active_dp2 if bool(self._cfg_scalar(cfg, f"{k}_req", False))]
            opt = [k for k in active_dp2 if not bool(self._cfg_scalar(cfg, f"{k}_req", False))]
            if "kill_mod_one_tap" in req:
                return True
            if "kill_mod_one_tap" in opt and len(opt) == 1:
                return True
            return False

        if not (len(active_dp2) == 1 and active_dp2[0] == "kill_mod_one_tap"):
            return False

        mods_any = str(self._cfg_scalar(cfg, "kill_mod_logic_mods", "any") or "any") == "any"
        mods_active = any(bool(self._cfg_scalar(cfg, k, False)) for k in self._SQL_MOD_KEYS)
        if mods_any and mods_active:
            return False
        return True

    def _refresh_hs_lock_state(self):
        try:
            if self._hs_only_is_required(self.v):
                self._lock_hs_to_only()
            else:
                self._unlock_hs()
        except Exception:
            pass

    def _install_hs_lock_watchers(self):
        if getattr(self, "_hs_lock_watchers_installed", False):
            return
        keys = {
            "kill_mod_one_tap", "kill_mod_trois_tap",
            "kill_mod_logic_dp2", "kill_mod_logic_mods",
            "kill_mod_one_tap_req",
            *self._SQL_MOD_KEYS,
            *(k for k, *_ in self._DP2_FILTER_DEFS),
        }
        for key in keys:
            var = self.v.get(key)
            if hasattr(var, "trace_add"):
                var.trace_add("write", lambda *_: self._refresh_hs_lock_state())
        self._hs_lock_watchers_installed = True
        self._refresh_hs_lock_state()

    def _wire_enable_must(self, enable_var: tk.BooleanVar, req_var: tk.BooleanVar):
        """Couple an Enable checkbox with its ★ Must checkbox.

        Rules:
          - Checking ★ Must while Enable is off → auto-enables the filter.
          - Unchecking Enable while Must is on → auto-clears Must.

        This prevents the silent bug where Must=True + Enable=False causes the
        filter to never appear in the active list, making Must silently ignored.
        Stores the pair in self._must_couplings for reference.
        """
        if not hasattr(self, "_must_couplings"):
            self._must_couplings: list = []
        self._must_couplings.append((enable_var, req_var))

        def _on_req_change(*_):
            if req_var.get() and not enable_var.get():
                enable_var.set(True)

        def _on_enable_change(*_):
            if not enable_var.get() and req_var.get():
                req_var.set(False)

        req_var.trace_add("write", _on_req_change)
        enable_var.trace_add("write", _on_enable_change)

    def _on_clutch_toggle(self, *_):
        """Show/hide clutch options based on clutch_enabled."""
        try:
            if self.v["clutch_enabled"].get():
                self._clutch_opts_inner.pack(fill="x")
            else:
                self._clutch_opts_inner.pack_forget()
        except Exception:
            pass

    @staticmethod
    def _clutch_allowed_sizes(cfg) -> set:
        """Return the set of allowed clutch sizes (1..5) from config.
        If all 1vX keys are False → all sizes allowed (empty set = no filter).
        """
        sizes = set()
        for n in range(1, 6):
            if cfg.get(f"clutch_1v{n}", False):
                sizes.add(n)
        return sizes  # empty = no restriction

    def _engage_trois_tap(self):
        self._refresh_hs_lock_state()

    def _disengage_trois_tap(self):
        self._refresh_hs_lock_state()


    def _retrigger_toggle_vars(self):
        """Nudge every BooleanVar and StringVar so hchk/hradio _update closures re-fire.

        Since those closures now call _t() for live colour lookups, re-triggering
        them applies the new theme to all checkboxes and radiobuttons immediately.
        """
        for key, var in self.v.items():
            try:
                if isinstance(var, (tk.BooleanVar, tk.StringVar)):
                    cur = var.get()
                    var.set(cur)
            except Exception:
                pass


    def _trois_shot_filter(self, demo_path, events, cfg):
        """Keep only lucky kills (TROIS SHOT filter).

        Reads weapon_fire data from _dp2_cache (populated by _dp2_parse_demo).
        Works on any weapon that has a threshold defined in TROIS_SHOT_THRESHOLDS
        (via CSDM_TO_DP2_WEAPON). Kills with weapons that have no threshold are
        passed through unchanged (no weapon restriction enforced in UI anymore).
        """
        if not os.path.isfile(demo_path):
            return events

        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)

        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        fire_index = data.get("fire_detail", {})

        def _is_lucky(kill_tick, killer_sid, weapon_raw):
            w_key = CSDM_TO_DP2_WEAPON.get(weapon_raw.lower().strip())
            if w_key is None:
                return False  # no threshold for this weapon — never lucky
            thresholds = TROIS_SHOT_THRESHOLDS[w_key]
            wp_suffix  = w_key[7:] if w_key.startswith("weapon_") else w_key

            entries = fire_index.get((killer_sid, wp_suffix))
            if not entries:
                return False

            ticks_only = [e[0] for e in entries]
            pos = bisect.bisect_right(ticks_only, kill_tick) - 1
            best = None
            best_dist = DP2_TICK_WINDOW + 1
            i = pos
            while i >= 0:
                ftick, acc, scoped, vel = entries[i]
                dist = kill_tick - ftick
                if dist < 0:
                    i -= 1; continue
                if dist >= DP2_TICK_WINDOW:
                    break
                if dist < best_dist:
                    best_dist = dist
                    best = (acc, scoped, vel)
                i -= 1

            if best is None:
                return False

            acc, scoped, vel = best
            if thresholds["scope"] and thresholds["vel"]:
                result = (not scoped) or (acc > thresholds["acc"]) or (vel > 100)
            elif thresholds["scope"]:
                result = (not scoped) or (acc > thresholds["acc"])
            else:
                result = acc > thresholds["acc"]

            if self._dp2_verbose:
                self._alog(
                    f"  🎲 [{weapon_raw}] acc={acc:.4f}(threshold={thresholds['acc']}) "
                    f"scoped={scoped} vel={vel:.0f} → {'✓ TROIS SHOT' if result else '✗ precise'}",
                    "info" if result else "dim")
            return result

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt)
                continue
            weapon_raw = evt.get("weapon", "")
            killer_sid = str(evt.get("killer_sid", ""))
            kill_tick  = int(evt.get("tick", 0))
            # Weapons with no threshold are skipped (not included)
            if CSDM_TO_DP2_WEAPON.get(weapon_raw.lower().strip()) is None:
                continue
            if _is_lucky(kill_tick, killer_sid, weapon_raw):
                filtered.append(evt)

        return filtered

    def _dp2_parse_demo(self, demo_path, required_sections=None):
        if required_sections is None:
            required_sections = {"fire", "death", "hurt"}
        required_sections = set(required_sections)
        with self._dp2_cache_lock:
            existing = self._dp2_cache.get(demo_path)
            if not isinstance(existing, dict):
                existing = {}
            existing_sections = set(existing.get("_sections", set()))
        needed = required_sections - existing_sections
        if not needed:
            return True
        if not os.path.isfile(demo_path):
            with self._dp2_cache_lock:
                cur = self._dp2_cache.get(demo_path, {})
                if not isinstance(cur, dict):
                    cur = {}
                cur.setdefault("fire_detail", {})
                cur.setdefault("fire_ticks", {})
                cur.setdefault("view_angles", {})
                cur.setdefault("hurt_index", {})
                cur.setdefault("death_flags", {})
                cur["_sections"] = set(cur.get("_sections", set())) | required_sections
                self._dp2_cache[demo_path] = cur
            return False
        try:
            from demoparser2 import DemoParser
        except ImportError:
            self._alog(
                "  ⚠ demoparser2 not installed — install with: pip install demoparser2",
                "warn")
            return False
        try:
            parser = DemoParser(demo_path)
        except Exception as e:
            self._alog(f"  ⚠ dp2 parse error ({Path(demo_path).name}): {e}", "warn")
            return False

        fire_detail = dict(existing.get("fire_detail") or {})
        fire_ticks = dict(existing.get("fire_ticks") or {})
        view_angles = dict(existing.get("view_angles") or {})
        hurt_index = dict(existing.get("hurt_index") or {})
        death_flags = dict(existing.get("death_flags") or {})

        if "fire" in needed:
            try:
                fire_df = parser.parse_event(
                    "weapon_fire",
                    player=["is_scoped", "velocity_X", "velocity_Y",
                            "accuracy_penalty", "player_steamid"],
                    other=[],
                )
                if fire_df is None or len(fire_df) == 0:
                    fire_detail = {}
                    fire_ticks = {}
                else:
                    cols = list(fire_df.columns)
                    def _col(name):
                        if name in cols:
                            return name
                        if f"user_{name}" in cols:
                            return f"user_{name}"
                        return None
                    col_sid = _col("player_steamid") or _col("steamid")
                    col_acc = _col("accuracy_penalty")
                    col_scope = _col("is_scoped")
                    col_vx = _col("velocity_X")
                    col_vy = _col("velocity_Y")
                    if not col_sid or not col_acc:
                        self._alog(
                            f"  ⚠ dp2: steamid/accuracy columns missing in weapon_fire "
                            f"({Path(demo_path).name})", "warn")
                        fire_detail = {}
                        fire_ticks = {}
                    else:
                        np_cols = ["tick", "weapon", col_sid, col_acc]
                        opt_cols = ([col_scope] if col_scope else []) + \
                                   ([col_vx] if col_vx else []) + \
                                   ([col_vy] if col_vy else [])
                        arr = fire_df[np_cols + opt_cols].to_numpy()
                        i_scope = 4 if col_scope else None
                        i_vx = 4 + (1 if col_scope else 0) if col_vx else None
                        i_vy = 4 + (1 if col_scope else 0) + (1 if col_vx else 0) if col_vy else None
                        fd = defaultdict(list)
                        for row in arr:
                            tick = int(row[0] or 0)
                            wpn = str(row[1] or "").lower()
                            sid = str(row[2] or "")
                            acc = float(row[3] or 0)
                            scoped = bool(row[i_scope]) if i_scope is not None else False
                            vx = float(row[i_vx]) if i_vx is not None else 0.0
                            vy = float(row[i_vy]) if i_vy is not None else 0.0
                            vel = (vx**2 + vy**2) ** 0.5
                            wpn_s = wpn[7:] if wpn.startswith("weapon_") else wpn
                            fd[(sid, wpn_s)].append((tick, acc, scoped, vel))
                        for k in fd:
                            fd[k].sort(key=lambda r: r[0])
                        fire_detail = dict(fd)
                        fire_ticks = {k: [r[0] for r in v] for k, v in fire_detail.items()}
            except Exception as e:
                self._alog(f"  ⚠ dp2 parse error ({Path(demo_path).name}): {e}", "warn")
                fire_detail = {}
                fire_ticks = {}

        if "death" in needed:
            view_angles = {}
            death_flags = {}
            try:
                death_df = parser.parse_event(
                    "player_death",
                    player=["pitch", "yaw"],
                    other=["attacker_steamid",
                           "noscope", "thrusmoke", "attackerblind",
                           "penetrated", "attackerinair"],
                )
                if death_df is not None and len(death_df) > 0:
                    dcols = list(death_df.columns)
                    def _dc(name):
                        if name in dcols:
                            return name
                        if f"attacker_{name}" in dcols:
                            return f"attacker_{name}"
                        if f"user_{name}" in dcols:
                            return f"user_{name}"
                        return None
                    col_atk = _dc("attacker_steamid") or next(
                        (c for c in dcols if "attacker" in c.lower() and "steam" in c.lower()), None)
                    col_yaw = next((c for c in dcols if "yaw" in c.lower()), None)
                    col_pitch = next((c for c in dcols if "pitch" in c.lower()), None)
                    flag_cols = {
                        "noscope": next((c for c in dcols if "noscope" in c.lower()), None),
                        "thrusmoke": next((c for c in dcols if "thrusmoke" in c.lower()), None),
                        "attackerblind": next((c for c in dcols if "attackerblind" in c.lower()), None),
                        "penetrated": next((c for c in dcols if "penetrated" in c.lower()), None),
                        "attackerinair": next((c for c in dcols if "attackerinair" in c.lower()), None),
                    }
                    if col_atk:
                        fetch_cols = ["tick", col_atk]
                        if col_yaw:
                            fetch_cols.append(col_yaw)
                        if col_pitch:
                            fetch_cols.append(col_pitch)
                        for fc in flag_cols.values():
                            if fc and fc not in fetch_cols:
                                fetch_cols.append(fc)
                        arr_d = death_df[fetch_cols].to_numpy()
                        yaw_i = fetch_cols.index(col_yaw) if col_yaw else None
                        pitch_i = fetch_cols.index(col_pitch) if col_pitch else None
                        flag_indices = {fname: fetch_cols.index(fc) for fname, fc in flag_cols.items() if fc}
                        for row in arr_d:
                            t = int(row[0] or 0)
                            sid = str(row[1] or "")
                            if not sid:
                                continue
                            yaw = float(row[yaw_i] or 0) if yaw_i is not None else 0.0
                            pit = float(row[pitch_i] or 0) if pitch_i is not None else 0.0
                            if yaw_i is not None or pitch_i is not None:
                                view_angles.setdefault(sid, []).append((t, yaw, pit))
                            flags = {}
                            for fname, fi in flag_indices.items():
                                val = row[fi]
                                if val is not None:
                                    flags[fname] = int(val) if fname == "penetrated" else bool(val)
                            if flags:
                                death_flags[(t, sid)] = flags
                for k in view_angles:
                    view_angles[k].sort(key=lambda r: r[0])
            except Exception:
                pass

        if "hurt" in needed:
            hurt_index = {}
            try:
                hurt_df = parser.parse_event(
                    "player_hurt",
                    player=[],
                    other=["attacker_steamid", "userid_steamid"],
                )
                if hurt_df is not None and len(hurt_df) > 0:
                    hcols = list(hurt_df.columns)
                    col_hatk = next((c for c in hcols if "attacker" in c.lower() and "steam" in c.lower()), None)
                    col_hvic = next((c for c in hcols if ("user" in c.lower() or "victim" in c.lower())
                                     and "steam" in c.lower() and "attacker" not in c.lower()), None)
                    if col_hatk and col_hvic:
                        for row in hurt_df[["tick", col_hatk, col_hvic]].to_numpy():
                            t = int(row[0] or 0)
                            atk = str(row[1] or "")
                            vic = str(row[2] or "")
                            if atk and vic:
                                hurt_index.setdefault(vic, []).append((t, atk))
                for k in hurt_index:
                    hurt_index[k].sort(key=lambda r: r[0])
            except Exception:
                pass

        with self._dp2_cache_lock:
            merged = self._dp2_cache.get(demo_path, {})
            if not isinstance(merged, dict):
                merged = {}
            merged["fire_detail"] = fire_detail
            merged["fire_ticks"] = fire_ticks
            merged["view_angles"] = view_angles
            merged["hurt_index"] = hurt_index
            merged["death_flags"] = death_flags
            merged["_sections"] = set(merged.get("_sections", set())) | required_sections
            self._dp2_cache[demo_path] = merged
        return True

    def _no_trois_shot_filter(self, demo_path, events, cfg):
        """Keep only precise kills — inverse of TROIS SHOT.
        Kills on weapons with no threshold are passed through (can't be lucky).
        """
        lucky_evts = self._trois_shot_filter(demo_path, events, cfg)
        lucky_sig = {
            (e.get("tick"), str(e.get("killer_sid")))
            for e in lucky_evts if e.get("type") == "kill"
        }
        filtered = []
        for e in events:
            if e.get("type") != "kill":
                filtered.append(e)
                continue
            sig = (e.get("tick"), str(e.get("killer_sid")))
            if sig not in lucky_sig:
                filtered.append(e)
        return filtered

    def _one_tap_filter(self, demo_path, events, cfg):
        """Keep only isolated single-shot kills.

        A kill is kept if the killer fired exactly one shot with that weapon
        in [kill_tick − WINDOW, kill_tick + WINDOW].
        Reads fire_ticks from _dp2_cache (populated by _dp2_parse_demo).
        If the demo is not yet cached, triggers a synchronous parse as fallback.
        (Headshot is pre-guaranteed by the DB query when kill_mod_one_tap is enabled.)
        """
        if not os.path.isfile(demo_path):
            return events

        # Ensure parsed — no-op if already cached
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)

        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        shots_index = data.get("fire_ticks", {})

        WINDOW = DP2_TICK_WINDOW  # 128 ticks ≈ 2s at 64 tick/s

        def _is_isolated(kill_tick, killer_sid, weapon_raw):
            """True iff exactly 1 shot with this weapon was fired in [kill_tick-WINDOW, kill_tick+WINDOW]."""
            # Resolve weapon suffix the same way as _trois_shot_filter
            w_key = CSDM_TO_DP2_WEAPON.get(weapon_raw.lower().strip())
            if w_key:
                wpn_s = w_key[7:] if w_key.startswith("weapon_") else w_key
            else:
                wpn_s = weapon_raw.lower().strip()
                if wpn_s.startswith("weapon_"):
                    wpn_s = wpn_s[7:]
            ticks = shots_index.get((str(killer_sid), wpn_s), [])
            if not ticks:
                return False
            lo, hi = kill_tick - WINDOW, kill_tick + WINDOW
            pos = bisect.bisect_left(ticks, lo)
            count = 0
            for i in range(pos, len(ticks)):
                if ticks[i] > hi:
                    break
                count += 1
                if count > 1:
                    return False  # more than one shot with this weapon in the window
            return count == 1

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt)
                continue
            killer_sid  = str(evt.get("killer_sid", ""))
            kill_tick   = int(evt.get("tick", 0))
            weapon_raw  = evt.get("weapon", "")
            isolated = _is_isolated(kill_tick, killer_sid, weapon_raw)
            if self._dp2_verbose:
                self._alog(
                    f"  🎯 [{weapon_raw}] [tick={kill_tick}] sid={killer_sid} → "
                    f"{'✓ isolated' if isolated else '✗ not isolated'}",
                    "info" if isolated else "dim")
            if isolated:
                filtered.append(evt)

        return filtered

    def _trois_tap_filter(self, demo_path, events, cfg):
        """TROIS TAP = TROIS SHOT AND ONE TAP combined.
        Keeps only lucky kills that are also isolated single shots.
        """
        lucky_events = self._trois_shot_filter(demo_path, events, cfg)
        return self._one_tap_filter(demo_path, lucky_events, cfg)

    def _spray_transfer_filter(self, demo_path, events, cfg):
        """Keep only kills that are part of a spray transfer.

        A spray transfer = the player kills ≥2 opponents in a single continuous
        burst with an automatic weapon (no trigger release between kills).
        Detection: at each kill tick, look back in weapon_fire for a shot within
        SPRAY_MAX_GAP_TICKS. Then walk backward through shots to find the burst
        start. A burst that spans ≥2 victims qualifies.

        Only automatic weapons are eligible (SPRAY_TRANSFER_WEAPONS_LOWER).
        Snipers, auto-snipers, shotguns, non-CZ pistols are excluded.
        """
        if not os.path.isfile(demo_path):
            return events

        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)

        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        fire_ticks = data.get("fire_ticks", {})

        # Group kills by (killer_sid, weapon_suffix) to check bursts
        kill_groups: dict = {}
        for evt in events:
            if evt.get("type") != "kill":
                continue
            weapon_raw = evt.get("weapon", "")
            if weapon_raw.lower().strip() not in SPRAY_TRANSFER_WEAPONS_LOWER:
                continue
            sid   = str(evt.get("killer_sid", ""))
            wpn_s = weapon_raw.lower().strip()
            kill_groups.setdefault((sid, wpn_s), []).append(int(evt.get("tick", 0)))

        spray_kill_sigs: set = set()

        for (sid, wpn_s), kill_ticks_list in kill_groups.items():
            if len(kill_ticks_list) < 2:
                continue
            shots = fire_ticks.get((sid, wpn_s), [])
            if not shots:
                continue

            kill_ticks_sorted = sorted(kill_ticks_list)

            # Walk shots once to segment into bursts, then classify kills per burst.
            # A burst ends when the gap between consecutive shots > SPRAY_MAX_GAP_TICKS.
            burst_ranges: list = []    # [(burst_start_tick, burst_end_tick), ...]
            b_start = shots[0]
            for j in range(1, len(shots)):
                if shots[j] - shots[j - 1] > SPRAY_MAX_GAP_TICKS:
                    burst_ranges.append((b_start, shots[j - 1]))
                    b_start = shots[j]
            burst_ranges.append((b_start, shots[-1]))

            # For each burst, find which kills fall inside it (±SPRAY_MAX_GAP_TICKS grace)
            ki = 0  # pointer into kill_ticks_sorted (both are sorted)
            for b_start, b_end in burst_ranges:
                window_end = b_end + SPRAY_MAX_GAP_TICKS
                burst_kills = []
                # Advance ki to first kill in this burst
                while ki < len(kill_ticks_sorted) and kill_ticks_sorted[ki] < b_start:
                    ki += 1
                j = ki
                while j < len(kill_ticks_sorted) and kill_ticks_sorted[j] <= window_end:
                    burst_kills.append(kill_ticks_sorted[j])
                    j += 1
                if len(burst_kills) >= 2:
                    for bkt in burst_kills:
                        spray_kill_sigs.add((bkt, sid))
                    if self._dp2_verbose:
                        self._alog(
                            f"  🔫 SPRAY TRANSFER [{wpn_s}] sid={sid} "
                            f"burst={b_start}→{b_end} kills={len(burst_kills)}", "info")

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt)
                continue
            sig = (int(evt.get("tick", 0)), str(evt.get("killer_sid", "")))
            if sig in spray_kill_sigs:
                filtered.append(evt)

        return filtered

    def _apply_spray_transfer_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_spray_transfer",
            self._spray_transfer_filter, "🔫 SPRAY → spray transfer")

    # ── dp2 filters: High Velocity, Flick, Savior ───────────────────────

    def _high_velocity_filter(self, demo_path, events, cfg):
        """Ferrari Peek — kill faster than the opponent can react.

        The player peeks an angle at speed, fires once, and immediately retreats —
        the entire exposure window is shorter than human reaction time (~150-250ms).

        A kill qualifies if ALL conditions hold:

          1. ISOLATED SHOT (optional, kill_mod_hv_one_shot): no weapon_fire from
             the player in PRE_WINDOW ticks before the kill shot. Ensures this is
             the opening shot, not the last bullet of a spray.

          2. MOVING BEFORE: the player was moving at speed during the peek approach.
             Checked in two ways:
             - The kill shot itself was fired at velocity >= approach_thr (still
               running at shot time, or counter-strafe was very recent), OR
             - A weapon_fire in the APPROACH_WIN before the shot had velocity >=
               approach_thr (only relevant when one-shot is disabled, since condition
               1 eliminates prior shots otherwise).
             APPROACH_WIN is intentionally tight (1s) — a fast approach 3s ago
             followed by camping is not a ferrari peek.

          3. RESUMES AFTER: at least one weapon_fire within RESUME_WIN after the
             kill has velocity >= RESUME_THR — player immediately moves away.
             Skipped gracefully if no post-kill fire is found.

        kill_mod_high_vel_thr: minimum approach speed (u/s) to qualify.
        Default 100 u/s — above walking speed, catches any active peek.
        """
        if not os.path.isfile(demo_path):
            return events
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)
        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        fire_index = data.get("fire_detail", {})

        approach_thr     = max(1.0, float(cfg.get("kill_mod_high_vel_thr", 100)))
        require_one_shot = cfg.get("kill_mod_hv_one_shot", True)
        RESUME_THR    = 80.0   # u/s — minimum speed to count as "moving after"
        PRE_WINDOW    = 48     # ticks — no prior shot allowed before kill (~0.75s)
        APPROACH_WIN  = 64     # ticks — recent movement window (~1s, intentionally tight)
        RESUME_WIN    = 128    # ticks — window to detect post-kill movement (~2s)
        SHOT_WINDOW   = 24     # ticks — window around kill to match kill shot

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt)
                continue

            kill_tick  = int(evt.get("tick", 0))
            killer_sid = str(evt.get("killer_sid", ""))

            # Collect all weapon_fire entries for this player (all weapons)
            all_entries: list = []
            for (sid, _wpn), entries in fire_index.items():
                if sid == killer_sid:
                    all_entries.extend(entries)
            all_entries.sort(key=lambda r: r[0])

            if not all_entries:
                # No fire data — pass through (cannot evaluate)
                filtered.append(evt)
                continue

            # ── Find the kill shot ─────────────────────────────────────────
            shot_entry = None
            for ftick, acc, scoped, vel in all_entries:
                if abs(kill_tick - ftick) <= SHOT_WINDOW:
                    if shot_entry is None or abs(kill_tick - ftick) < abs(kill_tick - shot_entry[0]):
                        shot_entry = (ftick, acc, scoped, vel)

            if shot_entry is None:
                # No matching shot found — pass through
                filtered.append(evt)
                continue

            shot_tick = shot_entry[0]
            shot_vel  = shot_entry[3]

            # ── Condition 1: isolated shot (one-shot kill) — optional ─────
            if require_one_shot:
                prior_shot = any(
                    (shot_tick - PRE_WINDOW) <= ftick < shot_tick
                    for ftick, *_ in all_entries
                )
                if prior_shot:
                    continue

            # ── Condition 2: was moving before (on the peek) ──────────────
            approach_start = shot_tick - APPROACH_WIN
            approach_end   = shot_tick - PRE_WINDOW
            approach_shots = [
                vel for ftick, _acc, _sc, vel in all_entries
                if approach_start <= ftick < approach_end
            ]
            was_moving_before = (
                (approach_shots and max(approach_shots) >= approach_thr)
                or shot_vel >= approach_thr  # shot while running (no CS)
            )
            if not was_moving_before:
                continue

            # ── Condition 3: resumes movement after kill ───────────────────
            resume_shots = [
                vel for ftick, _acc, _sc, vel in all_entries
                if kill_tick < ftick <= kill_tick + RESUME_WIN
            ]
            if resume_shots and max(resume_shots) < RESUME_THR:
                # Fired again but stationary — not resuming a peek
                continue
            # No post-kill fire → skip check (degrade gracefully)

            filtered.append(evt)

        return filtered

    def _flick_filter(self, demo_path, events, cfg):
        """Keep kills where the player made a large view-angle change just before the kill.

        Compares the yaw angle at the kill tick to the yaw ~0.5s (32 ticks) before.
        Angle delta ≥ kill_mod_flick_deg qualifies (default 50°).
        Uses view_angles cache populated from player_death events.
        """
        if not os.path.isfile(demo_path):
            return events
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)
        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        view_angles = data.get("view_angles", {})
        if not view_angles:
            # No data — pass through unchanged (degraded gracefully)
            return events

        min_deg = max(1.0, float(cfg.get("kill_mod_flick_deg", 50)))
        LOOK_BACK = 32  # ticks to look back for prior angle (~0.5s)

        def _angle_delta(a, b):
            """Smallest angle between two yaw values (handles 360→0 wrap)."""
            d = abs(a - b) % 360
            return d if d <= 180 else 360 - d

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt); continue
            kill_tick  = int(evt.get("tick", 0))
            killer_sid = str(evt.get("killer_sid", ""))
            angles = view_angles.get(killer_sid, [])
            if not angles:
                continue
            ticks = [a[0] for a in angles]
            # Find angle at/near kill tick
            pos = bisect.bisect_right(ticks, kill_tick) - 1
            if pos < 0:
                continue
            yaw_at_kill = angles[pos][1]
            # Find angle ~LOOK_BACK ticks before
            prior_tick = kill_tick - LOOK_BACK
            pos_prior  = bisect.bisect_right(ticks, prior_tick) - 1
            if pos_prior < 0 or pos_prior == pos:
                continue
            yaw_before = angles[pos_prior][1]
            delta = _angle_delta(yaw_at_kill, yaw_before)
            if delta >= min_deg:
                filtered.append(evt)
        return filtered

    def _sauveur_filter(self, demo_path, events, cfg):
        """Keep kills where the player killed an enemy who was hurting a teammate.

        A 'sauveur' kill: within SAUVEUR_WINDOW ticks before the kill, the
        victim (the player's target) was attacking a player on the same side
        as the active player. Requires hurt_index from player_death parse.
        """
        if not os.path.isfile(demo_path):
            return events
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)
        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        hurt_index = data.get("hurt_index", {})
        if not hurt_index:
            return events

        SAUVEUR_WINDOW = 128  # ~2s — the enemy was shooting at a teammate recently

        # Build set of active player sids for side-checking
        sids_set = {str(e.get("killer_sid","")) for e in events if e.get("type") == "kill"}

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt); continue
            kill_tick   = int(evt.get("tick", 0))
            victim_sid  = str(evt.get("victim_sid", ""))
            # Check if the victim was hurting someone in the window before the kill
            # hurt_index[victim_sid] = [(tick, attacker_sid), ...] where attacker=victim here
            # We actually need: victim of this kill was attacking (as attacker) someone near tick
            # hurt_index is keyed by the HURT VICTIM — need to find victim_sid as attacker
            # Reconstruct: search for entries where attacker == victim_sid
            # This is O(n) per kill — acceptable since hurt events per demo are bounded
            hurt_in_window = False
            for hurt_victim_sid, hurt_entries in hurt_index.items():
                for (ht, hatk) in hurt_entries:
                    if hatk == victim_sid and 0 <= kill_tick - ht <= SAUVEUR_WINDOW:
                        hurt_in_window = True
                        break
                if hurt_in_window:
                    break
            if hurt_in_window:
                filtered.append(evt)
        return filtered

    # ── Death-flag filters (dp2 — from player_death event fields) ─────────────
    # A single generic filter reads death_flags[(tick, killer_sid)][flag_name].
    # All four "missing DB column" mods are implemented here.

    _TICK_MATCH_WINDOW = 2   # ticks — death event tick vs kill event tick tolerance

    def _death_flag_filter(self, demo_path, events, cfg,
                           flag_name: str, threshold=True):
        """Generic filter: keep kills whose player_death event has flag_name truthy.

        flag_name  — key in death_flags dict (e.g. 'attackerinair', 'attackerblind',
                     'penetrated', 'noscope', 'thrusmoke')
        threshold  — value to compare against:
                       True  → flag must be truthy (bool flags)
                       int>0 → flag must be >= threshold (penetrated count)

        If death_flags is empty (parse failed / old demo), passes all kills through
        (graceful degradation — same behaviour as other dp2 filters).
        """
        if not os.path.isfile(demo_path):
            return events
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)
        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        death_flags = data.get("death_flags", {})

        if not death_flags:
            return events  # degrade gracefully

        filtered = []
        for evt in events:
            if evt.get("type") != "kill":
                filtered.append(evt)
                continue
            kill_tick  = int(evt.get("tick", 0))
            killer_sid = str(evt.get("killer_sid", ""))
            # Look up within a small tick window to tolerate minor tick offsets
            val = None
            for dt in range(-self._TICK_MATCH_WINDOW, self._TICK_MATCH_WINDOW + 1):
                entry = death_flags.get((kill_tick + dt, killer_sid))
                if entry is not None:
                    val = entry.get(flag_name)
                    break
            if val is None:
                # Flag absent for this kill — pass through (can't determine)
                filtered.append(evt)
                continue
            if isinstance(threshold, bool):
                if bool(val) == threshold:
                    filtered.append(evt)
            else:
                if int(val) >= threshold:
                    filtered.append(evt)
        return filtered

    def _wall_bang_dp2_filter(self, demo_path, events, cfg):
        """Wallbang via dp2 — penetrated > 0 in player_death event."""
        return self._death_flag_filter(demo_path, events, cfg, "penetrated", 1)

    def _airborne_dp2_filter(self, demo_path, events, cfg):
        """Airborne killer via dp2 — attackerinair = True in player_death event."""
        return self._death_flag_filter(demo_path, events, cfg, "attackerinair", True)

    def _attacker_blind_dp2_filter(self, demo_path, events, cfg):
        """Blind fire via dp2 — attackerblind = True in player_death event."""
        return self._death_flag_filter(demo_path, events, cfg, "attackerblind", True)

    def _collateral_dp2_filter(self, demo_path, events, cfg):
        """Collateral / noscope via dp2 — penetrated >= 1 like wallbang but
        this is specifically a bullet-through-body collateral.
        CS2 sets penetrated=1 for both wallbang and through-body kills;
        we use it as the best available proxy for collateral.
        """
        return self._death_flag_filter(demo_path, events, cfg, "penetrated", 1)

    def _apply_high_velocity_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_high_velocity",
            self._high_velocity_filter, "🏎 FERRARI PEEK → counter-strafe")

    def _apply_flick_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_flick",
            self._flick_filter, "↩ FLICK")

    def _apply_sauveur_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_sauveur",
            self._sauveur_filter, "🛡 SAVIOR")

    def _apply_wall_bang_dp2_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_wall_bang",
            self._wall_bang_dp2_filter, "🧱 WALLBANG → penetrated")

    def _apply_airborne_dp2_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_airborne",
            self._airborne_dp2_filter, "🪂 AIRBORNE → attackerinair")

    def _apply_attacker_blind_dp2_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_attacker_blind",
            self._attacker_blind_dp2_filter, "😵 BLIND FIRE → attackerblind")

    def _apply_collateral_dp2_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_collateral",
            self._collateral_dp2_filter, "🎯 COLLATERAL → penetrated")

    @staticmethod
    def _stamp_mf(events, cfg_key):
        """Add cfg_key to the _mf (matched-filters) set on every kill event in events."""
        for e in events:
            if e.get("type") == "kill":
                mf = e.get("_mf")
                if mf is None:
                    e["_mf"] = {cfg_key}
                else:
                    mf.add(cfg_key)

    @staticmethod
    def _split_required_optional(cfg, keys: list) -> tuple:
        """Split a list of active filter cfg_keys into (required, optional) for mixed mode.

        A key is "required" when its companion `<key>_req` flag is True in cfg.
        Returns two lists — callers intersect required sets and union optional sets,
        then intersect the two results.

        Used by all three filter engines (SQL mods, dp2, DB postfilters) so the
        mixed-mode logic lives in exactly one place.
        """
        required = [k for k in keys if cfg.get(f"{k}_req", False)]
        optional = [k for k in keys if not cfg.get(f"{k}_req", False)]
        return required, optional

    def _apply_filter_to_events(self, evts, cfg, cfg_key, filter_fn, label):
        """Apply a per-demo filter function to all demos in evts.

        Skips if cfg_key is falsy. Returns a new {demo_path: events} dict
        with empty-demo paths removed.

        Surviving kill events are tagged with cfg_key in their _mf (matched filters)
        set so that clip badges can show exactly which filter each clip triggered.
        """
        if not cfg.get(cfg_key):
            return evts
        result = {}
        for dp, events in evts.items():
            n_before = _count_kills(events)
            filtered = filter_fn(dp, events, cfg)
            n_after  = _count_kills(filtered)
            self._alog(
                f"  {label} [{Path(dp).name}] : {n_before} kills → {n_after}",
                "info" if n_after else "dim")
            if filtered:
                self._stamp_mf(filtered, cfg_key)
                result[dp] = filtered
        return result

    def _apply_trois_shot_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_trois_shot",
            self._trois_shot_filter, "🎲 TROIS SHOT → TROIS SHOT")

    def _apply_no_trois_shot_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_no_trois_shot",
            self._no_trois_shot_filter, "🚫🎲 Exclude → precise")

    def _apply_one_tap_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_one_tap",
            self._one_tap_filter, "🎯 ONE TAP → one tap")

    def _apply_trois_tap_to_events(self, evts, cfg):
        return self._apply_filter_to_events(
            evts, cfg, "kill_mod_trois_tap",
            self._trois_tap_filter, "🎯🎲 TROIS TAP → TROIS TAP")

    def _tab_tags(self, parent):
        p = self._make_tab_scroll(parent)

        sec = Sec(p, "🏷 TAGS  —  click to select/deselect")
        sec.pack(fill="x", pady=(0, 10))

        self._tags_active = set()   # IDs of currently selected tags

        self._tags_list_frame = tk.Frame(sec, bg=BG2)
        self._tags_list_frame.pack(fill="x", pady=(6, 0))

        btn_top = tk.Frame(sec, bg=BG2)
        btn_top.pack(fill="x", pady=(8, 0))
        tk.Button(btn_top, text="  + New tag  ", font=FONT_SM, bg=ORANGE, fg="white",
                  relief="flat", bd=0, cursor="hand2", activebackground=ORANGE2,
                  command=lambda: self._create_new_tag_dialog(from_combo=False)).pack(
            side="left", ipady=4, ipadx=6)
        tk.Button(btn_top, text="  Reload  ", font=FONT_SM, bg=BG3, fg=MUTED, relief="flat",
                  bd=0, cursor="hand2", command=self._connect_and_load).pack(
            side="left", padx=(8, 0), ipady=4, ipadx=6)
        tk.Button(btn_top, text="Deselect all", font=FONT_DESC, bg=BG3, fg=MUTED,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._tags_deselect_all).pack(side="right")

        self._tag_sel_lbl = tk.Label(sec, text="No tag selected", font=FONT_DESC,
                                     fg=MUTED, bg=BG2, anchor="w")
        self._tag_sel_lbl.pack(fill="x", pady=(6, 0))

        # Auto-tag on export: uses the active selection (multi-tag supported)
        auto_row = tk.Frame(sec, bg=BG2)
        auto_row.pack(fill="x", pady=(4, 0))
        self._tag_auto_var = tk.BooleanVar(
            value=self.v["tag_enabled"].get())
        _auto_cb = hchk(auto_row, "Auto-tag on export", self._tag_auto_var)
        _auto_cb.pack(side="left")
        add_tip(_auto_cb,
                "If checked, each successfully exported demo is automatically "
                "the tags selected above.\n"
                "Supports multiple tags simultaneously.")
        self._tag_auto_lbl = tk.Label(auto_row, text="(no tag selected)",
                                      font=FONT_DESC, fg=MUTED, bg=BG2)
        self._tag_auto_lbl.pack(side="left", padx=(8, 0))

        def _on_tag_auto_toggle(*_):
            self.v["tag_enabled"].set(self._tag_auto_var.get())
            # tag_on_export = first active tag (batch compat) ; others are in _tags_active
            active_names = self._get_active_tag_names()
            self.v["tag_on_export"].set(active_names[0] if active_names else "")
        self._tag_auto_var.trace_add("write", _on_tag_auto_toggle)

        # ── TAG DATE RANGE ──────────────────────────────
        sec_plage = Sec(p, "📅 TAG RANGE")
        sec_plage.pack(fill="x", pady=(0, 6))
        desc_label(sec_plage,
                   "Calculates the first and last demo with the selected tags, "
                   "and suggests applying these dates as a filter in Capture.").pack(fill="x")

        plage_btn_row = tk.Frame(sec_plage, bg=BG2)
        plage_btn_row.pack(fill="x", pady=(6, 0))
        tk.Button(plage_btn_row, text="📅 Calculate range",
                  font=FONT_SM, bg=BLUE, fg="#000000", relief="flat", bd=0,
                  cursor="hand2", activebackground="#7db8f0",
                  command=self._tag_calc_range).pack(side="left", ipady=4, ipadx=8)

        # Range result — displayed dynamically
        plage_result = tk.Frame(sec_plage, bg=BG2)
        plage_result.pack(fill="x", pady=(6, 0))

        self._plage_lbl = tk.Label(plage_result, text="", font=FONT_SM, fg=MUTED, bg=BG2, anchor="w")
        self._plage_lbl.pack(fill="x")

        plage_actions = tk.Frame(sec_plage, bg=BG2)
        plage_actions.pack(fill="x", pady=(4, 0))

        self._plage_btn_start = tk.Button(plage_actions, text="→ Apply start",
                  font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat", bd=0,
                  cursor="hand2", activebackground=BORDER, activeforeground=ORANGE,
                  state="disabled", command=self._tag_apply_range_start)
        self._plage_btn_start.pack(side="left", ipady=3, ipadx=6)
        add_tip(self._plage_btn_start, "Sets date_from to the date of the first tagged demo.")

        self._plage_btn_end = tk.Button(plage_actions, text="→ Apply end",
                  font=FONT_DESC, bg=BG3, fg=TEXT, relief="flat", bd=0,
                  cursor="hand2", activebackground=BORDER, activeforeground=ORANGE,
                  state="disabled", command=self._tag_apply_range_end)
        self._plage_btn_end.pack(side="left", padx=(6, 0), ipady=3, ipadx=6)
        add_tip(self._plage_btn_end, "Sets date_to to the date of the last tagged demo.")

        self._plage_btn_full = tk.Button(plage_actions, text="→ Apply full range",
                  font=FONT_DESC, bg=BG3, fg=GREEN, relief="flat", bd=0,
                  cursor="hand2", activebackground=BORDER, activeforeground=GREEN,
                  state="disabled", command=self._tag_apply_range_full)
        self._plage_btn_full.pack(side="left", padx=(6, 0), ipady=3, ipadx=6)
        add_tip(self._plage_btn_full, "Sets date_from and date_to to cover exactly the range of tagged demos.")

        self._plage_btn_after = tk.Button(plage_actions, text="→ After range",
                  font=FONT_DESC, bg=BG3, fg=BLUE, relief="flat", bd=0,
                  cursor="hand2", activebackground=BORDER, activeforeground=BLUE,
                  state="disabled", command=self._tag_apply_range_after)
        self._plage_btn_after.pack(side="left", padx=(6, 0), ipady=3, ipadx=6)
        add_tip(self._plage_btn_after,
                "Sets date_from to the day after the last tagged demo and clears date_to.\n"
                "Use: run preview after to see remaining demos to tag.")

        # Store computed dates
        self._plage_date_start = ""   # DD-MM-YYYY
        self._plage_date_end   = ""   # DD-MM-YYYY

        # ── OPERATIONS ──────────────────────────────────
        sec2 = Sec(p, "OPERATIONS")
        sec2.pack(fill="x", pady=(0, 6))

        row1 = tk.Frame(sec2, bg=BG2)
        row1.pack(fill="x", pady=(4, 0))
        mlabel(row1, "Search:").pack(side="left")
        tk.Button(row1, text="🔍 By tag",
                  font=FONT_SM, bg=ORANGE, fg="white", relief="flat", bd=0,
                  cursor="hand2", activebackground=ORANGE2,
                  command=self._tag_search_by_tag).pack(side="left", padx=(8, 0), ipady=4, ipadx=8)
        add_tip(row1.winfo_children()[-1], "All demos with the selected tags in DB, without config filter.")
        tk.Button(row1, text="🔍 By config",
                  font=FONT_SM, bg=BLUE, fg="#000000", relief="flat", bd=0,
                  cursor="hand2", activebackground="#7db8f0",
                  command=self._tag_search_demos).pack(side="left", padx=(6, 0), ipady=4, ipadx=8)
        add_tip(row1.winfo_children()[-1],
                "Demos matching the config (player+events+weapons+dates) AND already tagged.\n"
                "Useful to verify what is tagged in the current period.")

        row2 = tk.Frame(sec2, bg=BG2)
        row2.pack(fill="x", pady=(6, 0))
        mlabel(row2, "Actions :").pack(side="left")
        tk.Button(row2, text="🏷 Tag sel.", font=FONT_SM, bg=GREEN,
                  fg="#000000", relief="flat", bd=0, cursor="hand2", activebackground="#6ee7b7",
                  command=self._tag_apply_selected).pack(side="left", padx=(8, 0), ipady=4, ipadx=6)
        tk.Button(row2, text="Tag ALL", font=FONT_SM, bg=ORANGE2, fg="white",
                  relief="flat", bd=0, cursor="hand2", activebackground=ORANGE,
                  command=self._tag_apply_all).pack(side="left", padx=(6, 0), ipady=4, ipadx=6)
        tk.Button(row2, text="✕ Remove sel.", font=FONT_SM, bg=RED, fg="white",
                  relief="flat", bd=0, cursor="hand2", activebackground="#fca5a5",
                  command=self._tag_remove_selected).pack(side="left", padx=(6, 0), ipady=4, ipadx=6)

        # List of found demos
        lf = tk.Frame(sec2, bg=BG2)
        lf.pack(fill="x", pady=(6, 0))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self._tag_demo_lb = tk.Listbox(lf, font=FONT_SM, bg=BG3, fg=TEXT,
                                        selectbackground=ORANGE, selectforeground="white",
                                        activestyle="none", relief="flat", bd=0,
                                        highlightthickness=1, highlightbackground=BORDER,
                                        height=7, exportselection=False, selectmode="extended")
        self._tag_demo_lb.grid(row=0, column=0, sticky="nsew")
        dsb = ttk.Scrollbar(lf, orient="vertical", command=self._tag_demo_lb.yview)
        dsb.grid(row=0, column=1, sticky="ns")
        self._tag_demo_lb.configure(yscrollcommand=dsb.set)
        self._tag_found_demos = []

        self._tag_search_status = tk.Label(sec2, text="", font=FONT_DESC, fg=MUTED, bg=BG2,
                                           anchor="w", wraplength=400)
        self._tag_search_status.pack(fill="x", pady=(4, 0))

    def _tags_deselect_all(self):
        self._tags_active.clear()
        self._refresh_tags_list_display()

    def _tag_toggle(self, tag_id):
        if tag_id in self._tags_active:
            self._tags_active.discard(tag_id)
        else:
            self._tags_active.add(tag_id)
        self._refresh_tags_list_display()

    def _get_active_tag_names(self):
        return [tn for tid, tn, _ in self._tags_list if tid in self._tags_active]

    def _tag_search_by_tag(self):
        active_ids = list(self._tags_active)
        if not active_ids:
            self._alog("Tags: select at least one tag.", "err")
            return
        ts = self._tags_schema
        jt = ts.get("junction_table")
        jt_tag = ts.get("jt_tag_col")
        jt_match = ts.get("jt_match_col")
        mkm = self._find_col("matches", ["checksum", "id", "match_id"])
        dc = self._find_col("matches", ["demo_path", "demo_file_path", "demo_filepath",
                                         "share_code", "file_path", "path"])
        if not jt or not dc or not mkm:
            self._alog("Tags: insufficient DB schema.", "err")
            return

        self._tag_demo_lb.delete(0, "end")
        self._tag_found_demos = []

        def task():
            try:
                conn = self._pg_fresh()
                with conn.cursor() as cur:
                    ph = ",".join(["%s"] * len(active_ids))
                    cur.execute(
                        f'SELECT DISTINCT m."{dc}", m."{mkm}" '
                        f'FROM "{jt}" ct JOIN matches m ON m."{mkm}"=ct."{jt_match}" '
                        f'WHERE ct."{jt_tag}" IN ({ph}) ORDER BY m."{dc}"',
                        active_ids)
                    rows = cur.fetchall()
                conn.close()
            except Exception as e:
                self.after(0, lambda err=e: (self._alog(f"Tags error: {err}", "err"),
                                         self._tag_search_status.config(text="Error", fg=RED)))
                return

            found = [(str(r[0]), 0, 0) for r in rows]
            # Peupler le cache checksums
            for r in rows:
                dp, chk = str(r[0]), r[1]
                if chk and dp not in self._demo_checksums:
                    self._demo_checksums[dp] = chk

            def show():
                self._tag_found_demos = found
                self._tag_demo_lb.delete(0, "end")
                if not found:
                    self._alog("Tags: no demo found.", "warn")
                    self._tag_search_status.config(text="No demos.", fg=YELLOW)
                    return
                for dp, _, _ in found:
                    self._tag_demo_lb.insert("end", Path(dp).name)
                tag_names = ", ".join(self._get_active_tag_names())
                self._alog(f"[TAGS/tag] {len(found)} demo(s) — {tag_names}", "ok")
                self._tag_search_status.config(text=f"✓ {len(found)} demo(s)", fg=GREEN)
            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _refresh_tags_list_display(self):
        for w in self._tags_list_frame.winfo_children():
            w.destroy()
        if not self._tags_list:
            tk.Label(self._tags_list_frame, text="No tags.", font=FONT_SM, fg=MUTED,
                     bg=BG2).pack(anchor="w")
        else:
            for tid, tname, tcolor in self._tags_list:
                active = tid in self._tags_active
                bg_c = tcolor if tcolor and re.match(r'^#[0-9a-fA-F]{6}$', tcolor) else "#555555"
                row = tk.Frame(self._tags_list_frame,
                               bg=bg_c if active else BG2,
                               highlightthickness=1,
                               highlightbackground=bg_c if active else BORDER)
                row.pack(fill="x", pady=2, ipadx=2, ipady=1)

                prefix = "✓  " if active else "○  "
                fg_c = _contrast_fg(bg_c) if active else TEXT

                # Colored square — filled when active, border-only when inactive
                swatch_frame = tk.Frame(row,
                                        bg=bg_c if active else BG2,
                                        width=14, height=14,
                                        highlightthickness=2,
                                        highlightbackground=bg_c)
                swatch_frame.pack(side="left", padx=(6, 2), pady=4)
                swatch_frame.pack_propagate(False)
                tk.Label(swatch_frame, bg=bg_c if active else BG2).pack(fill="both", expand=True)

                tk.Button(
                    row,
                    text=f"{prefix}{tname}",
                    font=("Consolas", 9, "bold" if active else "normal"),
                    bg=bg_c if active else BG3,
                    fg=fg_c if active else TEXT,
                    relief="flat", cursor="hand2", bd=0, anchor="w",
                    activebackground=bg_c, activeforeground=_contrast_fg(bg_c),
                    command=lambda i=tid: self._tag_toggle(i)
                ).pack(side="left", fill="x", expand=True, ipady=4, ipadx=8)
                tk.Label(row, text=f"id:{tid}", font=FONT_DESC, fg=MUTED if not active else fg_c,
                         bg=bg_c if active else BG2).pack(side="left", padx=(4, 0))
                tk.Button(
                    row, text="✕", font=FONT_DESC,
                    bg=bg_c if active else BG3, fg=RED if not active else fg_c,
                    relief="flat", bd=0, cursor="hand2",
                    command=lambda i=tid, n=tname: self._delete_tag_ui(i, n)
                ).pack(side="right", padx=(4, 2))

        # Update the selection label and auto-tag
        active_names = self._get_active_tag_names()
        if hasattr(self, '_tag_sel_lbl'):
            if active_names:
                self._tag_sel_lbl.config(
                    text=f"Selected: {', '.join(active_names)}",
                    fg=ORANGE)
            else:
                self._tag_sel_lbl.config(text="No tag selected", fg=MUTED)
        # Sync auto tag : tag_on_export = first active tag, tag_enabled = checkbox
        if hasattr(self, '_tag_auto_lbl'):
            if active_names:
                self._tag_auto_lbl.config(
                    text=f"→ {', '.join(active_names)}", fg=ORANGE)
                # Update tag_on_export with the first active tag
                self.v["tag_on_export"].set(active_names[0])
            else:
                self._tag_auto_lbl.config(text="(no tag selected)", fg=MUTED)
                self.v["tag_on_export"].set("")

    def _tag_search_demos(self):
        """Find demos matching config (player+events+weapons+dates)
        that already have the selected tags in the DB."""
        active_ids = list(self._tags_active)
        active_names = self._get_active_tag_names()
        if not active_ids:
            self._alog("[TAGS/config] Select at least one tag.", "err")
            return
        if not self.player_search.get_steam_ids():
            self._alog("[TAGS/config] Select at least one player account in Capture.", "err")
            return
        if not any(v.get() for v in self.sel_events.values()) and not self.v["clutch_enabled"].get():
            self._alog("[TAGS/config] Select at least one event or enable Clutch.", "err")
            return

        ts = self._tags_schema
        jt       = ts.get("junction_table")
        jt_tag   = ts.get("jt_tag_col")
        jt_match = ts.get("jt_match_col")
        mkm_col  = self._find_col("matches", ["checksum", "id", "match_id"])
        if not jt or not jt_tag or not jt_match or not mkm_col:
            self._alog("[TAGS/config] Insufficient DB schema.", "err")
            return

        self._tag_demo_lb.delete(0, "end")
        self._tag_found_demos = []
        self._demo_checksums = {}
        cfg = self._build_run_cfg()

        def task():
            # 1. Fetch checksums already tagged with the selected tags
            try:
                conn = self._pg_fresh()
                with conn.cursor() as cur:
                    ph = ",".join(["%s"] * len(active_ids))
                    cur.execute(
                        f'SELECT DISTINCT "{jt_match}" FROM "{jt}" WHERE "{jt_tag}" IN ({ph})',
                        active_ids)
                    tagged_checksums = {r[0] for r in cur.fetchall()}
                conn.close()
            except Exception as e:
                self.after(0, lambda err=e: (
                    self._alog(f"[TAGS/config] DB error: {err}", "err"),
                    self._tag_search_status.config(text="Error", fg=RED)))
                return

            # 2. Config query (player+events+weapons+dates)
            try:
                evts = self._query_events(cfg)
            except Exception as e:
                self.after(0, lambda err=e: (
                    self._alog(f"[TAGS/config] Config error: {err}", "err"),
                    self._tag_search_status.config(text="Error", fg=RED)))
                return

            # 3. Intersection: keep only already-tagged demos
            found = []
            for dp in sorted(evts.keys(), key=self._demo_sort_key):
                chk = self._demo_checksums.get(dp) or self._get_demo_checksum(dp)
                if chk and chk in tagged_checksums:
                    ne = len(evts[dp])
                    seqs = self._build_sequences(evts[dp], cfg["tickrate"],
                                                 cfg["before"], cfg["after"])
                    found.append((dp, ne, len(seqs)))

            def show():
                self._tag_found_demos = found
                self._tag_demo_lb.delete(0, "end")
                _tag_names_str = ', '.join(active_names)
                _date_str = f"{cfg.get('date_from','∞')} → {cfg.get('date_to','∞')}"
                if not found:
                    self._alog(
                        f"[TAGS/config] No demo — tags: {_tag_names_str} — {_date_str}",
                        "warn")
                    self._tag_search_status.config(text="No demos.", fg=YELLOW)
                    return
                total_evt = sum(ne for _, ne, _ in found)
                total_seq = sum(ns for _, _, ns in found)
                for dp, ne, ns in found:
                    self._tag_demo_lb.insert("end", f"{Path(dp).name}  ({ne} events → {ns} seq)")
                self._alog(
                    f"[TAGS/config] {len(found)} demo(s) already tagged, {total_evt} events"
                    f" — tags: {_tag_names_str} — {_date_str}",
                    "ok")
                self._tag_search_status.config(text=f"✓ {len(found)} demo(s)", fg=GREEN)
            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _tag_calc_range(self):
        """Compute the date range of demos with selected tags (no config filter).
        Shows the range and enables the apply buttons."""
        active_ids = list(self._tags_active)
        active_names = self._get_active_tag_names()
        if not active_ids:
            self._alog("[TAGS/range] Select at least one tag.", "err")
            return
        ts = self._tags_schema
        jt      = ts.get("junction_table")
        jt_tag  = ts.get("jt_tag_col")
        jt_match= ts.get("jt_match_col")
        mkm     = self._find_col("matches", ["checksum", "id", "match_id"])
        dc      = self._find_col("matches", ["demo_path", "demo_file_path", "demo_filepath",
                                              "share_code", "file_path", "path"])
        if not jt or not jt_tag or not jt_match or not mkm or not dc:
            self._alog("[TAGS/range] Insufficient DB schema.", "err")
            return

        self._plage_lbl.config(text="Computing…", fg=YELLOW)
        for btn in (self._plage_btn_start, self._plage_btn_end,
                    self._plage_btn_full, self._plage_btn_after):
            btn.config(state="disabled")

        def task():
            try:
                conn = self._pg_fresh()
                with conn.cursor() as cur:
                    ph = ",".join(["%s"] * len(active_ids))
                    cur.execute(
                        f'SELECT DISTINCT m."{dc}", m."{mkm}" '
                        f'FROM "{jt}" ct JOIN matches m ON m."{mkm}"=ct."{jt_match}" '
                        f'WHERE ct."{jt_tag}" IN ({ph})',
                        active_ids)
                    rows = cur.fetchall()
                conn.close()
            except Exception as e:
                self.after(0, lambda err=e: (
                    self._alog(f"[TAGS/range] Error: {err}", "err"),
                    self._plage_lbl.config(text="DB error.", fg=RED)))
                return

            demos = [str(r[0]) for r in rows]
            for r in rows:
                dp_r, chk = str(r[0]), r[1]
                if chk and dp_r not in self._demo_checksums:
                    self._demo_checksums[dp_r] = chk

            if not demos:
                self.after(0, lambda: (
                    self._alog(f"[TAGS/range] No demos with these tags.", "warn"),
                    self._plage_lbl.config(text="No tagged demos.", fg=YELLOW)))
                return

            sorted_demos = sorted(demos, key=self._demo_sort_key)
            first_demo = sorted_demos[0]
            last_demo  = sorted_demos[-1]

            def _demo_to_date_str(dp):
                ts = self._get_demo_ts(dp)
                if ts is None:
                    sk = self._demo_sort_key(dp)
                    ts = sk[1] if sk[0] == 0 else None
                if ts is None:
                    return None
                try:
                    return datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
                except Exception:
                    return None

            date_start = _demo_to_date_str(first_demo)
            date_end   = _demo_to_date_str(last_demo)

            def _to_next_day(dstr):
                try:
                    return (datetime.strptime(dstr, "%d-%m-%Y") + timedelta(days=1)).strftime("%d-%m-%Y")
                except Exception:
                    return dstr

            date_after = _to_next_day(date_end) if date_end else None

            def show():
                _names_str = ", ".join(active_names)
                self._plage_date_start = date_start or ""
                self._plage_date_end   = date_end   or ""
                if date_start and date_end:
                    self._plage_lbl.config(
                        text=f"{len(demos)} demo(s) — \"{_names_str}\"  |  "
                             f"Start: {date_start}   End: {date_end}   After: {date_after}",
                        fg=GREEN)
                    for btn in (self._plage_btn_start, self._plage_btn_end,
                                self._plage_btn_full, self._plage_btn_after):
                        btn.config(state="normal")
                    self._alog(
                        f"[TAGS/range] {len(demos)} demo(s) \"{_names_str}\" — "
                        f"start: {date_start}  end: {date_end}  after: {date_after}",
                        "ok")
                else:
                    self._plage_lbl.config(
                        text=f"{len(demos)} demo(s) — dates unavailable (.dem files missing?)",
                        fg=YELLOW)
                    self._alog(f"[TAGS/range] {len(demos)} demo(s) — dates undetermined.", "warn")
            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _tag_apply_range_start(self):
        if self._plage_date_start:
            self.v["date_from"].set(self._plage_date_start)
            self._alog(f"[TAGS/range] date_from → {self._plage_date_start}", "ok")

    def _tag_apply_range_end(self):
        if self._plage_date_end:
            self.v["date_to"].set(self._plage_date_end)
            self._alog(f"[TAGS/range] date_to → {self._plage_date_end}", "ok")

    def _tag_apply_range_full(self):
        if self._plage_date_start and self._plage_date_end:
            self.v["date_from"].set(self._plage_date_start)
            self.v["date_to"].set(self._plage_date_end)
            self._alog(f"[TAGS/range] Full range: {self._plage_date_start} → {self._plage_date_end}", "ok")

    def _tag_apply_range_after(self):
        if self._plage_date_end:
            try:
                after = (datetime.strptime(self._plage_date_end, "%d-%m-%Y") + timedelta(days=1)).strftime("%d-%m-%Y")
            except Exception:
                after = self._plage_date_end
            self.v["date_from"].set(after)
            self.v["date_to"].set("")
            self._alog(f"[TAGS/range] After range: date_from → {after}, date_to cleared", "ok")

    def _tag_search_last_tagged(self):
        """Same intersection as By config (config ∩ DB tags),
        finds the most recent demo and applies date_from to the next day."""
        active_ids = list(self._tags_active)
        active_names = self._get_active_tag_names()
        if not active_ids:
            self._alog("Tags 📅: select at least one tag.", "err")
            return
        if not self.player_search.get_steam_ids():
            self._alog("Tags 📅: select at least one player account in Capture.", "err")
            return

        ts = self._tags_schema
        jt       = ts.get("junction_table")
        jt_tag   = ts.get("jt_tag_col")
        jt_match = ts.get("jt_match_col")
        mkm_col  = self._find_col("matches", ["checksum", "id", "match_id"])
        if not jt or not jt_tag or not jt_match or not mkm_col:
            self._alog("Tags 📅: insufficient DB schema.", "err")
            return

        cfg = self._build_run_cfg()

        def task():
            # 1. Checksums tagged in DB
            try:
                conn = self._pg_fresh()
                with conn.cursor() as cur:
                    ph = ",".join(["%s"] * len(active_ids))
                    cur.execute(
                        f'SELECT DISTINCT "{jt_match}" FROM "{jt}" WHERE "{jt_tag}" IN ({ph})',
                        active_ids)
                    tagged_checksums = {r[0] for r in cur.fetchall()}
                conn.close()
            except Exception as e:
                self.after(0, lambda err=e: self._alog(f"Tags 📅 DB error: {err}", "err"))
                return

            # 2. Demos matching config
            try:
                evts = self._query_events(cfg)
            except Exception as e:
                self.after(0, lambda err=e: self._alog(f"Tags 📅 config error: {err}", "err"))
                return

            # 3. Intersection: config demos ∩ tagged
            matched = []
            for dp in evts:
                chk = self._demo_checksums.get(dp) or self._get_demo_checksum(dp)
                if chk and chk in tagged_checksums:
                    matched.append(dp)

            if not matched:
                _names_str = ", ".join(active_names)
                self.after(0, lambda: (
                    self._alog(f"[TAGS/📅] No tagged demo in current config \"{_names_str}\".", "warn"),
                    self._tag_search_status.config(text="No tagged demos.", fg=YELLOW)))
                return

            # 4. Find the most recent
            matched_sorted = sorted(matched, key=self._demo_sort_key)
            last_demo = matched_sorted[-1]
            last_ts = self._get_demo_ts(last_demo)
            if last_ts is None:
                sk = self._demo_sort_key(last_demo)
                last_ts = sk[1] if sk[0] == 0 else None

            suggest_date = None
            if last_ts:
                try:
                    suggest_date = (datetime.fromtimestamp(last_ts) + timedelta(days=1)).strftime("%d-%m-%Y")
                except Exception:
                    pass

            def show(matched=matched_sorted, last_demo=last_demo, suggest_date=suggest_date):
                _names_str = ", ".join(active_names)
                _last_date = self._format_demo_date(last_demo)
                if suggest_date:
                    self.v["date_from"].set(suggest_date)
                    self._alog(
                        f"[TAGS/📅] {len(matched)} demo(s) tagged in config"
                        f" — latest: {_last_date} — date_from → {suggest_date}",
                        "ok")
                    self._tag_search_status.config(
                        text=f"✓ {len(matched)} demo(s) — date_from → {suggest_date}", fg=GREEN)
                else:
                    self._alog(
                        f"[TAGS/📅] {len(matched)} demo(s) — most recent date undetermined.",
                        "warn")
                    self._tag_search_status.config(text=f"✓ {len(matched)} demo(s)", fg=YELLOW)

            self.after(0, show)

        threading.Thread(target=task, daemon=True).start()

    def _tag_apply_selected(self):
        names = self._get_active_tag_names()
        if not names:
            self._alog("Tags: select at least one tag.", "err")
            return
        sel = self._tag_demo_lb.curselection()
        if not sel:
            self._alog("Tags: select demos from the list.", "err")
            return
        demos = [self._tag_found_demos[i][0] for i in sel if i < len(self._tag_found_demos)]
        for name in names:
            self._do_tag_demos(demos, name)

    def _tag_apply_all(self):
        names = self._get_active_tag_names()
        if not names:
            self._alog("Tags: select at least one tag.", "err")
            return
        if not self._tag_found_demos:
            self._alog("Tags: run a search first.", "err")
            return
        demos = [dp for dp, _, _ in self._tag_found_demos]
        for name in names:
            self._do_tag_demos(demos, name)

    def _tag_remove_selected(self):
        names = self._get_active_tag_names()
        if not names:
            self._alog("Tags: select at least one tag.", "err")
            return
        sel = self._tag_demo_lb.curselection()
        if not sel:
            self._alog("Tags: select demos.", "err")
            return
        demos = [self._tag_found_demos[i][0] for i in sel if i < len(self._tag_found_demos)]
        if not demos:
            return


        def task():
            ok_count, err_first = 0, ""
            for dp in demos:
                for name in names:
                    success, err = self._untag_demo(dp, name)
                    if success:
                        ok_count += 1
                    elif not err_first:
                        err_first = err

            def finish():
                total = len(demos) * len(names)
                if ok_count == total:
                    self._alog(f"Tags ✓ tag(s) removed from {len(demos)} demo(s).", "ok")
                    self._tag_search_status.config(text=f"✓ removed from {len(demos)}", fg=GREEN)
                elif ok_count > 0:
                    self._alog(f"Tags ⚠ {ok_count}/{total} OK — {err_first}", "warn")
                    self._tag_search_status.config(text=f"⚠ {ok_count}/{total}", fg=YELLOW)
                else:
                    self._alog(f"Tags ✗ failed: {err_first}", "err")
                    self._tag_search_status.config(text="✗ failed", fg=RED)
            self.after(0, finish)

        threading.Thread(target=task, daemon=True).start()

    def _delete_tag_ui(self, tag_id, tag_name):
        if not messagebox.askyesno("Delete tag", f"Delete '{tag_name}' and all its links?"):
            return
        ok, err = self._delete_tag_from_db(tag_id, tag_name)
        if ok:
            self._refresh_tag_combo()
            self._refresh_tags_list_display()
            self._log(f"Tag '{tag_name}' supprime.", "ok")
        else:
            messagebox.showerror("Tags", f"Error: {err}")

    # ── TAB TOOLS ──
    # ── Theme application ──────────────────────────────────────────────────

    def _change_theme(self, bg_name: str | None = None, accent: str | None = None):
        """Change theme at runtime. Pass None to keep the current value.

        Saves to config, updates globals, and re-paints every widget.
        """
        old = _THEME.copy()
        current_bg     = self.v["theme_bg"].get()
        current_accent = self.v["theme_accent"].get()
        new_bg     = bg_name if bg_name is not None else current_bg
        new_accent = accent  if accent  is not None else current_accent
        self.v["theme_bg"].set(new_bg)
        self.v["theme_accent"].set(new_accent)
        _apply_theme_globals(new_bg, new_accent)
        new = _THEME.copy()

        # Build the set of accent-button widget ids to exclude from the generic walker.
        # Each accent button has a fixed fg (its own colour) that must never be remapped.
        try:
            _ac_exclude = frozenset(id(btn) for btn, _ in self._ac_btn_refs)
        except Exception:
            _ac_exclude = frozenset()

        self._apply_theme_to_widgets(self, old, new, exclude_ids=_ac_exclude)
        self._reapply_ttk_styles()

        # Accent preset buttons: update only bg/activebackground, preserve fg
        try:
            for btn, fixed_fg in self._ac_btn_refs:
                btn.configure(bg=new["BG3"], activebackground=new["BORDER"])
        except Exception:
            pass

        # Retrigger hchk/hradio closures so they pick up the new _t() colours
        self._retrigger_toggle_vars()

        self._auto_save()

    def _reapply_ttk_styles(self):
        """Reapply ttk styles with current theme colours."""
        s = ttk.Style()
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=MUTED,
                    font=("Consolas", 9, "bold"), padding=[12, 7], borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", BG2)],
              foreground=[("selected", ORANGE)])
        s.configure("TCombobox",
                    fieldbackground=BG3, background=BG3, foreground=TEXT,
                    arrowcolor=ORANGE, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER,
                    selectbackground=ORANGE, selectforeground="white")
        s.map("TCombobox",
              fieldbackground=[("readonly", BG3), ("disabled", BG)],
              foreground=[("readonly", TEXT), ("disabled", MUTED)],
              background=[("readonly", BG3)],
              arrowcolor=[("readonly", ORANGE)])
        s.configure("TPanedwindow", background=BORDER)
        s.configure("Vertical.TPanedwindow", background=BORDER)
        s.configure("DemoPicker.Treeview",
                    background=BG3, fieldbackground=BG3,
                    foreground=TEXT, rowheight=18, font=FONT_SM)
        s.configure("DemoPicker.Treeview.Heading",
                    background=BG2, foreground=MUTED,
                    font=FONT_DESC, relief="flat")
        s.map("DemoPicker.Treeview",
              background=[("selected", BORDER)],
              foreground=[("selected", ORANGE)])
        # Re-configure log tags
        try:
            for tag, c in [("ok", GREEN), ("err", RED), ("info", ORANGE),
                            ("dim", MUTED), ("warn", YELLOW), ("blue", BLUE)]:
                self.log.tag_configure(tag, foreground=c)
            self.log.tag_configure("search_hi",  background=ORANGE2, foreground="white")
            self.log.tag_configure("search_cur", background=ORANGE,  foreground="white")
            self.log.tag_configure("badge_kill",   foreground=RED)
            self.log.tag_configure("badge_warn",   foreground=YELLOW)
            self.log.tag_configure("badge_safe",   foreground=GREEN)
            self.log.tag_configure("badge_filter", foreground=BLUE)
            self.log.configure(bg=_THEME["LOG_BG"], fg=TEXT,
                               insertbackground=ORANGE, selectbackground=ORANGE2)
        except Exception:
            pass
        try:
            self._demo_tree.tag_configure("ok",  foreground=TEXT)
            self._demo_tree.tag_configure("off", foreground=MUTED)
        except Exception:
            pass

    @staticmethod
    def _apply_theme_to_widgets(root, old: dict, new: dict,
                                exclude_ids: frozenset = frozenset()):
        """Recursively walk all tk widgets and swap old theme colours for new ones.

        Checks every configurable colour property against every value in old{} and
        replaces it with the corresponding new{} value.  Works for Label, Frame,
        Button, Checkbutton, Radiobutton, Entry, Text, Scale, Scrollbar, etc.

        exclude_ids — frozenset of id(widget) to skip entirely (e.g. accent preset
                      buttons whose fg must stay fixed at their own colour).

        The mapping is colour-value based (old hex → new hex) so it is fully
        DRY — no widget-type-specific code, no per-widget references needed.
        """
        # Build bidirectional mapping: old_hex → new_hex
        # Only map colours that actually changed to avoid unnecessary writes
        colour_map: dict = {}
        for key in old:
            ov, nv = old[key].lower(), new[key].lower()
            if ov != nv:
                colour_map[ov] = nv

        if not colour_map:
            return  # Theme didn't change

        # Also include LOG_BG which is not a named global but is used on the log widget
        old_log = old.get("LOG_BG", "").lower()
        new_log = new.get("LOG_BG", "").lower()
        if old_log and new_log and old_log != new_log:
            colour_map[old_log] = new_log

        # Widget config keys to check — listed once, used for every widget
        _COLOUR_PROPS = (
            "bg", "fg", "background", "foreground",
            "activebackground", "activeforeground",
            "selectcolor", "selectbackground", "selectforeground",
            "highlightbackground", "highlightcolor",
            "insertbackground", "disabledforeground",
            "troughcolor", "readonlybackground",
        )

        def _walk(widget):
            if id(widget) in exclude_ids:
                return  # skip — fixed-colour widget (e.g. accent preset buttons)
            try:
                for prop in _COLOUR_PROPS:
                    try:
                        cur = widget.cget(prop)
                        if isinstance(cur, str):
                            mapped = colour_map.get(cur.lower())
                            if mapped:
                                widget.configure(**{prop: mapped})
                    except (tk.TclError, Exception):
                        pass
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    _walk(child)
            except Exception:
                pass

        _walk(root)

    def _tab_outils(self, parent):
        p = self._make_tab_scroll(parent)

        sec = Sec(p, "PATHS")
        sec.pack(fill="x", pady=(0, 10))
        PathField(sec, "CSDM Executable", "csdm.CMD or csdm.exe",
                  self.v["csdm_exe"], "file").pack(fill="x", pady=4)
        _pf_cfg = PathField(sec, "CS2 cfg folder",
                  r"Optional override (…\Counter-Strike Global Offensive\game\csgo\cfg)",
                  self.v["cs2_cfg_dir"], "dir")
        _pf_cfg.pack(fill="x", pady=4)
        add_tip(_pf_cfg, "Optional manual override for CS2 cfg directory.\n"
                         "Used by CS mode to inject csdm_batch_runtime.cfg and autoexec block.\n"
                         "Leave empty to use automatic Steam library detection.")
        _pf_clips = PathField(sec, "Raw clips folder",
                  "A subfolder per demo is created here",
                  self.v["output_dir_clips"], "dir")
        _pf_clips.pack(fill="x", pady=4)
        add_tip(_pf_clips, "Root folder where CSDM places raw clips.\n"
                           "A subfolder named after the demo is created there if the option is active.")
        _pf_concat = PathField(sec, "Concatenated clips folder",
                  "Empty = same folder as raw clips",
                  self.v["output_dir_concat"], "dir")
        _pf_concat.pack(fill="x", pady=4)
        add_tip(_pf_concat, "Folder where concatenated clips per demo are placed.\n"
                            "Leave empty to use the same folder as raw clips.")
        _pf_asm = PathField(sec, "Assembled file folder",
                  "Empty = same folder as raw clips",
                  self.v["output_dir_assembled"], "dir")
        _pf_asm.pack(fill="x", pady=4)
        add_tip(_pf_asm, "Folder where the final assembled file is placed.\n"
                         "Leave empty to use the same folder as raw clips.")
        _sub_cb = hchk(sec, "Subfolder per demo", self.v["subfolder_per_demo"])
        _sub_cb.pack(anchor="w", pady=(4, 0))
        add_tip(_sub_cb, "Creates a folder per demo in the raw clips folder.")

        sec = Sec(p, "UI THEME")
        sec.pack(fill="x", pady=(0, 12))

        # ── Background row ────────────────────────────────────────────────────
        bg_row = tk.Frame(sec, bg=BG2)
        bg_row.pack(fill="x", pady=(4, 0))
        mlabel(bg_row, "Background:").pack(side="left")
        _BG_BTN_DEFS = [
            ("dark",     "Dark",      MUTED),
            ("amoled",   "AMOLED",    TEXT),
            ("deepblue", "Deep Blue", "#7a9fda"),
            ("white",    "White",     "#555555"),
        ]
        for _bg_key, _bg_lbl, _bg_fg in _BG_BTN_DEFS:
            def _make_bg_cmd(k=_bg_key):
                return lambda: self._change_theme(k, self.v["theme_accent"].get())
            tk.Button(bg_row, text=_bg_lbl, font=FONT_SM, bg=BG3, fg=_bg_fg,
                      relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                      activebackground=BORDER, activeforeground=ORANGE,
                      command=_make_bg_cmd()).pack(side="left", padx=(8, 0), ipady=4, ipadx=8)

        # ── Accent row ────────────────────────────────────────────────────────
        ac_row = tk.Frame(sec, bg=BG2)
        ac_row.pack(fill="x", pady=(8, 0))
        mlabel(ac_row, "Accent:    ").pack(side="left")
        _AC_BTN_DEFS = [
            ("green",  "Green",  "#22c55e"),
            ("blue",   "Blue",   "#3b82f6"),
            ("orange", "Orange", "#f97316"),
            ("purple", "Purple", "#a855f7"),
            ("red",    "Red",    "#ef4444"),
            ("cyan",   "Cyan",   "#06b6d4"),
            ("pink",   "Pink",   "#ec4899"),
            ("yellow", "Yellow", "#eab308"),
        ]
        # Keep refs so _apply_theme_to_widgets skips their fg (each btn keeps its own colour)
        # and so _change_theme can update only their bg/activebackground.
        self._ac_btn_refs: list = []   # [(widget, fixed_fg_hex), ...]
        for _ac_key, _ac_lbl, _ac_col in _AC_BTN_DEFS:
            def _make_ac_cmd(k=_ac_key):
                return lambda: self._change_theme(self.v["theme_bg"].get(), k)
            _btn = tk.Button(ac_row, text=_ac_lbl, font=FONT_SM, bg=BG3, fg=_ac_col,
                             relief="flat", bd=0, cursor="hand2", highlightthickness=0,
                             activebackground=BORDER, activeforeground=_ac_col,
                             command=_make_ac_cmd())
            _btn.pack(side="left", padx=(8 if _ac_key == "green" else 4, 0), ipady=4, ipadx=8)
            self._ac_btn_refs.append((_btn, _ac_col))

        # ── Custom colour picker ───────────────────────────────────────────────
        custom_row = tk.Frame(sec, bg=BG2)
        custom_row.pack(fill="x", pady=(8, 0))
        mlabel(custom_row, "Custom:    ").pack(side="left")

        def _pick_custom_accent():
            cur = self.v["theme_accent"].get()
            init = cur if cur.startswith("#") else _ACCENT_PRESETS.get(cur, {}).get("ACCENT", "#22c55e")
            result = colorchooser.askcolor(color=init, parent=self, title="Pick accent colour")
            if result and result[1]:
                self._change_theme(self.v["theme_bg"].get(), result[1])

        tk.Button(custom_row, text="🎨 Custom colour…", font=FONT_SM,
                  bg=BG3, fg=ORANGE, relief="flat", bd=0, cursor="hand2",
                  highlightthickness=0, activebackground=BORDER, activeforeground=ORANGE,
                  command=_pick_custom_accent).pack(side="left", padx=(8, 0), ipady=4, ipadx=8)

        mlabel(custom_row, "   Current:").pack(side="left", padx=(12, 0))
        self._theme_preview_lbl = tk.Label(custom_row, text="  ██  ", font=FONT_SM,
                                            fg=ORANGE, bg=BG3, relief="flat")
        self._theme_preview_lbl.pack(side="left", padx=(4, 0))
        add_tip(self._theme_preview_lbl, "Current accent colour preview.")

        sec = Sec(p, "UI LAYOUT")
        sec.pack(fill="x", pady=(0, 12))
        row = tk.Frame(sec, bg=BG2)
        row.pack(fill="x", pady=(6, 0))
        mlabel(row, "Window").pack(side="left")
        sentry(row, self.v["ui_window_w"], width=7).pack(side="left", padx=(8, 4), ipady=4)
        tk.Label(row, text="x", font=FONT_SM, fg=MUTED, bg=BG2).pack(side="left")
        sentry(row, self.v["ui_window_h"], width=7).pack(side="left", padx=(4, 10), ipady=4)
        mlabel(row, "Split %").pack(side="left")
        sentry(row, self.v["ui_split_pct"], width=5).pack(side="left", padx=(8, 0), ipady=4)

        row2 = tk.Frame(sec, bg=BG2)
        row2.pack(fill="x", pady=(8, 0))
        tk.Button(row2, text="Apply", font=FONT_SM, bg=BG3, fg=TEXT,
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=BORDER, activeforeground=ORANGE,
                  command=self._apply_layout_vars).pack(side="left", ipady=5, ipadx=8)
        tk.Button(row2, text="Auto", font=FONT_SM, bg=BG3, fg=BLUE,
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=BORDER, activeforeground=ORANGE,
                  command=self._auto_layout).pack(side="left", padx=(6, 0), ipady=5, ipadx=8)
        tk.Button(row2, text="Reset default", font=FONT_SM, bg=BG3, fg=YELLOW,
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=BORDER, activeforeground=ORANGE,
                  command=self._reset_layout_defaults).pack(side="left", padx=(6, 0), ipady=5, ipadx=8)
        _rem = hchk(row2, "Remember current layout", self.v["ui_remember_layout"])
        _rem.pack(side="left", padx=(12, 0))
        add_tip(_rem, "When enabled, manual window resize and splitter moves are saved automatically.")

        sec = Sec(p, "POSTGRESQL CONNECTION")
        sec.pack(fill="x", pady=(0, 12))
        pg = tk.Frame(sec, bg=BG2)
        pg.pack(fill="x", pady=(6, 0))
        for i in range(5):
            pg.columnconfigure(i, weight=1)
        for col, (lbl, key, show) in enumerate([
            ("Host", "pg_host", ""), ("Port", "pg_port", ""), ("Base", "pg_db", ""),
            ("User", "pg_user", ""), ("Pass", "pg_pass", "*")
        ]):
            f = tk.Frame(pg, bg=BG2)
            f.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
            mlabel(f, lbl).pack(fill="x")
            kw = {"show": "*"} if show == "*" else {}
            sentry(f, self.v[key], **kw).pack(fill="x", ipady=5, ipadx=6, pady=(3, 0))
        br = tk.Frame(sec, bg=BG2)
        br.pack(fill="x", pady=(12, 0))
        tk.Button(br, text="  Test & Reload", font=FONT_SM, bg=ORANGE, fg="white",
                  relief="flat", cursor="hand2", bd=0, activebackground=ORANGE2,
                  command=self._connect_and_load).pack(side="left", ipady=6, ipadx=8)
        tk.Label(br, textvariable=self.db_status, font=("Consolas", 9, "bold"), bg=BG2,
                 fg=YELLOW).pack(side="left", padx=(12, 0))

        sec_perf = Sec(p, "PERFORMANCE")
        sec_perf.pack(fill="x", pady=(0, 10))

        dp2_row = tk.Frame(sec_perf, bg=BG2)
        dp2_row.pack(fill="x", pady=(6, 0))
        dp2_top = tk.Frame(dp2_row, bg=BG2)
        dp2_top.pack(fill="x")
        mlabel(dp2_top, "DP2 parse threads").pack(side="left")
        _dp2_val_lbl = tk.Label(dp2_top,
                                text=str(self.v["dp2_threads"].get()),
                                font=FONT_SM, fg=ORANGE, bg=BG2)
        _dp2_val_lbl.pack(side="right")
        tk.Scale(dp2_row, from_=1, to=8,
                 variable=self.v["dp2_threads"],
                 orient="horizontal", bg=BG2, fg=TEXT,
                 troughcolor=BG3, activebackground=ORANGE,
                 highlightthickness=0, bd=0, showvalue=False, cursor="hand2",
                 command=lambda v: _dp2_val_lbl.config(
                     text=str(int(float(v))))).pack(fill="x", pady=(2, 0))
        add_tip(dp2_row,
                "Number of parallel threads used to pre-parse demo files\n"
                "with demoparser2 (TROIS SHOT / ONE TAP / TROIS TAP filters).\n"
                "Higher = faster pre-parse on multi-core CPUs.\n"
                "Recommended: 2–4.  Set to 1 to disable parallelism.")

        sec_pre = Sec(p, "SAVE A PRESET")
        sec_pre.pack(fill="x", pady=(0, 10))

        self._preset_name_var = tk.StringVar()
        nr = tk.Frame(sec_pre, bg=BG2)
        nr.pack(fill="x", pady=(6, 0))
        mlabel(nr, "Name:").pack(side="left")
        sentry(nr, self._preset_name_var).pack(side="left", fill="x", expand=True,
                                                padx=(6, 0), ipady=4)

        self._preset_cat_var = tk.StringVar(value="full")
        mlabel(sec_pre, "Type :").pack(anchor="w", pady=(8, 2))
        for key, label in PRESET_CATEGORIES.items():
            tk.Radiobutton(sec_pre, text=label, variable=self._preset_cat_var, value=key,
                           **_CHK_KW).pack(anchor="w", padx=(8, 0), pady=1)

        tk.Button(sec_pre, text="  SAVE  ", font=FONT_SM, bg=ORANGE, fg="white",
                  relief="flat", cursor="hand2", bd=0, highlightthickness=0,
                  activebackground=ORANGE2, command=self._save_preset).pack(
            anchor="w", pady=(10, 0), ipady=6, ipadx=8)

        sec_load = Sec(p, "LOAD / DELETE")
        sec_load.pack(fill="x", pady=(0, 12))
        self._preset_list_frame = tk.Frame(sec_load, bg=BG2)
        self._preset_list_frame.pack(fill="x", pady=(6, 0))
        self._refresh_preset_list()

    def _save_preset(self):
        name = self._preset_name_var.get().strip()
        if not name:
            messagebox.showerror("Preset", "Enter a name.")
            return
        cat = self._preset_cat_var.get()
        cfg = self._collect_config()
        keys = PRESET_KEYS.get(cat)
        data = {k: cfg[k] for k in keys if k in cfg} if keys else cfg
        self.presets[name] = {"type": cat, "data": data}
        save_presets(self.presets)
        self._refresh_preset_list()
        messagebox.showinfo("Preset", f"'{name}' saved.")

    def _load_preset(self, name):
        p = self.presets.get(name)
        if not p:
            return
        self._apply_config(p["data"], keys=PRESET_KEYS.get(p.get("type", "full")))
        self._post_apply_ui()
        self._log(f"Preset '{name}' loaded.", "ok")

    def _post_apply_ui(self):
        """Sync derived widgets after _apply_config (resolution, slow-motion…)."""
        # Resolution combo: reflect current width × height
        try:
            w = self.v["width"].get()
            h = self.v["height"].get()
            self.v["resolution"].set(f"{w}x{h}")
        except Exception:
            pass
        # v60 structured selectors: infer definition + ratio from width/height
        try:
            w = self.v["width"].get()
            h = self.v["height"].get()
            # Definition
            def_lbl = next((lbl for lbl, dh in DEFINITIONS if dh == h), None)
            # Ratio
            ratio_lbl = None
            for lbl, rw, rh in ASPECT_RATIOS:
                if h > 0 and abs(w / h - rw / rh) < 0.02:
                    ratio_lbl = lbl
                    break
            if def_lbl and ratio_lbl:
                self.v["res_definition"].set(def_lbl)
                self.v["res_aspect"].set(ratio_lbl)
                self.v["res_custom"].set(False)
            else:
                self.v["res_custom"].set(True)
            self._on_res_custom_toggle()
            self._update_res_preview()
        except Exception:
            pass
        self._on_game_speed_var()

    def _delete_preset(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            self.presets.pop(name, None)
            save_presets(self.presets)
            self._refresh_preset_list()

    def _refresh_preset_list(self):
        for w in self._preset_list_frame.winfo_children():
            w.destroy()
        if not self.presets:
            tk.Label(self._preset_list_frame, text="No presets.", font=FONT_SM, fg=MUTED,
                     bg=BG2).pack(anchor="w")
            return
        for name, p in self.presets.items():
            cat = p.get("type", "full")
            row = tk.Frame(self._preset_list_frame, bg=BG2)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, font=FONT_SM, fg=TEXT, bg=BG2).pack(side="left")
            tk.Label(row, text=f"  [{cat}]", font=FONT_DESC, fg=MUTED, bg=BG2).pack(side="left")
            tk.Button(row, text="Load", font=FONT_DESC, bg=BG3, fg=GREEN, relief="flat",
                      cursor="hand2", bd=0,
                      command=lambda n=name: self._load_preset(n)).pack(side="right", padx=(4, 0))
            tk.Button(row, text="Suppr", font=FONT_DESC, bg=BG3, fg=RED, relief="flat",
                      cursor="hand2", bd=0,
                      command=lambda n=name: self._delete_preset(n)).pack(side="right")

    def _chk(self, p, text, var, **kw):
        f = tk.Frame(p, bg=BG2)
        hchk(f, text, var, **kw).pack()
        return f

    def _radio(self, p, text, var, val):
        return hradio(p, text, var, val)

    def _slider(self, p, label, var, mn, mx, row, col):
        f = tk.Frame(p, bg=BG2)
        f.grid(row=row, column=col, sticky="ew", padx=(0, 12 if col == 0 else 0), pady=4)
        top = tk.Frame(f, bg=BG2)
        top.pack(fill="x")
        mlabel(top, label).pack(side="left")
        lbl = tk.Label(top, text=f"{var.get()}s", font=FONT_SM, fg=ORANGE, bg=BG2)
        lbl.pack(side="right")
        tk.Scale(f, from_=mn, to=mx, variable=var, orient="horizontal", bg=BG2, fg=TEXT,
                 troughcolor=BG3, activebackground=ORANGE, highlightthickness=0, bd=0,
                 showvalue=False, cursor="hand2",
                 command=lambda v: lbl.config(text=f"{int(float(v))}s")).pack(fill="x", pady=(2, 0))
        return f

    def _calc_summary(self, all_events, cfg):
        """Return (nb_demos, nb_clips, total_sec, avg_sec) from events and config."""
        tickrate = cfg.get("tickrate", 64)
        before_s = self._effective_before(cfg)
        after_s = cfg.get("after", 5)
        nb_demos = len(all_events)
        nb_clips = 0
        total_ticks = 0
        for events in all_events.values():
            seqs = self._build_sequences(events, tickrate, before_s, after_s)
            nb_clips += len(seqs)
            for s in seqs:
                total_ticks += s["end_tick"] - s["start_tick"]
        total_sec = total_ticks / tickrate if tickrate else 0
        avg_sec = (total_sec / nb_clips) if nb_clips else 0
        return nb_demos, nb_clips, total_sec, avg_sec

    def _hms(self, s):
        s = int(s)
        if s < 60:   return f"{s}s"
        if s < 3600: return f"{s//60}m{s%60:02d}s"
        return f"{s//3600}h{(s%3600)//60:02d}m{s%60:02d}s"

    @staticmethod
    def _read_demo_date_from_info(demo_path):
        """
        Read the .info file next to the .dem and extract the Unix timestamp
        of the actual match date.

        The .info file is a binary protobuf. The date field is a varint
        (field 5, type 0) encoding a Unix timestamp in seconds.

        CDataGCCStrike15_v2_MatchInfo format:
          field 1 = matchid (uint64)
          field 2 = matchtime (uint32) ← match timestamp
          ...
        Minimal parsing with no protobuf dependency.
        """
        info_path = Path(demo_path).with_suffix(".info")
        if not info_path.exists():
            # Also try demo_path + ".info" (some versions append to the name)
            info_path2 = Path(str(demo_path) + ".info")
            if info_path2.exists():
                info_path = info_path2
            else:
                return None
        try:
            data = info_path.read_bytes()
            i = 0
            while i < len(data):
                # Read tag varint
                tag = 0
                shift = 0
                while i < len(data):
                    b = data[i]; i += 1
                    tag |= (b & 0x7F) << shift
                    shift += 7
                    if not (b & 0x80):
                        break
                field_num = tag >> 3
                wire_type = tag & 0x07
                if wire_type == 0:   # varint
                    val = 0; shift = 0
                    while i < len(data):
                        b = data[i]; i += 1
                        val |= (b & 0x7F) << shift
                        shift += 7
                        if not (b & 0x80):
                            break
                    if field_num == 2 and val > 1_000_000_000:
                        # matchtime: Unix timestamp post-2001 → valid match date
                        return val
                elif wire_type == 2: # length-delimited
                    length = 0; shift = 0
                    while i < len(data):
                        b = data[i]; i += 1
                        length |= (b & 0x7F) << shift
                        shift += 7
                        if not (b & 0x80):
                            break
                    i += length
                elif wire_type in (1, 5):
                    i += 8 if wire_type == 1 else 4
                else:
                    break   # unknown wire type, stop
        except Exception:
            pass
        return None

    @staticmethod
    def _ts_from_demo_path(demo_path):
        """Return the .dem file mtime as a Unix timestamp, or None if not found.
        Best fallback when .info is absent — typically close to the download date."""
        try:
            p = Path(demo_path)
            if p.is_file():
                return int(p.stat().st_mtime)
        except Exception:
            pass
        return None

    def _get_demo_ts(self, demo_path):
        """Return the canonical demo timestamp. Cached after the first call.
        Priority: 1) .info file  2) .dem mtime  (None if unavailable)."""
        if demo_path in self._ts_cache:
            return self._ts_cache[demo_path]
        ts = self._read_demo_date_from_info(demo_path)
        if ts is None:
            ts = self._ts_from_demo_path(demo_path)
        self._ts_cache[demo_path] = ts
        return ts

    def _format_demo_date(self, demo_path):
        ts = self._get_demo_ts(demo_path)
        if ts is not None:
            try:
                return datetime.fromtimestamp(ts).strftime("%d %m %Y")
            except Exception:
                pass
        # Fallback DB (often = import date)
        raw = self._demo_dates.get(demo_path)
        if raw is None:
            return "??-??-????"
        try:
            if hasattr(raw, "strftime"):
                return raw.strftime("%d %m %Y")
            if isinstance(raw, (int, float)):
                t = int(raw)
                if t > 4_000_000_000:
                    t //= 1000
                return datetime.fromtimestamp(t).strftime("%d %m %Y")
            s = str(raw).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(s[:len(fmt)], fmt).strftime("%d %m %Y")
                except ValueError:
                    continue
        except Exception:
            pass
        return "??-??-????"

    def _demo_sort_key(self, demo_path):
        """Cached sort key — avoids repeated strptime on the same raw date value."""
        # _ts_cache covers _get_demo_ts (covers .info and mtime).
        # For DB raw dates, normalise once and store back as int in _demo_dates.
        ts = self._get_demo_ts(demo_path)
        if ts is not None:
            return (0, ts)
        raw = self._demo_dates.get(demo_path)
        if raw is None:
            return (1, 0)
        # Already normalised on a previous call?
        if isinstance(raw, (int, float)):
            t = int(raw)
            t = t // 1000 if t > 4_000_000_000 else t
            return (0, t)
        try:
            if hasattr(raw, "timestamp"):
                t = int(raw.timestamp())
                self._demo_dates[demo_path] = t  # normalise in-place
                return (0, t)
            s = str(raw).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    t = int(datetime.strptime(s[:len(fmt)], fmt).timestamp())
                    self._demo_dates[demo_path] = t  # normalise in-place
                    return (0, t)
                except ValueError:
                    continue
        except Exception:
            pass
        return (1, 0)

    def _fmt_summary(self, nb_demos, nb_clips, total_sec, avg_sec):
        h = self._hms
        return (f"  {nb_clips} clip{'s' if nb_clips != 1 else ''}  •  "
                f"total duration {h(total_sec)}  •  "
                f"avg. {h(avg_sec)}/clip  •  "
                f"{nb_demos} demo{'s' if nb_demos != 1 else ''}")

    def _log(self, msg, tag=""):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag)
        if self._log_autoscroll.get():
            self.log.see("end")
        self.log.configure(state="disabled")

    def _log_parts(self, parts):
        self.log.configure(state="normal")
        for txt, tag in parts:
            self.log.insert("end", txt, tag or "")
        self.log.insert("end", "\n")
        if self._log_autoscroll.get():
            self.log.see("end")
        self.log.configure(state="disabled")

    def _alog(self, msg, tag=""):
        """Thread-safe async log. Appends to buffer; main thread drains every _LOG_PUMP_MS ms.

        Never calls after(0) per message — avoids flooding the event queue during
        parallel operations (dp2 pre-parse, worker) and keeps the UI responsive.
        """
        with self._log_buf_lock:
            self._log_buf.append((msg, tag))

    def _alog_parts(self, parts):
        """Thread-safe async log for multi-part lines (badge rows)."""
        with self._log_buf_lock:
            self._log_buf.append(("__parts__", parts))

    _LOG_PUMP_MS = 50   # drain interval in milliseconds — 50ms ≈ 20 flushes/sec

    def _drain_log_buffer_once(self):
        if not self._log_buf:
            return
        with self._log_buf_lock:
            pending = list(self._log_buf)
            self._log_buf.clear()
        try:
            self.log.configure(state="normal")
            autoscroll = self._log_autoscroll.get()
            for item in pending:
                if item[0] == "__parts__":
                    for txt, tag in item[1]:
                        self.log.insert("end", txt, tag or "")
                    self.log.insert("end", "\n")
                else:
                    msg, tag = item
                    self.log.insert("end", msg + "\n", tag)
            if autoscroll:
                self.log.see("end")
            self.log.configure(state="disabled")
        except Exception:
            pass

    def _log_pump(self):
        """Drain the async log buffer in a single Text widget operation.

        Called every _LOG_PUMP_MS ms on the main thread via self.after().
        Batches all pending messages into one configure/insert/see/configure
        cycle — N messages = 1 redraw instead of N redraws.
        """
        self._drain_log_buffer_once()
        self.after(self._LOG_PUMP_MS, self._log_pump)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _toggle_log_badges(self, event=None):
        try:
            self._log_badges_enabled.set(not self._log_badges_enabled.get())
            on = self._log_badges_enabled.get()
            if self._log_badges_btn is not None and self._log_badges_btn.winfo_exists():
                self._log_badges_btn.config(
                    text=f"Badges: {'ON' if on else 'OFF'}",
                    fg=GREEN if on else MUTED
                )
            self._log_flash(
                f"  {'✓' if on else 'ℹ'} Clip badges {'enabled' if on else 'collapsed'}.",
                "ok" if on else "dim"
            )
        except Exception:
            pass
        return "break"

    # Ordered list of (cfg_key, emoji_label, category) for every kill filter that has a badge.
    # category: "mods" | "dp2" | "db"
    # Used by _build_filter_badges (per-clip) and _build_filter_header_parts (preview header).
    _FILTER_BADGE_DEFS = [
        # Mods (SQL boolean columns — present in most CSDM DB versions)
        ("kill_mod_through_smoke",  "💨 SMOKE",         "mods"),
        ("kill_mod_no_scope",       "🔭 NOSCOPE",       "mods"),
        ("kill_mod_assisted_flash", "⚡ VIC.FLASH",     "mods"),
        # dp2 (demoparser2 — weapon_fire and player_death event fields)
        ("kill_mod_trois_tap",      "🎯🎲 TROIS TAP",  "dp2"),
        ("kill_mod_trois_shot",     "🎲 TROIS SHOT",   "dp2"),
        ("kill_mod_no_trois_shot",  "🚫🎲 Exclude",    "dp2"),
        ("kill_mod_one_tap",        "🎯 ONE TAP",       "dp2"),
        ("kill_mod_spray_transfer", "🔫 SPRAY",         "dp2"),
        ("kill_mod_high_velocity",  "🏎 FERRARI",       "dp2"),
        ("kill_mod_flick",          "↩ FLICK",          "dp2"),
        ("kill_mod_sauveur",        "🛡 SAVIOR",        "dp2"),
        # dp2 — player_death event flags (formerly "missing DB columns")
        ("kill_mod_wall_bang",      "🧱 WALLBANG",      "dp2"),
        ("kill_mod_airborne",       "🪂 AIR",           "dp2"),
        ("kill_mod_attacker_blind", "😵 BLIND",         "dp2"),
        ("kill_mod_collateral",     "🎯 COLLAT.",       "dp2"),
        # DB (post-filter — cross-round context)
        ("kill_mod_entry_frag",     "🚀 ENTRY",         "db"),
        ("kill_mod_ace",            "🃏 ACE",            "db"),
        ("kill_mod_multi_kill",     "⚡ MULTI",          "db"),
        ("kill_mod_bourreau",       "💀 BULLY",          "db"),
        ("kill_mod_eco_frag",       "💰 ECO",            "db"),
    ]

    _SQL_MOD_KEYS = (
        "kill_mod_through_smoke",
        "kill_mod_no_scope",
        "kill_mod_assisted_flash",
    )

    def _mods_dp2_global_any_union_enabled(self, cfg):
        if cfg.get("kill_mod_logic_mods", "any") != "any":
            return False
        if cfg.get("kill_mod_logic_dp2", "any") != "any":
            return False
        if not any(cfg.get(k) for k in self._SQL_MOD_KEYS):
            return False
        if cfg.get("kill_mod_trois_tap"):
            return False
        return any(cfg.get(k) for k, *_ in self._DP2_FILTER_DEFS)

    def _build_filter_badges(self, cfg, events=None):
        """Return (text, tag) badge tuples for kill filters that matched this clip.

        When events are provided (clip-level), reads the union of _mf sets from
        all kill events — reflecting exactly which filter(s) each kill triggered.

        Falls back to all active filters from cfg when no event has _mf (e.g. when
        no kill filter was active or events come from paths that don't tag _mf).
        """
        if events is not None:
            # Collect the union of all _mf sets across kill events in this clip
            matched: set = set()
            for e in events:
                if e.get("type") == "kill":
                    matched |= (e.get("_mf") or set())
            if matched:
                # Emit badges in _FILTER_BADGE_DEFS order for consistency
                return [(f" [{lbl}]", "badge_filter")
                        for k, lbl, _cat in self._FILTER_BADGE_DEFS if k in matched]

        # Fallback: no _mf data — emit all active filters from cfg
        active = [lbl for k, lbl, _cat in self._FILTER_BADGE_DEFS if cfg.get(k)]
        return [(f" [{lbl}]", "badge_filter") for lbl in active]

    def _build_filter_header_parts(self, cfg):
        """Return a list of grouped filter strings for the preview header Filters: line.

        Groups active filters by category (Mods / dp2 / DB), each prefixed with its
        logic mode.  Returns [] when no kill filter is active.
        """
        _CAT_META = {
            "mods": ("Mods",  "kill_mod_logic_mods"),
            "dp2":  ("dp2",   "kill_mod_logic_dp2"),
            "db":   ("Situation", "kill_mod_logic_db"),
        }
        groups: dict = {}  # category → [label, ...]
        for k, lbl, cat in self._FILTER_BADGE_DEFS:
            if cfg.get(k):
                groups.setdefault(cat, []).append(lbl)
        parts = []
        for cat in ("mods", "dp2", "db"):
            lbls_raw = groups.get(cat)
            if not lbls_raw:
                continue
            cat_name, logic_key = _CAT_META[cat]
            logic_val = cfg.get(logic_key, "any")
            if logic_val == "all":
                logic_str = "ALL"
            elif logic_val == "mixed":
                logic_str = "MIXED"
            else:
                logic_str = "ANY"

            if logic_val == "mixed":
                # Show ★ prefix on required filters
                lbls = []
                for k, lbl, c in self._FILTER_BADGE_DEFS:
                    if c == cat and cfg.get(k):
                        prefix = "★ " if cfg.get(f"{k}_req", False) else ""
                        lbls.append(f"{prefix}{lbl}")
            else:
                lbls = lbls_raw

            parts.append(f"{cat_name} [{logic_str}]: {' · '.join(lbls)}")
        return parts

    def _build_clip_badges(self, events, cfg):
        """Build inline badges that describe what a sequence *contains* followed by which
        kill filters it matched.

        Layout per demo line:
          [content badge]  [filter badge 1]  [filter badge 2]  …

        Content badge: derived from actual events (weapon, type, count).
        Filter badges: one per active kill filter (emojis only, blue).
        """
        badges = []
        kill_events  = [e for e in events if e.get("type") == "kill"]
        death_events = [e for e in events if e.get("type") == "death"]
        round_events = [e for e in events if e.get("type") == "round"]

        def _wpn_str(event_list):
            """Return a compact weapon string for a list of events."""
            raw = [str(e.get("weapon", "")).lower().strip() for e in event_list if e.get("weapon")]
            def _fmt(w):
                w = w.replace("weapon_", "")
                return w.upper() if len(w) <= 6 else w.title()
            seen = {}
            for w in raw:
                d = _fmt(w)
                seen[d] = seen.get(d, 0) + 1
            items = list(seen.items())
            if not items:       return "?"
            if len(items) == 1: return items[0][0]
            if len(items) == 2: return f"{items[0][0]} + {items[1][0]}"
            return f"{items[0][0]} +{len(items)-1}"

        # ── Kill content ──────────────────────────────────────────────────────
        if kill_events:
            n = len(kill_events)
            wpn = _wpn_str(kill_events)
            badge_txt = f" [{n}✕ {wpn}]" if n > 1 else f" [KILL {wpn}]"
            badges.append((badge_txt, "badge_kill"))

        # ── Death content ─────────────────────────────────────────────────────
        if death_events:
            n = len(death_events)
            wpn = _wpn_str(death_events)
            badge_txt = (f" [{n}✕ DEATH by {wpn}]" if n > 1 else f" [DEATH by {wpn}]")
            badges.append((badge_txt, "badge_warn"))

        # ── Round marker ──────────────────────────────────────────────────────
        if round_events and not kill_events and not death_events:
            badges.append((" [ROUND]", "badge_safe"))

        if not badges:
            badges.append((" [?]", "badge_safe"))

        # ── Active kill filter badges (appended after content) ─────────────
        badges.extend(self._build_filter_badges(cfg, events))

        return badges

    def _build_demo_log_base(self, date_str, demo_name, event_count, seq_count, idx=None, total=None, timing_str=""):
        if idx is not None and total is not None:
            return f"\n[{idx}/{total}]  {date_str}  {demo_name}  ({event_count} events → {seq_count} seq){timing_str}"
        return f"  {date_str}  {demo_name}  ({event_count} events → {seq_count} seq){timing_str}"

    def _emit_demo_log_entry(self, date_str, demo_name, events, seq_count, cfg, idx=None, total=None, timing_str="", async_emit=False):
        base = self._build_demo_log_base(
            date_str=date_str,
            demo_name=demo_name,
            event_count=len(events),
            seq_count=seq_count,
            idx=idx,
            total=total,
            timing_str=timing_str,
        )
        if self._log_badges_enabled.get():
            parts = [(base, "blue")]
            parts.extend(self._build_clip_badges(events, cfg))
            if async_emit:
                self._alog_parts(parts)
            else:
                self._log_parts(parts)
            return
        if async_emit:
            self._alog(base, "blue")
        else:
            self._log(base, "blue")

    # ═══════════════════════════════════════════════════
    #  CLI + BDD queries
    # ═══════════════════════════════════════════════════
    def _resolve_cli(self, p):
        if not p:
            return "csdm"
        p = os.path.abspath(p)
        b = os.path.basename(p).lower()
        d = os.path.dirname(p)
        if b in ("csdm.exe", "csdm.cmd") and os.path.isfile(p):
            return p
        for n in ("csdm.CMD", "csdm.cmd", "csdm.exe"):
            for sd in (d, os.path.join(d, "resources")):
                c = os.path.join(sd, n)
                if os.path.exists(c):
                    return c
        w = shutil.which("csdm")
        return w if w else p

    def _find_col(self, table, candidates):
        key = (table, tuple(candidates))
        if key in self._col_cache:
            return self._col_cache[key]
        cols = self._db_schema.get(table, [])
        result = None
        for c in candidates:
            if c in cols:
                result = c
                break
        self._col_cache[key] = result
        return result

    def _query_events(self, cfg):
        sids = self._get_sids(cfg)
        if not sids:
            return {}

        date_from_iso = cfg.get("date_from", "")
        date_to_iso   = cfg.get("date_to", "")

        # Pre-compute epoch bounds for the post-query Python date filter
        ts_from = None
        ts_to   = None
        if date_from_iso:
            try:
                ts_from = int(datetime.strptime(date_from_iso, "%Y-%m-%d")
                              .replace(hour=0, minute=0, second=0).timestamp())
            except Exception:
                pass
        if date_to_iso:
            try:
                ts_to = int((datetime.strptime(date_to_iso, "%Y-%m-%d")
                             .replace(hour=23, minute=59, second=59)).timestamp())
            except Exception:
                pass

        def _demo_passes_date_filter(demo_path):
            if ts_from is None and ts_to is None:
                return True
            ts = self._get_demo_ts(demo_path)
            if ts is None:
                return False  # unknown date + active filter → exclude
            if ts_from is not None and ts < ts_from:
                return False
            if ts_to is not None and ts > ts_to:
                return False
            return True

        conn = self._pg()
        results = {}
        try:
            with conn.cursor() as cur:
                tc = self._find_col("kills", ["tick", "killer_tick", "round_tick"])
                # Victim death tick — for grenades/molotov where the DB tick
                # is the throw but death occurs later
                dtc = self._find_col("kills", ["victim_death_tick", "death_tick",
                                                "killed_tick", "victim_tick"])
                dc = self._find_col("matches",
                                    ["demo_path", "demo_file_path", "demo_filepath", "share_code"])
                mkk = self._find_col("kills", ["match_checksum", "match_id", "checksum"])
                mkm = self._find_col("matches", ["checksum", "id", "match_id"])
                kc = self._find_col("kills", ["killer_steam_id", "attacker_steam_id"])
                vc = self._find_col("kills", ["victim_steam_id", "killed_steam_id"])
                wc = self._find_col("kills", ["weapon_name", "weapon", "weapon_type"])
                if not vc:
                    for c in self._db_schema.get("kills", []):
                        if "victim" in c.lower() and "steam" in c.lower():
                            vc = c
                            break
                if not dc:
                    raise Exception("Demo path column not found")
                if not mkk or not mkm:
                    raise Exception("kills<->matches join column not found")

                kills_on = cfg["events_kills"]
                deaths_on = cfg["events_deaths"]
                weapons = cfg["weapons"]
                # Resolve headshots_mode — force ONLY only when logic guarantees HS-only output
                _hsmode = cfg.get("headshots_mode", "all")
                if self._hs_only_is_required(cfg):
                    _hsmode = "only"
                headshots_only   = (_hsmode == "only")
                headshots_exclude = (_hsmode == "exclude")
                _tkmode = cfg.get("teamkills_mode", "include")
                include_teamkills = (_tkmode != "exclude")
                teamkills_only    = (_tkmode == "only")

                # Headshot column (optional)
                hc = self._find_col("kills", ["is_headshot", "headshot", "is_hs", "hs"])
                hsql = ""
                if (headshots_only or headshots_exclude) and not hc:
                    self._alog("⚠ Headshots filter: column not found in kills — filter ignored.", "warn")
                elif headshots_only and hc:
                    hsql = f' AND k."{hc}" = TRUE'
                elif headshots_exclude and hc:
                    hsql = f' AND k."{hc}" = FALSE'

                tkc_k = self._find_col("kills", ["killer_team_name", "killer_side", "killer_team"])
                tkc_v = self._find_col("kills", ["victim_team_name", "victim_side", "victim_team"])
                tksql = ""
                if teamkills_only:
                    if tkc_k and tkc_v:
                        tksql = f' AND k."{tkc_k}" = k."{tkc_v}"'
                    else:
                        self._alog("⚠ Teamkills only: team columns not found — filter ignored.", "warn")
                elif not include_teamkills:
                    if tkc_k and tkc_v:
                        tksql = f' AND k."{tkc_k}" != k."{tkc_v}"'
                    else:
                        self._alog("⚠ Exclude teamkills: team columns not found — filter ignored.", "warn")

                # Suicide filter — weapon_name IN ('world','suicide','world_entity',...)
                SUICIDE_WEAPONS = ("world", "suicide", "world_entity", "trigger_hurt",
                                   "fall", "env_fire", "planted_c4")
                suicidesql = ""
                if not cfg.get("include_suicides", True) and wc:
                    ph = ",".join(["%s"] * len(SUICIDE_WEAPONS))
                    suicidesql = f' AND k."{wc}" NOT IN ({ph})'

                _MOD_COLS = {
                    "kill_mod_through_smoke":  ["is_through_smoke", "through_smoke"],
                    "kill_mod_no_scope":       ["is_no_scope", "no_scope"],
                    "kill_mod_assisted_flash": ["is_assisted_flash", "assisted_flash"],  # VICTIM blinded
                }
                active_mods = [k for k in _MOD_COLS if cfg.get(k, False)]
                modsql = ""
                _mods_dp2_or_any = self._mods_dp2_global_any_union_enabled(cfg)
                if active_mods:
                    mod_clauses = []
                    missing_mods = []
                    for mod_key in active_mods:
                        col = self._find_col("kills", _MOD_COLS[mod_key])
                        if col:
                            # wallbang alternatif : penetrated_objects > 0
                            if mod_key == "kill_mod_wall_bang":
                                pen_col = self._find_col("kills", ["penetrated_objects"])
                                if pen_col and not col:
                                    mod_clauses.append(f'k."{pen_col}" > 0')
                                else:
                                    mod_clauses.append(f'k."{col}" = TRUE')
                            else:
                                mod_clauses.append(f'k."{col}" = TRUE')
                        else:
                            missing_mods.append(mod_key)
                    if missing_mods:
                        missing_set = frozenset(missing_mods)
                        if not mod_clauses:
                            # All checked modifiers absent from DB →
                            # cannot filter, return empty rather than all clips
                            if missing_set != self._warned_missing_mods:
                                missing_labels = ", ".join(
                                    m.replace("kill_mod_", "").replace("_", " ")
                                    for m in missing_mods)
                                self._alog(
                                    f"⛔ Modifiers not found in DB: {missing_labels}. "
                                    f"No clips returned — uncheck these modifiers or check the schema.",
                                    "err")
                                self._warned_missing_mods = missing_set
                            if not _mods_dp2_or_any:
                                conn.close()
                                return {}
                        else:
                            # Some columns absent — warn once per unique missing set
                            if missing_set != self._warned_missing_mods:
                                missing_labels = ", ".join(
                                    m.replace("kill_mod_", "").replace("_", " ")
                                    for m in missing_mods)
                                self._alog(
                                    f"⚠ Modifiers not found in DB: {missing_labels} — ignored. "
                                    f"Only the others are applied.",
                                    "warn")
                                self._warned_missing_mods = missing_set
                    if mod_clauses:
                        if not _mods_dp2_or_any:
                            _mods_logic = cfg.get("kill_mod_logic_mods", "any")
                            if _mods_logic == "all":
                                modsql = " AND (" + " AND ".join(mod_clauses) + ")"
                            elif _mods_logic == "mixed":
                                _key_clause = []
                                _mi = 0
                                for mod_key in active_mods:
                                    col = self._find_col("kills", _MOD_COLS[mod_key])
                                    if col:
                                        _key_clause.append((mod_key, mod_clauses[_mi]))
                                        _mi += 1
                                req_keys = [k for k, _ in _key_clause if cfg.get(f"{k}_req", False)]
                                opt_clauses = [c for k, c in _key_clause if not cfg.get(f"{k}_req", False)]
                                req_clauses = [c for k, c in _key_clause if cfg.get(f"{k}_req", False)]
                                parts = req_clauses[:]
                                if opt_clauses:
                                    parts.append("(" + " OR ".join(opt_clauses) + ")")
                                if parts:
                                    modsql = " AND (" + " AND ".join(parts) + ")"
                                elif req_clauses:
                                    modsql = " AND (" + " AND ".join(req_clauses) + ")"
                            else:
                                modsql = " AND (" + " OR ".join(mod_clauses) + ")"

                date_col = self._date_col   # may be None → auto-detected below
                if not date_col and self._db_schema.get("matches"):
                    _m_types = self._db_col_types.get("matches", {})
                    _DATE_TYPES = {
                        "date", "timestamp", "timestamp with time zone",
                        "timestamp without time zone", "timestamptz",
                    }
                    date_col = next(
                        (c for c, t in _m_types.items() if t.lower() in _DATE_TYPES), None)
                    if not date_col:
                        _HINTS = ("played_at","match_date","game_date","start_date",
                                  "started_at","date","match_timestamp")
                        date_col = next(
                            (c for c in self._db_schema["matches"] if c.lower() in _HINTS), None)
                    if not date_col:
                        date_col = next(
                            (c for c in self._db_schema["matches"]
                             if "date" in c.lower() and "analyze" not in c.lower()), None)
                    if date_col:
                        self._date_col      = date_col
                        self._date_col_type = _m_types.get(date_col, "").lower()

                # Empty _build_dsql: date filter applied in Python post-query
                def _build_dsql(base_params):
                    return ""

                if (kills_on or deaths_on) and tc and kc:
                    # Build the player clause for N SIDs
                    sid_ph = ",".join(["%s"] * len(sids))
                    per_sid_conds = []
                    per_sid_params = []
                    if kills_on:
                        per_sid_conds.append(f'k."{kc}" IN ({sid_ph})')
                        per_sid_params.extend(sids)
                    if deaths_on and vc:
                        per_sid_conds.append(f'k."{vc}" IN ({sid_ph})')
                        per_sid_params.extend(sids)
                    psql = "(" + " OR ".join(per_sid_conds) + ")"

                    params = per_sid_params[:]
                    wsql = ""
                    if weapons and wc:
                        wsql = f' AND k."{wc}" IN ({",".join(["%s"] * len(weapons))})'
                        params.extend(weapons)
                    dsql = _build_dsql(params)

                    extra, enames = "", []
                    if kc:
                        extra += f',k."{kc}"'
                        enames.append("k")
                    if vc:
                        extra += f',k."{vc}"'
                        enames.append("v")
                    if wc:
                        extra += f',k."{wc}"'
                        enames.append("w")
                    if dtc:
                        extra += f',k."{dtc}"'
                        enames.append("dt")

                    # Fetch each resolved SQL-mod boolean column so we can tag
                    # _mf (matched filters) precisely per event row.
                    # _mod_extra: list of (cfg_key, col_name) for resolved active mods
                    _mod_extra: list = []
                    for mod_key in active_mods:
                        col = self._find_col("kills", _MOD_COLS[mod_key])
                        if col:
                            extra += f',k."{col}"'
                            enames.append(f"_mod_{mod_key}")
                            _mod_extra.append((mod_key, f"_mod_{mod_key}"))
                    # headshots_mode tag key — fetched if hc is available
                    if headshots_only and hc:
                        extra += f',k."{hc}"'
                        enames.append("_hs")

                    date_sel = f',m."{date_col}"' if date_col else ""
                    sql = (f'SELECT m."{dc}",k."{tc}",m."{mkm}"{date_sel}{extra} FROM kills k '
                           f'JOIN matches m ON m."{mkm}"=k."{mkk}" '
                           f'WHERE {psql}{wsql}{hsql}{tksql}{suicidesql}{modsql}{dsql} ORDER BY m."{dc}",k."{tc}"')
                    if suicidesql:
                        params = params + list(SUICIDE_WEAPONS)
                    cur.execute(sql, params)
                    sids_set = set(sids)
                    for row in cur.fetchall():
                        dp, tick, chk = row[0], row[1], row[2]
                        if not dp or tick is None:
                            continue
                        if chk and dp not in self._demo_checksums:
                            self._demo_checksums[dp] = chk
                        if date_col and dp not in self._demo_dates:
                            raw_date = row[3] if len(row) > 3 else None
                            if raw_date is not None:
                                self._demo_dates[dp] = raw_date
                        extra_offset = 4 if date_col else 3
                        ex = {}
                        for ci, cn in enumerate(enames):
                            if extra_offset + ci < len(row):
                                ex[cn] = row[extra_offset + ci]
                        killer_sid = ex.get("k", "")
                        victim_sid = ex.get("v", "")
                        weapon_raw = ex.get("w", "") or ""

                        death_tick = ex.get("dt")
                        if (death_tick is not None
                                and weapon_raw.lower() in DELAYED_EFFECT_WEAPONS):
                            event_tick = int(death_tick)
                        else:
                            event_tick = int(tick)

                        et = "kill" if killer_sid in sids_set else (
                             "death" if victim_sid in sids_set else "kill")
                        if et == "kill" and not kills_on:
                            continue
                        if et == "death" and not deaths_on:
                            continue

                        # Build _mf: set of cfg_key strings that matched for this row
                        _mf: set = set()
                        for mod_key, en in _mod_extra:
                            if ex.get(en):
                                _mf.add(mod_key)
                        if headshots_only and ex.get("_hs"):
                            _mf.add("headshots_mode")

                        evt = {"tick": event_tick, "type": et, "weapon": weapon_raw,
                               "killer_sid": killer_sid, "victim_sid": victim_sid}
                        if _mf:
                            evt["_mf"] = _mf
                        results.setdefault(dp, []).append(evt)

                if cfg["events_rounds"] and self._db_schema.get("rounds"):
                    rtc = self._find_col("rounds",
                                         ["start_tick", "freeze_time_end_tick", "tick", "end_tick"])
                    rmk = self._find_col("rounds", ["match_checksum", "match_id", "checksum"])
                    pmk = self._find_col("players", ["match_checksum", "match_id"])
                    if rtc and rmk and pmk:
                        sid_ph = ",".join(["%s"] * len(sids))
                        params = list(sids)
                        dsql = _build_dsql(params)
                        date_sel2 = f',m."{date_col}"' if date_col else ""
                        sql = (f'SELECT m."{dc}",r."{rtc}",m."{mkm}"{date_sel2} FROM rounds r '
                               f'JOIN matches m ON m."{mkm}"=r."{rmk}" '
                               f'WHERE r."{rmk}" IN '
                               f'(SELECT p."{pmk}" FROM players p WHERE p.steam_id IN ({sid_ph}))'
                               f'{dsql} ORDER BY m."{dc}",r."{rtc}"')
                        try:
                            cur.execute(sql, params)
                            for row in cur.fetchall():
                                dp, tick = row[0], row[1]
                                chk = row[2] if len(row) > 2 else None
                                if dp and tick is not None:
                                    if chk and dp not in self._demo_checksums:
                                        self._demo_checksums[dp] = chk
                                    if date_col and dp not in self._demo_dates and len(row) > 3:
                                        if row[3] is not None:
                                            self._demo_dates[dp] = row[3]
                                    results.setdefault(dp, []).append(
                                        {"tick": int(tick), "type": "round", "weapon": ""})
                        except Exception:
                            pass

                # ── Clutch events ─────────────────────────────────────────────
                if cfg.get("events_clutch") and kc and vc:
                    clutch_raw = self._query_clutch_events(
                        cfg, conn, sids, dc, mkm, tc, kc, vc, wc, mkk, dtc, date_col)
                    for dp, groups in clutch_raw.items():
                        sizes = [g[0].get("clutch_size", "?") for g in groups if g]
                        sizes_str = ", ".join(f"1v{s}" for s in sorted(sizes))
                        self._alog(
                            f"  🤝 CLUTCH [{Path(dp).name}]: "
                            f"{len(groups)} clutch(es) — {sizes_str}",
                            "info")
                        results.setdefault(dp, [])
                        existing_sigs = {(e["tick"], e.get("killer_sid")) for e in results[dp]}
                        for group in groups:
                            for kill in group:
                                sig = (kill["tick"], kill.get("killer_sid"))
                                if sig not in existing_sigs:
                                    results[dp].append(kill)
                                    existing_sigs.add(sig)

        finally:
            pass  # persistent connection — kept open for reuse

        # Applied here rather than SQL because the DB column often contains
        # the import date and not the actual match date.
        if ts_from is not None or ts_to is not None:
            results = {
                dp: evts_val for dp, evts_val in results.items()
                if _demo_passes_date_filter(dp)
            }

        # ── DB post-query filters ──────────────────────────────────────────
        # These operate on the already-fetched results dict and require knowledge
        # of the full event context per demo (all rounds, all kills in match).
        results = self._apply_db_postfilters(cfg, results, sids)

        return results

    def _apply_db_postfilters(self, cfg, results, sids):
        """Apply DB-level post-query filters that require cross-round context.

        These cannot be expressed as simple SQL WHERE clauses on individual kill rows
        because they need information from the full round or match context:
        - Entry Frag: first kill of the round
        - Ace:        player kills all 5 opponents in one round
        - Multi-Kill: ≥N kills in one round within T seconds
        - BULLY:   same victim killed ≥N times across the match
        - Eco-Frag:   pistol vs full-buy (uses victim_weapon if available)

        Called after the main query and date filter — results is a dict
        {demo_path: [event_dict, ...]}. Returns a filtered copy.

        Logic mode (cfg["kill_mod_logic_db"]):
          "any" (default) — OR: a kill qualifies if it matches at least one active modifier.
          "all"           — AND: a kill must match every active modifier simultaneously.

        If none of the relevant modifiers are active, returns results unchanged.
        """
        do_entry   = cfg.get("kill_mod_entry_frag", False)
        do_ace     = cfg.get("kill_mod_ace", False)
        do_multi   = cfg.get("kill_mod_multi_kill", False)
        do_bour    = cfg.get("kill_mod_bourreau", False)
        do_eco     = cfg.get("kill_mod_eco_frag", False)

        active_flags = [do_entry, do_ace, do_multi, do_bour, do_eco]
        if not any(active_flags):
            return results

        logic_and   = cfg.get("kill_mod_logic_db", "any") == "all"
        n_active    = sum(1 for f in active_flags if f)

        multi_n = max(2, int(cfg.get("kill_mod_multi_kill_n", 3)))
        multi_s = max(1, int(cfg.get("kill_mod_multi_kill_s", 12)))
        bour_n  = max(2, int(cfg.get("kill_mod_bourreau_n", 3)))

        # Pistols (lowercase suffixes) for Eco-Frag detection
        PISTOLS = {"deagle","revolver","usp_silencer","hkp2000","glock","p250",
                   "fiveseven","cz75a","tec9","elite",
                   "usp-s","p2000","glock-18","five-seven","cz75-auto","tec-9",
                   "dual berettas","desert eagle","r8 revolver"}
        # Full-buy weapons (victim must have one of these for eco-frag to count)
        FULL_BUY = {"ak47","m4a1","m4a1_silencer","ak-47","m4a4","m4a1-s",
                    "sg556","aug","galilar","famas","sg 553","galil ar",
                    "scar20","g3sg1","awp","ssg08","ssg 08","scar-20",
                    "m249","negev"}

        sids_set = set(str(s) for s in sids)
        filtered = {}

        for dp, events in results.items():
            kill_events = [e for e in events if e.get("type") == "kill"]
            non_kill    = [e for e in events if e.get("type") != "kill"]

            if not kill_events:
                filtered[dp] = events
                continue

            # ── Group kills by (checksum, round_idx) for per-round analysis ─
            # round_idx is stored in the event dict as "round_idx" if available,
            # otherwise we use a tick-gap heuristic to approximate round boundaries.
            # Events come pre-sorted by tick from the SQL ORDER BY.
            def _round_key(e):
                ri = e.get("round_idx")
                if ri is not None:
                    return (e.get("_chk", ""), ri)
                # fallback: ~2-minute rounds ≈ 7680 ticks at 64tick
                return (e.get("_chk", ""), int(e["tick"]) // 7680)

            # Build per-round groups — only player's kills
            player_kills = [e for e in kill_events
                            if str(e.get("killer_sid", "")) in sids_set]

            round_groups: dict = {}
            for e in player_kills:
                rk = _round_key(e)
                round_groups.setdefault(rk, []).append(e)

            # All kills in demo (for BULLY: need all, not just player)
            all_kills_by_round: dict = {}
            for e in kill_events:
                rk = _round_key(e)
                all_kills_by_round.setdefault(rk, []).append(e)

            # Each active modifier collects its own sig set, paired with its cfg_key.
            # OR mode  → union  all sets.
            # AND mode → intersect all sets (a kill must appear in every set).
            per_mod_sigs: list = []  # list of (cfg_key, set_of_sigs)

            # ── Entry Frag ────────────────────────────────────────────────
            if do_entry:
                _sigs: set = set()
                for rk, r_kills in all_kills_by_round.items():
                    first_tick = min(e["tick"] for e in r_kills)
                    for e in r_kills:
                        if e["tick"] == first_tick and str(e.get("killer_sid","")) in sids_set:
                            _sigs.add((e["tick"], str(e.get("killer_sid",""))))
                per_mod_sigs.append(("kill_mod_entry_frag", _sigs))

            # ── Ace ────────────────────────────────────────────────────────
            if do_ace:
                _sigs = set()
                for rk, r_kills in round_groups.items():
                    victims = {str(e.get("victim_sid","")) for e in r_kills}
                    if len(victims) >= 5:
                        for e in r_kills:
                            _sigs.add((e["tick"], str(e.get("killer_sid",""))))
                per_mod_sigs.append(("kill_mod_ace", _sigs))

            # ── Multi-Kill (Triple / Quadra) ───────────────────────────────
            if do_multi:
                max_ticks = multi_s * 64
                try:
                    max_ticks = multi_s * int(cfg.get("tickrate", 64))
                except Exception:
                    pass
                _sigs = set()
                for rk, r_kills in round_groups.items():
                    if len(r_kills) < multi_n:
                        continue
                    r_sorted = sorted(r_kills, key=lambda e: e["tick"])
                    span = r_sorted[-1]["tick"] - r_sorted[0]["tick"]
                    if span <= max_ticks:
                        for e in r_kills:
                            _sigs.add((e["tick"], str(e.get("killer_sid",""))))
                per_mod_sigs.append(("kill_mod_multi_kill", _sigs))

            # ── BULLY ──────────────────────────────────────────────────────
            if do_bour:
                from collections import Counter
                pair_count: Counter = Counter()
                for e in kill_events:
                    ks = str(e.get("killer_sid",""))
                    vs = str(e.get("victim_sid",""))
                    if ks in sids_set and vs:
                        pair_count[(ks, vs)] += 1
                pair_seen: Counter = Counter()
                _sigs = set()
                for e in sorted(kill_events, key=lambda e: e["tick"]):
                    ks = str(e.get("killer_sid",""))
                    vs = str(e.get("victim_sid",""))
                    if ks not in sids_set:
                        continue
                    pair_seen[(ks, vs)] += 1
                    if pair_count[(ks, vs)] >= bour_n and pair_seen[(ks, vs)] >= bour_n:
                        _sigs.add((e["tick"], ks))
                per_mod_sigs.append(("kill_mod_bourreau", _sigs))

            # ── Eco-Frag ───────────────────────────────────────────────────
            if do_eco:
                _sigs = set()
                for e in player_kills:
                    kw = (e.get("weapon") or "").lower().strip()
                    if kw not in PISTOLS:
                        continue
                    vw = (e.get("victim_weapon") or "").lower().strip()
                    if not vw:
                        _sigs.add((e["tick"], str(e.get("killer_sid",""))))
                        continue
                    if vw in FULL_BUY:
                        _sigs.add((e["tick"], str(e.get("killer_sid",""))))
                per_mod_sigs.append(("kill_mod_eco_frag", _sigs))

            # ── Combine per-modifier sets ──────────────────────────────────
            if not per_mod_sigs:
                continue

            logic_mode = cfg.get("kill_mod_logic_db", "any")

            if logic_mode == "mixed":
                active_db_keys = [k for k, _ in per_mod_sigs]
                req_keys, opt_keys = self._split_required_optional(cfg, active_db_keys)
                req_sets = [s for k, s in per_mod_sigs if k in req_keys]
                opt_sets = [s for k, s in per_mod_sigs if k in opt_keys]
                # Required: all must match → intersect
                if req_sets:
                    req_sigs = req_sets[0].intersection(*req_sets[1:]) if len(req_sets) > 1 else set(req_sets[0])
                else:
                    req_sigs = None  # no required → no restriction from req side
                # Optional: at least one → union (or unrestricted if none checked)
                if opt_sets:
                    opt_sigs: set = set()
                    for s in opt_sets:
                        opt_sigs |= s
                else:
                    opt_sigs = None  # no optionals → no restriction from opt side
                # Combine: must satisfy all required AND at least one optional
                if req_sigs is not None and opt_sigs is not None:
                    keep_sigs = req_sigs & opt_sigs
                elif req_sigs is not None:
                    keep_sigs = req_sigs
                elif opt_sigs is not None:
                    keep_sigs = opt_sigs
                else:
                    keep_sigs = set()
            elif logic_and and len(per_mod_sigs) > 1:
                sig_sets = [s for _, s in per_mod_sigs]
                keep_sigs = sig_sets[0].intersection(*sig_sets[1:])
            else:
                keep_sigs: set = set()
                for _, s in per_mod_sigs:
                    keep_sigs |= s

            # Build sig → set_of_matched_cfg_keys for _mf tagging
            sig_to_keys: dict = {}
            for fkey, fset in per_mod_sigs:
                for sig in fset:
                    if sig in keep_sigs:
                        sig_to_keys.setdefault(sig, set()).add(fkey)

            kept_kills = []
            for e in kill_events:
                sig = (e["tick"], str(e.get("killer_sid","")))
                if sig in keep_sigs:
                    matched = sig_to_keys.get(sig, set())
                    if matched:
                        existing = e.get("_mf") or set()
                        e["_mf"] = existing | matched
                    kept_kills.append(e)

            if kept_kills or non_kill:
                filtered[dp] = kept_kills + non_kill
            # If no kills survived AND no non-kill events, drop the demo entirely

        return filtered
    def _effective_before(self, cfg):
        """Return the effective BEFORE duration in seconds.
        In 'both' mode, victim_pre_s is added so the killer phase is fully
        included in the recorded sequence.
        Any other perspective — killer, victim — uses before as-is.
        """
        before = cfg.get("before", 3)
        if cfg.get("perspective") == "both":
            before = before + max(0, cfg.get("victim_pre_s", 0))
        return before

    def _build_sequences(self, events, tickrate, before_s, after_s):
        """Build merged clip sequences from a list of events.
        Events must be sorted by tick (guaranteed by SQL ORDER BY in _query_events).
        """
        if not events:
            return []
        bt, at = before_s * tickrate, after_s * tickrate
        raw = [{"start_tick": max(0, e["tick"] - bt), "end_tick": e["tick"] + at, "events": [e]}
               for e in events]
        merged = [raw[0]]
        for s in raw[1:]:
            p = merged[-1]
            if s["start_tick"] <= p["end_tick"]:
                p["end_tick"] = max(p["end_tick"], s["end_tick"])
                p["events"].extend(s["events"])
            else:
                merged.append(s)
        return merged

    def _build_clutch_sequences(self, clutch_groups, tickrate, before_s, after_s):
        """Build one sequence per clutch group.

        Each group is the player's kills in a clutch round.
        The sequence spans from the FIRST kill minus before_s to the LAST kill
        plus after_s. This is NOT the full CS round — it covers only the kill
        window of the clutch (± padding).

        clip_mode="individual": fall back to standard per-kill sequences.
        """
        sequences = []
        for kills in clutch_groups:
            if not kills:
                continue
            kills_sorted = sorted(kills, key=lambda e: e["tick"])
            first_tick = kills_sorted[0]["tick"]
            last_tick  = kills_sorted[-1]["tick"]
            start = max(0, first_tick - before_s * tickrate)
            end   = last_tick + after_s * tickrate
            sequences.append({
                "start_tick": start,
                "end_tick":   end,
                "events":     kills_sorted,
            })
        return sequences

    def _query_clutch_events(self, cfg, conn, sids, dc, mkm, tc, kc, vc, wc, mkk, dtc, date_col):
        """Detect true clutch situations: the active player was the last alive on
        their team and then killed the remaining opponents in the same round.

        A clutch is defined as:
          1. At the tick of the player's first kill in the round, ALL teammates
             are already dead (player is the sole survivor of their team).
          2. The number of opponents still alive at that tick (clutch size) is in
             the allowed set from _clutch_allowed_sizes(cfg). Empty set = all sizes.

        Algorithm:
          - Fetch ALL kills from every match the active player participated in
            (needed to reconstruct who was alive on both sides at any tick).
          - Reconstruct round brackets from the rounds table (or tick gaps).
          - For each round where the player killed at least one opponent:
              a. Determine the player's side from their kills in that round.
              b. At the player's first kill tick in the round:
                 - teammates_alive = teammates who hadn't died yet
                 - if teammates_alive > 0 → not a clutch (player not alone)
              c. Count opponents alive at that tick → clutch size.
          - Apply allowed_sizes filter on clutch size.
          - Optionally filter by round winner (require_win).

        Returns {demo_path: [[kill_evt, …], …]} — one group per clutch.
        """
        # Allowed clutch sizes: empty set = no restriction (all 1v1..1v5)
        allowed_sizes = App._clutch_allowed_sizes(cfg)
        require_win = cfg.get("clutch_require_win", False)

        results: dict = {}
        sids_set = set(str(s) for s in sids)

        try:
            with conn.cursor() as cur:
                if not tc or not kc or not vc or not dc or not mkk or not mkm:
                    return {}

                # Side/team columns
                kside_col = self._find_col("kills", ["killer_team_name", "killer_side",
                                                      "killer_team", "attacker_side"])
                vside_col = self._find_col("kills", ["victim_team_name", "victim_side",
                                                      "victim_team"])
                rwin_col  = self._find_col("rounds", ["winner_name", "winner_side", "winner",
                                                       "winning_side", "win_reason"])
                rtc_col   = self._find_col("rounds", ["start_tick", "freeze_time_end_tick",
                                                       "tick", "end_tick"])
                retc_col  = self._find_col("rounds", ["end_tick", "official_end_tick"])
                rmk_col   = self._find_col("rounds", ["match_checksum", "match_id", "checksum"])

                # ── Step 1: find all match checksums the player participated in ──
                sid_ph = ",".join(["%s"] * len(sids))
                cur.execute(
                    f'SELECT DISTINCT k."{mkk}" FROM kills k '
                    f'WHERE k."{kc}" IN ({sid_ph}) OR k."{vc}" IN ({sid_ph})',
                    list(sids) * 2)
                match_chksums = [r[0] for r in cur.fetchall() if r[0]]
                if not match_chksums:
                    return {}

                # ── Step 2: fetch ALL kills from those matches ────────────────
                chk_ph = ",".join(["%s"] * len(match_chksums))
                sel_ks = f',k."{kside_col}"' if kside_col else ""
                sel_vs = f',k."{vside_col}"' if vside_col else ""
                sel_wc = f',k."{wc}"'        if wc        else ""
                sel_dt = f',k."{dtc}"'       if dtc       else ""
                date_sel = f',m."{date_col}"' if date_col else ""

                all_kills_sql = (
                    f'SELECT m."{dc}",k."{tc}",m."{mkm}"{date_sel},'
                    f'k."{kc}",k."{vc}"{sel_ks}{sel_vs}{sel_wc}{sel_dt} '
                    f'FROM kills k JOIN matches m ON m."{mkm}"=k."{mkk}" '
                    f'WHERE k."{mkk}" IN ({chk_ph}) '
                    f'ORDER BY m."{dc}",k."{tc}"')
                cur.execute(all_kills_sql, match_chksums)
                all_rows = cur.fetchall()

                # ── Step 3: fetch round brackets ─────────────────────────────
                round_brackets: dict = {}  # {chk: [(start, end, winner), ...]}
                if rtc_col and rmk_col:
                    r_sel_ret  = f',r."{retc_col}"' if (retc_col and retc_col != rtc_col) else ""
                    r_sel_rwin = f',r."{rwin_col}"' if rwin_col else ""
                    r_sql = (f'SELECT r."{rmk_col}",r."{rtc_col}"{r_sel_ret}{r_sel_rwin} '
                             f'FROM rounds r WHERE r."{rmk_col}" IN ({chk_ph}) '
                             f'ORDER BY r."{rmk_col}",r."{rtc_col}"')
                    try:
                        cur.execute(r_sql, match_chksums)
                        for rr in cur.fetchall():
                            chk     = rr[0]
                            r_start = int(rr[1] or 0)
                            i = 2
                            r_end = None
                            if retc_col and retc_col != rtc_col:
                                r_end = int(rr[i] or 0) if rr[i] else None
                                i += 1
                            r_win = rr[i] if rwin_col else None
                            round_brackets.setdefault(chk, []).append([r_start, r_end, r_win])
                    except Exception:
                        pass
                    for chk in round_brackets:
                        brackets = round_brackets[chk]
                        for i, b in enumerate(brackets):
                            if b[1] is None:
                                b[1] = brackets[i+1][0] - 1 if i+1 < len(brackets) else b[0] + 8000
                    # Convert to tuples
                    round_brackets = {c: [tuple(b) for b in bs]
                                      for c, bs in round_brackets.items()}

                def _round_idx_for(chk, tick):
                    for i, (s, e, rw) in enumerate(round_brackets.get(chk, [])):
                        if s <= tick <= e:
                            return i, rw
                    # Fallback: largest start ≤ tick
                    best_i, best_rw = None, None
                    for i, (s, e, rw) in enumerate(round_brackets.get(chk, [])):
                        if s <= tick:
                            best_i, best_rw = i, rw
                    return best_i, best_rw

                # ── Step 4: parse all kill rows into per-match/round structures ─
                # Structure: {(dp, chk, round_idx): [kill_row_dict, ...]}
                round_kills: dict = {}

                # Column index mapping
                # Fixed: 0=dp, 1=tick, 2=chk, (3=date?), then kc, vc, kside?, vside?, wc?, dtc?
                base_off = 4 if date_col else 3
                col_names = ["kc", "vc"]
                if kside_col: col_names.append("ks")
                if vside_col: col_names.append("vs")
                if wc:        col_names.append("wc")
                if dtc:       col_names.append("dt")

                for row in all_rows:
                    dp  = row[0]
                    tick = row[1]
                    chk  = row[2]
                    if not dp or tick is None:
                        continue
                    ex = {}
                    for ci, cn in enumerate(col_names):
                        if base_off + ci < len(row):
                            ex[cn] = row[base_off + ci]

                    killer_sid = str(ex.get("kc", "") or "")
                    victim_sid = str(ex.get("vc", "") or "")
                    k_side     = str(ex.get("ks", "") or "").upper()
                    v_side     = str(ex.get("vs", "") or "").upper()
                    weapon_raw = ex.get("wc", "") or ""
                    death_tick = ex.get("dt")

                    if death_tick is not None and weapon_raw.lower() in DELAYED_EFFECT_WEAPONS:
                        event_tick = int(death_tick)
                    else:
                        event_tick = int(tick)

                    round_idx, round_winner = _round_idx_for(chk, event_tick)
                    if round_idx is None:
                        round_idx = event_tick // 8000  # coarse fallback

                    key = (dp, chk, round_idx)
                    round_kills.setdefault(key, []).append({
                        "tick":        event_tick,
                        "killer_sid":  killer_sid,
                        "victim_sid":  victim_sid,
                        "killer_side": k_side,
                        "victim_side": v_side,
                        "weapon":      weapon_raw,
                        "round_winner": round_winner,
                    })

                    # Store demo date/checksum
                    if date_col and dp not in self._demo_dates and len(row) > 3:
                        if row[3] is not None:
                            self._demo_dates[dp] = row[3]
                    if dp not in self._demo_checksums and chk:
                        self._demo_checksums[dp] = chk

                # ── Step 5: clutch detection per round ───────────────────────
                def _norm_side(s):
                    s = (s or "").upper().replace("-", "_").replace(" ", "_")
                    if s in ("CT", "COUNTER_TERRORIST", "COUNTER", "COUNTERTERRORIST"):
                        return "CT"
                    if s in ("T", "TERRORIST", "TERROR"):
                        return "T"
                    return s

                group_id = 0
                for (dp, chk, round_idx), kills_in_round in round_kills.items():
                    kills_sorted = sorted(kills_in_round, key=lambda k: k["tick"])

                    # Only process rounds where at least one active player made a kill
                    player_kills = [k for k in kills_sorted if k["killer_sid"] in sids_set]
                    if not player_kills:
                        continue

                    # Determine active player and their side for this round
                    player_sid = player_kills[0]["killer_sid"]
                    player_side = _norm_side(player_kills[0].get("killer_side", ""))
                    if not player_side:
                        # Infer from victim side: if victim_side is CT → player is T and vice versa
                        vs = _norm_side(player_kills[0].get("victim_side", ""))
                        player_side = "T" if vs == "CT" else ("CT" if vs == "T" else "")

                    # All deaths in this round before the player's first kill tick
                    first_kill_tick = player_kills[0]["tick"]

                    # Teammates = players on same side who died as victims (excluding the player)
                    # Opponents = players on opposing side
                    def _is_teammate(kill):
                        v_s = _norm_side(kill.get("victim_side", ""))
                        if player_side and v_s:
                            return v_s == player_side and kill["victim_sid"] != player_sid
                        # No side data: can't determine — treat as unknown
                        return False

                    def _is_opponent_death(kill):
                        v_s = _norm_side(kill.get("victim_side", ""))
                        if player_side and v_s:
                            return v_s != player_side
                        return False

                    # Teammates alive at first kill tick = teammates who haven't died yet
                    teammates_dead_before = {k["victim_sid"] for k in kills_sorted
                                              if k["tick"] < first_kill_tick and _is_teammate(k)}
                    all_teammates = {k["victim_sid"] for k in kills_sorted if _is_teammate(k)}
                    teammates_alive_at_clutch = all_teammates - teammates_dead_before

                    # If any teammate was still alive at the first kill → not a clutch
                    if teammates_alive_at_clutch:
                        continue

                    # If we have no side data at all → skip (can't verify)
                    if player_side == "":
                        continue

                    # Opponents alive at first kill tick
                    opponents_dead_before = {k["victim_sid"] for k in kills_sorted
                                              if k["tick"] < first_kill_tick and _is_opponent_death(k)}
                    all_opponents = {k["victim_sid"] for k in kills_sorted if _is_opponent_death(k)}
                    opponents_alive = all_opponents - opponents_dead_before

                    clutch_size = len(opponents_alive)
                    if allowed_sizes and clutch_size not in allowed_sizes:
                        continue

                    # require_win check
                    if require_win:
                        round_winner = player_kills[0].get("round_winner")
                        winner_norm  = _norm_side(round_winner)
                        if player_side and winner_norm:
                            if player_side != winner_norm:
                                continue  # lost the clutch round

                    # Build clean kill events (only the player's kills in this round)
                    clean_kills = []
                    for k in player_kills:
                        clean_kills.append({
                            "tick":       k["tick"],
                            "type":       "kill",
                            "weapon":     k["weapon"],
                            "killer_sid": k["killer_sid"],
                            "victim_sid": k["victim_sid"],
                            "clutch_group":  group_id,
                            "clutch_size":   clutch_size,
                        })
                    results.setdefault(dp, []).append(clean_kills)
                    self._alog(
                        f"  🤝 1v{clutch_size} clutch "
                        f"[{Path(dp).name}] tick={first_kill_tick} "
                        f"({len(clean_kills)} kill{'s' if len(clean_kills)>1 else ''})",
                        "info")
                    group_id += 1

        except Exception as e:
            self._alog(f"  ⚠ Clutch query error: {e}", "warn")

        return results

    def _build_run_cfg(self):
        cfg = self._collect_config()
        cfg["events_kills"]  = self.sel_events["Kills"].get()
        cfg["events_deaths"] = self.sel_events["Deaths"].get()
        cfg["events_rounds"] = self.sel_events["Rounds"].get()
        cfg["events_clutch"] = self.v["clutch_enabled"].get()
        return cfg

    def _get_sids(self, cfg):
        return cfg.get("steam_ids") or ([cfg["steam_id"]] if cfg.get("steam_id") else [])

    def _player_str(self, cfg):
        sids = self._get_sids(cfg)
        if not sids:
            return "—"
        if len(sids) == 1:
            pn = cfg.get("player_name", "") or self._player_names.get(sids[0], sids[0])
            return f"{pn} ({sids[0]})"
        return "  +  ".join(self._player_names.get(s, s) for s in sids)

    def _cfg_int(self, cfg, key, default, lo=None, hi=None):
        raw = cfg.get(key, default)
        try:
            val = int(float(str(raw).strip()))
        except Exception:
            self._alog(f"  ⚠ cfg '{key}' invalid ({raw}) — fallback {default}", "warn")
            val = int(default)
        if lo is not None:
            val = max(lo, val)
        if hi is not None:
            val = min(hi, val)
        return val

    def _cfg_float(self, cfg, key, default, lo=None, hi=None):
        raw = cfg.get(key, default)
        try:
            val = float(str(raw).strip())
        except Exception:
            self._alog(f"  ⚠ cfg '{key}' invalid ({raw}) — fallback {default}", "warn")
            val = float(default)
        if lo is not None:
            val = max(lo, val)
        if hi is not None:
            val = min(hi, val)
        return val

    def _cfg_bool(self, cfg, key, default):
        raw = cfg.get(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, str):
            s = raw.strip().lower()
            if s in {"1", "true", "yes", "on"}:
                return True
            if s in {"0", "false", "no", "off"}:
                return False
        self._alog(f"  ⚠ cfg '{key}' invalid ({raw}) — fallback {default}", "warn")
        return bool(default)

    def _common_cs2_injection(self, cfg):
        launch_args = []
        wm = cfg.get("cs2_window_mode", "none")
        wm_map = {
            "fullscreen": "-fullscreen",
            "windowed": "-windowed",
            "noborder": "-windowed -noborder",
        }
        if wm in wm_map:
            launch_args.extend(wm_map[wm].split())

        cmds = [
            f"cl_ragdoll_gravity {self._cfg_int(cfg, 'phys_ragdoll_gravity', 600, -5000, 5000)}",
            f"ragdoll_gravity_scale {self._cfg_float(cfg, 'phys_ragdoll_scale', 1.0, -10.0, 10.0)}",
            f"sv_gravity {self._cfg_int(cfg, 'phys_sv_gravity', 800, -5000, 5000)}",
            f"cl_ragdoll_physics_enable {1 if self._cfg_bool(cfg, 'phys_ragdoll_enable', True) else 0}",
            f"violence_hblood {1 if self._cfg_bool(cfg, 'phys_blood', True) else 0}",
            f"r_dynamic {1 if self._cfg_bool(cfg, 'phys_dynamic_lighting', True) else 0}",
        ]
        return {"launch_args": launch_args, "console_cmds": cmds}

    def _resolve_cs2_cfg_dir(self, cfg):
        hint = (cfg.get("cs2_cfg_dir") or "").strip()
        candidates = [hint] if hint else []

        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        steam_roots = [os.path.join(pf86, "Steam")]
        steam_roots.extend([
            r"C:\Steam",
            r"D:\Steam",
            r"E:\Steam",
            r"F:\Steam",
        ])

        seen = set()
        for root in steam_roots:
            if not root or root in seen:
                continue
            seen.add(root)
            candidates.append(
                os.path.join(root, "steamapps", "common",
                             "Counter-Strike Global Offensive", "game", "csgo", "cfg")
            )
            lib_vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
            if os.path.isfile(lib_vdf):
                try:
                    txt = Path(lib_vdf).read_text(encoding="utf-8", errors="ignore")
                    for p in re.findall(r'"path"\s*"([^"]+)"', txt):
                        p = p.replace("\\\\", "\\")
                        candidates.append(
                            os.path.join(p, "steamapps", "common",
                                         "Counter-Strike Global Offensive", "game", "csgo", "cfg")
                        )
                except Exception:
                    pass

        for c in candidates:
            if c and os.path.isdir(c):
                return c
        return ""

    def _inject_cs_runtime_cfg(self, cfg, shared):
        cfg_dir = self._resolve_cs2_cfg_dir(cfg)
        if not cfg_dir:
            self._alog("  ⚠ CS injection: CS2 cfg folder not found. "
                       "Set cs2_cfg_dir in csdm_config.json.", "warn")
            return False

        runtime_cmds = list(shared.get("console_cmds", []))
        sm = self._cfg_int(cfg, "hlae_slow_motion", 100, 1, 1000)
        if sm != 100:
            runtime_cmds.append(f"host_timescale {round(sm / 100.0, 4)}")
        if self._cfg_bool(cfg, "hlae_workshop_download", False):
            runtime_cmds.append("cl_downloadfilter all")
        if self._cfg_bool(cfg, "hlae_no_spectator_ui", True):
            runtime_cmds.append("cl_draw_only_deathnotices 1")

        if not runtime_cmds:
            return True

        runtime_cfg_path = os.path.join(cfg_dir, CSDM_RUNTIME_CFG_NAME)
        try:
            Path(runtime_cfg_path).write_text("\n".join(runtime_cmds) + "\n",
                                              encoding="utf-8")
        except Exception as e:
            self._alog(f"  ⚠ CS injection: failed to write runtime cfg: {e}", "warn")
            return False

        autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
        try:
            if os.path.isfile(autoexec_path):
                current = Path(autoexec_path).read_text(encoding="utf-8", errors="ignore")
            else:
                current = ""
            block = f"{CSDM_RUNTIME_BLOCK_START}\nexec {Path(CSDM_RUNTIME_CFG_NAME).stem}\n{CSDM_RUNTIME_BLOCK_END}\n"
            pattern = re.compile(
                rf"{re.escape(CSDM_RUNTIME_BLOCK_START)}.*?{re.escape(CSDM_RUNTIME_BLOCK_END)}\n?",
                re.S
            )
            if pattern.search(current):
                updated = pattern.sub(block, current)
            else:
                sep = "" if (not current or current.endswith("\n")) else "\n"
                updated = f"{current}{sep}{block}"
            Path(autoexec_path).write_text(updated, encoding="utf-8")
        except Exception as e:
            self._alog(f"  ⚠ CS injection: failed to update autoexec.cfg: {e}", "warn")
            return False

        self._alog(f"  🎮 CS injection ready: {runtime_cfg_path}", "dim")
        if shared.get("launch_args"):
            self._alog(
                f"  ⚠ CS launch options not injectable via CSDM JSON: {' '.join(shared['launch_args'])}",
                "warn")
        return True

    def _inject_hlae_extra_args(self, cfg, shared):
        hlae_options = {}
        fov = self._cfg_int(cfg, "hlae_fov", 90, 1, 179)
        if fov and int(fov) != 90:
            hlae_options["mirv_fov"] = int(fov)
        slow_mo = self._cfg_int(cfg, "hlae_slow_motion", 100, 1, 1000)
        if slow_mo and int(slow_mo) != 100:
            hlae_options["host_timescale"] = round(int(slow_mo) / 100.0, 4)
        if self._cfg_bool(cfg, "hlae_afx_stream", False):
            hlae_options["afxStream"] = True
        if self._cfg_bool(cfg, "hlae_no_spectator_ui", True):
            hlae_options["hideSpectatorUi"] = True

        tokens = []
        tokens.extend(shared.get("launch_args", []))
        tokens.extend(f"+{c}" for c in shared.get("console_cmds", []))
        if self._cfg_bool(cfg, "hlae_no_spectator_ui", True):
            tokens.append("+cl_draw_only_deathnotices 1")
        if self._cfg_bool(cfg, "hlae_fix_scope_fov", True):
            tokens.append("+mirv_fov handleZoom enabled 1")
        if self._cfg_bool(cfg, "hlae_workshop_download", False):
            tokens.append("+cl_downloadfilter all")

        extra_raw = cfg.get("hlae_extra_args", "").strip()
        if extra_raw:
            try:
                tokens.extend(shlex.split(extra_raw, posix=False))
            except Exception:
                tokens.extend(extra_raw.split())

        if tokens:
            hlae_options["extraArgs"] = " ".join(tokens)
        return hlae_options

    def _build_json(self, demo_path, sequences, cfg):
        # In multi-player, sid = first SID (JSON compat), but we determine
        # the "owner" of each event dynamically from killer_sid/victim_sid.
        sids_active = set(self._get_sids(cfg))
        primary_sid = cfg.get("steam_id") or (next(iter(sids_active)) if sids_active else "")
        tickrate = cfg.get("tickrate", 64)
        perspective = cfg.get("perspective", "killer")
        recsys = cfg.get("recsys", "HLAE")

        victim_pre_s = cfg.get("victim_pre_s", 2)
        victim_pre_ticks = max(0, int(victim_pre_s) * tickrate)

        def _build_cams_killer(seq):
            """Killer mode: camera on our player, switches to the killer at each event."""
            sorted_evts = sorted(seq["events"], key=lambda e: e["tick"])
            cam_ticks = build_camera_ticks(seq, tickrate)
            cams = []
            for t in cam_ticks:
                target = primary_sid
                for e in sorted_evts:
                    if e["tick"] <= t:
                        ks = e.get("killer_sid")
                        if ks in sids_active:
                            target = ks
                        elif not target:
                            target = primary_sid
                cams.append({"tick": t, "playerSteamId": target,
                             "playerName": self._player_names.get(target, "")})
            return cams

        def _build_cams_victim(seq):
            """Victim mode: camera fixed on the victim of the first kill by our player.
            If the event is our player's death, the camera follows our player.
            No camera switch during the whole sequence."""
            sorted_evts = sorted(
                [e for e in seq["events"] if e.get("killer_sid") in sids_active
                 or e.get("victim_sid") in sids_active],
                key=lambda e: e["tick"]
            )

            # Determine the single camera target for the whole sequence
            target_sid = primary_sid
            if sorted_evts:
                first_ev = sorted_evts[0]
                if first_ev.get("type") == "death" and first_ev.get("victim_sid") in sids_active:
                    # Our player dies: follow them
                    target_sid = first_ev["victim_sid"]
                elif first_ev.get("victim_sid"):
                    # Our player kills: follow the victim
                    target_sid = first_ev["victim_sid"]

            # A single camera point at start_tick is enough — CSDM holds the target
            return [{"tick": seq["start_tick"], "playerSteamId": target_sid,
                     "playerName": self._player_names.get(target_sid, "")}]

        def _build_cams_both(seq):
            """Both mode: camera on the killer from the start of the sequence,
            switches to victim victim_pre_ticks before the kill.
            Sequence already extended by victim_pre_s via _effective_before,
            so the switch is guaranteed inside the clip."""
            sorted_evts = sorted(
                [e for e in seq["events"] if e.get("killer_sid") in sids_active
                 or e.get("victim_sid") in sids_active],
                key=lambda e: e["tick"]
            )
            if not sorted_evts:
                return [{"tick": seq["start_tick"], "playerSteamId": primary_sid,
                         "playerName": self._player_names.get(primary_sid, "")}]

            # Build an explicit (tick, target_sid) timeline
            timeline = []

            for ev in sorted_evts:
                ev_tick = ev["tick"]
                if ev.get("type") == "death" and ev.get("victim_sid") in sids_active:
                    # Our player dies: follow them throughout
                    our_sid = ev["victim_sid"]
                    timeline.append((seq["start_tick"], our_sid))
                else:
                    ksid = ev.get("killer_sid") or primary_sid
                    vsid = ev.get("victim_sid") or primary_sid
                    # Killer phase: from the start of the sequence
                    timeline.append((seq["start_tick"], ksid))
                    # Victim phase: switch victim_pre_ticks before the kill
                    switch_tick = max(seq["start_tick"], ev_tick - victim_pre_ticks)
                    timeline.append((switch_tick, vsid))

            # Deduplicate: keep the last instruction per tick
            timeline.sort(key=lambda x: x[0])
            deduped = {}
            for t_entry, tsid in timeline:
                deduped[t_entry] = tsid
            sorted_timeline = sorted(deduped.items())

            # Initial target = our killer (or our player)
            first_ev = sorted_evts[0]
            if first_ev.get("type") == "death" and first_ev.get("victim_sid") in sids_active:
                initial_sid = first_ev["victim_sid"]
            elif first_ev.get("killer_sid") in sids_active:
                initial_sid = first_ev["killer_sid"]
            else:
                initial_sid = primary_sid

            cam_ticks = build_camera_ticks(seq, tickrate)
            cams = []
            for t in cam_ticks:
                target = initial_sid
                for tl_tick, tl_sid in sorted_timeline:
                    if tl_tick <= t:
                        target = tl_sid
                    else:
                        break
                cams.append({"tick": t, "playerSteamId": target,
                             "playerName": self._player_names.get(target, "")})
            return cams

        seqs = []
        for idx, seq in enumerate(sequences, 1):
            if perspective == "both":
                cams = _build_cams_both(seq)
            elif perspective == "victim":
                cams = _build_cams_victim(seq)
            else:
                cams = _build_cams_killer(seq)

            cam_sids = {c["playerSteamId"] for c in cams if c.get("playerSteamId")}
            if perspective in ("victim", "both"):
                for ev in seq["events"]:
                    vsid = ev.get("victim_sid")
                    if vsid:
                        cam_sids.add(vsid)


            # Collect killers and victims for the sequence
            seq_killer_sids = {ev.get("killer_sid") for ev in seq["events"] if ev.get("killer_sid")}
            seq_victim_sids  = {ev.get("victim_sid")  for ev in seq["events"] if ev.get("victim_sid")}
            all_seq_sids = (cam_sids | seq_killer_sids | seq_victim_sids) - {None, ""}

            players_opts = []
            seen_opts = set()
            # Active players first, then other SIDs in the sequence
            ordered = list(sids_active) + sorted(all_seq_sids - sids_active)
            # In victim mode, camera-target SIDs must have showKill:true
            # otherwise CSDM ignores the camera switch
            cam_target_sids = {c["playerSteamId"] for c in cams if c.get("playerSteamId")}

            for psid in ordered:
                if not psid or psid in seen_opts:
                    continue
                seen_opts.add(psid)
                pname = self._player_names.get(psid, "")
                is_our    = psid in sids_active
                is_killer = psid in seq_killer_sids
                is_cam_target = psid in cam_target_sids

                if perspective == "killer":
                    show = is_our or is_killer
                    hi   = is_our
                elif perspective == "victim":
                    show = is_our or is_killer or is_cam_target
                    hi   = is_our
                else:  # both
                    show = True
                    hi   = is_our

                players_opts.append({"steamId": psid, "playerName": pname,
                                     "showKill": show, "highlightKill": hi,
                                     "isVoiceEnabled": True})

            seqs.append({
                "number": idx,
                "startTick": seq["start_tick"],
                "endTick": seq["end_tick"],
                "showOnlyDeathNotices": cfg.get("show_only_death_notices", True),
                "deathNoticesDuration": cfg.get("death_notices_duration", 5),
                "showXRay": cfg.get("show_xray", True),
                "showAssists": False,
                "recordAudio": True,
                "playerVoicesEnabled": True,
                "playerCameras": cams,
                "cameras": [],
                "playersOptions": players_opts,
            })

        _clips_dir = (cfg.get("output_dir_clips") or cfg.get("output_dir") or "").strip()
        od = os.path.abspath(_clips_dir) if _clips_dir else ""
        if cfg.get("subfolder_per_demo", True) and od:
            od = os.path.join(od, safe_folder_name(Path(demo_path).name))
            os.makedirs(od, exist_ok=True)

        shared_injection = self._common_cs2_injection(cfg)
        hlae_options = self._inject_hlae_extra_args(cfg, shared_injection) if recsys == "HLAE" else {}

        # Encoding preset — injected into outputParameters for CPU codecs only
        # GPU codecs (NVENC/AMF) ignore -preset from libx264/libx265
        _CPU_CODECS = {"libx264", "libx265", "libsvtav1", "libaom-av1", "libvpx-vp9",
                       "prores_ks", "utvideo"}
        video_codec = cfg.get("video_codec", "libx264")
        video_preset = cfg.get("video_preset", "medium").strip()
        user_out_params = cfg.get("ffmpeg_output_params", "").strip()
        # Only inject preset if: CPU codec + non-empty preset + not already in paramsr
        if (video_codec in _CPU_CODECS and video_preset
                and "-preset" not in user_out_params):
            preset_injection = f"-preset {video_preset}"
            out_params = (preset_injection + " " + user_out_params).strip()
        else:
            out_params = user_out_params

        out = {
            "demoPath": os.path.abspath(demo_path),
            "outputFolderPath": od,
            "encoderSoftware": cfg.get("encoder", "FFmpeg"),
            "recordingSystem": cfg.get("recsys", "HLAE"),
            "recordingOutput": "video",
            "framerate": cfg.get("framerate", 60),
            "width": cfg.get("width", 1920),
            "height": cfg.get("height", 1080),
            "closeGameAfterRecording": cfg.get("close_game_after", True),
            "concatenateSequences": cfg.get("concatenate_sequences", False),
            "showOnlyDeathNotices": cfg.get("show_only_death_notices", True),
            "deathNoticesDuration": cfg.get("death_notices_duration", 5),
            "trueView": cfg.get("true_view", True),
            "ffmpegSettings": {
                "audioBitrate": cfg.get("audio_bitrate", 256),
                "constantRateFactor": cfg.get("crf", 18),
                "customLocationEnabled": False,
                "customExecutableLocation": "",
                "videoContainer": cfg.get("video_container", "mp4"),
                "videoCodec": video_codec,
                "audioCodec": cfg.get("audio_codec", "libmp3lame"),
                "inputParameters": cfg.get("ffmpeg_input_params", ""),
                "outputParameters": out_params,
            },
            "sequences": seqs,
        }
        if hlae_options:
            out["hlaeOptions"] = hlae_options
        return out

    # ═══════════════════════════════════════════════════
    #  Exec
    # ═══════════════════════════════════════════════════
    RETRYABLE = ["game error", "game crashed", "process exited", "timed out"]
    FATAL = ["is not iterable", "ENOENT", "Cannot find", "not found", "TypeError",
             "ReferenceError", "SyntaxError", "FATAL", "Unhandled", "Cannot read properties"]
    # "error:" (with colon) avoids false positives on "no errors found",
    # "error-corrected", "errorless", etc.
    ALL_ERR = RETRYABLE + FATAL + ["error:", "Error:"]

    def _start_cs2_minimize_watcher(self):
        """Start a thread that waits for the CS2 window and minimizes it once.
        Requires pywin32; returns silently without it."""
        def _watch():
            try:
                import win32gui
                import win32con
            except ImportError:
                self._alog("  ℹ cs2_minimize: pywin32 not installed — option ignored.", "dim")
                return

            CS2_TITLES = ("Counter-Strike 2", "cs2", "CS2")
            deadline = time.time() + 60  # 60s timeout to find CS2

            def _find_cs2():
                found = []
                def _cb(hwnd, _):
                    if not win32gui.IsWindowVisible(hwnd):
                        return
                    t = win32gui.GetWindowText(hwnd)
                    if any(k.lower() in t.lower() for k in CS2_TITLES):
                        found.append(hwnd)
                win32gui.EnumWindows(_cb, None)
                return found

            # Phase 1: wait for CS2 (fast polling 100ms)
            first_seen = None
            while time.time() < deadline and self._running:
                hwnds = _find_cs2()
                for hwnd in hwnds:
                    try:
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                        if first_seen is None:
                            self._alog("  🗕 CS2 minimized.", "dim")
                            first_seen = time.time()
                    except Exception:
                        pass
                if first_seen:
                    break
                time.sleep(0.1)

            if not first_seen:
                return  # CS2 not found within timeout
            # CS2 minimized once — thread stops.

        threading.Thread(target=_watch, daemon=True).start()

    def _exec(self, cmd):
        errs, has_err, retryable = [], False, False
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, encoding="utf-8", errors="replace", bufsize=1)
            # Start CS2 minimize watcher if the option is enabled
            if getattr(self, "v", {}) and self.v.get("cs2_minimize") and self.v["cs2_minimize"].get():
                self._start_cs2_minimize_watcher()
            for line in iter(self._proc.stdout.readline, ""):
                line = line.rstrip("\n\r")
                if not line:
                    continue
                ll = line.lower()
                is_e = any(k.lower() in ll for k in self.ALL_ERR)
                if is_e:
                    has_err = True
                    errs.append(line)
                    if any(k in ll for k in self.RETRYABLE):
                        retryable = True
                    self._alog(f"  > {line}", "err")
                else:
                    self._alog(f"  > {line}", "dim")
            self._proc.stdout.close()
            rc = self._proc.wait()
            return (rc == 0) and not has_err, rc, errs, retryable
        except Exception as e:
            return False, -1, [str(e)], False

    def _run(self):
        if not self.player_search.get_steam_ids():
            messagebox.showerror("", "Check at least one registered account.")
            return
        if not any(v.get() for v in self.sel_events.values()) and not self.v["clutch_enabled"].get():
            messagebox.showerror("", "Select at least one event or enable Clutch.")
            return
        ensure_csdm_dirs()
        cfg = self._build_run_cfg()
        self._running = True
        self._stop_after_current = False
        self._kill_triggered = False
        self._tagged_this_batch = []   # [(demo_path, tag_name), ...] — for rollback
        self.run_btn.config(state="disabled", bg=BG3, fg=MUTED)
        self.stop_btn.config(state="normal")
        self.kill_btn.config(state="normal")
        self._log(f"\n{'═' * 60}", "dim")
        self._log(f"  ▶ LAUNCH  —  {datetime.now().strftime('%H:%M:%S')}", "info")
        self._log(f"{'═' * 60}", "dim")
        self._summary_lbl.config(text="  Querying DB…", fg=YELLOW)
        threading.Thread(target=self._worker, args=(cfg,), daemon=True).start()

    def _stop_graceful(self):
        """Stop after current demo: kill the running CSDM process immediately,
        mark current demo as failed, then do not start the next one."""
        self._stop_after_current = True
        self._running = False
        self._alog("\n⏸ Graceful stop — aborting current demo.", "warn")
        self.stop_btn.config(state="disabled")
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def _kill_now(self):
        """Hard kill: stop everything immediately, kill CS2 process, skip assembly,
        and revert tags applied during this batch."""
        self._kill_triggered = True
        self._running = False
        self._stop_after_current = True
        self._alog("\n⛔ KILL — aborting and killing CS2.", "err")
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
        # Kill CS2 process (Windows only — silent no-op on others)
        try:
            subprocess.Popen(
                ["taskkill", "/F", "/IM", "cs2.exe"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
        except Exception:
            pass
        self.after(0, self._reset_btns)

    def _reset_btns(self):
        self._running = False
        self._stop_after_current = False
        self.run_btn.config(state="normal", bg=ORANGE, fg="white")
        self.stop_btn.config(state="disabled")
        self.kill_btn.config(state="disabled")

    def _preparse_dp2(self, cfg, demo_paths):
        """Pre-parse demo files with demoparser2 in parallel threads.

        Calls _dp2_parse_demo for each demo NOT yet in cache.
        Already-cached demos are skipped — the cache is never flushed.
        This means a Preview followed immediately by a Batch run with the same
        demo set will skip the pre-parse entirely on the second call.

        Partial cache hits are handled naturally: if 100 demos were cached
        from a previous run and 5 new demos appear, only the 5 are parsed.

        Thread-safe via _dp2_cache_lock (inside _dp2_parse_demo).
        """
        required_sections = self._dp2_required_sections(cfg)
        if not required_sections:
            return

        paths = [dp for dp in demo_paths if os.path.isfile(dp)]
        if not paths:
            return

        # Determine which demos are not yet cached for the required sections
        with self._dp2_cache_lock:
            missing = []
            for dp in paths:
                entry = self._dp2_cache.get(dp, {})
                have = set(entry.get("_sections", set())) if isinstance(entry, dict) else set()
                if not required_sections.issubset(have):
                    missing.append(dp)

        n_cached = len(paths) - len(missing)

        if not missing:
            self._alog(
                f"  ⚡ Pre-parse: all {len(paths)} demo(s) already cached — skipping",
                "dim")
            return

        n_threads = max(1, min(8, int(cfg.get("dp2_threads", 2))))
        if n_cached:
            self._alog(
                f"  ⚡ Pre-parsing {len(missing)} demo(s) "
                f"({n_cached} already cached) with {n_threads} thread(s)…",
                "info")
        else:
            self._alog(
                f"  ⚡ Pre-parsing {len(missing)} demo(s) with {n_threads} thread(s)…",
                "info")

        done = 0
        total = len(missing)
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as ex:
            futs = {ex.submit(self._dp2_parse_demo, dp, required_sections): dp for dp in missing}
            for fut in concurrent.futures.as_completed(futs):
                done += 1
                try:
                    fut.result()
                except Exception as e:
                    self._alog(
                        f"  ⚠ Pre-parse error ({Path(futs[fut]).name}): {e}",
                        "warn")
                # Update progress label directly — safe because we're on the worker thread
                # and after() is thread-safe; but we batch: only schedule every 5 completions
                # or on the last one to avoid flooding the event queue.
                if done == total or done % 5 == 0:
                    self.after(0, lambda d=done, t=total:
                               self.progress_lbl.config(text=f"Pre-parse {d}/{t}"))

        cached_total = n_cached + done
        self._alog(
            f"  ✓ Pre-parse done ({done} parsed, {cached_total}/{len(paths)} total in cache)",
            "ok")

    @staticmethod
    def _dp2_required_sections(cfg):
        sections = set()
        fire_keys = {
            "kill_mod_trois_tap",
            "kill_mod_trois_shot",
            "kill_mod_no_trois_shot",
            "kill_mod_one_tap",
            "kill_mod_spray_transfer",
            "kill_mod_high_velocity",
        }
        death_keys = {
            "kill_mod_wall_bang",
            "kill_mod_airborne",
            "kill_mod_attacker_blind",
            "kill_mod_collateral",
            "kill_mod_flick",
        }
        if any(cfg.get(k) for k in fire_keys):
            sections.add("fire")
        if any(cfg.get(k) for k in death_keys):
            sections.add("death")
        if cfg.get("kill_mod_sauveur"):
            sections.add("hurt")
        return sections


    def _dry_run(self):
        if not self.player_search.get_steam_ids():
            messagebox.showerror("", "Check at least one registered account.")
            return
        cfg = self._build_run_cfg()
        self._log(f"\n{'─' * 60}", "dim")
        self._log(f"  🔍 PREVIEW  —  {datetime.now().strftime('%H:%M:%S')}", "info")
        self._log(f"{'─' * 60}", "dim")
        self._summary_lbl.config(text="  Computing…", fg=YELLOW)

        def task():
            t0_total = time.time()
            try:
                t0 = time.time()
                evts = self._query_events(cfg)
                t_query = time.time() - t0
            except Exception as e:
                self._alog(f"Error: {e}", "err")
                return
            # ── Signature-based DP2 pre-parse (cache preserved if same demo set) ──
            t0 = time.time()
            self._preparse_dp2(cfg, list(evts.keys()))
            t_preparse = time.time() - t0
            # ─────────────────────────────────────────────────────────────────
            # Apply demoparser2 modifiers before preview (shared helper handles AND/OR logic).
            t0 = time.time()
            evts = self._apply_dp2_filters_to_events(evts, cfg)
            t_filters = time.time() - t0
            t_total = time.time() - t0_total
            timings = {
                "query":    t_query,
                "preparse": t_preparse,
                "filters":  t_filters,
                "total":    t_total,
            }
            self.after(0, lambda evts=evts, cfg=cfg, tm=timings:
                       self._show_preview(evts, cfg, tm))

        threading.Thread(target=task, daemon=True).start()

    def _show_preview(self, evts, cfg, timings=None):
        """Display preview results. Must be called on the main thread.
        timings: optional dict with keys query/preparse/filters/total/seqbuild (seconds).
        """
        self._drain_log_buffer_once()
        if not evts:
            self._log("No events.", "warn")
            self._summary_lbl.config(text="  No clips found.", fg=MUTED)
            return
        te = sum(len(e) for e in evts.values())

        # ── Header ─────────────────────────────────────────────────────────────
        self._log(f"Player:  {self._player_str(cfg)}", "info")

        _auto_tags = self._get_active_tag_names() if self.v["tag_enabled"].get() else []
        if _auto_tags:
            self._log(f"Tag:     🏷 {', '.join(_auto_tags)}", "info")

        df = cfg.get("date_from", "")
        dt = cfg.get("date_to", "")
        if df or dt:
            self._log(f"Dates:   {df or '∞'}  →  {dt or '∞'}", "info")

        # Events row
        _ev_parts = []
        if cfg.get("events_kills"):   _ev_parts.append("Kills")
        if cfg.get("events_deaths"):  _ev_parts.append("Deaths")
        if cfg.get("events_rounds"):  _ev_parts.append("Rounds")
        if cfg.get("events_clutch"):
            _csizes = App._clutch_allowed_sizes(cfg)
            _cs = " ".join(f"1v{n}" for n in sorted(_csizes)) if _csizes else "all"
            _ev_parts.append(f"Clutch [{_cs}]")
        self._log(f"Events:  {' + '.join(_ev_parts) if _ev_parts else '—'}", "info")

        # Weapons row
        _weapons = cfg.get("weapons", [])
        if _weapons:
            _cat_counts = {}
            for w in _weapons:
                c = _weapon_category(w)
                _cat_counts[c] = _cat_counts.get(c, 0) + 1
            _wstr = ", ".join(f"{WEAPON_ICONS.get(c,'')} {c}({n})" for c, n in sorted(_cat_counts.items()))
        else:
            _wstr = "all"
        self._log(f"Weapons: {_wstr}", "info")

        # Perspective / TrueView / order
        _persp = PERSP_LABELS.get(cfg.get("perspective","killer"), cfg.get("perspective","killer"))
        _tv    = "ON" if cfg.get("true_view") else "OFF"
        _order = "Chronological" if cfg.get("clip_order","chrono") == "chrono" else "Random 🎲"
        self._log(f"Rec:     {_persp}  |  TrueView: {_tv}  |  Order: {_order}", "info")

        # Active kill filters — grouped by category, derived from shared definition table
        _kf_parts = self._build_filter_header_parts(cfg)

        # TK / suicides / HS
        _tkm = cfg.get("teamkills_mode", "include")
        _misc = []
        if _tkm == "exclude":  _misc.append("🚫 TK")
        elif _tkm == "only":   _misc.append("⚔ TK only")
        if not cfg.get("include_suicides", True): _misc.append("🚫 suicides")
        _hsm = cfg.get("headshots_mode", "all")
        if _hsm == "only":    _misc.append("🎯 HS only")
        elif _hsm == "exclude": _misc.append("🎯 no HS")
        if _misc: _kf_parts.append(" · ".join(_misc))

        if _kf_parts:
            self._log(f"Filters: {' | '.join(_kf_parts)}", "ok")

        # Result counts
        self._log(f"Found:   {len(evts)} demo(s)  ·  {te} event(s)", "ok")

        _out = (cfg.get("output_dir_clips") or cfg.get("output_dir") or "").strip()
        if _out:
            self._log(f"Output:  {_out}", "dim")
        self._log("Dates:   .info › mtime .dem › DB", "dim")
        # ── end header ─────────────────────────────────────────────────────────
        tickrate  = cfg["tickrate"]
        before_s  = self._effective_before(cfg)
        after_s   = cfg["after"]
        nb_clips  = 0
        nb_clutch_clips = 0
        total_ticks = 0
        clutch_ticks = 0
        sorted_demos = sorted(evts.keys(), key=self._demo_sort_key)
        # Populate demo picker with the range-filtered demo list
        self._demo_picker_populate(sorted_demos, keep_existing=False)
        demo_dates = {}
        t0_seqbuild = time.time()
        for dp in sorted_demos:
            # Clutch full-round sequences
            if (cfg.get("events_clutch") and
                    cfg.get("clutch_clip_mode", "full") == "full"):
                clutch_groups = {}
                for evt in evts[dp]:
                    gid = evt.get("clutch_group")
                    if gid is not None:
                        clutch_groups.setdefault(gid, []).append(evt)
                non_clutch = [e for e in evts[dp] if e.get("clutch_group") is None]
                seqs = []
                if non_clutch:
                    seqs = self._build_sequences(non_clutch, tickrate, before_s, after_s)
                if clutch_groups:
                    c_seqs = self._build_clutch_sequences(
                        list(clutch_groups.values()), tickrate, before_s, after_s)
                    seqs += c_seqs
                    nb_clutch_clips += len(c_seqs)
                    for s in c_seqs:
                        clutch_ticks += s["end_tick"] - s["start_tick"]
                seqs.sort(key=lambda s: s["start_tick"])
            else:
                seqs = self._build_sequences(evts[dp], tickrate, before_s, after_s)
            nb_clips += len(seqs)
            for s in seqs:
                total_ticks += s["end_tick"] - s["start_tick"]
            date_str = self._format_demo_date(dp)
            demo_dates[dp] = date_str
            self._emit_demo_log_entry(
                date_str=date_str,
                demo_name=Path(dp).name,
                events=evts[dp],
                seq_count=len(seqs),
                cfg=cfg,
            )
        known_dates = {d for d in demo_dates.values() if d != "??-??-????"}
        if len(known_dates) == 1 and len(sorted_demos) > 3:
            self._log(
                f"\n⚠  All dates are identical ({next(iter(known_dates))}).\n"
                f"   .info files are missing — the displayed date is the .dem mtime\n"
                f"   (download date), not the exact match date.",
                "warn")
        total_sec = total_ticks / tickrate if tickrate else 0
        avg_sec   = total_sec / nb_clips if nb_clips else 0
        nb_demos  = len(evts)
        t_seqbuild = time.time() - t0_seqbuild

        # ── Timing summary ─────────────────────────────────────────────────
        if timings is not None:
            timings["seqbuild"] = t_seqbuild
            _parts = [f"DB {timings['query']*1000:.0f}ms"]
            if timings["preparse"] > 0.05:
                _parts.append(f"dp2-parse {timings['preparse']:.2f}s")
            if timings["filters"] > 0.01:
                _parts.append(f"filters {timings['filters']*1000:.0f}ms")
            _parts.append(f"seq-build {t_seqbuild*1000:.0f}ms")
            _parts.append(f"total {timings['total'] + t_seqbuild:.2f}s")
            self._log(f"  ⏱ {' | '.join(_parts)}", "dim")

        # Build adaptive summary line
        h = self._hms
        nb_regular = nb_clips - nb_clutch_clips
        summary_txt = self._fmt_summary(nb_demos, nb_clips, total_sec, avg_sec)
        self._log(f"\n{'─'*56}", "dim")
        avg_line = f"  ▶ {nb_clips} clips  |  total {h(total_sec)}"
        if nb_clutch_clips > 0 and nb_regular > 0:
            # Mixed: show separate averages
            reg_sec   = (total_sec - clutch_ticks / tickrate) / nb_regular if nb_regular else 0
            cl_sec    = (clutch_ticks / tickrate) / nb_clutch_clips if nb_clutch_clips else 0
            avg_line += (f"  |  {nb_regular} clip{'s' if nb_regular!=1 else ''} avg. {h(reg_sec)}"
                         f"  +  {nb_clutch_clips} clutch avg. {h(cl_sec)}")
        elif nb_clutch_clips > 0:
            # All clutch clips
            avg_line += f"  |  avg. {h(avg_sec)}/clutch"
        else:
            avg_line += f"  |  avg. {h(avg_sec)}/clip"
        self._log(avg_line, "ok")
        self._log(f"{'─'*56}", "dim")
        self._summary_lbl.config(text=summary_txt, fg=GREEN)

    def _assemble_clips(self, cfg, produced_dirs):
        container = cfg.get("video_container", "mp4")

        # Map conteneur → nom de format FFmpeg (-f) — mkv s'appelle "matroska" pour FFmpeg
        _FMT_MAP = {
            "mkv": "matroska",
            "mp4": "mp4",
            "avi": "avi",
            "mov": "mov",
            "webm": "webm",
        }
        ffmpeg_fmt = _FMT_MAP.get(container, container)

        # Chercher FFmpeg
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            p = Path.home() / ".csdm" / "ffmpeg" / "ffmpeg.exe"
            ffmpeg = str(p) if p.exists() else None
        if not ffmpeg:
            self._alog("  Assembly: FFmpeg not found.", "err")
            return

        # Collect all video files from produced directories
        _asm_base = (cfg.get("output_dir_assembled") or
                    cfg.get("output_dir_clips") or
                    cfg.get("output_dir") or "").strip()
        out_root = os.path.abspath(_asm_base) if _asm_base else ""
        clips = []
        search_dirs = [d for d in produced_dirs if d] or ([out_root] if out_root else [])
        for d in search_dirs:
            if os.path.isdir(d):
                for ext in (f".{container}", ".mp4", ".avi", ".mkv", ".mov"):
                    clips.extend(sorted(Path(d).glob(f"*{ext}")))
        # Deduplicate preserving order
        seen = set()
        clips = [c for c in clips if not (str(c) in seen or seen.add(str(c)))]

        if not clips:
            self._alog("  Assembly: no clip found.", "warn")
            return

        self._alog(f"  {len(clips)} clip(s) to assemble…", "info")

        # Resolve the output path
        out_name = (cfg.get("assemble_output", "assembled.mp4") or "assembled.mp4").strip()
        if not os.path.isabs(out_name):
            out_name = os.path.join(out_root, out_name)
        if not Path(out_name).suffix:
            out_name = out_name + f".{container}"
        os.makedirs(os.path.dirname(out_name) or ".", exist_ok=True)

        # Write the FFmpeg concat list
        # Use Windows paths with backslashes — FFmpeg concat handles them better
        # No apostrophes or quotes in concat format: use double quotes
        # and escape special chars (# would be interpreted as a sequence otherwise)
        try:
            lst = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="csdm_concat_",
                                              delete=False, encoding="utf-8")
            for c in clips:
                safe = str(c).replace("\\", "/").replace("'", "\\'")
                lst.write(f"file '{safe}'\n")
            lst.close()
            lst_path = lst.name
        except Exception as e:
            self._alog(f"  Assembly: list error — {e}", "err")
            return

        # The # in out_name causes issues with FFmpeg on the command line.
        # Use a temp output file without special chars, then rename.
        special_chars = set('#%?*')
        needs_rename = any(c in special_chars for c in os.path.basename(out_name))
        if needs_rename:
            tmp_out = os.path.join(os.path.dirname(out_name),
                                   f"_csdm_tmp_{uuid.uuid4().hex[:8]}{Path(out_name).suffix}")
        else:
            tmp_out = out_name

        # movflags+faststart only for mp4/mov (not supported by matroska/avi)
        fast_start = ["-movflags", "+faststart"] if container in ("mp4", "mov") else []

        cmd = [ffmpeg, "-y",
               "-fflags", "+genpts",           # recompute missing/negative PTS
               "-f", "concat", "-safe", "0",
               "-i", lst_path,
               "-c:v", "copy",                 # copy video stream (no re-encode)
               "-c:a", "aac",                  # re-encode audio to fix drift
               "-b:a", f"{cfg.get('audio_bitrate', 256)}k",
               "-af", "aresample=async=1000",  # resync audio to video timeline
               ] + fast_start + [
               "-f", ffmpeg_fmt, tmp_out]

        success, rc, errs, _ = self._exec(cmd)
        try:
            os.unlink(lst_path)
        except Exception:
            pass

        if success:
            # Rename to final name if a temp file was used
            if needs_rename and tmp_out != out_name:
                try:
                    if os.path.exists(out_name):
                        os.remove(out_name)
                    os.rename(tmp_out, out_name)
                except Exception as e:
                    self._alog(f"  ⚠ Assembled but rename failed: {e}\n  File: {tmp_out}", "warn")
                    out_name = tmp_out
            self._alog(f"  ✓ Assembled: {out_name}", "ok")
            if cfg.get("delete_after_assemble"):
                deleted = 0
                dirs_to_check = set()
                for c in clips:
                    try:
                        dirs_to_check.add(c.parent)
                        c.unlink()
                        deleted += 1
                    except Exception:
                        pass
                # Remove clip folders (never the root output dir)
                out_root = Path(os.path.abspath(cfg.get("output_dir", ""))).resolve()
                removed_dirs = 0
                for d in dirs_to_check:
                    try:
                        if d.resolve() == out_root:
                            continue
                        # Delete even if non-empty (residual JSON files etc.)
                        shutil.rmtree(d, ignore_errors=True)
                        if not d.exists():
                            removed_dirs += 1
                    except Exception:
                        pass
                msg = f"  🗑 {deleted} clip(s) deleted"
                if removed_dirs:
                    msg += f", {removed_dirs} folder(s) deleted"
                self._alog(msg + ".", "dim")
        else:
            if needs_rename and os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except Exception:
                    pass
            err_msg = errs[0] if errs else f"code {rc}"
            self._alog(f"  ✗ Assembly failed: {err_msg}", "err")


    # ── dp2 filter definition table ────────────────────────────────────────
    # Single source of truth for every demoparser2 kill modifier.
    # Each row: (cfg_key, filter_fn_attr, apply_fn_attr, log_label, result_label, skip_label)
    #
    # filter_fn_attr  — per-demo filter method name (used by _apply_dp2_modifiers worker path)
    # apply_fn_attr   — dict-level apply method name (used by _apply_dp2_filters_to_events preview path)
    #
    # TROIS TAP is NOT listed here — it is always exclusive and handled separately.
    _DP2_FILTER_DEFS = [
        ("kill_mod_trois_shot",     "_trois_shot_filter",          "_apply_trois_shot_to_events",
         "🎲 TROIS SHOT",    "TROIS SHOT",     "0 TROIS SHOT"),
        ("kill_mod_no_trois_shot",  "_no_trois_shot_filter",       "_apply_no_trois_shot_to_events",
         "🚫🎲 Exclude",     "precise",        "0 EXCLUDE"),
        ("kill_mod_one_tap",        "_one_tap_filter",             "_apply_one_tap_to_events",
         "🎯 ONE TAP",       "one tap",        "0 ONE TAP"),
        ("kill_mod_spray_transfer", "_spray_transfer_filter",      "_apply_spray_transfer_to_events",
         "🔫 SPRAY",         "spray transfer", "0 SPRAY"),
        ("kill_mod_high_velocity",  "_high_velocity_filter",       "_apply_high_velocity_to_events",
         "🏎 FERRARI PEEK",  "counter-strafe", "0 FERRARI PEEK"),
        ("kill_mod_flick",          "_flick_filter",               "_apply_flick_to_events",
         "↩ FLICK",          "flick",          "0 FLICK"),
        ("kill_mod_sauveur",        "_sauveur_filter",             "_apply_sauveur_to_events",
         "🛡 SAVIOR",        "savior",         "0 SAVIOR"),
        # Filters formerly SQL-only; now backed by player_death event flags via dp2
        ("kill_mod_wall_bang",      "_wall_bang_dp2_filter",       "_apply_wall_bang_dp2_to_events",
         "🧱 WALLBANG",      "wallbang",       "0 WALLBANG"),
        ("kill_mod_airborne",       "_airborne_dp2_filter",        "_apply_airborne_dp2_to_events",
         "🪂 AIRBORNE",      "airborne",       "0 AIRBORNE"),
        ("kill_mod_attacker_blind", "_attacker_blind_dp2_filter",  "_apply_attacker_blind_dp2_to_events",
         "😵 BLIND FIRE",    "blind fire",     "0 BLIND FIRE"),
        ("kill_mod_collateral",     "_collateral_dp2_filter",      "_apply_collateral_dp2_to_events",
         "🎯 COLLATERAL",    "collateral",     "0 COLLATERAL"),
    ]

    def _apply_dp2_modifiers(self, dp, events, cfg):
        """Apply active demoparser2 kill modifiers for one demo (batch worker path).

        Logic mode (cfg["kill_mod_logic_dp2"]):
          "any"   (OR):    a kill passes if it satisfies at least one active filter.
          "all"   (AND):   a kill must pass every active filter.
          "mixed":         required filters must ALL match AND at least one optional matches.
        TROIS TAP always exclusive. Derived from _DP2_FILTER_DEFS.
        Returns filtered events or None if no kills remain.
        """
        if cfg.get("kill_mod_trois_tap"):
            n_before = _count_kills(events)
            events   = self._trois_tap_filter(dp, events, cfg)
            n_after  = _count_kills(events)
            self._alog(f"  🎯🎲 TROIS TAP : {n_before} kills → {n_after} TROIS TAP", "info")
            if not events:
                self._alog("  ⏭ SKIP: 0 TROIS TAP in this demo", "dim")
                return None
            self._stamp_mf(events, "kill_mod_trois_tap")
            return events

        if cfg.get("kill_mod_no_trois_shot"):
            n_before = _count_kills(events)
            events = self._no_trois_shot_filter(dp, events, cfg)
            n_after = _count_kills(events)
            self._alog(f"  🚫🎲 Exclude : {n_before} kills → {n_after} precise", "info")
            if not events:
                self._alog("  ⏭ SKIP: 0 precise kills after Exclude in this demo", "dim")
                return None
            self._stamp_mf(events, "kill_mod_no_trois_shot")

        active = [(k, getattr(self, fn), ll, rl, sl)
                  for k, fn, _afn, ll, rl, sl in self._DP2_FILTER_DEFS
                  if cfg.get(k) and k != "kill_mod_no_trois_shot"]
        if not active:
            return events

        logic = cfg.get("kill_mod_logic_dp2", "any")

        if logic == "all":
            for cfg_key, filter_fn, log_label, result_label, skip_label in active:
                n_before = _count_kills(events)
                events   = filter_fn(dp, events, cfg)
                n_after  = _count_kills(events)
                self._alog(f"  {log_label} : {n_before} kills → {n_after} {result_label}", "info")
                if not events:
                    self._alog(f"  ⏭ SKIP: {skip_label} in this demo", "dim")
                    return None
                self._stamp_mf(events, cfg_key)
            return events

        def _run_or(filters):
            """Run filters independently on original events, return sig→keys union."""
            non_kill = [e for e in events if e.get("type") != "kill"]
            s2k: dict = {}
            for cfg_key, filter_fn, log_label, result_label, _ in filters:
                n_before = _count_kills(events)
                passed   = filter_fn(dp, events, cfg)
                n_after  = _count_kills(passed)
                self._alog(f"  {log_label} : {n_before} kills → {n_after} {result_label}", "info")
                for e in passed:
                    if e.get("type") == "kill":
                        sig = (e["tick"], str(e.get("killer_sid", "")))
                        s2k.setdefault(sig, set()).add(cfg_key)
            return s2k, non_kill

        def _run_and(filters):
            """Chain filters, return surviving event list."""
            evts = list(events)
            for cfg_key, filter_fn, log_label, result_label, skip_label in filters:
                n_before = _count_kills(evts)
                evts = filter_fn(dp, evts, cfg)
                n_after = _count_kills(evts)
                self._alog(f"  {log_label} : {n_before} kills → {n_after} {result_label}", "info")
                if not evts:
                    self._alog(f"  ⏭ SKIP: {skip_label} in this demo", "dim")
                    return None
                self._stamp_mf(evts, cfg_key)
            return evts

        if logic == "mixed":
            active_keys = [k for k, *_ in active]
            req_keys, opt_keys = self._split_required_optional(cfg, active_keys)
            req_active = [(k, fn, ll, rl, sl) for k, fn, ll, rl, sl in active if k in req_keys]
            opt_active = [(k, fn, ll, rl, sl) for k, fn, ll, rl, sl in active if k in opt_keys]

            # Required: all must pass → AND chain
            if req_active:
                req_events = _run_and(req_active)
                if req_events is None:
                    return None
                req_sigs = frozenset((e["tick"], str(e.get("killer_sid", "")))
                                     for e in req_events if e.get("type") == "kill")
            else:
                req_sigs = None

            # Optional: at least one → OR union
            if opt_active:
                opt_s2k, non_kill = _run_or(opt_active)
                opt_sigs = frozenset(opt_s2k.keys())
            else:
                opt_s2k, non_kill = {}, [e for e in events if e.get("type") != "kill"]
                opt_sigs = None

            # Combine: intersect required and optional sig sets
            if req_sigs is not None and opt_sigs is not None:
                keep_sigs = req_sigs & opt_sigs
            elif req_sigs is not None:
                keep_sigs = req_sigs
            elif opt_sigs is not None:
                keep_sigs = opt_sigs
            else:
                keep_sigs = frozenset()

            # Build merged _mf: stamp req keys + optional matched keys
            kept_kills = []
            for e in events:
                if e.get("type") != "kill":
                    continue
                sig = (e["tick"], str(e.get("killer_sid", "")))
                if sig in keep_sigs:
                    all_matched = set(req_keys)
                    all_matched |= opt_s2k.get(sig, set())
                    mf = e.get("_mf")
                    e["_mf"] = (mf | all_matched) if mf else set(all_matched)
                    kept_kills.append(e)
            result = kept_kills + non_kill
            if not result:
                self._alog("  ⏭ SKIP: 0 kills after dp2 MIXED filters in this demo", "dim")
                return None
            return result

        else:  # "any" — OR
            s2k, non_kill = _run_or(active)
            include_mod_or = self._mods_dp2_global_any_union_enabled(cfg)
            mod_sig_to_keys = {}
            if include_mod_or:
                mod_keys = set(self._SQL_MOD_KEYS)
                for e in events:
                    if e.get("type") != "kill":
                        continue
                    matched_mods = (e.get("_mf") or set()) & mod_keys
                    if not matched_mods:
                        continue
                    sig = (e["tick"], str(e.get("killer_sid", "")))
                    ex = mod_sig_to_keys.get(sig)
                    mod_sig_to_keys[sig] = (ex | matched_mods) if ex else set(matched_mods)
            kill_sigs_union = set(s2k.keys())
            if mod_sig_to_keys:
                kill_sigs_union |= set(mod_sig_to_keys.keys())
            kept_kills = []
            for e in events:
                if e.get("type") != "kill":
                    continue
                sig = (e["tick"], str(e.get("killer_sid", "")))
                if sig in kill_sigs_union:
                    matched = set(s2k.get(sig, set()))
                    if mod_sig_to_keys:
                        matched |= mod_sig_to_keys.get(sig, set())
                    if matched:
                        mf = e.get("_mf")
                        e["_mf"] = (mf | matched) if mf else set(matched)
                    kept_kills.append(e)
            result = kept_kills + non_kill
            if not result:
                self._alog("  ⏭ SKIP: 0 kills after dp2 OR filters in this demo", "dim")
                return None
            return result

    def _apply_dp2_filters_to_events(self, evts, cfg):
        """Apply active dp2 modifiers to a full {demo_path: events} dict (preview/redo path).

        Logic mode (cfg["kill_mod_logic_dp2"]): "any" | "all" | "mixed".
        TROIS TAP always exclusive. Derived from _DP2_FILTER_DEFS.
        _mf stamped on all surviving kill events via _apply_filter_to_events.
        Returns a new dict with empty-demo entries removed.
        """
        if cfg.get("kill_mod_trois_tap"):
            self._alog("  🎯🎲 TROIS TAP — analyzing demos…", "info")
            return self._apply_trois_tap_to_events(evts, cfg)

        if cfg.get("kill_mod_no_trois_shot"):
            self._alog("  🚫🎲 Exclude — analyzing demos…", "info")
            evts = self._apply_no_trois_shot_to_events(evts, cfg)
            if not evts:
                return {}

        active = [(k, getattr(self, afn), ll)
                  for k, _fn, afn, ll, _rl, _sl in self._DP2_FILTER_DEFS
                  if cfg.get(k) and k != "kill_mod_no_trois_shot"]
        if not active:
            return evts

        logic = cfg.get("kill_mod_logic_dp2", "any")
        include_mod_or = self._mods_dp2_global_any_union_enabled(cfg)

        def _chain(filters, src):
            """AND-chain: each apply_fn narrows the dict further."""
            result = src
            for cfg_key, apply_fn, log_label in filters:
                self._alog(f"  {log_label} — analyzing demos…", "info")
                result = apply_fn(result, cfg)
            return result

        def _union(filters, src):
            """OR-union: run each independently, merge _mf per sig."""
            per = []
            for cfg_key, apply_fn, log_label in filters:
                self._alog(f"  {log_label} — analyzing demos…", "info")
                per.append((cfg_key, apply_fn(src, cfg)))

            all_demos: set = set()
            for _, r in per:
                all_demos |= set(r.keys())
            if include_mod_or:
                all_demos |= set(src.keys())

            merged = {}
            for dp in all_demos:
                sig_to_mf: dict = {}
                if include_mod_or:
                    mod_keys = set(self._SQL_MOD_KEYS)
                    for e in src.get(dp, []):
                        if e.get("type") != "kill":
                            continue
                        matched_mods = (e.get("_mf") or set()) & mod_keys
                        if not matched_mods:
                            continue
                        sig = (e["tick"], str(e.get("killer_sid", "")))
                        ex = sig_to_mf.get(sig)
                        sig_to_mf[sig] = (ex | matched_mods) if ex else set(matched_mods)
                for _ck, r in per:
                    for e in r.get(dp, []):
                        if e.get("type") == "kill":
                            sig = (e["tick"], str(e.get("killer_sid", "")))
                            ex = sig_to_mf.get(sig)
                            sig_to_mf[sig] = (ex | e["_mf"]) if ex else set(e.get("_mf") or set())
                kill_sigs = set(sig_to_mf.keys())
                original = src.get(dp, [])
                non_kill = [e for e in original if e.get("type") != "kill"]
                kept = []
                for e in original:
                    if e.get("type") != "kill":
                        continue
                    sig = (e["tick"], str(e.get("killer_sid", "")))
                    if sig in kill_sigs:
                        mf = sig_to_mf.get(sig)
                        if mf:
                            e["_mf"] = (e["_mf"] | mf) if e.get("_mf") else set(mf)
                        kept.append(e)
                if kept or non_kill:
                    merged[dp] = kept + non_kill
            return merged

        if logic == "all":
            return _chain(active, evts)

        if logic == "mixed":
            active_keys = [k for k, *_ in active]
            req_keys, opt_keys = self._split_required_optional(cfg, active_keys)
            req_active = [(k, fn, ll) for k, fn, ll in active if k in req_keys]
            opt_active = [(k, fn, ll) for k, fn, ll in active if k in opt_keys]

            req_result = _chain(req_active, evts) if req_active else None
            opt_result = _union(opt_active, evts) if opt_active else None

            if req_result is None and opt_result is None:
                return evts
            if req_result is None:
                return opt_result
            if opt_result is None:
                return req_result

            # Intersect: keep demos and kills present in BOTH results
            merged = {}
            for dp in set(req_result.keys()) & set(opt_result.keys()):
                req_sigs = frozenset((e["tick"], str(e.get("killer_sid", "")))
                                     for e in req_result.get(dp, []) if e.get("type") == "kill")
                original = evts.get(dp, [])
                non_kill = [e for e in original if e.get("type") != "kill"]
                kept = []
                opt_sig_mf = {
                    (e["tick"], str(e.get("killer_sid", ""))): e.get("_mf") or set()
                    for e in opt_result.get(dp, []) if e.get("type") == "kill"
                }
                for e in original:
                    if e.get("type") != "kill":
                        continue
                    sig = (e["tick"], str(e.get("killer_sid", "")))
                    if sig in req_sigs and sig in opt_sig_mf:
                        combined_mf = set(req_keys) | opt_sig_mf.get(sig, set())
                        e["_mf"] = (e["_mf"] | combined_mf) if e.get("_mf") else combined_mf
                        kept.append(e)
                if kept or non_kill:
                    merged[dp] = kept + non_kill
            return merged

        # "any" — OR
        return _union(active, evts)

    def _worker(self, cfg):
        cli = self._resolve_cli(cfg["csdm_exe"])
        self._alog(f"CLI: {cli}", "dim")
        if not os.path.isfile(cli):
            w = shutil.which(cli)
            if w:
                cli = w
            else:
                self._alog(f"CLI not found: {cli}", "err")
                self.after(0, self._reset_btns)
                return
        player_str = self._player_str(cfg)
        tv = cfg.get("true_view", True)
        tag_name = cfg.get("tag_on_export", "")
        tag_enabled = cfg.get("tag_enabled", False) and bool(tag_name)
        perspective = cfg.get("perspective", "killer")
        self._alog(f"Player(s): {player_str}", "info")
        self._alog(f"Video: {cfg['width']}x{cfg['height']}@{cfg['framerate']}fps CRF={cfg['crf']} {cfg['video_codec']} {cfg['video_container']}", "info")
        tag_str = f" | Tag: \U0001f3f7 {tag_name}" if tag_enabled else ""
        recsys = cfg.get("recsys", "HLAE")
        hlae_info = ""
        if recsys == "HLAE":
            fov = cfg.get("hlae_fov", 90)
            sm = cfg.get("hlae_slow_motion", 100)
            hlae_info = f" | FOV:{fov}"
            if int(sm) != 100:
                hlae_info += f" Slow:{sm}%"
            if cfg.get("hlae_fix_scope_fov", True):
                hlae_info += " | ScopeFOV:fix"
            # Non-default physics
            phys_parts = []
            rg = cfg.get("phys_ragdoll_gravity", 600)
            if int(rg) != 600:   phys_parts.append(f"RagGrav:{rg}")
            sg = cfg.get("phys_sv_gravity", 800)
            if int(sg) != 800:   phys_parts.append(f"Grav:{sg}")
            rs = cfg.get("phys_ragdoll_scale", "1.0")
            if float(rs) != 1.0: phys_parts.append(f"RagScale:{rs}")
            if not cfg.get("phys_ragdoll_enable", True): phys_parts.append("NoRagdoll")
            if not cfg.get("phys_blood", True):          phys_parts.append("NoBlood")
            if not cfg.get("phys_dynamic_lighting", True): phys_parts.append("NoDynLight")
            if phys_parts:
                hlae_info += f" | Phys: {' '.join(phys_parts)}"
        self._alog(f"Encoder: {cfg['encoder']} | RecSys: {recsys}{hlae_info} | TrueView: {'ON' if tv else 'OFF'} | Perspective: {PERSP_LABELS.get(perspective, perspective)}{tag_str}", "info")
        if recsys == "CS":
            _shared = self._common_cs2_injection(cfg)
            self._inject_cs_runtime_cfg(cfg, _shared)
            self._alog(
                "  ⚠ RecSys CS: CS2 replays the demo from tick 0 to reach the target tick.\n"
                "  Each clip will take as long as the full demo before the event.\n"
                "  HLAE is strongly recommended for batch recording.", "warn")
        _hsm = cfg.get("headshots_mode", "all")
        if _hsm == "only":
            self._alog("🎯 Headshots only", "info")
        elif _hsm == "exclude":
            self._alog("🎯 Headshots excluded", "info")
        if not cfg.get("include_suicides", True):
            self._alog("🚫 Suicides excluded", "info")
        _tkm = cfg.get("teamkills_mode", "include")
        if _tkm == "exclude":
            self._alog("🚫 Teamkills excluded", "info")
        elif _tkm == "only":
            self._alog("⚔ Teamkills only", "info")
        batch_start = time.time()
        _df = cfg.get("date_from", "")
        _dt = cfg.get("date_to", "")
        if _df or _dt:
            self._alog(f"Date filter: {_df or '∞'}  →  {_dt or '∞'}", "info" if self._date_col else "warn")
        self._alog("Querying DB...", "info")
        t0_query = time.time()
        try:
            all_events = self._query_events(cfg)
        except Exception as e:
            self._alog(f"Error: {e}", "err")
            self.after(0, self._reset_btns)
            return
        t_query = time.time() - t0_query
        if not all_events:
            self._alog("No events.", "warn")
            self.after(0, lambda: self._summary_lbl.config(text="  No clips found.", fg=MUTED))
            self.after(0, self._reset_btns)
            return
        te = sum(len(e) for e in all_events.values())
        # Compute summary once (reused at the end)
        _nd, _nc, _ts, _as = self._calc_summary(all_events, cfg)
        _stxt = self._fmt_summary(_nd, _nc, _ts, _as)
        self.after(0, lambda t=_stxt: self._summary_lbl.config(text=t + "  [running…]", fg=YELLOW))
        self._alog(f"OK: {len(all_events)} demo(s), {te} events  ⏱ DB {t_query*1000:.0f}ms", "ok")
        self._alog("-" * 56, "dim")

        order = cfg.get("clip_order", "chrono")
        # Apply demo picker filter — only keep demos checked in the picker
        _picker_active = self._demo_picker_get_active()
        if _picker_active is not None:
            _picker_set = set(_picker_active)
            _before = len(all_events)
            all_events = {dp: evts for dp, evts in all_events.items()
                          if dp in _picker_set}
            _removed = _before - len(all_events)
            if _removed:
                self._alog(f"  ⚙ Demo picker: {_removed} demo(s) excluded by manual selection", "dim")
        if order == "random":
            items = list(all_events.items())
            random.shuffle(items)
            demo_list = items
            self._alog("Order: Random 🎲", "info")
        else:
            demo_list = sorted(all_events.items(), key=lambda kv: self._demo_sort_key(kv[0]))
            self._alog("Order: Chronological", "info")

        ok = fail = skip = retried = tagged = 0
        summary = []
        produced_dirs = []   # output dirs of successful demos (for assembly)

        # ── Signature-based DP2 pre-parse (cache preserved if same demo set) ──
        self._preparse_dp2(cfg, [dp for dp, _ in demo_list])
        # ─────────────────────────────────────────────────────────────────────

        skip_already_tagged = False   # True = skip already-tagged demos
        _already_tagged_paths = set() # paths of already-tagged demos
        if tag_enabled:
            ts = self._tags_schema
            jt       = ts.get("junction_table")
            jt_tag   = ts.get("jt_tag_col")
            jt_match = ts.get("jt_match_col")
            tag_id   = next((tid for tid, tn, _ in self._tags_list if tn == tag_name), None)
            mkm      = self._find_col("matches", ["checksum", "id", "match_id"])
            dc       = self._find_col("matches", ["demo_path", "demo_file_path",
                                                   "demo_filepath", "share_code",
                                                   "file_path", "path"])
            if jt and jt_tag and jt_match and tag_id and mkm and dc:
                try:
                    conn = self._pg_fresh()
                    with conn.cursor() as cur:
                        # Fetch all checksums already associated with this tag
                        cur.execute(
                            f'SELECT "{jt_match}" FROM "{jt}" WHERE "{jt_tag}"=%s',
                            (tag_id,))
                        tagged_checksums = {r[0] for r in cur.fetchall()}
                    conn.close()
                    # Map demo paths to their checksums
                    for dp, _ in demo_list:
                        chk = self._get_demo_checksum(dp)
                        if chk and chk in tagged_checksums:
                            _already_tagged_paths.add(dp)
                except Exception:
                    pass

            if _already_tagged_paths:
                n_already = len(_already_tagged_paths)
                # Ask the user — must run on the main thread
                # Yes = include anyway, No = ignore, Cancel = stop and redo preview
                _ev = threading.Event()
                _choice = [None]  # True = include, False = ignore, None = cancel

                def _ask_user(n=n_already, names=[]):
                    lines = "\n".join(f"  • {nm}" for nm in names[:5])
                    ellipsis = "\n  …" if n > 5 else ""
                    msg = (
                        f"{n}/{len(demo_list)} demo(s) already have tag \"{tag_name}\":\n"
                        f"{lines}{ellipsis}\n\n"
                        f"[Yes] Include anyway\n"
                        f"[No] Ignore\n"
                        f"[Cancel] Stop and redo preview without them"
                    )
                    res = messagebox.askyesnocancel(
                        "Already tagged demos",
                        msg,
                        default="no"
                    )
                    _choice[0] = res  # True = include, False = ignore, None = cancel
                    _ev.set()

                demo_names = [Path(dp).name for dp, _ in demo_list if dp in _already_tagged_paths]
                self.after(0, lambda: _ask_user(n_already, demo_names))
                _ev.wait()
                choice = _choice[0]
                if choice is None:
                    # Cancel → redo preview without already-tagged demos
                    filtered_events = {dp: ev for dp, ev in all_events.items()
                                       if dp not in _already_tagged_paths}
                    self._alog(f"  ⏭ Cancelled — preview restarted without {n_already} already-tagged demo(s)", "info")
                    def _redo():
                        self._log(f"\n{'─' * 60}", "dim")
                        self._log(f"  PREVIEW (without already tagged)  —  {datetime.now().strftime('%H:%M:%S')}", "info")
                        self._log(f"{'─' * 60}", "dim")
                        self._summary_lbl.config(text="  Computing…", fg=YELLOW)
                        # Run DP2 filters in background thread for the redo preview too
                        _fe = filtered_events
                        def _bg():
                            nonlocal _fe
                            # Pre-parse (no-op if already cached from the previous preview)
                            self._preparse_dp2(cfg, list(_fe.keys()))
                            # Apply dp2 modifiers via shared helper (handles AND/OR logic)
                            _fe = self._apply_dp2_filters_to_events(_fe, cfg)
                            self.after(0, lambda: self._show_preview(_fe, cfg))
                        threading.Thread(target=_bg, daemon=True).start()
                    self.after(0, _redo)
                    self.after(0, self._reset_btns)
                    return
                elif choice is True:
                    skip_already_tagged = False
                    self._alog(f"  ▶ {n_already} already-tagged demo(s) → included anyway", "info")
                else:
                    skip_already_tagged = True
                    self._alog(f"  ⏭ {n_already} already-tagged demo(s) → ignored", "info")

        for i, (dp, events) in enumerate(demo_list, 1):
            if self._stop_after_current or not self._running:
                for j in range(i - 1, len(demo_list)):
                    summary.append((Path(demo_list[j][0]).name, "SKIP", 0, 0, "Stop"))
                    skip += 1
                break

            # Skip already-tagged demos if the user chose to ignore them
            if skip_already_tagged and dp in _already_tagged_paths:
                dn_skip = Path(dp).name
                self._alog(f"  ⏭ SKIP (already tagged): {dn_skip}", "dim")
                summary.append((Path(dp).name, "SKIP", 0, 0, "Already tagged"))
                skip += 1
                continue

            # ── demoparser2 kill modifiers ─────────────────────────────────────
            t0_dp2 = time.time()
            events = self._apply_dp2_modifiers(dp, events, cfg)
            t_dp2 = time.time() - t0_dp2
            if events is None:
                summary.append((Path(dp).name, "SKIP", 0, 0, "0 kills after filter"))
                skip += 1
                continue

            # Clutch clip_mode="full": rebuild sequences spanning whole clutch groups
            t0_seq = time.time()
            if (cfg.get("events_clutch") and
                    cfg.get("clutch_clip_mode", "full") == "full"):
                clutch_groups = {}
                for evt in events:
                    gid = evt.get("clutch_group")
                    if gid is not None:
                        clutch_groups.setdefault(gid, []).append(evt)
                non_clutch = [e for e in events if e.get("clutch_group") is None]
                seqs = []
                if non_clutch:
                    seqs = self._build_sequences(
                        non_clutch, cfg["tickrate"],
                        self._effective_before(cfg), cfg["after"])
                if clutch_groups:
                    seqs += self._build_clutch_sequences(
                        list(clutch_groups.values()), cfg["tickrate"],
                        self._effective_before(cfg), cfg["after"])
                seqs.sort(key=lambda s: s["start_tick"])
            else:
                seqs = self._build_sequences(
                    events, cfg["tickrate"],
                    self._effective_before(cfg), cfg["after"])
            t_seq = time.time() - t0_seq
            if not seqs:
                continue
            dn = Path(dp).name
            ad = os.path.abspath(dp)
            date_str = self._format_demo_date(dp)
            self.after(0, lambda lbl=f"{i}/{len(demo_list)}":
                       self.progress_lbl.config(text=lbl))
            _timing_str = ""
            if t_dp2 > 0.01 or t_seq > 0.001:
                _parts = []
                if t_dp2 > 0.01:
                    _parts.append(f"dp2 {t_dp2*1000:.0f}ms")
                if t_seq > 0.001:
                    _parts.append(f"seq {t_seq*1000:.1f}ms")
                _timing_str = f"  ⏱ {' '.join(_parts)}"
            self._emit_demo_log_entry(
                date_str=date_str,
                demo_name=dn,
                events=events,
                seq_count=len(seqs),
                cfg=cfg,
                idx=i,
                total=len(demo_list),
                timing_str=_timing_str,
                async_emit=True,
            )
            if not os.path.isfile(ad):
                self._alog(f"  SKIP: {ad}", "warn")
                summary.append((dn, "SKIP", 0, 0, "Not found"))
                skip += 1
                continue

            cj = self._build_json(dp, seqs, cfg)

            # ── Extended logging ───────────────────────────────────────────────
            tickrate = cfg.get("tickrate", 64)
            for si, seq in enumerate(seqs, 1):
                dur_ticks = seq["end_tick"] - seq["start_tick"]
                dur_s = dur_ticks / tickrate if tickrate else 0
                self._alog(
                    f"  seq {si}/{len(seqs)}  tick {seq['start_tick']}→{seq['end_tick']}"
                    f"  ({dur_s:.1f}s)", "dim")
            self._alog(
                f"  RecSys: {cfg.get('recsys','HLAE')} | "
                f"TrueView: {'ON' if cfg.get('true_view') else 'OFF'} | "
                f"Concat: {'ON' if cfg.get('concatenate_sequences') else 'OFF'}",
                "dim")
            if cj.get("hlaeOptions"):
                ho = cj["hlaeOptions"]
                parts = []
                if "mirv_fov" in ho:         parts.append(f"FOV={ho['mirv_fov']}")
                if "host_timescale" in ho:   parts.append(f"Slow={ho['host_timescale']}")
                if ho.get("afxStream"):      parts.append("AFX")
                if ho.get("hideSpectatorUi"):parts.append("NoUI")
                if ho.get("extraArgs"):      parts.append(f"args={ho['extraArgs'][:60]}")
                if parts:
                    self._alog(f"  HLAE: {' | '.join(parts)}", "dim")
            # ──────────────────────────────────────────────────────────────────

            try:
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix="csdm_",
                                                   delete=False, encoding="utf-8")
                json.dump(cj, tmp, indent=2, ensure_ascii=False)
                tmp.close()
                tp = tmp.name
            except Exception as e:
                summary.append((dn, "FAIL", 0, 0, str(e)))
                fail += 1
                continue

            self._alog(f"  JSON: {tp}", "dim")
            cmd = [cli, "video", "--config-file", tp]
            self._alog(f"  CMD: {' '.join(cmd)}", "dim")

            mx = 1 + cfg.get("retry_count", 2)
            att = 0
            d_ok = False
            d_err = ""
            t0 = time.time()
            while att < mx:
                if self._stop_after_current and att > 0:
                    break
                att += 1
                if att > 1:
                    retried += 1
                    delay = cfg.get("retry_delay", 15)
                    self._alog(f"  ↻ Retry {att - 1} — {delay}s...", "warn")
                    for _ in range(delay):
                        if not self._running:
                            break
                        time.sleep(1)
                    if not self._running:
                        break
                success, rc, errs, retryable = self._exec(cmd)
                if success:
                    d_ok = True
                    break
                d_err = errs[0] if errs else f"code {rc}"
                if retryable and att < mx:
                    continue
                break

            dur = time.time() - t0
            threading.Thread(
                target=lambda p=tp: (time.sleep(10), os.unlink(p))
                if os.path.exists(p) else None, daemon=True).start()

            if d_ok:
                ds = fmt_duration(dur)
                ri = f" x{att}" if att > 1 else ""
                tag_msg = ""
                if tag_enabled:
                    _auto_names = self._get_active_tag_names() if self._get_active_tag_names() else ([tag_name] if tag_name else [])
                    _tag_ok_names, _tag_fail = [], ""
                    for _tn in _auto_names:
                        _tok, _terr = self._tag_demo(dp, _tn)
                        if _tok:
                            _tag_ok_names.append(_tn)
                            self._tagged_this_batch.append((dp, _tn))
                        elif not _tag_fail:
                            _tag_fail = _terr
                    if _tag_ok_names:
                        tagged += 1
                        tag_msg = f" \U0001f3f7 {', '.join(_tag_ok_names)}"
                    if _tag_fail:
                        tag_msg += f" \U0001f3f7 FAILED: {_tag_fail}"
                self.after(0, lambda d=ds, r=ri, tm=tag_msg:
                           self._log(f"  ✓ OK [{d}]{r}{tm}", "ok"))
                summary.append((dn, "OK", dur, att, ""))
                produced_dirs.append(cj.get("outputFolderPath", ""))
                ok += 1
            else:
                ds = fmt_duration(dur)
                self.after(0, lambda d=ds, e=d_err:
                           self._log(f"  ✗ FAILED [{d}] {e}", "err"))
                summary.append((dn, "FAIL", dur, att, d_err))
                fail += 1

            if i < len(demo_list) and not self._stop_after_current:
                delay = cfg.get("delay_between_demos", 3)
                if delay > 0:
                    self._alog(f"  Pause {delay}s...", "dim")
                    for _ in range(delay):
                        if self._stop_after_current:
                            break
                        time.sleep(1)

        bd = time.time() - batch_start
        self._alog("\n" + "═" * 60, "dim")
        self._alog("  SUMMARY", "info")
        self._alog("═" * 60, "dim")
        for n, st, d, a, e in summary:
            ds = fmt_duration(d) if d > 0 else "-"
            rs = f" x{a}" if a > 1 else ""
            if st == "OK":
                self.after(0, lambda n=n, d=ds, r=rs:
                           self._log(f"  ✓ {n} [{d}]{r}", "ok"))
            elif st == "SKIP":
                self.after(0, lambda n=n, e=e:
                           self._log(f"  ⏭ {n} {e}", "warn"))
            else:
                self.after(0, lambda n=n, d=ds, e=e, r=rs:
                           self._log(f"  ✗ {n} [{d}]{r} {e}", "err"))
        self._alog("─" * 60, "dim")
        tag_summary = f" Tagged:{tagged}" if tag_enabled else ""
        self._alog(f"  OK:{ok} Failed:{fail} Skip:{skip} Retries:{retried}{tag_summary} Duration:{fmt_duration(bd)}", "info")
        self._alog("═" * 60, "dim")
        self.after(0, lambda: self.progress_lbl.config(
            text=f"{ok}/{len(demo_list)} OK ({fmt_duration(bd)})"))
        # Final summary — reuse the summary computed before the loop
        _color = GREEN if fail == 0 else (YELLOW if ok > 0 else RED)
        _status = f"  ✓ {ok}/{len(demo_list)} demos OK" if fail == 0 else f"  ⚠ {ok} OK / {fail} failed"
        _stxt_final = self._fmt_summary(_nd, _nc, _ts, _as) + f"  —  {fmt_duration(bd)}{_status}"
        self.after(0, lambda t=_stxt_final, c=_color: self._summary_lbl.config(text=t, fg=c))

        if ok > 0 and cfg.get("assemble_after") and not self._kill_triggered:
            self._alog("\n⚙  Final assembly in progress...", "info")
            try:
                self._assemble_clips(cfg, produced_dirs)
            except Exception as e:
                self._alog(f"  Assembly error: {e}", "err")
        elif self._kill_triggered and cfg.get("assemble_after"):
            self._alog("\n⏭ Assembly skipped (batch killed).", "warn")

        # ── Tag rollback on premature stop ────────────────────────────────────
        _was_interrupted = self._kill_triggered or (self._stop_after_current and ok < len(demo_list))
        if _was_interrupted and self._tagged_this_batch and tag_enabled:
            self._alog(f"\n↩ Rolling back {len(self._tagged_this_batch)} tag(s)…", "warn")
            _rolled_back, _rb_fail = 0, 0
            for _dp, _tn in self._tagged_this_batch:
                try:
                    conn = self._pg()
                    chk = self._demo_checksums.get(_dp)
                    if not chk:
                        _rb_fail += 1
                        continue
                    with conn.cursor() as cur:
                        # Find tag id by name
                        cur.execute("SELECT id FROM tags WHERE name = %s LIMIT 1", (_tn,))
                        row = cur.fetchone()
                        if not row:
                            _rb_fail += 1
                            continue
                        tag_id = row[0]
                        cur.execute(
                            "DELETE FROM checksum_tags WHERE checksum = %s AND tag_id = %s",
                            (chk, tag_id))
                        conn.commit()
                        _rolled_back += 1
                except Exception as _e:
                    _rb_fail += 1
            msg = f"  ↩ Rolled back {_rolled_back} tag(s)"
            if _rb_fail:
                msg += f" ({_rb_fail} failed)"
            self._alog(msg, "warn")
        self._tagged_this_batch = []

        self.after(0, self._reset_btns)

if __name__ == "__main__":
    App().mainloop()
