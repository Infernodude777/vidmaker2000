"""Delivery profiles.

Kept deliberately data-only so the UI can list profiles and the export path can
look up width/height/fps without importing anything heavy.
"""

from __future__ import annotations

PROFILES = {
    "preview_720p": {"width": 1280, "height": 720, "fps": 30, "aspect": "16:9",
                     "bitrate_mbps": 6, "note": "fast review renders"},
    "youtube_1080p": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9",
                      "bitrate_mbps": 16, "note": "upload default"},
    "youtube_4k": {"width": 3840, "height": 2160, "fps": 30, "aspect": "16:9",
                   "bitrate_mbps": 60, "note": "heavy - proxy first"},
    "shorts_1080x1920": {"width": 1080, "height": 1920, "fps": 30, "aspect": "9:16",
                         "bitrate_mbps": 14, "note": "vertical social"},
    "square_1080": {"width": 1080, "height": 1080, "fps": 30, "aspect": "1:1",
                    "bitrate_mbps": 12, "note": "feed posts"},
    "cinema_24": {"width": 1920, "height": 1080, "fps": 24, "aspect": "16:9",
                  "bitrate_mbps": 20, "note": "filmic cadence"},
}


def list_profiles() -> list[str]:
    """Sorted profile names."""
    return sorted(PROFILES)


def get_profile(name: str) -> dict:
    """Profile dict by name (falls back to the preview profile)."""
    return dict(PROFILES.get(name, PROFILES["preview_720p"]))


def summary(name: str) -> str:
    """Short human label, e.g. "youtube_1080p 1920x1080@30 16:9"."""
    p = get_profile(name)
    return f"{name} {p['width']}x{p['height']}@{p['fps']} {p['aspect']}"


def matches_aspect(source_w: int, source_h: int, name: str, tolerance: float = 0.02) -> bool:
    """True when the source aspect is close to the profile's target aspect."""
    if source_w <= 0 or source_h <= 0:
        return False
    target = get_profile(name)
    want = target["width"] / float(target["height"])
    have = source_w / float(source_h)
    return abs(want - have) <= tolerance * max(1.0, want)


def crop_box(source_w: int, source_h: int, name: str) -> tuple[int, int, int, int]:
    """Centre-crop box (x0, y0, x1, y1) to reach the profile aspect."""
    if source_w <= 0 or source_h <= 0:
        return (0, 0, source_w, source_h)
    target = get_profile(name)
    want = target["width"] / float(target["height"])
    have = source_w / float(source_h)
    if abs(have - want) <= 1e-6:
        return (0, 0, source_w, source_h)
    if have > want:
        width = int(round(source_h * want))
        x0 = (source_w - width) // 2
        return (x0, 0, x0 + width, source_h)
    height = int(round(source_w / want))
    y0 = (source_h - height) // 2
    return (0, y0, source_w, y0 + height)
