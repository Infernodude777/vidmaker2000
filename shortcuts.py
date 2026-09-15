"""Editor shortcut registry.

Keeps shortcut_hint / all_shortcuts / help_text exactly as before and adds a
structured registry (groups, descriptions) that the keymap and docs share.
"""

from __future__ import annotations

SHORTCUTS = [
    {"key": "space", "action": "play_pause", "group": "Playback",
     "desc": "Play or pause the preview"},
    {"key": "left", "action": "step_back", "group": "Playback",
     "desc": "Nudge the playhead back half a second"},
    {"key": "right", "action": "step_fwd", "group": "Playback",
     "desc": "Nudge the playhead forward half a second"},
    {"key": "j", "action": "jump_back", "group": "Playback",
     "desc": "Jump back two seconds"},
    {"key": "l", "action": "jump_fwd", "group": "Playback",
     "desc": "Jump forward two seconds"},
    {"key": "k", "action": "pause", "group": "Playback",
     "desc": "Pause the preview"},
    {"key": "i", "action": "trim_in", "group": "Edit",
     "desc": "Trim the in point of the clip under the playhead"},
    {"key": "o", "action": "trim_out", "group": "Edit",
     "desc": "Trim the out point of the clip under the playhead"},
    {"key": "s", "action": "split", "group": "Edit",
     "desc": "Split the clip at the playhead"},
    {"key": "d", "action": "duplicate", "group": "Edit",
     "desc": "Duplicate the selected clip"},
    {"key": "delete", "action": "delete", "group": "Edit",
     "desc": "Remove the selected clip"},
    {"key": "ctrl+z", "action": "undo", "group": "Edit", "desc": "Undo"},
    {"key": "ctrl+y", "action": "redo", "group": "Edit", "desc": "Redo"},
    {"key": "ctrl+s", "action": "save", "group": "Project",
     "desc": "Save the project + autosave snapshot"},
    {"key": "m", "action": "mute", "group": "Grade", "desc": "Toggle mute"},
    {"key": "r", "action": "reset_grade", "group": "Grade",
     "desc": "Reset the grade to defaults"},
    {"key": "e", "action": "export", "group": "Delivery",
     "desc": "Export the current timeline"},
    {"key": "+", "action": "zoom_in", "group": "View",
     "desc": "Zoom the timeline in"},
    {"key": "-", "action": "zoom_out", "group": "View",
     "desc": "Zoom the timeline out"},
]

# Legacy lookup used by the old help overlay.
_TRANSPORT_HINTS = {
    "space": "play/pause",
    "left": "step back",
    "right": "step forward",
    "j": "jump back",
    "l": "jump forward",
}


def shortcut_hint(k):
    """Original helper: human hint for a key (or "" when unknown)."""
    key = (k or "").strip().lower()
    for entry in SHORTCUTS:
        if entry["key"] == key:
            return entry["desc"]
    return _TRANSPORT_HINTS.get(key, "")


def all_shortcuts():
    """Original helper: every shortcut entry as a list of dicts."""
    return [dict(entry) for entry in SHORTCUTS]


def help_text():
    """Original helper: the full cheat sheet as one string."""
    lines = ["vidmaker2000 shortcuts", "=" * 24]
    for group in groups():
        lines.append("")
        lines.append(group)
        for entry in by_group(group):
            lines.append(f"  {entry['key'].ljust(10)} {entry['desc']}")
    return "\n".join(lines)


def groups() -> list[str]:
    """Distinct group names, in first-seen order."""
    seen = []
    for entry in SHORTCUTS:
        if entry["group"] not in seen:
            seen.append(entry["group"])
    return seen


def by_group(group: str) -> list[dict]:
    """Shortcut entries inside one group."""
    return [dict(e) for e in SHORTCUTS if e["group"] == group]


def lookup(key: str) -> dict | None:
    """Entry bound to ``key`` (None when unknown)."""
    wanted = (key or "").strip().lower()
    for entry in SHORTCUTS:
        if entry["key"] == wanted:
            return dict(entry)
    return None


def conflicts() -> list[tuple[str, str]]:
    """Key -> action pairs that appear twice (empty when the map is clean)."""
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for entry in SHORTCUTS:
        key = entry["key"]
        if key in seen and seen[key] != entry["action"]:
            out.append((key, entry["action"]))
        seen.setdefault(key, entry["action"])
    return out
