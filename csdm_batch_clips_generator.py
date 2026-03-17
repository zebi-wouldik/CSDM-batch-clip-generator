#!/usr/bin/env python3
"""CSDM Batch Clips Generator v79"""


import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
import subprocess, threading, json, os, tempfile, time, shutil, re, uuid, random
import bisect, concurrent.futures
from collections import defaultdict
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
APP_VERSION = "v79"

# ═══════════════════════════════════════════════════════
#  Theme
# ═══════════════════════════════════════════════════════
BG, BG2, BG3 = "#0e0e0e", "#141414", "#1a1a1a"
BORDER = "#252525"
ORANGE, ORANGE2 = "#22c55e", "#16a34a"
TEXT, MUTED = "#e0e0e0", "#999999"
GREEN, RED, YELLOW, BLUE = "#86efac", "#f87171", "#fde68a", "#93c5fd"
DESC_COLOR = "#888888"
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

EVENTS = ["Kills", "Deaths", "Rounds"]
ENCODER_OPTIONS = ["FFmpeg", "VirtualDub"]
RECSYS_OPTIONS = ["HLAE", "CS"]
REC_OUTPUT_OPTIONS = ["video", "images", "images_and_video"]
VIDEO_CONTAINERS = ["mp4", "avi", "mkv", "mov", "webm"]
PERSP_LABELS = {"killer": "POV Killer", "victim": "POV Victim", "both": "Both"}

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
# CSDM display names eligible (all variants, lowercase) for UI filter
TROIS_SHOT_ELIGIBLE_LOWER = set(CSDM_TO_DP2_WEAPON.keys())

