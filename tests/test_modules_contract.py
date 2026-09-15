"""API contract tests.

Every module in the project is imported and its public surface asserted, so a
future refactor that silently drops a function the UI calls fails loudly here
instead of at runtime.
"""

from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPECTED = {
    "utils": ["sec_to_tc", "tc_to_sec", "safe_name", "clamp", "ease_inout"],
    "timeline": ["Grade", "Clip", "Timeline", "TimelineSet", "Marker"],
    "timeline_ops": ["ripple_delete", "insert_at", "close_gaps", "nudge", "merge_adjacent", "stats"],
    "captions": ["draw_caption", "draw_title", "draw_timecode", "CaptionTrack",
                 "parse_subtitles", "wrap_text"],
    "histogram": ["frame_histogram_strip", "luma_waveform", "rgb_parade", "vectorscope", "scope_strip"],
    "transitions": ["crossfade", "wipe_left", "dip_to_black", "apply_transition", "list_names"],
    "effects_rack": ["list_looks", "apply_look", "apply_named_look", "reset_look"],
    "themes": ["get_theme", "set_theme", "list_themes"],
    "shortcuts": ["shortcut_hint", "all_shortcuts", "help_text"],
    "thumbnails": ["contact_sheet", "make_filmstrip", "cached_filmstrip", "thumb_at"],
    "audio_wave": ["fake_waveform", "render_audio_strip", "has_audio"],
    "share": ["share_path", "export_log_line", "write_manifest", "export_bundle"],
    "keymap": ["default_keymap", "binding_for", "action_for", "remap", "to_lines"],
    "autosave": ["snapshot", "restore", "latest", "rotate", "info"],
    "render_queue": ["RenderJob", "RenderQueue"],
    "proxy_cache": ["proxy_path", "ensure_proxy", "cache_stats", "clear"],
    "scene_detect": ["scene_changes", "auto_split_points"],
    "beat_detect": ["detect_beats", "beat_markers", "read_wav_mono"],
    "lut": ["build_table", "preset_table", "apply_table", "list_presets"],
    "export": ["export_timeline", "get_preset", "list_presets"],
    "profiles": ["list_profiles", "get_profile", "summary", "crop_box"],
    "broll": ["index_folder", "suggest", "pick_shot"],
    "media_index": ["MediaIndex"],
}


def test_expected_modules_import():
    missing = []
    for name in EXPECTED:
        try:
            importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - reported below
            missing.append(f"{name}: {exc}")
    assert not missing, f"modules failed to import: {missing}"


def test_public_symbols_present():
    problems = []
    for name, symbols in EXPECTED.items():
        try:
            module = importlib.import_module(name)
        except Exception as exc:
            problems.append(f"{name}: {exc}")
            continue
        for symbol in symbols:
            if not hasattr(module, symbol):
                problems.append(f"{name}.{symbol} missing")
    assert not problems, problems


def test_no_ui_import_in_helper_modules():
    """Helper modules must stay UI-free so they run headless."""
    offenders = []
    for name in EXPECTED:
        if name in ("themes",):
            continue
        try:
            source = importlib.import_module(name)
        except Exception:
            continue
        if "flet" in (getattr(source, "__dict__", {}) or {}):
            offenders.append(name)
    assert not offenders, f"UI leaked into: {offenders}"
