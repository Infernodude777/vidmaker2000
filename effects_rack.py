"""One-click looks for the effects rack.

``LOOKS``, ``list_looks``, ``apply_look``, ``apply_named_look`` and
``reset_look`` behave exactly as before; new looks and helpers are additive.
"""

from __future__ import annotations

import copy

LOOKS = {
    "vhs": {"scanlines": 0.6, "chromatic": 0.5, "grain": 0.4, "blur": 0.15},
    "film": {"grain": 0.3, "contrast": 0.85, "saturation": 0.9},
    "retro": {"grain": 0.4, "chromatic": 0.3, "temperature": 0.2},
    "glitchy": {"glitch": 0.4, "chromatic": 0.4, "scanlines": 0.3},
    "noir": {"saturation": 0.0, "contrast": 1.2, "grain": 0.25},
    "clean": {"contrast": 1.06, "saturation": 1.05, "sharpen": 0.15},
    "punchy": {"contrast": 1.18, "saturation": 1.25, "exposure": 0.08},
    "dreamy": {"blur": 0.22, "saturation": 1.12, "exposure": 0.05, "vignette": 0.3},
    "cold": {"temperature": -0.25, "tint": 0.08, "contrast": 1.05},
    "warm": {"temperature": 0.28, "tint": -0.05, "saturation": 1.08},
}

# Attributes a look is allowed to touch: keeps a look from nuking flip/rotate.
_GRADE_FIELDS = (
    "exposure", "brightness", "contrast", "saturation", "temperature", "tint",
    "highlights", "shadows", "vignette", "blur", "sharpen", "pixelate",
    "glitch", "grain", "chromatic", "scanlines",
)


def list_looks():
    """Sorted look names."""
    return sorted(LOOKS)


def apply_look(grade, name):
    """Apply a look to a Grade object in place. Returns the values applied."""
    values = LOOKS.get(name, {})
    for key, value in values.items():
        if key in _GRADE_FIELDS and hasattr(grade, key):
            try:
                setattr(grade, key, float(value))
            except (TypeError, ValueError):
                continue
    return dict(values)


def apply_named_look(frame, grade, name):
    """Apply the look to ``grade`` and grade a frame with it, if possible."""
    apply_look(grade, name)
    try:
        from video_processor import grade_frame
        return grade_frame(frame, grade, 0.0, 1.0)
    except Exception:
        return frame


def reset_look(grade):
    """Reset only the fields looks touch, leaving transform flags alone."""
    defaults = {
        "exposure": 0.0, "brightness": 0.0, "contrast": 1.0, "saturation": 1.0,
        "temperature": 0.0, "tint": 0.0, "highlights": 0.0, "shadows": 0.0,
        "vignette": 0.25, "blur": 0.0, "sharpen": 0.0, "pixelate": 0.0,
        "glitch": 0.0, "grain": 0.0, "chromatic": 0.0, "scanlines": 0.0,
    }
    for key, value in defaults.items():
        if hasattr(grade, key):
            try:
                setattr(grade, key, value)
            except (TypeError, ValueError):
                continue


def look_preview(name) -> str:
    """Human summary of what a look changes."""
    values = LOOKS.get(name)
    if not values:
        return f"{name}: unknown look"
    parts = [f"{k}={v:g}" for k, v in sorted(values.items())]
    return f"{name}: " + ", ".join(parts)


def merge_looks(first: str, second: str, weight: float = 0.5) -> dict:
    """Blend two looks into a new settings dict (weight 0 = first)."""
    w = max(0.0, min(1.0, float(weight)))
    a = LOOKS.get(first, {})
    b = LOOKS.get(second, {})
    out = copy.deepcopy(a)
    for key, value in b.items():
        if key in out:
            try:
                out[key] = float(out[key]) * (1.0 - w) + float(value) * w
            except (TypeError, ValueError):
                out[key] = value
        else:
            out[key] = value
    return out


def describe_all() -> list[str]:
    """All looks with their settings, for a help panel."""
    return [look_preview(name) for name in list_looks()]
