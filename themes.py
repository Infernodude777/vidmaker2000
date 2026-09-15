"""UI themes for vidmaker2000.

The three original helpers are unchanged in behaviour; themes are now a data
registry with validation, optional JSON persistence and swatch helpers.
"""

from __future__ import annotations

import json
import os

THEMES = {
    "neon": {
        "bg": "#0f0e17", "panel": "#191827", "ink": "#fffffe", "muted": "#a7a9be",
        "accent": "#ff8906", "secondary": "#7f5af0", "good": "#2cb67d", "warn": "#d04648",
    },
    "midnight": {
        "bg": "#0b1020", "panel": "#141a2e", "ink": "#f2f5ff", "muted": "#93a0c3",
        "accent": "#4da3ff", "secondary": "#9a6bff", "good": "#39d98a", "warn": "#ff6b6b",
    },
    "sunset": {
        "bg": "#1a1014", "panel": "#251821", "ink": "#fff4e8", "muted": "#c3a08f",
        "accent": "#ff7043", "secondary": "#ffb300", "good": "#66bb6a", "warn": "#e53935",
    },
    "daylight": {
        "bg": "#f2f2f7", "panel": "#ffffff", "ink": "#1a1a2e", "muted": "#5c5c70",
        "accent": "#d97b00", "secondary": "#6c4de0", "good": "#1f9d61", "warn": "#c0392b",
    },
}

# themes whose ``panel`` is brighter than their ``bg`` (used to pick the
# light-mode icon in the UI)
LIGHT_THEMES = {"daylight"}

_ACTIVE = "neon"


def list_themes() -> list[str]:
    """Names of every available theme."""
    return sorted(THEMES)


def get_theme(name=None) -> dict:
    """Palette dict for ``name`` (falls back to the active theme)."""
    key = name or _ACTIVE
    if key not in THEMES:
        key = _ACTIVE if _ACTIVE in THEMES else list(THEMES)[0]
    return dict(THEMES.get(key, THEMES["neon"]))


def set_theme(name) -> dict:
    """Make ``name`` active. Returns the palette in use afterwards."""
    global _ACTIVE
    key = (name or "").strip().lower()
    if key in THEMES:
        _ACTIVE = key
    return get_theme()


def active_name() -> str:
    """Name of the active theme."""
    return _ACTIVE


def swatch(name) -> str:
    """Small CSS-ish gradient string for a theme button."""
    palette = get_theme(name)
    return f"linear-gradient(90deg, {palette['accent']}, {palette['secondary']})"


def palette_lines(name=None) -> list[str]:
    """Palette as "role #hex" lines for a settings panel."""
    palette = get_theme(name)
    width = max(len(k) for k in palette)
    return [f"{k.ljust(width)}  {palette[k]}" for k in sorted(palette)]


def save(path) -> bool:
    """Persist the active theme name to ``path`` (JSON)."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"theme": _ACTIVE}, fh, indent=2)
        return True
    except OSError:
        return False


def load(path) -> str:
    """Load the saved theme name (falls back to the current one)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        name = str((data or {}).get("theme", _ACTIVE))
    except (OSError, ValueError):
        return _ACTIVE
    return set_theme(name) and name or _ACTIVE


def default_path(folder=None) -> str:
    """Where the theme preference is stored by default."""
    base = folder or os.path.join(os.path.expanduser("~"), ".vidmaker2000")
    return os.path.join(str(base), "theme.json")
