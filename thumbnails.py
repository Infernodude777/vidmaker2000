"""Thumbnail and filmstrip helpers.

Same public helpers as before, now backed by a small on-disk PNG cache so
repeated timeline refreshes stop re-decoding the same frames.
"""

from __future__ import annotations

import hashlib
import os

CACHE_DIR_NAME = "vidmaker2000_thumbs"


def _cache_dir(folder=None) -> str:
    import tempfile
    base = folder or os.path.join(tempfile.gettempdir(), CACHE_DIR_NAME)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        return ""
    return base


def _key(path, tag: str, **kw) -> str:
    raw = "|".join([str(path), tag] + [f"{k}={v}" for k, v in sorted(kw.items())])
    try:
        st = os.stat(str(path))
        raw += f"|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        pass
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:20]


def _encode(img) -> bytes | None:
    try:
        import cv2
    except Exception:
        return None
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else None


def _open(path):
    try:
        import cv2
    except Exception:
        return None
    cap = cv2.VideoCapture(str(path))
    return cap if cap.isOpened() else None


def _sample_frames(path, count: int):
    """Yield up to ``count`` evenly spaced BGR frames from a video file."""
    cap = _open(path)
    if cap is None:
        return []
    frames = []
    try:
        import cv2
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            ok, frame = cap.read()
            return [frame] if ok and frame is not None else []
        for i in range(max(1, int(count))):
            position = int(total * (i + 0.5) / max(1, int(count)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, position)
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
    except Exception:
        return frames
    finally:
        cap.release()
    return frames


def _grid(frames, count: int, thumb_w: int) -> bytes | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if not frames:
        return None
    strips = []
    for frame in frames[:count]:
        height, width = frame.shape[:2]
        if width <= 0:
            continue
        scale = thumb_w / float(width)
        resized = cv2.resize(frame, (thumb_w, max(2, int(height * scale))))
        strips.append(resized)
    if not strips:
        return None
    target_h = max(s.shape[0] for s in strips)
    padded = []
    for strip in strips:
        if strip.shape[0] < target_h:
            pad = np.zeros((target_h - strip.shape[0], strip.shape[1], 3), dtype=np.uint8)
            strip = np.vstack([strip, pad])
        padded.append(strip)
    return _encode(np.hstack(padded))


def contact_sheet(path, count=8, thumb_w=160):
    """One wide image of ``count`` evenly spaced frames (PNG bytes or None)."""
    return _grid(_sample_frames(path, count), count, thumb_w)


def make_filmstrip(path, count=5, thumb_w=160):
    """Alias for contact_sheet with a filmstrip default framing."""
    return contact_sheet(path, count=count, thumb_w=thumb_w)


def cached_filmstrip(path, count=4, thumb_w=80):
    """List of individual thumbnail PNGs, memoised on disk.

    Returns [] when the media is unreadable or OpenCV is missing so callers can
    render a placeholder instead of crashing the refresh cycle.
    """
    if not path or not os.path.exists(str(path)):
        return []
    folder = _cache_dir()
    if folder:
        key = _key(path, f"strip{count}x{thumb_w}")
        cached = []
        missing = False
        for i in range(int(count)):
            candidate = os.path.join(folder, f"{key}-{i}.png")
            if os.path.exists(candidate):
                cached.append(candidate)
            else:
                missing = True
                break
        if cached and not missing:
            out = []
            for candidate in cached:
                try:
                    with open(candidate, "rb") as fh:
                        out.append(fh.read())
                except OSError:
                    return [_encode(f) for f in _sample_frames(path, count) if _encode(f)]
            return out
    frames = _sample_frames(path, count)
    blobs = []
    for i, frame in enumerate(frames):
        blob = _encode(frame)
        if not blob:
            continue
        blobs.append(blob)
        if folder:
            key = _key(path, f"strip{count}x{thumb_w}")
            try:
                with open(os.path.join(folder, f"{key}-{i}.png"), "wb") as fh:
                    fh.write(blob)
            except OSError:
                pass
    return blobs


def thumb_at(path, t_sec, thumb_w=320):
    """Single frame thumbnail at ``t_sec`` (PNG bytes or None)."""
    cap = _open(path)
    if cap is None:
        return None
    try:
        import cv2
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(float(t_sec) * fps)))
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        height, width = frame.shape[:2]
        scale = thumb_w / float(width or 1)
        return _encode(cv2.resize(frame, (thumb_w, max(2, int(height * scale)))))
    except Exception:
        return None
    finally:
        cap.release()


def clear_cache(folder=None) -> int:
    """Delete cached thumbnails. Returns the number removed."""
    base = _cache_dir(folder)
    if not base:
        return 0
    removed = 0
    for name in os.listdir(base):
        if not name.endswith(".png"):
            continue
        try:
            os.unlink(os.path.join(base, name))
            removed += 1
        except OSError:
            continue
    return removed
