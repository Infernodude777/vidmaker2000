"""Audio waveform strips.

Renders a wide waveform PNG for the UI. Real WAV peaks are used when the file
is readable; otherwise a deterministic synthetic waveform keeps the UI honest
about the missing audio (and ``muted`` still draws the red mute line).
"""

from __future__ import annotations

import os
import wave


def fake_waveform(width=480, height=64, seed=3):
    """Deterministic synthetic waveform (BGR image)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    rng = np.random.default_rng(seed)
    bars = rng.integers(4, max(6, height - 8), size=max(1, width // 4))
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (35, 20, 23)
    for i, value in enumerate(bars):
        x = i * 4
        y0 = (height - int(value)) // 2
        cv2.rectangle(img, (x, y0), (x + 2, y0 + int(value)), (240, 90, 127), -1)
    return img


def peaks_from_wav(path, buckets=240, max_seconds=90.0):
    """Peak amplitude per bucket from a PCM WAV file ([] when unreadable)."""
    try:
        with wave.open(str(path), "rb") as fh:
            channels = max(1, fh.getnchannels())
            width = fh.getsampwidth()
            rate = int(fh.getframerate() or 0)
            if width not in (1, 2, 3, 4) or rate <= 0:
                return []
            limit = int(rate * max(1.0, max_seconds)) * channels * width
            raw = fh.readframes(int(limit / max(1, channels * width)))
    except (wave.Error, OSError, EOFError):
        return []
    if not raw or buckets <= 0:
        return []
    step = channels * width
    usable = len(raw) - (len(raw) % step)
    divisor = float(2 ** (8 * width - 1))
    per_bucket = max(1, usable // (step * buckets))
    peaks: list[float] = []
    peak = 0.0
    counted = 0
    for offset in range(0, usable, step):
        chunk = raw[offset:offset + width]
        if len(chunk) < width:
            break
        value = int.from_bytes(chunk, "little", signed=(width > 1))
        if width == 1:
            value -= 128
        peak = max(peak, abs(value) / divisor)
        counted += 1
        if counted >= per_bucket:
            peaks.append(min(1.0, peak))
            peak = 0.0
            counted = 0
    if counted:
        peaks.append(min(1.0, peak))
    return peaks


def _render_peaks(peaks, width, height, color):
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:, :] = (35, 20, 23)
    if not peaks:
        return img
    span = max(1, width // max(1, len(peaks)))
    for i, value in enumerate(peaks):
        bar = max(1, int(value * (height - 4)))
        x0 = i * span
        y0 = (height - bar) // 2
        cv2.rectangle(img, (x0, y0), (x0 + max(1, span - 1), y0 + bar), color, -1)
    return img


def render_audio_strip(muted=False, speed=1.0, width=240, path=None):
    """Waveform strip as PNG bytes (None when rendering is impossible).

    Positional compatibility matters here: callers pass (muted, speed) and the
    keyword ``width``.
    """
    try:
        import cv2
    except Exception:
        return None
    height = 48
    try:
        speed = float(speed or 1.0)
    except (TypeError, ValueError):
        speed = 1.0
    peaks = peaks_from_wav(path, buckets=max(24, int(width) // 2)) if path else []
    color = (150, 150, 160) if muted else (127, 90, 240)
    img = _render_peaks(peaks, int(width), height, color) if peaks else fake_waveform(
        width=int(width), height=height, seed=7 + int(speed * 10))
    if img is None:
        return None
    if muted:
        try:
            import cv2 as _cv
            row = img.shape[0] // 2
            _cv.line(img, (0, row), (img.shape[1], row), (70, 70, 255), 2)
        except Exception:
            pass
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else None


def has_audio(path):
    """True when ``path`` looks like a WAV with non-silent audio."""
    peaks = peaks_from_wav(path, buckets=32)
    return bool(peaks) and max(peaks) > 0.01


def strip_summary(path) -> str:
    """Short status line about a media file's audio."""
    if not path or not os.path.exists(str(path)):
        return "no media"
    peaks = peaks_from_wav(path, buckets=32)
    if not peaks:
        return "no readable audio (video track only)"
    loudest = max(peaks)
    return f"audio ok, peak {loudest:.2f}"
