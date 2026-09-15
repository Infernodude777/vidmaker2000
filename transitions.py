"""Clip-to-clip transitions.

Every original transition keeps its signature; ``apply_transition`` gains the
new names and always returns something usable so a render loop never dies on a
bad transition name.
"""

from __future__ import annotations

DEFAULT_NAMES = (
    "cut", "crossfade", "wipe_left", "dip_to_black", "slide_left",
    "zoom_dissolve", "flash", "push_up", "whip_pan", "glitch_cut",
)


def _safe_frames(a, b):
    """Coerce two frames to matching numpy arrays (None when impossible)."""
    if a is None or b is None:
        return None, None
    try:
        import numpy as np
    except Exception:
        return None, None
    a_arr = np.asarray(a)
    b_arr = np.asarray(b)
    if a_arr.shape != b_arr.shape:
        try:
            import cv2
            b_arr = cv2.resize(b_arr, (a_arr.shape[1], a_arr.shape[0]))
        except Exception:
            return None, None
    return a_arr, b_arr


def _blend(a, b, t):
    """Linear blend of two frames (0 = a, 1 = b)."""
    try:
        import cv2
    except Exception:
        return a if t < 0.5 else b
    return cv2.addWeighted(a, 1.0 - t, b, t, 0)


def crossfade(a, b, t):
    """Classic dissolve."""
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    return _blend(a_arr, b_arr, t)


def wipe_left(a, b, t):
    """Hard-edged wipe moving left to right."""
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    width = a_arr.shape[1]
    edge = int(width * t)
    out = a_arr.copy()
    out[:, :edge] = b_arr[:, :edge]
    return out


def dip_to_black(a, b, t):
    """Fade out to black, then in from black."""
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    if t < 0.5:
        return _blend(a_arr, a_arr * 0, t * 2.0)
    return _blend(b_arr * 0, b_arr, (t - 0.5) * 2.0)


def slide_left(a, b, t):
    """Both frames slide left together."""
    try:
        import numpy as np
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    width = a_arr.shape[1]
    shift = int(width * t)
    out = np.zeros_like(a_arr)
    if shift < width:
        out[:, :width - shift] = a_arr[:, shift:]
    if shift > 0:
        out[:, width - shift:] = b_arr[:, :shift]
    return out


def zoom_dissolve(a, b, t):
    """Zoom the outgoing frame while crossfading."""
    try:
        import cv2
        import numpy as np
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    scale = 1.0 + 0.25 * t
    height, width = a_arr.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), 0.0, scale)
    zoomed = cv2.warpAffine(a_arr, matrix, (width, height))
    return _blend(zoomed, b_arr, t)


def flash(a, b, t):
    """Blow out to white at the midpoint, like a flash cut."""
    try:
        import numpy as np
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    white = np.full_like(a_arr, 255)
    if t < 0.5:
        return _blend(a_arr, white, t * 2.0)
    return _blend(white, b_arr, (t - 0.5) * 2.0)


def push_up(a, b, t):
    """The outgoing frame is pushed up by the incoming one."""
    try:
        import numpy as np
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    height = a_arr.shape[0]
    shift = int(height * t)
    out = np.zeros_like(a_arr)
    if shift < height:
        out[:height - shift] = a_arr[shift:]
    if shift > 0:
        out[height - shift:] = b_arr[:shift]
    return out


def whip_pan(a, b, t):
    """Fast horizontal motion blur that masks the cut."""
    try:
        import cv2
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    kernel = max(3, int(3 + 24 * abs(0.5 - t) * 2))
    if kernel % 2 == 0:
        kernel += 1
    blurred_a = cv2.blur(a_arr, (kernel, 1))
    blurred_b = cv2.blur(b_arr, (kernel, 1))
    eased = t * t * (3.0 - 2.0 * t)
    return _blend(blurred_a, blurred_b, eased)


def glitch_cut(a, b, t):
    """Datamosh-style row displacement around the cut point."""
    try:
        import numpy as np
    except Exception:
        return crossfade(a, b, t)
    a_arr, b_arr = _safe_frames(a, b)
    if a_arr is None:
        return a if a is not None else b
    t = max(0.0, min(1.0, float(t)))
    base = _blend(a_arr, b_arr, t)
    if not (0.2 <= t <= 0.8):
        return base
    rng = np.random.default_rng(int(t * 1000))
    height = base.shape[0]
    out = base.copy()
    for _ in range(6):
        row = int(rng.integers(0, height))
        span = int(rng.integers(4, max(6, height // 6)))
        shift = int(rng.integers(-24, 25))
        out[row:row + span] = np.roll(base[row:row + span], shift, axis=1)
    return out


def list_names():
    """Every transition name (used by the UI row)."""
    return list(DEFAULT_NAMES)


def apply_transition(name, a, b, t):
    """Dispatch a transition by name; unknown names crossfade."""
    key = (name or "cut").lower()
    if key == "cut":
        return b if float(t) >= 0.5 else a
    table = {
        "crossfade": crossfade,
        "wipe_left": wipe_left,
        "dip_to_black": dip_to_black,
        "slide_left": slide_left,
        "zoom_dissolve": zoom_dissolve,
        "flash": flash,
        "push_up": push_up,
        "whip_pan": whip_pan,
        "glitch_cut": glitch_cut,
    }
    func = table.get(key, crossfade)
    try:
        return func(a, b, t)
    except Exception:
        return crossfade(a, b, t)
