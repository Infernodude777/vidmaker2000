"""Video scopes: RGB histogram strip, luma waveform, RGB parade, vectorscope.

The original helpers keep their exact signatures; ``scope_strip`` is a new
single entry point that the UI can switch modes through.
"""

from __future__ import annotations

_SCOPE_MODES = ("histogram", "parade", "waveform", "vectorscope")


def _blank(h: int, w: int):
    import numpy as np
    return np.zeros((max(4, h), max(4, w), 3), dtype=np.uint8)


def frame_histogram_strip(frame_bgr, w=240, h=64):
    """RGB histogram strip as PNG bytes (None when the frame is unusable)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame_bgr is None:
        return None
    try:
        img = np.zeros((h, w, 3), dtype=np.uint8)
        colors = ((0, 0, 255), (0, 255, 0), (255, 0, 0))
        for channel, color in enumerate(colors):
            hist = cv2.calcHist([frame_bgr], [channel], None, [w], [0, 256]).flatten()
            peak = float(hist.max()) or 1.0
            for x, value in enumerate(hist):
                bar = int((value / peak) * (h - 2))
                if bar <= 0:
                    continue
                cv2.line(img, (x, h - 1), (x, h - 1 - bar), color, 1)
        ok, buf = cv2.imencode(".png", img)
        return buf.tobytes() if ok else None
    except Exception:
        return None


def luma_waveform(frame_bgr, w=240, h=48):
    """Luma waveform as PNG bytes (x = source x, y = luma)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame_bgr is None:
        return None
    try:
        grey = cv2.cvtColor(cv2.resize(frame_bgr, (w, h)), cv2.COLOR_BGR2GRAY)
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        for x in range(w):
            for y in range(h):
                value = int(grey[y, x])
                py = h - 1 - int(value / 255.0 * (h - 1))
                canvas[py, x] = (80, 255, 80)
        canvas = cv2.GaussianBlur(canvas, (3, 3), 0)
        ok, buf = cv2.imencode(".png", canvas)
        return buf.tobytes() if ok else None
    except Exception:
        return None


def rgb_parade(frame_bgr, w=240, h=64):
    """Split RGB parade as PNG bytes (three side-by-side histograms)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame_bgr is None:
        return None
    try:
        third = max(4, w // 3)
        img = np.zeros((h, third * 3, 3), dtype=np.uint8)
        colors = ((0, 0, 255), (0, 255, 0), (255, 0, 0))
        for channel, color in enumerate(colors):
            hist = cv2.calcHist([frame_bgr], [channel], None, [third], [0, 256]).flatten()
            peak = float(hist.max()) or 1.0
            for x, value in enumerate(hist):
                bar = int((value / peak) * (h - 2))
                if bar <= 0:
                    continue
                cv2.line(img, (channel * third + x, h - 1),
                         (channel * third + x, h - 1 - bar), color, 1)
        ok, buf = cv2.imencode(".png", img)
        return buf.tobytes() if ok else None
    except Exception:
        return None


def vectorscope(frame_bgr, size=128):
    """Cr/Cb vectorscope as PNG bytes (round scope with a graticule ring)."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    if frame_bgr is None:
        return None
    try:
        size = max(48, int(size))
        small = cv2.resize(frame_bgr, (128, 72))
        ycrcb = cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb)
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        centre = size // 2
        cv2.circle(canvas, (centre, centre), centre - 2, (40, 40, 40), 1)
        for row in ycrcb:
            for cr, cb in ((int(p[1]), int(p[2])) for p in row):
                x = int(centre + (cb - 128) / 128.0 * (centre - 4))
                y = int(centre - (cr - 128) / 128.0 * (centre - 4))
                if 0 <= x < size and 0 <= y < size:
                    canvas[y, x] = (200, 200, 200)
        canvas = cv2.GaussianBlur(canvas, (3, 3), 0)
        ok, buf = cv2.imencode(".png", canvas)
        return buf.tobytes() if ok else None
    except Exception:
        return None


def scope_strip(frame_bgr, mode="histogram", w=240, h=64):
    """Unified scope entry point used by the UI scope switcher."""
    key = (mode or "histogram").lower()
    if key == "parade":
        return rgb_parade(frame_bgr, w=w, h=h)
    if key == "waveform":
        return luma_waveform(frame_bgr, w=w, h=min(h, 48))
    if key == "vectorscope":
        return vectorscope(frame_bgr, size=min(w, h) or 128)
    return frame_histogram_strip(frame_bgr, w=w, h=h)


def list_scopes() -> list[str]:
    """Scope modes available in the UI."""
    return list(_SCOPE_MODES)
