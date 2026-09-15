"""Caption rendering plus SRT/VTT interchange.

Keeps the original drawing helpers (draw_caption / draw_title / draw_timecode)
so existing callers keep working, and adds a small track model with subtitle
file import/export for real delivery work.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

DEFAULT_FONT_SCALE = 0.9
DEFAULT_THICKNESS = 2
_POSITIONS = ("bottom", "top", "center")


def _as_bgr(frame):
    """Validate a frame is a writable 3-channel image (None if not)."""
    if frame is None:
        return None
    shape = getattr(frame, "shape", None)
    if not shape or len(shape) != 3:
        return None
    return frame


def wrap_text(text: str, width: int = 32) -> list[str]:
    """Wrap caption text into lines no wider than ``width`` characters."""
    if not text:
        return []
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width=max(8, int(width))) or [""])
    return lines


def _anchor_y(frame, lines, pos: str, pad: int) -> int:
    """Baseline y for the first line of a block at ``pos``."""
    import cv2
    _h, w = frame.shape[:2]
    line_h = 26
    if pos == "top":
        return pad + line_h
    if pos == "center":
        block = max(1, len(lines)) * line_h
        return max(line_h, (frame.shape[0] - block) // 2 + line_h)
    return frame.shape[0] - pad - max(0, len(lines) - 1) * line_h


def draw_caption(frame_bgr, text, pos="bottom", scale=0.9, thickness=2, pad=10):
    """Draw ``text`` onto ``frame_bgr`` in place and return the frame.

    ``pos`` is one of "bottom" (default), "top" or "center". Long captions are
    wrapped automatically so they never run off the frame. Any failure returns
    the frame untouched rather than raising, because this runs every frame.
    """
    frame = _as_bgr(frame_bgr)
    if frame is None or not text:
        return frame_bgr
    try:
        import cv2
    except Exception:
        return frame_bgr
    position = pos if pos in _POSITIONS else "bottom"
    width_chars = max(16, int(frame.shape[1] / max(8.0, 22.0 * scale)))
    lines = wrap_text(text, width_chars)
    if not lines:
        return frame
    try:
        font = cv2.FONT_HERSHEY_SIMPLEX
        y = _anchor_y(frame, lines, position, pad)
        for line in lines:
            (tw, th), _base = cv2.getTextSize(line, font, scale, thickness)
            x = max(pad, (frame.shape[1] - tw) // 2)
            cv2.putText(frame, line, (x, y), font, scale, (0, 0, 0),
                        thickness + 3, cv2.LINE_AA)
            cv2.putText(frame, line, (x, y), font, scale, (255, 255, 255),
                        thickness, cv2.LINE_AA)
            y += th + max(6, thickness * 3)
    except Exception:
        return frame_bgr
    return frame


def draw_title(frame_bgr, title, subtitle=""):
    """Big centred title (plus optional subtitle) for openers."""
    frame = _as_bgr(frame_bgr)
    if frame is None or not title:
        return frame_bgr
    try:
        import cv2
    except Exception:
        return frame_bgr
    try:
        font = cv2.FONT_HERSHEY_DUPLEX
        _h, w = frame.shape[:2]
        scale = max(0.7, min(2.2, w / max(1, len(title) * 12)))
        (tw, th), _ = cv2.getTextSize(title, font, scale, 3)
        x = max(10, (w - tw) // 2)
        y = max(th + 20, frame.shape[0] // 2)
        cv2.putText(frame, title, (x, y), font, scale, (0, 0, 0), 7, cv2.LINE_AA)
        cv2.putText(frame, title, (x, y), font, scale, (255, 255, 255), 3, cv2.LINE_AA)
        if subtitle:
            ss = max(0.5, scale * 0.5)
            (sw, sh), _ = cv2.getTextSize(subtitle, font, ss, 2)
            sx = max(10, (w - sw) // 2)
            sy = y + sh + 18
            cv2.putText(frame, subtitle, (sx, sy), font, ss, (0, 0, 0), 5, cv2.LINE_AA)
            cv2.putText(frame, subtitle, (sx, sy), font, ss, (220, 220, 220), 2, cv2.LINE_AA)
    except Exception:
        return frame_bgr
    return frame


def draw_timecode(frame, tc):
    """Small monospace-ish timecode in the top-left corner."""
    frame = _as_bgr(frame)
    if frame is None or not tc:
        return frame_bgr
    try:
        import cv2
    except Exception:
        return frame_bgr
    try:
        font = cv2.FONT_HERSHEY_PLAIN
        cv2.putText(frame, str(tc), (10, 24), font, 1.4, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, str(tc), (10, 24), font, 1.4, (255, 255, 255), 2, cv2.LINE_AA)
    except Exception:
        return frame_bgr
    return frame


# ─── caption track model ────────────────────────────────────────────────────

def _srt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours, rest = divmod(seconds, 3600.0)
    minutes, rest = divmod(rest, 60.0)
    secs = int(rest)
    millis = int(round((rest - secs) * 1000.0))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{int(hours):02d}:{int(minutes):02d}:{secs:02d},{millis:03d}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")


_SRT_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


class CaptionTrack:
    """Ordered list of (start, end, text) cues."""

    def __init__(self, cues=None):
        self.cues: list[tuple[float, float, str]] = list(cues or [])

    def add(self, start: float, end: float, text: str) -> None:
        self.cues.append((max(0.0, float(start)), max(0.0, float(end)), str(text)))
        self.cues.sort(key=lambda c: c[0])

    def text_at(self, t: float) -> str:
        """Caption text visible at time ``t`` ("" when none)."""
        for start, end, text in self.cues:
            if start <= t < end:
                return text
        return ""

    def to_srt(self) -> str:
        blocks = []
        for i, (start, end, text) in enumerate(self.cues, 1):
            blocks.append(f"{i}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
        return "\n".join(blocks)

    def to_vtt(self) -> str:
        blocks = ["WEBVTT\n"]
        for start, end, text in self.cues:
            blocks.append(f"{_vtt_time(start)} --> {_vtt_time(end)}\n{text}\n")
        return "\n".join(blocks)

    def save_srt(self, path) -> bool:
        try:
            Path(path).write_text(self.to_srt(), encoding="utf-8")
            return True
        except OSError:
            return False

    def save_vtt(self, path) -> bool:
        try:
            Path(path).write_text(self.to_vtt(), encoding="utf-8")
            return True
        except OSError:
            return False

    def duration(self) -> float:
        return self.cues[-1][1] if self.cues else 0.0


def _to_seconds(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_subtitles(text: str) -> CaptionTrack:
    """Parse SRT or VTT text into a CaptionTrack (tolerant of junk)."""
    track = CaptionTrack()
    blocks = re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n"))
    for block in blocks:
        match = _SRT_RE.search(block)
        if not match:
            continue
        start = _to_seconds(*match.groups()[:4])
        end = _to_seconds(*match.groups()[4:])
        body = block[match.end():].strip()
        if body:
            track.add(start, end, body)
    return track


def load_subtitles(path) -> CaptionTrack:
    """Load an SRT/VTT file from disk (empty track on failure)."""
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return CaptionTrack()
    return parse_subtitles(raw)


def from_clips(clips) -> CaptionTrack:
    """Build a track from timeline clips that carry a .caption string."""
    track = CaptionTrack()
    cursor = 0.0
    for clip in clips or ():
        span = float(getattr(clip, "trim_dur", 0.0) or 0.0)
        text = getattr(clip, "caption", "") or ""
        if text:
            track.add(cursor, cursor + max(0.2, span), text)
        cursor += span
    return track
