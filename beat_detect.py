"""Beat detection for music-synced editing.

Pure standard-library WAV reading plus a simple energy-based onset picker, so
the feature works even when numpy/ffmpeg are unavailable. Everything is
defensive: a malformed audio file returns an empty marker list.
"""

from __future__ import annotations

import os
import struct
import wave


def read_wav_mono(path, max_seconds: float = 60.0) -> tuple[list[float], int]:
    """Read a mono float sample list + sample rate from a WAV file.

    Multi-channel files are averaged down to mono. Returns ([], 0) when the
    file is missing or not a readable PCM WAV.
    """
    if not path or not os.path.exists(str(path)):
        return [], 0
    try:
        with wave.open(str(path), "rb") as fh:
            channels = max(1, fh.getnchannels())
            width = fh.getsampwidth()
            rate = int(fh.getframerate() or 0)
            if width not in (1, 2, 3, 4) or rate <= 0:
                return [], 0
            limit = int(rate * max(1.0, max_seconds))
            frames = fh.readframes(limit)
    except (wave.Error, OSError, EOFError):
        return [], 0
    if not frames or width not in (1, 2, 3, 4):
        return [], 0
    samples: list[float] = []
    step = width * channels
    divisor = float(2 ** (8 * width - 1))
    usable = len(frames) - (len(frames) % step)
    for offset in range(0, usable, step):
        total = 0
        for ch in range(channels):
            start = offset + ch * width
            chunk = frames[start:start + width]
            if len(chunk) < width:
                continue
            value = int.from_bytes(chunk, "little", signed=(width > 1))
            if width == 1:
                value -= 128
            total += value
        samples.append(total / (channels * divisor))
    return samples, rate


def energy_envelope(samples, window: int = 1024) -> list[float]:
    """Mean absolute amplitude per window (cheap onset proxy)."""
    if not samples:
        return []
    window = max(16, int(window))
    out: list[float] = []
    for start in range(0, len(samples), window):
        chunk = samples[start:start + window]
        if not chunk:
            break
        out.append(sum(abs(v) for v in chunk) / len(chunk))
    return out


def detect_beats(samples, rate: int, window: int = 1024,
                 sensitivity: float = 1.5, min_gap_s: float = 0.22) -> list[float]:
    """Return beat timestamps in seconds from raw samples.

    An onset is a window whose energy exceeds the local average by
    ``sensitivity`` and that is at least ``min_gap_s`` after the previous hit.
    """
    if not samples or rate <= 0:
        return []
    envelope = energy_envelope(samples, window=window)
    if not envelope:
        return []
    beats: list[float] = []
    per_window = window / float(rate)
    lookback = 8
    for i, value in enumerate(envelope):
        start = max(0, i - lookback)
        history = envelope[start:i] or [envelope[max(0, i - 1)]]
        local = sum(history) / len(history)
        if value < local * max(1.01, sensitivity):
            continue
        t = i * per_window
        if beats and (t - beats[-1]) < min_gap_s:
            continue
        beats.append(round(t, 3))
    return beats


def beat_markers(path, sensitivity: float = 1.5) -> list[float]:
    """Convenience: WAV path -> beat timestamps (empty list on any failure)."""
    samples, rate = read_wav_mono(path)
    return detect_beats(samples, rate, sensitivity=sensitivity)


def snap_to_beats(t: float, beats) -> float:
    """Nearest beat to ``t`` (``t`` itself when no beats are known)."""
    if not beats:
        return t
    return min(beats, key=lambda b: abs(b - t))
