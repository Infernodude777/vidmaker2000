"""Proxy media cache for vidmaker2000.

Decoding a 4K source on every scrub frame is the main cause of a sluggish
timeline. This module builds a small cached copy (or frame extract) keyed by
source path + size + mtime so an edited file invalidates naturally.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

MAX_PROXY_HEIGHT = 540


def cache_key(src) -> str:
    """Stable key from path + size + mtime (changes when the file changes)."""
    p = Path(src)
    try:
        st = p.stat()
        raw = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        raw = str(src)
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def proxy_path(src, cache_dir, target_h: int = 360) -> Path:
    """Deterministic proxy path for ``src`` inside ``cache_dir``."""
    base = Path(cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem[:40] or "clip"
    return base / f"{stem}-{cache_key(src)}-{int(target_h)}p.mp4"


def _open_capture(src):
    import cv2  # imported lazily: keeps this module importable without cv2
    cap = cv2.VideoCapture(str(src))
    return cap if cap.isOpened() else None


def ensure_proxy(src, cache_dir, target_h: int = 360, overwrite: bool = False) -> str | None:
    """Return a cached proxy for ``src``, building it when missing.

    Falls back to the original path when the source cannot be decoded, so the
    caller always has something playable.
    """
    if not src or not os.path.exists(str(src)):
        return None
    out = proxy_path(src, cache_dir, target_h)
    if out.exists() and not overwrite and out.stat().st_size > 0:
        return str(out)
    import cv2
    cap = _open_capture(src)
    if cap is None:
        return str(src)
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
        if height <= target_h or width <= 0:
            return str(src)
        scale = target_h / float(height)
        size = (max(2, int(width * scale) // 2 * 2), int(target_h) // 2 * 2)
        writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        if not writer.isOpened():
            return str(src)
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                writer.write(cv2.resize(frame, size))
        finally:
            writer.release()
    finally:
        cap.release()
    return str(out) if out.exists() else str(src)


def cache_stats(cache_dir) -> dict:
    """Count and total bytes of cached proxies."""
    base = Path(cache_dir)
    if not base.exists():
        return {"count": 0, "bytes": 0}
    count = 0
    total = 0
    for p in base.glob("*-*p.mp4"):
        try:
            total += p.stat().st_size
            count += 1
        except OSError:
            continue
    return {"count": count, "bytes": total}


def clear(cache_dir) -> int:
    """Delete every cached proxy. Returns the number removed."""
    base = Path(cache_dir)
    if not base.exists():
        return 0
    removed = 0
    for p in base.glob("*-*p.mp4"):
        try:
            p.unlink()
            removed += 1
        except OSError:
            continue
    return removed