# Tick window for demoparser2 shot matching (~1 second at CS2 64 tick/s)
DP2_TICK_WINDOW = 128

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
    "steam_id": "", "player_name": "",
    "events": ["Kills"], "weapons": [],
    "date_from": "", "date_to": "",
    "before": 3, "after": 5,
    "encoder": "FFmpeg", "recsys": "HLAE",
    "recording_output": "video", "tickrate": 64,
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
    # Headshot filter
    "headshots_only": False,
    "teamkills_mode": "include",
    "include_suicides": True,   # include suicides (weapon world/suicide/world_entity)
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
    # Sequence options
    "show_xray": True,
    # Encoding preset (libx264/libx265/libsvtav1 only — no effect on GPU)
    "video_preset": "medium",
    # HLAE options (used when recsys == "HLAE")
    "hlae_fov": 90,
    "hlae_slow_motion": 100,   # % of speed : 100 = normal, 50 = half-speed
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
               "perspective", "victim_pre_s", "headshots_only", "include_suicides", "teamkills_mode",
               "kill_mod_through_smoke", "kill_mod_no_scope", "kill_mod_wall_bang",
               "kill_mod_airborne", "kill_mod_assisted_flash", "kill_mod_collateral",
               "kill_mod_trois_shot", "kill_mod_no_trois_shot", "kill_mod_trois_tap",
               "kill_mod_one_tap",
               "clip_order", "show_xray"],
    "video": ["encoder", "recsys", "recording_output", "width", "height", "framerate",
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
            cfg = DEFAULT_CONFIG.copy(); cfg.update(saved); return cfg
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
        tk.Button(br, text="Picker systeme...", font=FONT_SM, bg=BG3, fg=BLUE, relief="flat",
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
        self._all_players   = []          # [(label, sid, name), …] — base BDD
        self._filtered      = []
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
            self._active_lbl.config(
                text="⚠  No active account — check a player above.",
                fg=RED)
        elif n == 1:
            sid = next(iter(self._active_sids))
            name = self._active_names.get(sid, sid)
            self._active_lbl.config(
                text=f"Actif : {name}  ({sid})", fg=GREEN)
        else:
            names = ", ".join(self._active_names.get(s, s) for s in sorted(self._active_sids))
            self._active_lbl.config(
                text=f"{n} active: {names}", fg=GREEN)

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

    def _refresh(self, query=""):
        q = query.strip().lower()
        self._lb.delete(0, "end")
        self._filtered = []
        for label, sid, name in self._all_players:
            if not q or q in label.lower() or q in sid.lower():
                self._lb.insert("end", label)
                self._filtered.append((label, sid, name))

    def _on_lb_select(self, *_):
        sel = self._lb.curselection()
        if not sel or sel[0] >= len(self._filtered):
            return
        label, sid, name = self._filtered[sel[0]]
        self._lb_label, self._lb_sid, self._lb_name = label, sid, name
        self._lb_sel_lbl.config(
            text=f"Selected: {name}  ({sid})  ← ★ to register",
            fg=YELLOW)

    def _select_by_label(self, label):
        for i, (l, sid, name) in enumerate(self._filtered):
            if l == label:
                self._lb.selection_clear(0, "end")
                self._lb.selection_set(i)
                self._lb.see(i)
                self._lb_label, self._lb_sid, self._lb_name = label, sid, name
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
            cb.config(bg=ORANGE2, fg="white",
                      activebackground=ORANGE, activeforeground="white",
                      selectcolor=ORANGE2)
        else:
            cb.config(bg=BG3, fg=MUTED,
                      activebackground=BG3, activeforeground=ORANGE,
                      selectcolor=BG3)
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
            rb.config(bg=ORANGE2, fg="white",
                      activebackground=ORANGE, activeforeground="white",
                      selectcolor=ORANGE2)
        else:
            rb.config(bg=BG3, fg=MUTED,
                      activebackground=BG3, activeforeground=ORANGE,
                      selectcolor=BG3)
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

# ═══════════════════════════════════════════════════════
#  App
# ═══════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"CSDM Batch {APP_VERSION}")
        self.configure(bg=BG)
        self.geometry("1600x900")
        self.minsize(1000, 600)
        self.option_add('*TCombobox*Listbox.background', BG3)
        self.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.option_add('*TCombobox*Listbox.selectBackground', ORANGE)
        self.option_add('*TCombobox*Listbox.selectForeground', "white")
        self.option_add('*TCombobox*Listbox.font', FONT_SM)

        self.cfg = load_config()
        self.presets = load_presets()
        self._player_names = {}
        self._tags_list = []
        self._tags_active = set()   # IDs of currently selected tags
        self._tags_schema = {}
        self._demo_checksums = {}  # {demo_path: checksum} — populated by _query_events
        self._demo_dates     = {}  # {demo_path: date_val} — populated by _query_events
        self._tag_search_results = {}

        self.v = {}
        str_keys = ["pg_host", "pg_port", "pg_user", "pg_pass", "pg_db", "csdm_exe", "output_dir",
                     "date_from", "date_to", "encoder", "recsys", "recording_output", "video_codec",
                     "audio_codec", "video_container", "ffmpeg_input_params", "ffmpeg_output_params",
                     "tag_on_export", "perspective", "hlae_extra_args", "clip_order",
                     "cs2_window_mode",
                     "output_dir_clips", "output_dir_concat", "output_dir_assembled",
                     "assemble_output", "video_preset", "teamkills_mode", "phys_ragdoll_scale"]
        int_keys = ["before", "after", "tickrate", "width", "height", "framerate", "crf", "audio_bitrate",
                     "death_notices_duration", "retry_count", "retry_delay", "delay_between_demos",
                     "hlae_fov", "hlae_slow_motion",
                     "phys_ragdoll_gravity", "phys_sv_gravity",
                     "victim_pre_s", "dp2_threads"]
        bool_keys = ["use_config_file_mode", "close_game_after", "show_only_death_notices",
                      "concatenate_sequences", "subfolder_per_demo", "true_view", "tag_enabled",
                      "hlae_afx_stream", "hlae_no_spectator_ui",
                      "hlae_fix_scope_fov", "hlae_workshop_download",
                      "headshots_only", "include_suicides", "show_xray",
                      "kill_mod_through_smoke", "kill_mod_no_scope", "kill_mod_wall_bang",
                      "kill_mod_airborne", "kill_mod_assisted_flash", "kill_mod_collateral",
                      "kill_mod_trois_shot", "kill_mod_no_trois_shot", "kill_mod_trois_tap",
                      "kill_mod_one_tap",
                      "assemble_after", "delete_after_assemble",
                      "phys_ragdoll_enable", "phys_blood", "phys_dynamic_lighting",
                      "cs2_minimize"]
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
        self.db_status = tk.StringVar(value="Non connecte")
        self.sel_events = {e: tk.BooleanVar(value=(e in self.cfg.get("events", []))) for e in EVENTS}
        self.sel_weapons = {}
        for w in self.cfg.get("weapons", []):
            self.sel_weapons[w] = tk.BooleanVar(value=True)
        self._running = False
        self._stop_after_current = False
        self._proc = None
        self._dp2_cache      = {}                  # {demo_path: {"fire_detail": …, "fire_ticks": …}}
        self._dp2_cache_lock = threading.Lock()    # protects _dp2_cache during parallel pre-parse
        self._db_schema = {}
        self._db_col_types = {}
        self._date_col = None
        self._date_col_type = ""      # actual SQL type of the date column
        self._pending_restore_sid  = None   # steam_id to restore once DB is ready
        self._pending_restore_tags = []     # tag names to restore once DB is ready
        self._sm_cb = None                 # slow-motion combo reference (updated on preset load)

        self._build_ui()

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
        self.after(60, self._update_res_preview)

        self._auto_save()
        self.after(200, self._preflight)
        if HAS_PG:
            self.after(500, self._connect_and_load)

    def _on_player_change(self, name, sid):
        try:
            if name and sid:
                short = name[:22] + ("…" if len(name) > 22 else "")
                self._hdr_player_lbl.config(text=f"● {short}", fg=ORANGE)
            else:
                self._hdr_player_lbl.config(text="", fg=MUTED)
        except Exception:
            pass

    def _preflight(self):
        for d in ensure_csdm_dirs():
            self._log(f"[PRE] Cree: {d}", "ok")
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
            if k in self.v:
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
                # Compat ancienne config mono-joueur
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
        return psycopg2.connect(host=self.v["pg_host"].get(), port=int(self.v["pg_port"].get()),
                                user=self.v["pg_user"].get(), password=self.v["pg_pass"].get(),
                                dbname=self.v["pg_db"].get(), connect_timeout=5)

    def _connect_and_load(self):
        self.db_status.set("Connexion...")
        self.db_status_lbl.config(fg=YELLOW)

        def task():
            try:
                conn = self._pg()
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

                    cur.execute(
                        "SELECT DISTINCT p.name, p.steam_id FROM players p "
                        "WHERE p.name IS NOT NULL AND p.steam_id IS NOT NULL "
                        "AND p.name!='' AND p.steam_id!='' ORDER BY p.name")
                    rows = cur.fetchall()

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
                players = [(f"{n}  ({s})", s, n) for n, s in rows]
                names = {s: n for n, s in rows}
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
            conn = self._pg()
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
            conn = self._pg()
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
            conn = self._pg()
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
            conn = self._pg()
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
                    conn = self._pg()
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
            conn = self._pg()
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

        # Position the sash once the window is actually visible
        # Wait for <Map> event then force geometry
        def _set_sash(event=None):
            self.update_idletasks()
            w = self.winfo_width()
            if w > 100:
                try:
                    outer.sashpos(0, int(w * 0.60))
                except Exception:
                    pass
        self.bind("<Map>", _set_sash)

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

        sec = Sec(p, "PLAYER")
        sec.pack(fill="x", pady=(0, 10))
        self.player_search = PlayerSearchWidget(sec, on_change=self._on_player_change)
        self.player_search.pack(fill="x")

        sec = Sec(p, "EVENTS & CAMERA")
        sec.pack(fill="x", pady=(0, 10))

        ev_row = tk.Frame(sec, bg=BG2)
        ev_row.pack(fill="x")
        mlabel(ev_row, "Capture:").pack(side="left")
        for e in EVENTS:
            self._chk(ev_row, e, self.sel_events[e]).pack(side="left", padx=(10, 0))
        desc_label(ev_row, "  Deaths = active players' deaths").pack(side="left", padx=(10, 0))

        opt_row = tk.Frame(sec, bg=BG2)
        opt_row.pack(fill="x", pady=(4, 0))
        self._hs_cb = hchk(opt_row, "HS only", self.v["headshots_only"])
        self._hs_cb.pack(side="left")
        add_tip(self._hs_cb, "Only captures headshot kills (is_headshot column).")
        _sui_cb = hchk(opt_row, "Suicides", self.v["include_suicides"])
        _sui_cb.pack(side="left", padx=(4, 0))
        add_tip(_sui_cb, "Include world / fall / suicide deaths in clips.")
        mlabel(opt_row, "   TK:").pack(side="left", padx=(8, 0))
        for lbl, val, tip in [
            ("Include","include","All kills, including teamkills"),
            ("Exclude","exclude","Exclude teamkill frags"),
            ("Only","only","Only kills on teammates"),
        ]:
            _rb = hradio(opt_row, lbl, self.v["teamkills_mode"], val)
            _rb.pack(side="left", padx=(4, 0))
            add_tip(_rb, tip)

        tk.Frame(sec, height=1, bg=BORDER).pack(fill="x", pady=(6, 4))

        mods_row = tk.Frame(sec, bg=BG2)
        mods_row.pack(fill="x")
        _m_lbl = mlabel(mods_row, "Mods (OR):")
        _m_lbl.pack(side="left")
        add_tip(_m_lbl, "If none checked → all kills included.\nIf multiple checked → one must match (OR).")
        _MODS = [
            ("kill_mod_through_smoke",  "Smoke",     "Kill through a smoke grenade"),
            ("kill_mod_no_scope",       "No-scope",  "No-scope kill (sniper only)"),
            ("kill_mod_wall_bang",      "Wallbang",  "Kill by penetrating a wall / object"),
            ("kill_mod_airborne",       "Airborne",  "Killer in the air at time of shot"),
            ("kill_mod_assisted_flash", "Flashed",   "Victim blinded by a flashbang"),
            ("kill_mod_collateral",     "Collateral","Bullet passes through a first victim"),
        ]
        for key, lbl, tip in _MODS:
            _cb = hchk(mods_row, lbl, self.v[key])
            _cb.pack(side="left", padx=(4, 0))
            add_tip(_cb, tip)

        # ── TROIS SHOT (v62) ─────────────────────────────────────────────────
        trois_row = tk.Frame(sec, bg=BG2)
        trois_row.pack(fill="x", pady=(4, 0))
        _ts_lbl = mlabel(trois_row, "🎲 TROIS SHOT:")
        _ts_lbl.pack(side="left")
        add_tip(_ts_lbl,
                "Lucky kills on single/semi-auto precision weapons.\n"
                "Detection via demoparser2 (requires pip install demoparser2).\n\n"
                "Eligible weapons: Deagle, R8, AWP, SCAR-20, G3SG1, SSG 08\n"
                "Detection by bloom (accuracy_penalty), scope and velocity\n"
                "at the exact shot tick in the demo.\n\n"
                "⚠ Enable → automatically locks ineligible weapons.")
        _ts_cb = hchk(trois_row, "Enable", self.v["kill_mod_trois_shot"],
                      command=self._on_trois_shot_toggle)
        _ts_cb.pack(side="left", padx=(4, 0))
        _nts_cb = hchk(trois_row, "Exclude", self.v["kill_mod_no_trois_shot"],
                       command=self._on_no_trois_shot_toggle)
        _nts_cb.pack(side="left", padx=(12, 0))
        add_tip(_nts_cb,
                "Exclude lucky kills — inverse of the TROIS SHOT filter.\n"
                "Keeps only precise kills on these weapons.\n"
                "⚠ Incompatible with 'Enable' TROIS SHOT.")
        _ts_badge = tk.Label(trois_row, text="demoparser2",
                             font=FONT_DESC, fg=BLUE, bg=BG2)
        _ts_badge.pack(side="left", padx=(8, 0))
        add_tip(_ts_badge, "Requires: pip install demoparser2")

        # ── TROIS TAP (v68) ────────────────────────────────────────────────────
        tt_row = tk.Frame(sec, bg=BG2)
        tt_row.pack(fill="x", pady=(4, 0))
        _tt_lbl = mlabel(tt_row, "🎯🎲 TROIS TAP:")
        _tt_lbl.pack(side="left")
        add_tip(_tt_lbl,
                "TROIS SHOT + ONE TAP: lucky AND isolated single-shot headshot.\n"
                "Combined conditions:\n"
                "  • Mandatory headshot\n"
                "  • Eligible TROIS SHOT weapon (Deagle, R8, AWP, SCAR-20, G3SG1, SSG 08)\n"
                "  • Bloom / scope / velocity (TROIS SHOT)\n"
                "  • No shot in the 2s BEFORE and AFTER (ONE TAP)\n"
                "Detection via demoparser2.\n\n"
                "⚠ Enable → forces 'HS only' + locks ineligible weapons.")
        _tt_cb = hchk(tt_row, "Enable", self.v["kill_mod_trois_tap"],
                      command=self._on_trois_tap_toggle)
        _tt_cb.pack(side="left", padx=(4, 0))
        _tt_badge = tk.Label(tt_row, text="demoparser2",
                             font=FONT_DESC, fg=BLUE, bg=BG2)
        _tt_badge.pack(side="left", padx=(8, 0))
        add_tip(_tt_badge, "Requires: pip install demoparser2")

        # ── ONE TAP (v66) ─────────────────────────────────────────────────────
        ot_row = tk.Frame(sec, bg=BG2)
        ot_row.pack(fill="x", pady=(4, 0))
        _ot_lbl = mlabel(ot_row, "🎯 ONE TAP:")
        _ot_lbl.pack(side="left")
        add_tip(_ot_lbl,
                "Isolated single-shot headshot kills.\n"
                "Strict conditions:\n"
                "  • Mandatory headshot (1 bullet, 1 kill)\n"
                "  • No shot in the 2s BEFORE the shot (silence)\n"
                "  • No shot in the 2s AFTER the shot (no follow-up)\n"
                "Detection via demoparser2.\n\n"
                "⚠ Enable → forces 'HS only' (locked).")
        _ot_cb = hchk(ot_row, "Enable", self.v["kill_mod_one_tap"],
                      command=self._on_one_tap_toggle)
        _ot_cb.pack(side="left", padx=(4, 0))
        _ot_badge = tk.Label(ot_row, text="demoparser2",
                             font=FONT_DESC, fg=BLUE, bg=BG2)
        _ot_badge.pack(side="left", padx=(8, 0))
        add_tip(_ot_badge, "Requires: pip install demoparser2")

        persp_row = tk.Frame(sec, bg=BG2)
        persp_row.pack(fill="x", pady=(4, 0))
        mlabel(persp_row, "Perspective:").pack(side="left")
        for lbl, val, tip in [
            ("POV Killer",  "killer","Camera constantly on the killer"),
            ("POV Victim","victim","Camera constantly on the victim (no switch)"),
            ("Both",  "both",  "Killer from start, switches to victim before the kill (configurable)"),
        ]:
            _rb = hradio(persp_row, lbl, self.v["perspective"], val,
                         command=self._on_perspective_change)
            _rb.pack(side="left", padx=(4, 0))
            add_tip(_rb, tip)

        # "Before switch" slider — visible only in victim/both mode (v69)
        self._victim_pre_row = tk.Frame(sec, bg=BG2)
        self._victim_pre_row.pack(fill="x", pady=(4, 0))
        _vp_lbl = mlabel(self._victim_pre_row, "Switch delay (s):")
        _vp_lbl.pack(side="left")
        add_tip(_vp_lbl,
                "Duration (seconds) before the kill during which camera\n"
                "still follows the killer before switching to the victim.\n"
                "Adds to BEFORE seconds: if BEFORE=3s and switch=2s,\n"
                "the clip starts 3s before the kill, camera switches at 2s before.\n"
                "0 = switch at the exact kill tick.\n"
                "⚠ Automatically capped at BEFORE seconds.")
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

        sec = Sec(p, "TIMING & ROBUSTNESS")
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

        sec = Sec(p, "DATE FILTER")
        sec.pack(fill="x", pady=(0, 6))

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
                  command=lambda: [self.v["date_from"].set(""), self.v["date_to"].set("")]
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

    # ── TAB VIDEO ──
    def _tab_video(self, parent):
        p = self._make_tab_scroll(parent)

        sec = Sec(p, "RECORDING SYSTEM")
        sec.pack(fill="x", pady=(0, 12))
        rg = tk.Frame(sec, bg=BG2)
        rg.pack(fill="x")
        rg.columnconfigure(0, weight=1)
        rg.columnconfigure(1, weight=1)
        rg.columnconfigure(2, weight=1)
        for col, (title, opts, key, tip) in enumerate([
            ("Encoder", ENCODER_OPTIONS, "encoder", "FFmpeg = standard. VirtualDub = legacy."),
            ("System",  RECSYS_OPTIONS,  "recsys",
             "HLAE = injects via HLAE into CS2 (recommended — full options).\n"
             "CS = native CSDM recording without HLAE.\n\n"
             "⚠ CS mode does NOT support: FOV, slow-motion, physics, window mode,\n"
             "  or any HLAE options. All HLAE section settings are ignored.\n"
             "⚠ In CS mode, CS2 plays the demo interactively from start to finish —\n"
             "  the demo viewer UI is visible and the game cannot be minimized safely."),
            ("Output", REC_OUTPUT_OPTIONS, "recording_output", "video / images / both.")
        ]):
            f = tk.Frame(rg, bg=BG2)
            f.grid(row=0, column=col, sticky="new", padx=(0, 12 if col < 2 else 0))
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

        tk.Frame(bot_row, bg=BORDER, width=1).pack(side="left", fill="y", padx=(0, 20))

        # CS2 window mode
        wm_frm = tk.Frame(bot_row, bg=BG2)
        wm_frm.pack(side="left", padx=(0, 20))
        _wm_lbl = mlabel(wm_frm, "CS2 window mode")
        _wm_lbl.pack(anchor="w")
        add_tip(_wm_lbl,
                "Launch flag injected into CS2 arguments (HLAE only).\n"
                "None = does not change current mode.\n"
                "Borderless windowed = -windowed -noborder (recommended for recording behind other windows).")
        for lbl, val in [
            ("None",               "none"),
            ("Fullscreen",         "fullscreen"),
            ("Windowed",           "windowed"),
            ("Borderless windowed","noborder"),
        ]:
            hradio(wm_frm, lbl, self.v["cs2_window_mode"], val).pack(anchor="w", pady=(2, 0))

        _min_row2 = tk.Frame(wm_frm, bg=BG2)
        _min_row2.pack(anchor="w", pady=(6, 0))
        _min_cb2 = hchk(_min_row2, "Minimize on launch", self.v["cs2_minimize"])
        _min_cb2.pack(side="left")
        add_tip(_min_cb2,
                "Automatically minimizes CS2 window as soon as it appears.\n"
                "Requires pywin32 (pip install pywin32).\n"
                "Without pywin32: silently ignored.")

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

        self._hlae_sec = Sec(p, "⚡ HLAE OPTIONS (advanced)")
        self._hlae_sec.pack(fill="x", pady=(0, 12))
        desc_label(self._hlae_sec,
                   "These options are passed to HLAE via CSDM.\n"
                   "They have no effect if RecSys = CS.\n"
                   "ℹ Audio is captured directly by HLAE via startmovie (bypasses Windows mixer) —\n"
                   "  muting CS2 in Windows does not affect clip audio.\n"
                   "⚠ CS2 console may briefly appear during recording: this is normal.").pack(fill="x")

        # FOV
        fov_row = tk.Frame(self._hlae_sec, bg=BG2)
        fov_row.pack(fill="x", pady=(8, 0))
        mlabel(fov_row, "FOV:").pack(side="left")
        sentry(fov_row, self.v["hlae_fov"], width=5).pack(side="left", padx=(6, 0), ipady=4)
        desc_label(fov_row, "  (e.g. 90 = normal, 100-110 = wide, 60 = zoom)").pack(side="left", padx=(8, 0))

        # Slow motion
        sm_row = tk.Frame(self._hlae_sec, bg=BG2)
        sm_row.pack(fill="x", pady=(6, 0))
        mlabel(sm_row, "Slow-motion (%):").pack(side="left")
        sm_cb = scombo(sm_row, tk.StringVar(), ["100", "75", "50", "33", "25", "10"], 6)
        self._sm_cb = sm_cb   # kept for update on preset load
        sm_cb.set(str(self.v["hlae_slow_motion"].get()))
        sm_cb.pack(side="left", padx=(6, 0))
        sm_cb.bind("<<ComboboxSelected>>",
                   lambda e, c=sm_cb: self.v["hlae_slow_motion"].set(int(c.get())))
        desc_label(sm_row, "  100 = normal speed, 50 = half speed").pack(side="left", padx=(8, 0))

        # Options bool HLAE (ligne compacte + tooltips)
        bool_opts = tk.Frame(self._hlae_sec, bg=BG2)
        bool_opts.pack(fill="x", pady=(8, 0))
        for txt, key, tip in [
            ("AFX Stream",      "hlae_afx_stream",
             "Records separate passes (color, depth, stencil) for compositing."),
            ("No spectator UI", "hlae_no_spectator_ui",
             "Hides spectator mode HUD elements for a cleaner render."),
            ("Fix scope FOV",   "hlae_fix_scope_fov",
             "Injects: mirv_fov handleZoom enabled 1\n"
             "Prevents mirv_fov from overriding the zoom FOV when a player\n"
             "uses a scoped weapon (AWP, SSG 08, SCAR-20, G3SG1).\n"
             "Without this, scoped shots appear at the custom FOV instead of\n"
             "the correct zoomed FOV. Recommended: ON."),
        ]:
            _cb = hchk(bool_opts, txt, self.v[key])
            _cb.pack(side="left", padx=(0, 4))
            add_tip(_cb, tip)


        # Physique CS2
        tk.Frame(self._hlae_sec, height=1, bg=BORDER).pack(fill="x", pady=(10, 6))
        mlabel(self._hlae_sec, "CS2 physics:").pack(anchor="w")
        desc_label(self._hlae_sec,
                   "Console commands injected at startup. Allow modifying "
                   "the appearance of ragdolls and game physics.").pack(anchor="w")

        phys_grid = tk.Frame(self._hlae_sec, bg=BG2)
        phys_grid.pack(fill="x", pady=(6, 0))
        phys_grid.columnconfigure(0, weight=1)
        phys_grid.columnconfigure(1, weight=1)

        col_l = tk.Frame(phys_grid, bg=BG2)
        col_l.grid(row=0, column=0, sticky="new", padx=(0, 16))
        for lbl, key, tip, presets in [
            ("cl_ragdoll_gravity", "phys_ragdoll_gravity",
             "Ragdoll gravity (cl_ragdoll_gravity).\nDefault 600 | negative = float | 5000 = slam hard.",
             ["600", "200", "0", "-200", "-500", "2000", "5000"]),
            ("ragdoll_gravity_scale", "phys_ragdoll_scale",
             "Ragdoll gravity scale (ragdoll_gravity_scale).\nDefault 1.0 | 0.1 = slow | 3.0 = fast.",
             ["1.0", "0.5", "0.1", "0.0", "2.0", "3.0"]),
            ("sv_gravity", "phys_sv_gravity",
             "World gravity (sv_gravity).\nDefault 800 | 200 = moon | 2000 = very heavy.",
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
            for p in presets:
                tk.Button(row, text=p, font=FONT_DESC, bg=BG3, fg=TEXT,
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=BORDER, activeforeground=ORANGE,
                          command=lambda v=p, k=key: self.v[k].set(v)
                          ).pack(side="left", padx=(4, 0), ipady=2, ipadx=3)

        col_r = tk.Frame(phys_grid, bg=BG2)
        col_r.grid(row=0, column=1, sticky="new")
        for txt, key, tip in [
            ("Ragdoll physics",  "phys_ragdoll_enable",
             "cl_ragdoll_physics_enable\nDisable = frozen corpses."),
            ("Blood on walls",   "phys_blood",
             "violence_hblood\nDisable for a cleaner render."),
            ("Dynamic lighting", "phys_dynamic_lighting",
             "r_dynamic\nDisable to remove explosion flashes."),
        ]:
            f = tk.Frame(col_r, bg=BG2)
            f.pack(fill="x", pady=(0, 6))
            _cb = hchk(f, txt, self.v[key])
            _cb.pack(anchor="w")
            add_tip(_cb, tip)

        # Args CLI additionnels
        wdl_row = tk.Frame(self._hlae_sec, bg=BG2)
        wdl_row.pack(fill="x", pady=(8, 0))
        _wdl_cb = hchk(wdl_row, "Auto Workshop downloads",
             self.v["hlae_workshop_download"])
        _wdl_cb.pack(side="left")
        add_tip(_wdl_cb, "Injects +cl_downloadfilter all — allows downloading "
                         "old Workshop map versions to be downloaded.")

        _ea_lbl = tk.Label(self._hlae_sec, text="Additional CLI args (HLAE):",
                 font=FONT_SM, fg=MUTED, bg=BG2)
        _ea_lbl.pack(anchor="w", pady=(8, 0))
        add_tip(_ea_lbl, "Arguments passed directly to the HLAE session.\n"
                         "⚠ If CS2 gets stuck on an old Workshop map: add "
                         "+cl_downloadfilter all in Steam Launch Options, not here.")
        sentry(self._hlae_sec, self.v["hlae_extra_args"]).pack(fill="x", ipady=4, pady=(2, 0))

        # Trace recsys to show/hide
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

    def _on_recsys_change(self, *_):
        try:
            is_hlae = self.v["recsys"].get() == "HLAE"
            if is_hlae:
                self._hlae_sec.pack(fill="x", pady=(0, 12))
            else:
                self._hlae_sec.pack_forget()
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
        """Toggle TROIS SHOT. Locks ineligible weapons.
        If both TROIS SHOT + ONE TAP are now checked → auto-enable TROIS TAP."""
        active = self.v["kill_mod_trois_shot"].get()
        # Mutually exclusive with Exclude (no_trois_shot)
        if active and self.v["kill_mod_no_trois_shot"].get():
            self.v["kill_mod_no_trois_shot"].set(False)
        # Mutually exclusive with TROIS TAP
        if active and self.v["kill_mod_trois_tap"].get():
            self.v["kill_mod_trois_tap"].set(False)
            self._disengage_trois_tap()
        # Auto TROIS TAP: if both TROIS SHOT + ONE TAP active → engage TROIS TAP
        if active and self.v["kill_mod_one_tap"].get():
            self.v["kill_mod_trois_shot"].set(False)
            self.v["kill_mod_one_tap"].set(False)
            self.v["kill_mod_trois_tap"].set(True)
            self._engage_trois_tap()
            return
        if not hasattr(self, "sel_weapons"):
            return
        for w, var in self.sel_weapons.items():
            if active and w.lower().strip() not in TROIS_SHOT_ELIGIBLE_LOWER:
                var.set(False)
        if hasattr(self, "_cat_vars"):
            for cat in self._cat_vars:
                self._update_cat_var(cat)
        try:
            self._refresh_weapons_lock(active)
        except Exception:
            pass

    def _on_no_trois_shot_toggle(self, *_):
        """Toggle Exclude (inverse TROIS SHOT).
        Mutually exclusive with TROIS SHOT and TROIS TAP only."""
        active = self.v["kill_mod_no_trois_shot"].get()
        if active:
            if self.v["kill_mod_trois_shot"].get():
                self.v["kill_mod_trois_shot"].set(False)
                try:
                    self._refresh_weapons_lock(False)
                except Exception:
                    pass
            if self.v["kill_mod_trois_tap"].get():
                self.v["kill_mod_trois_tap"].set(False)
                self._disengage_trois_tap()

    def _on_one_tap_toggle(self, *_):
        """Toggle ONE TAP. Forces and locks 'HS only'.
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
        try:
            if active:
                self.v["headshots_only"].set(True)
                self._hs_cb.config(state="disabled")
            else:
                if not self.v["kill_mod_trois_tap"].get():
                    self._hs_cb.config(state="normal")
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

    def _engage_trois_tap(self):
        """Apply all side-effects of TROIS TAP becoming active."""
        try:
            self.v["headshots_only"].set(True)
            self._hs_cb.config(state="disabled")
        except Exception:
            pass
        if not hasattr(self, "sel_weapons"):
            return
        for w, var in self.sel_weapons.items():
            if w.lower().strip() not in TROIS_SHOT_ELIGIBLE_LOWER:
                var.set(False)
        if hasattr(self, "_cat_vars"):
            for cat in self._cat_vars:
                self._update_cat_var(cat)
        try:
            self._refresh_weapons_lock(True)
        except Exception:
            pass

    def _disengage_trois_tap(self):
        """Undo side-effects of TROIS TAP (unlock weapons, release HS lock)."""
        try:
            self._refresh_weapons_lock(False)
        except Exception:
            pass
        try:
            if not self.v["kill_mod_one_tap"].get():
                self._hs_cb.config(state="normal")
        except Exception:
            pass


    def _refresh_weapons_lock(self, locked):
        """Grey out ineligible weapon checkboxes when locked=True."""
        if not hasattr(self, "_wg_frame") or self._wg_frame is None:
            return
        for widget in self._wg_frame.winfo_descendants():
            if isinstance(widget, tk.Checkbutton):
                txt = widget.cget("text").strip().lower()
                eligible = txt in TROIS_SHOT_ELIGIBLE_LOWER
                if locked and not eligible:
                    widget.config(state="disabled", fg=BORDER)
                else:
                    widget.config(state="normal",
                                  fg=MUTED if not self.sel_weapons.get(
                                      widget.cget("text").strip(),
                                      tk.BooleanVar(value=False)).get() else TEXT)

    def _trois_shot_filter(self, demo_path, events, cfg):
        """Keep only lucky kills (TROIS SHOT filter).

        Reads weapon_fire data from _dp2_cache (populated by _dp2_parse_demo).
        If the demo is not yet cached, triggers a synchronous parse as fallback.
        """
        if not os.path.isfile(demo_path):
            return events

        # Ensure parsed — no-op if already cached
        if demo_path not in self._dp2_cache:
            self._dp2_parse_demo(demo_path)

        with self._dp2_cache_lock:
            data = self._dp2_cache.get(demo_path, {})
        fire_index = data.get("fire_detail", {})

        def _is_lucky(kill_tick, killer_sid, weapon_raw):
            w_key = CSDM_TO_DP2_WEAPON.get(weapon_raw.lower().strip())
            if w_key is None:
                return False
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
            if weapon_raw.lower().strip() not in TROIS_SHOT_ELIGIBLE_LOWER:
                continue
            if _is_lucky(kill_tick, killer_sid, weapon_raw):
                filtered.append(evt)

        return filtered

    def _dp2_parse_demo(self, demo_path):
        """Parse a single demo with demoparser2 and store the result in _dp2_cache.

        This is the ONLY method that calls demoparser2 in the entire codebase.
        weapon_fire is parsed ONCE with all needed player fields; both indexes
        (fire_detail and fire_ticks) are derived from that single parse.

        Cache entry stored under demo_path:
          {
            "fire_detail": {(sid, wpn_suffix): [(tick, acc, scoped, vel), ...]},
              — used by _trois_shot_filter / _no_trois_shot_filter
            "fire_ticks":  {(sid, wpn_suffix): [tick, ...]},
              — used by _one_tap_filter / _trois_tap_filter
              — derived from fire_detail, no second parse needed
          }

        To add a future filter that needs a new event type (e.g. "player_hurt"):
          1. Add a parser.parse_event("player_hurt", ...) call here
          2. Build and store the new index under a new key in the cache entry
          3. Read it in the new filter via _dp2_cache.get(path, {}).get("new_key", {})
          No other method needs to change.

        Thread-safe: double-check inside lock before parsing.
        Safe to call concurrently on the same demo (only one thread will parse).
        Returns True on success, False on import/parse failure.
        """
        # Fast path — already in cache
        with self._dp2_cache_lock:
            if demo_path in self._dp2_cache:
                return True

        if not os.path.isfile(demo_path):
            with self._dp2_cache_lock:
                self._dp2_cache[demo_path] = {}
            return False

        try:
            from demoparser2 import DemoParser
        except ImportError:
            self._alog(
                "  ⚠ demoparser2 not installed — install with: pip install demoparser2",
                "warn")
            return False

        try:
            parser  = DemoParser(demo_path)
            fire_df = parser.parse_event(
                "weapon_fire",
                player=["is_scoped", "velocity_X", "velocity_Y",
                        "accuracy_penalty", "player_steamid"],
                other=[],
            )
        except Exception as e:
            self._alog(f"  ⚠ dp2 parse error ({Path(demo_path).name}): {e}", "warn")
            with self._dp2_cache_lock:
                self._dp2_cache[demo_path] = {}
            return False

        if fire_df is None or len(fire_df) == 0:
            with self._dp2_cache_lock:
                self._dp2_cache[demo_path] = {"fire_detail": {}, "fire_ticks": {}}
            return True

        cols = list(fire_df.columns)
        def _col(name):
            if name in cols: return name
            if f"user_{name}" in cols: return f"user_{name}"
            return None

        col_sid   = _col("player_steamid") or _col("steamid")
        col_acc   = _col("accuracy_penalty")
        col_scope = _col("is_scoped")
        col_vx    = _col("velocity_X")
        col_vy    = _col("velocity_Y")

        if not col_sid or not col_acc:
            self._alog(
                f"  ⚠ dp2: steamid/accuracy columns missing in weapon_fire "
                f"({Path(demo_path).name})", "warn")
            with self._dp2_cache_lock:
                self._dp2_cache[demo_path] = {"fire_detail": {}, "fire_ticks": {}}
            return True

        np_cols  = ["tick", "weapon", col_sid, col_acc]
        opt_cols = ([col_scope] if col_scope else []) + \
                   ([col_vx]    if col_vx    else []) + \
                   ([col_vy]    if col_vy    else [])
        arr = fire_df[np_cols + opt_cols].to_numpy()

        i_scope = 4                                if col_scope else None
        i_vx    = 4 + (1 if col_scope else 0)     if col_vx    else None
        i_vy    = 4 + (1 if col_scope else 0) \
                    + (1 if col_vx    else 0)     if col_vy    else None

        fire_detail: dict = defaultdict(list)
        for row in arr:
            tick   = int(row[0]   or 0)
            wpn    = str(row[1]   or "").lower()
            sid    = str(row[2]   or "")
            acc    = float(row[3] or 0)
            scoped = bool(row[i_scope]) if i_scope is not None else False
            vx     = float(row[i_vx])   if i_vx   is not None else 0.0
            vy     = float(row[i_vy])   if i_vy   is not None else 0.0
            vel    = (vx**2 + vy**2) ** 0.5
            wpn_s  = wpn[7:] if wpn.startswith("weapon_") else wpn
            fire_detail[(sid, wpn_s)].append((tick, acc, scoped, vel))

        for k in fire_detail:
            fire_detail[k].sort(key=lambda r: r[0])

        fire_detail = dict(fire_detail)

        # fire_ticks derived from fire_detail — no second parse needed
        fire_ticks = {k: [r[0] for r in v] for k, v in fire_detail.items()}

        with self._dp2_cache_lock:
            self._dp2_cache[demo_path] = {
                "fire_detail": fire_detail,
                "fire_ticks":  fire_ticks,
                # Future event types go here, e.g.:
                # "damage": {...},
            }
        return True

    def _no_trois_shot_filter(self, demo_path, events, cfg):
        """Keep only precise kills — inverse of TROIS SHOT.
        Eligible weapons that are NOT lucky are kept, plus all non-eligible weapon kills.
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
            self._alog(
                f"  🎯 [{weapon_raw}] [tick={kill_tick}] sid={killer_sid} → "
                f"{'✓ isolated' if isolated else '✗ not isolated'}",
                "info" if isolated else "dim")
            if isolated:
                filtered.append(evt)

        return filtered

    def _trois_tap_filter(self, demo_path, events, cfg):
        """TROIS TAP = TROIS SHOT AND ONE TAP combined.
        Keeps only lucky kills (eligible precision weapons) that are also isolated single shots.
        """
        lucky_events = self._trois_shot_filter(demo_path, events, cfg)
        return self._one_tap_filter(demo_path, lucky_events, cfg)

    def _apply_filter_to_events(self, evts, cfg, cfg_key, filter_fn, label):
        """Apply a per-demo filter function to all demos in evts.

        Skips if cfg_key is falsy. Returns a new {demo_path: events} dict
        with empty-demo paths removed.
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
                conn = self._pg()
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
                self.after(0, lambda err=e: (self._alog(f"Tags erreur: {err}", "err"),
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
        if not any(v.get() for v in self.sel_events.values()):
            self._alog("[TAGS/config] Select at least one event in Capture.", "err")
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
                conn = self._pg()
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
                conn = self._pg()
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
                conn = self._pg()
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
    def _tab_outils(self, parent):
        p = self._make_tab_scroll(parent)

        sec = Sec(p, "PATHS")
        sec.pack(fill="x", pady=(0, 10))
        PathField(sec, "CSDM Executable", "csdm.CMD or csdm.exe",
                  self.v["csdm_exe"], "file").pack(fill="x", pady=4)
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
        # Combo slow-motion (StringVar anonyme → maj manuelle)
        try:
            if self._sm_cb is not None:
                self._sm_cb.set(str(self.v["hlae_slow_motion"].get()))
        except Exception:
            pass

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
                # Lire le tag (varint)
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
                        # matchtime : unix timestamp > 2001 → vraisemblable
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
        """Return the canonical demo timestamp (same source for display AND filter).
        Priority: 1) .info file  2) .dem mtime  (None if unavailable)."""
        ts = self._read_demo_date_from_info(demo_path)
        if ts is not None:
            return ts
        return self._ts_from_demo_path(demo_path)

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
        ts = self._get_demo_ts(demo_path)
        if ts is not None:
            return (0, ts)
        raw = self._demo_dates.get(demo_path)
        if raw is None:
            return (1, 0)
        try:
            if hasattr(raw, "timestamp"):
                return (0, int(raw.timestamp()))
            if isinstance(raw, (int, float)):
                t = int(raw)
                return (0, t // 1000 if t > 4_000_000_000 else t)
            s = str(raw).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return (0, int(datetime.strptime(s[:len(fmt)], fmt).timestamp()))
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

    def _alog(self, msg, tag=""):
        self.after(0, lambda m=msg, t=tag: self._log(m, t))

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

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
        cols = self._db_schema.get(table, [])
        for c in candidates:
            if c in cols:
                return c
        return None

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
                return False  # date inconnue + filtre actif → on exclut
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
                # ONE TAP and TROIS TAP require mandatory headshot in DB
                headshots_only = (cfg.get("headshots_only", False)
                                  or cfg.get("kill_mod_one_tap", False)
                                  or cfg.get("kill_mod_trois_tap", False))
                _tkmode = cfg.get("teamkills_mode", "include")
                include_teamkills = (_tkmode != "exclude")
                teamkills_only    = (_tkmode == "only")

                # Headshot column (optional)
                hc = self._find_col("kills", ["is_headshot", "headshot", "is_hs", "hs"])
                hsql = ""
                if headshots_only and hc:
                    hsql = f' AND k."{hc}" = TRUE'
                elif headshots_only and not hc:
                    self._alog("⚠ Headshots only: column not found in kills — filter ignored.", "warn")

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
                    "kill_mod_wall_bang":      ["is_wall_bang", "wall_bang", "is_wallbang", "wallbang"],
                    "kill_mod_airborne":       ["is_airborne", "airborne"],
                    "kill_mod_assisted_flash": ["is_assisted_flash", "assisted_flash",
                                                "is_blind", "attacker_blind"],
                    "kill_mod_collateral":     ["is_collateral", "collateral",
                                                "is_trade", "through_body"],
                }
                active_mods = [k for k in _MOD_COLS if cfg.get(k, False)]
                modsql = ""
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
                        missing_labels = ", ".join(
                            m.replace("kill_mod_", "").replace("_", " ") for m in missing_mods)
                        if not mod_clauses:
                            # All checked modifiers absent from DB →
                            # cannot filter, return empty rather than all clips
                            self._alog(
                                f"⛔ Modifiers not found in DB: {missing_labels}. "
                                f"No clips returned — uncheck these modifiers or check the schema.",
                                "err")
                            conn.close()
                            return {}
                        else:
                            self._alog(
                                f"⚠ Modifiers partially not found: {missing_labels} — ignored. "
                                f"Only the others are applied.",
                                "warn")
                    if mod_clauses:
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
                        results.setdefault(dp, []).append(
                            {"tick": event_tick, "type": et, "weapon": weapon_raw,
                             "killer_sid": killer_sid, "victim_sid": victim_sid})

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
        finally:
            conn.close()

        # Applied here rather than SQL because the DB column often contains
        # the import date and not the actual match date.
        if ts_from is not None or ts_to is not None:
            results = {
                dp: evts_val for dp, evts_val in results.items()
                if _demo_passes_date_filter(dp)
            }

        return results
    def _effective_before(self, cfg):
        """Return the effective BEFORE duration in seconds.
        In 'both' mode, victim_pre_s is added to before so that
        the killer phase is complete in the recorded sequence."""
        before = cfg.get("before", 3)
        if cfg.get("perspective") == "both":
            before = before + cfg.get("victim_pre_s", 0)
        return before

    def _build_sequences(self, events, tickrate, before_s, after_s):
        if not events:
            return []
        bt, at = before_s * tickrate, after_s * tickrate
        raw = [{"start_tick": max(0, e["tick"] - bt), "end_tick": e["tick"] + at, "events": [e]}
               for e in sorted(events, key=lambda x: x["tick"])]
        merged = [raw[0]]
        for s in raw[1:]:
            p = merged[-1]
            if s["start_tick"] <= p["end_tick"]:
                p["end_tick"] = max(p["end_tick"], s["end_tick"])
                p["events"].extend(s["events"])
            else:
                merged.append(s)
        return merged

    def _build_run_cfg(self):
        cfg = self._collect_config()
        cfg["events_kills"]  = self.sel_events["Kills"].get()
        cfg["events_deaths"] = self.sel_events["Deaths"].get()
        cfg["events_rounds"] = self.sel_events["Rounds"].get()
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

        # --- HLAE extra options ---
        hlae_options = {}
        if recsys == "HLAE":
            fov = cfg.get("hlae_fov", 90)
            if fov and int(fov) != 90:
                hlae_options["mirv_fov"] = int(fov)
            slow_mo = cfg.get("hlae_slow_motion", 100)
            if slow_mo and int(slow_mo) != 100:
                hlae_options["host_timescale"] = round(int(slow_mo) / 100.0, 4)
            if cfg.get("hlae_afx_stream", False):
                hlae_options["afxStream"] = True
            extra = cfg.get("hlae_extra_args", "").strip()
            if cfg.get("hlae_no_spectator_ui", True):
                hlae_options["hideSpectatorUi"] = True
                _spec_cmd = "+cl_draw_only_deathnotices 1"
                if _spec_cmd not in extra:
                    extra = (_spec_cmd + " " + extra).strip()
            if cfg.get("hlae_fix_scope_fov", True):
                _scope_cmd = "+mirv_fov handleZoom enabled 1"
                if _scope_cmd not in extra:
                    extra = (_scope_cmd + " " + extra).strip()
            if cfg.get("hlae_workshop_download", False):
                dl_arg = "+cl_downloadfilter all"
                if dl_arg not in extra:
                    extra = (dl_arg + " " + extra).strip()

            # CS2 physics commands — injected if different from defaults
            phys_cmds = []
            rg = cfg.get("phys_ragdoll_gravity", 600)
            if int(rg) != 600:
                phys_cmds.append(f"+cl_ragdoll_gravity {rg}")
            rs = cfg.get("phys_ragdoll_scale", "1.0")
            if float(rs) != 1.0:
                phys_cmds.append(f"+ragdoll_gravity_scale {rs}")
            sg = cfg.get("phys_sv_gravity", 800)
            if int(sg) != 800:
                phys_cmds.append(f"+sv_gravity {sg}")
            if not cfg.get("phys_ragdoll_enable", True):
                phys_cmds.append("+cl_ragdoll_physics_enable 0")
            if not cfg.get("phys_blood", True):
                phys_cmds.append("+violence_hblood 0")
            if not cfg.get("phys_dynamic_lighting", True):
                phys_cmds.append("+r_dynamic 0")
            if phys_cmds:
                extra = (" ".join(phys_cmds) + " " + extra).strip()

            # CS2 window mode
            wm = cfg.get("cs2_window_mode", "none")
            _WM_FLAGS = {
                "fullscreen": "-fullscreen",
                "windowed":   "-windowed",
                "noborder":   "-windowed -noborder",
            }
            wm_flag = _WM_FLAGS.get(wm, "")
            if wm_flag and wm_flag not in extra:
                extra = (wm_flag + " " + extra).strip()

            if extra:
                hlae_options["extraArgs"] = extra

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
            "recordingOutput": cfg.get("recording_output", "video"),
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
            deadline = time.time() + 60  # timeout 60s pour trouver CS2

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

            # Phase 1 : attendre CS2 (polling rapide 100ms)
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
        if not any(v.get() for v in self.sel_events.values()):
            messagebox.showerror("", "Select at least one event.")
            return
        ensure_csdm_dirs()
        cfg = self._build_run_cfg()
        self._running = True
        self._stop_after_current = False
        self.run_btn.config(state="disabled", bg=BG3, fg=MUTED)
        self.stop_btn.config(state="normal")
        self.kill_btn.config(state="normal")
        self._log(f"\n{'═' * 60}", "dim")
        self._log(f"  ▶ LAUNCH  —  {datetime.now().strftime('%H:%M:%S')}", "info")
        self._log(f"{'═' * 60}", "dim")
        self._summary_lbl.config(text="  Querying DB…", fg=YELLOW)
        threading.Thread(target=self._worker, args=(cfg,), daemon=True).start()

    def _stop_graceful(self):
        self._stop_after_current = True
        self._alog("\n⏸ Graceful stop.", "warn")
        self.stop_btn.config(state="disabled")

    def _kill_now(self):
        self._running = False
        self._stop_after_current = True
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._alog("\n⛔ KILL", "err")
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
        needs_dp2 = (cfg.get("kill_mod_trois_shot") or
                     cfg.get("kill_mod_no_trois_shot") or
                     cfg.get("kill_mod_one_tap") or
                     cfg.get("kill_mod_trois_tap"))
        if not needs_dp2:
            return

        paths = [dp for dp in demo_paths if os.path.isfile(dp)]
        if not paths:
            return

        # Determine which demos are not yet cached
        with self._dp2_cache_lock:
            missing = [dp for dp in paths if dp not in self._dp2_cache]

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
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as ex:
            futs = {ex.submit(self._dp2_parse_demo, dp): dp for dp in missing}
            for fut in concurrent.futures.as_completed(futs):
                done += 1
                try:
                    fut.result()
                except Exception as e:
                    self._alog(
                        f"  ⚠ Pre-parse error ({Path(futs[fut]).name}): {e}",
                        "warn")
                self.after(0, lambda d=done, t=len(missing):
                           self.progress_lbl.config(text=f"Pre-parse {d}/{t}"))

        cached_total = n_cached + done
        self._alog(
            f"  ✓ Pre-parse done ({done} parsed, {cached_total}/{len(paths)} total in cache)",
            "ok")


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
            try:
                evts = self._query_events(cfg)
            except Exception as e:
                self._alog(f"Error: {e}", "err")
                return
            # ── Signature-based DP2 pre-parse (cache preserved if same demo set) ──
            self._preparse_dp2(cfg, list(evts.keys()))
            # ─────────────────────────────────────────────────────────────────
            # Apply demoparser2 modifiers before preview.
            # trois_tap is exclusive; trois_shot + no_trois_shot + one_tap are cumulative (AND).
            if cfg.get("kill_mod_trois_tap"):
                self._alog("  🎯🎲 TROIS TAP — analyzing demos…", "info")
                evts = self._apply_trois_tap_to_events(evts, cfg)
            else:
                if cfg.get("kill_mod_trois_shot"):
                    self._alog("  🎲 TROIS SHOT — analyzing demos…", "info")
                    evts = self._apply_trois_shot_to_events(evts, cfg)
                if cfg.get("kill_mod_no_trois_shot"):
                    self._alog("  🚫🎲 Exclude — analyzing demos…", "info")
                    evts = self._apply_no_trois_shot_to_events(evts, cfg)
                if cfg.get("kill_mod_one_tap"):
                    self._alog("  🎯 ONE TAP — analyzing demos…", "info")
                    evts = self._apply_one_tap_to_events(evts, cfg)
            self.after(0, lambda evts=evts, cfg=cfg: self._show_preview(evts, cfg))

        threading.Thread(target=task, daemon=True).start()

    def _show_preview(self, evts, cfg):
        """Display preview results. Must be called on the main thread."""
        if not evts:
            self._log("No events.", "warn")
            self._summary_lbl.config(text="  No clips found.", fg=MUTED)
            return
        te = sum(len(e) for e in evts.values())
        self._log(f"Player(s): {self._player_str(cfg)}", "info")
        _auto_tags = self._get_active_tag_names() if self.v["tag_enabled"].get() else []
        if _auto_tags:
            self._log(f"Auto-tag: 🏷 {', '.join(_auto_tags)}", "info")
        df = cfg.get("date_from", "")
        dt = cfg.get("date_to", "")
        if df or dt:
            self._log(f"Date filter: {df or '∞'}  →  {dt or '∞'}", "info")
        _weapons = cfg.get("weapons", [])
        if _weapons:
            _cat_counts = {}
            for w in _weapons:
                c = _weapon_category(w)
                _cat_counts[c] = _cat_counts.get(c, 0) + 1
            _wstr = "  |  Armes: " + ", ".join(
                f"{WEAPON_ICONS.get(c,'')} {c}({n})" for c, n in sorted(_cat_counts.items()))
        else:
            _wstr = "  |  Armes: toutes"
        self._log(f"TrueView: {'ON' if cfg.get('true_view') else 'OFF'} | "
                  f"Perspective: {PERSP_LABELS.get(cfg.get('perspective','killer'), cfg.get('perspective','killer'))}"
                  f"{_wstr}", "info")
        order = cfg.get("clip_order", "chrono")
        hs_str = "  🎯 HS only" if cfg.get("headshots_only") else ""
        _tkm = cfg.get("teamkills_mode", "include")
        tk_str = ("  🚫 TK excluded" if _tkm == "exclude" else
                  "  ⚔ TK only" if _tkm == "only" else "")
        ts_str  = "  🎲 TROIS SHOT"    if cfg.get("kill_mod_trois_shot")    else ""
        nts_str = "  🚫🎲 Exclude"      if cfg.get("kill_mod_no_trois_shot") else ""
        tt_str  = "  🎯🎲 TROIS TAP"   if cfg.get("kill_mod_trois_tap")     else ""
        ot_str  = "  🎯 ONE TAP"        if cfg.get("kill_mod_one_tap")       else ""
        self._log(f"Order: {'Chronological' if order == 'chrono' else 'Random'} | "
                  f"{len(evts)} demo(s), {te} events{hs_str}{tk_str}{ts_str}{nts_str}{tt_str}{ot_str}", "ok")
        _out = (cfg.get("output_dir_clips") or cfg.get("output_dir") or "").strip()
        if _out:
            self._log(f"Output: {_out}", "dim")
        self._log("Source dates: .info › mtime .dem › DB", "dim")
        tickrate  = cfg["tickrate"]
        before_s  = self._effective_before(cfg)
        after_s   = cfg["after"]
        nb_clips  = 0
        total_ticks = 0
        sorted_demos = sorted(evts.keys(), key=self._demo_sort_key)
        demo_dates = {}
        for dp in sorted_demos:
            seqs = self._build_sequences(evts[dp], tickrate, before_s, after_s)
            nb_clips += len(seqs)
            for s in seqs:
                total_ticks += s["end_tick"] - s["start_tick"]
            date_str = self._format_demo_date(dp)
            demo_dates[dp] = date_str
            self._log(
                f"  {date_str}  {Path(dp).name}  "
                f"({len(evts[dp])} events → {len(seqs)} seq)",
                "blue")
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
        summary_txt = self._fmt_summary(nb_demos, nb_clips, total_sec, avg_sec)
        self._log(f"\n{'─'*56}", "dim")
        self._log(f"  ▶ {nb_clips} clips  |  total duration {self._hms(total_sec)}"
                  f"  |  avg. {self._hms(avg_sec)}/clip", "ok")
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
            self._alog("  Assemblage: FFmpeg introuvable.", "err")
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
                # Supprimer les dossiers des clips (jamais la racine output)
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

    def _apply_dp2_modifiers(self, dp, events, cfg):
        """Apply active demoparser2 kill modifiers for one demo.

        Returns the filtered event list, or None if no kills remain
        (caller should skip this demo).
        TROIS TAP is exclusive; the others are cumulative (AND logic).
        """
        modifiers = [
            ("kill_mod_trois_tap",     self._trois_tap_filter,
             "🎯🎲 TROIS TAP",  "TROIS TAP",  "0 TROIS TAP"),
        ]
        cumulative = [
            ("kill_mod_trois_shot",    self._trois_shot_filter,
             "🎲 TROIS SHOT",   "TROIS SHOT", "0 TROIS SHOT"),
            ("kill_mod_no_trois_shot", self._no_trois_shot_filter,
             "🚫🎲 Exclude",    "precise",    "0 EXCLUDE"),
            ("kill_mod_one_tap",       self._one_tap_filter,
             "🎯 ONE TAP",      "one tap",    "0 ONE TAP"),
        ]

        if cfg.get("kill_mod_trois_tap"):
            active = modifiers
        else:
            active = [m for m in cumulative if cfg.get(m[0])]

        for cfg_key, filter_fn, log_label, result_label, skip_label in active:
            n_before = _count_kills(events)
            events   = filter_fn(dp, events, cfg)
            n_after  = _count_kills(events)
            self._alog(
                f"  {log_label} : {n_before} kills → {n_after} {result_label}",
                "info")
            if not events:
                self._alog(f"  ⏭ SKIP: {skip_label} in this demo", "dim")
                return None
        return events


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
            self._alog(
                "  ℹ RecSys CS: HLAE options ignored. CS2 plays the demo "
                "interactively — do NOT minimize CS2 during recording.", "warn")
        if cfg.get("headshots_only"):
            self._alog("🎯 Headshots only", "info")
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
        try:
            all_events = self._query_events(cfg)
        except Exception as e:
            self._alog(f"Error: {e}", "err")
            self.after(0, self._reset_btns)
            return
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
        self._alog(f"OK: {len(all_events)} demo(s), {te} events", "ok")
        self._alog("-" * 56, "dim")

        order = cfg.get("clip_order", "chrono")
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
                    conn = self._pg()
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
                            if cfg.get("kill_mod_trois_tap"):
                                self._alog("  🎯🎲 TROIS TAP — analyzing demos…", "info")
                                _fe = self._apply_trois_tap_to_events(_fe, cfg)
                            else:
                                if cfg.get("kill_mod_trois_shot"):
                                    self._alog("  🎲 TROIS SHOT — analyzing demos…", "info")
                                    _fe = self._apply_trois_shot_to_events(_fe, cfg)
                                if cfg.get("kill_mod_no_trois_shot"):
                                    self._alog("  🚫🎲 Exclude — analyzing demos…", "info")
                                    _fe = self._apply_no_trois_shot_to_events(_fe, cfg)
                                if cfg.get("kill_mod_one_tap"):
                                    self._alog("  🎯 ONE TAP — analyzing demos…", "info")
                                    _fe = self._apply_one_tap_to_events(_fe, cfg)
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
            events = self._apply_dp2_modifiers(dp, events, cfg)
            if events is None:
                summary.append((Path(dp).name, "SKIP", 0, 0, "0 kills after filter"))
                skip += 1
                continue

            seqs = self._build_sequences(events, cfg["tickrate"], self._effective_before(cfg), cfg["after"])
            if not seqs:
                continue
            dn = Path(dp).name
            ad = os.path.abspath(dp)
            date_str = self._format_demo_date(dp)
            self.after(0, lambda lbl=f"{i}/{len(demo_list)}":
                       self.progress_lbl.config(text=lbl))
            self.after(0, lambda n=dn, ns=len(seqs), ne=len(events), idx=i, ds=date_str:
                       self._log(
                           f"\n[{idx}/{len(demo_list)}]  {ds}  {n}  ({ne} events → {ns} seq)", "blue"))
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
                f"Output: {cfg.get('recording_output','video')} | "
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
                    # Multi-tags: use _tags_active if available, else tag_name alone
                    _auto_names = self._get_active_tag_names() if self._get_active_tag_names() else ([tag_name] if tag_name else [])
                    _tag_ok_names, _tag_fail = [], ""
                    for _tn in _auto_names:
                        _tok, _terr = self._tag_demo(dp, _tn)
                        if _tok:
                            _tag_ok_names.append(_tn)
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

        if ok > 0 and cfg.get("assemble_after"):
            self._alog("\n⚙  Final assembly in progress...", "info")
            try:
                self._assemble_clips(cfg, produced_dirs)
            except Exception as e:
                self._alog(f"  Assembly error: {e}", "err")

        self.after(0, self._reset_btns)

if __name__ == "__main__":
    App().mainloop()