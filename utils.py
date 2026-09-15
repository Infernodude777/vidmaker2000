import math
import os
import tempfile

BG = "#0f0e17"
PANEL = "#191827"
INK = "#fffffe"
MUTED = "#a7a9be"
ORANGE = "#ff8906"
VIOLET = "#7f5af0"
MINT = "#2cb67d"
RED = "#d04648"


def clamp(v, lo=0.0, hi=255.0):
    return max(lo, min(hi, v))


def clamp01(v):
    return max(0.0, min(1.0, v))


def lerp(a, b, t):
    return a + (b - a) * clamp01(t)


def ease_inout(t):
    t = clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def sec_to_tc(sec, fps=30.0):
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    f = int(round((sec - math.floor(sec)) * fps)) % max(1, int(fps))
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}:{f:02d}"
    return f"{m:02d}:{s:02d}:{f:02d}"


def tc_to_sec(tc, fps=30.0):
    try:
        parts = tc.strip().split(":")
        if len(parts) == 4:
            h, m, s, f = map(float, parts)
            return h * 3600 + m * 60 + s + f / fps
        if len(parts) == 3:
            m, s, f = map(float, parts)
            return m * 60 + s + f / fps
        m, s = map(float, parts)
        return m * 60 + s
    except Exception:
        return 0.0


def speed_to_delay_ms(speed, fps=30.0):
    eff = max(0.25, min(2.0, speed)) * fps
    return int(1000.0 / eff)


def format_bytes(n):
    n = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024.0


def clamp_loop(v, lo, hi):
    span = hi - lo
    if span <= 0:
        return lo
    while v < lo:
        v += span
    while v >= hi:
        v -= span
    return v


def safe_name(name, maxlen=24):
    keep = "".join(
        c if c.isalnum() or c in ("-", "_", " ", ".") else "_"
        for c in (name or "untitled")
    )
    return keep.strip()[:maxlen] or "untitled"


def temp_path(name="vidmaker2000_output.mp4"):
    return os.path.join(tempfile.gettempdir(), name)


def fmt_pct(done, total):
    if total <= 0:
        return "0%"
    return f"{done * 100 // max(1, total)}%"


def parse_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "yes")
