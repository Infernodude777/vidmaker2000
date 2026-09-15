"""Keyboard map registry for vidmaker2000.

A single source of truth for editor shortcuts so the UI, the help overlay and
tests all agree. Bindings are plain strings ("ctrl+z", "space", "j") which the
Flet keyboard handler normalises to the same form.
"""

from __future__ import annotations

DEFAULTS = {
    "play_pause": "space",
    "trim_in": "i",
    "trim_out": "o",
    "split": "s",
    "duplicate": "d",
    "delete": "delete",
    "export": "e",
    "mute": "m",
    "reset_grade": "r",
    "step_back": "left",
    "step_fwd": "right",
    "jump_back": "j",
    "jump_fwd": "l",
    "pause": "k",
    "save": "ctrl+s",
    "undo": "ctrl+z",
    "redo": "ctrl+y",
    "zoom_in": "+",
    "zoom_out": "-",
}

_KEYMAP = dict(DEFAULTS)


def default_keymap() -> dict:
    """Return a copy of the default action -> key map."""
    return dict(DEFAULTS)


def current_keymap() -> dict:
    """Return a copy of the live action -> key map."""
    return dict(_KEYMAP)


def binding_for(action: str, fallback: str = "") -> str:
    """Key bound to ``action`` (empty string when unknown)."""
    return _KEYMAP.get(action, fallback)


def action_for(key: str) -> str:
    """Action bound to ``key`` (empty string when unbound)."""
    k = (key or "").strip().lower()
    for action, bound in _KEYMAP.items():
        if bound == k:
            return action
    return ""


def remap(action: str, key: str) -> bool:
    """Rebind ``action`` to ``key``. Returns False for unknown actions."""
    if action not in _KEYMAP:
        return False
    k = (key or "").strip().lower()
    if not k:
        return False
    _KEYMAP[action] = k
    return True


def reset() -> None:
    """Restore every binding to its default."""
    _KEYMAP.clear()
    _KEYMAP.update(DEFAULTS)


def to_lines() -> list[str]:
    """Human-readable "action  ->  key" lines, sorted for a help panel."""
    width = max(len(a) for a in _KEYMAP) if _KEYMAP else 0
    return [f"{a.ljust(width)}  ->  {_KEYMAP[a]}" for a in sorted(_KEYMAP)]


def describe() -> str:
    """One-line summary used in status messages."""
    return f"{len(_KEYMAP)} shortcuts bound ({len(DEFAULTS)} defaults)"
