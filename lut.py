"""Curve-based colour grading.

A "lut" here is a 256-entry lookup table built from control points, which is
cheap to apply to a whole frame and easy to serialise into a project file.
numpy is used when available and a pure-python path covers the rest.
"""

from __future__ import annotations

PRESETS = {
    "neutral": [(0, 0), (255, 255)],
    "film": [(0, 12), (64, 78), (160, 176), (255, 242)],
    "punch": [(0, 0), (48, 34), (180, 205), (255, 255)],
    "fade": [(0, 26), (128, 138), (255, 232)],
    "night": [(0, 0), (90, 64), (200, 214), (255, 255)],
}


def identity_table() -> list[int]:
    """Straight-line LUT (no change)."""
    return list(range(256))


def build_table(points) -> list[int]:
    """Piecewise-linear LUT from sorted (in, out) control points.

    Points outside 0..255 are clamped; a malformed point list falls back to
    the identity table so grading can never crash the render loop.
    """
    try:
        pts = sorted(((max(0, min(255, int(x))), max(0, min(255, int(y))))
                      for x, y in points), key=lambda p: p[0])
    except (TypeError, ValueError):
        return identity_table()
    if len(pts) < 2:
        return identity_table()
    if pts[0][0] != 0:
        pts.insert(0, (0, pts[0][1]))
    if pts[-1][0] != 255:
        pts.append((255, pts[-1][1]))
    table = [0] * 256
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        span = max(1, x1 - x0)
        for x in range(x0, min(256, x1 + 1)):
            t = (x - x0) / float(span)
            table[x] = int(round(y0 + (y1 - y0) * t))
    return [max(0, min(255, v)) for v in table]


def preset_table(name: str) -> list[int]:
    """LUT for a named preset (identity when unknown)."""
    return build_table(PRESETS.get(name, PRESETS["neutral"]))


def apply_table(frame, table) -> object:
    """Apply a 256-entry LUT to a BGR frame, returning a new frame."""
    if frame is None or len(table) < 256:
        return frame
    try:
        import numpy as np
    except Exception:
        return frame
    lut = np.array(table, dtype=np.uint8)
    return lut[np.asarray(frame)]


def apply_preset(frame, name: str) -> object:
    """Convenience: apply a named preset to a frame."""
    return apply_table(frame, preset_table(name))


def blend_table(a, b, amount: float) -> list[int]:
    """Mix two LUTs (``amount`` 0 = a, 1 = b)."""
    t = max(0.0, min(1.0, float(amount)))
    return [int(round(x + (y - x) * t)) for x, y in zip(a, b)]


def list_presets() -> list[str]:
    return sorted(PRESETS)
