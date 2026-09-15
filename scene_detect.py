"""Scene-change detection for vidmaker2000.

Compares downscaled grayscale histograms between sampled frames; a large delta
is a cut. Output is seconds, ready to feed into timeline split points.
"""

from __future__ import annotations

import os

DEFAULT_THRESHOLD = 0.42
DEFAULT_SAMPLE_FPS = 4.0


def _fingerprint(frame, size=(64, 36)):
    import cv2
    grey = cv2.cvtColor(cv2.resize(frame, size), cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([grey], [0], None, [32], [0, 256])
    cv2.normalize(hist, hist)
    return hist


def delta(a, b) -> float:
    """Histogram distance in 0..1 (0 = identical frames)."""
    import numpy as np
    return float(np.abs(a - b).sum() / 2.0)


def scene_changes(path, threshold: float = DEFAULT_THRESHOLD,
                  sample_fps: float = DEFAULT_SAMPLE_FPS,
                  max_frames: int = 4000) -> list[float]:
    """Return cut timestamps (seconds) found in ``path``.

    An unreadable file yields an empty list rather than raising, so the UI can
    report "no scenes found" without a try/except at the call site.
    """
    if not path or not os.path.exists(str(path)):
        return []
    try:
        import cv2
    except Exception:
        return []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
    step = max(1, int(round(fps / max(0.25, sample_fps))))
    cuts: list[float] = []
    previous = None
    index = 0
    sampled = 0
    try:
        while sampled < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                current = _fingerprint(frame)
                if previous is not None and delta(previous, current) >= threshold:
                    cuts.append(round(index / fps, 3))
                previous = current
                sampled += 1
            index += 1
    finally:
        cap.release()
    return cuts


def auto_split_points(path, threshold: float = DEFAULT_THRESHOLD,
                      min_gap: float = 0.4) -> list[float]:
    """Cut list with near-duplicate detections collapsed (min_gap seconds)."""
    points = scene_changes(path, threshold=threshold)
    kept: list[float] = []
    for t in points:
        if not kept or (t - kept[-1]) >= min_gap:
            kept.append(t)
    return kept
