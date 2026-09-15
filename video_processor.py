import cv2
import numpy as np
import lut as lut_mod
from filters import (
    apply_vignette, apply_blur, apply_sharpen,
    apply_pixelate, apply_glitch, apply_fade,
    apply_grain, apply_chromatic, apply_scanlines,
)
from transitions import apply_transition

MAX_PREVIEW_W = 640
IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp"}
VIDEO_EXTS = {"mp4", "mov", "webm", "avi", "mkv"}
DEFAULT_IMAGE_DURATION = 3.0
DEFAULT_IMAGE_FPS = 30.0

_PROBE_CACHE = {}


def _ext_of(path):
    return (str(path).rsplit(".", 1)[-1] if "." in str(path) else "").lower()


def probe_media(path, image_duration=DEFAULT_IMAGE_DURATION):
    ext = _ext_of(path)
    if ext in IMAGE_EXTS:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        return {"kind": "image", "fps": float(DEFAULT_IMAGE_FPS),
                "frames": int(image_duration * DEFAULT_IMAGE_FPS),
                "width": int(w), "height": int(h), "duration": float(image_duration)}
    info = probe_video(path)
    if info is not None:
        info["kind"] = "video"
    return info


def probe_video(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    dur = n / fps if fps else 0.0
    cap.release()
    return {"fps": float(fps), "frames": n, "width": w, "height": h, "duration": float(dur)}


def grab_media_frame(path, kind="video", t_sec=0.0, preview=True):
    if (kind or "video") == "image":
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            return None, None
        if preview and img.shape[1] > MAX_PREVIEW_W:
            s = MAX_PREVIEW_W / img.shape[1]
            img = cv2.resize(img, (MAX_PREVIEW_W, int(img.shape[0] * s)))
        return img, float(t_sec or 0.0)
    return grab_frame(path, t_sec, preview=preview)


def grab_frame(path, t_sec, preview=True):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None, None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    idx = int(max(0, min(n - 1, t_sec * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None, None
    if preview and frame.shape[1] > MAX_PREVIEW_W:
        s = MAX_PREVIEW_W / frame.shape[1]
        frame = cv2.resize(frame, (MAX_PREVIEW_W, int(frame.shape[0] * s)))
    return frame, float(idx / fps)


def grade_frame(frame_bgr, g, t_local=0.0, trim_dur=1.0):
    img = frame_bgr.astype(np.float32)
    img = img * (2.0 ** float(getattr(g, "exposure", 0.0)))
    img = img + float(getattr(g, "brightness", 0.0)) * 2.2
    c = float(getattr(g, "contrast", 1.0))
    img = (img - 128.0) * c + 128.0
    hi = float(getattr(g, "highlights", 0.0))
    sh = float(getattr(g, "shadows", 0.0))
    if abs(hi) > 0.01 or abs(sh) > 0.01:
        lum = img.mean(axis=2, keepdims=True) / 255.0
        img = img + (hi * 40 * np.clip(lum - 0.6, 0, 1) - sh * 40 * np.clip(0.4 - lum, 0, 1))
    tmp = float(getattr(g, "temperature", 0.0))
    tint = float(getattr(g, "tint", 0.0))
    if abs(tmp) > 0.01:
        img[:, :, 2] += tmp * 22
        img[:, :, 0] -= tmp * 22
    if abs(tint) > 0.01:
        img[:, :, 1] += tint * 18
    img = np.clip(img, 0, 255).astype(np.uint8)
    sat = float(getattr(g, "saturation", 1.0))
    if abs(sat - 1.0) > 0.01:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat, 0, 255)
        img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    if bool(getattr(g, "grayscale", False)):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    img = apply_blur(img, float(getattr(g, "blur", 0.0)))
    img = apply_sharpen(img, float(getattr(g, "sharpen", 0.0)))
    img = apply_pixelate(img, float(getattr(g, "pixelate", 0.0)))
    img = apply_glitch(img, float(getattr(g, "glitch", 0.0)), seed=int(t_local * 10) + 7)
    img = apply_grain(img, float(getattr(g, "grain", 0.0)))
    img = apply_chromatic(img, float(getattr(g, "chromatic", 0.0)))
    img = apply_scanlines(img, float(getattr(g, "scanlines", 0.0)))
    lut_name = str(getattr(g, "lut", "") or "neutral")
    if lut_name and lut_name != "neutral":
        img = lut_mod.apply_preset(img, lut_name)
    img = apply_vignette(img, float(getattr(g, "vignette", 0.0)))
    img = apply_fade(img, float(getattr(g, "fade_in", 0.0)), float(getattr(g, "fade_out", 0.0)), t_local, trim_dur)
    if bool(getattr(g, "flip_h", False)):
        img = cv2.flip(img, 1)
    if bool(getattr(g, "flip_v", False)):
        img = cv2.flip(img, 0)
    rot = int(getattr(g, "rotate", 0)) % 360
    if rot == 90:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif rot == 180:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif rot == 270:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def render_frame(frame_bgr, g, t_local=0.0, trim_dur=1.0,
                 prev_frame=None, trans="cut", trans_dur=0.5, caption="",
                 caption_style=None):
    graded = grade_frame(frame_bgr, g, t_local, trim_dur)
    if prev_frame is not None and trans and trans != "cut" and t_local < trans_dur:
        t = max(0.0, min(1.0, t_local / max(0.01, trans_dur)))
        graded = apply_transition(trans, prev_frame, graded, t)
    if caption:
        try:
            from captions import draw_caption
            graded = draw_caption(graded, caption, style=caption_style)
        except Exception:
            pass
    return graded


def frame_to_png_bytes(frame_bgr):
    ok, buf = cv2.imencode(".png", frame_bgr)
    return buf.tobytes() if ok else None


def frame_to_jpeg_bytes(frame_bgr, quality=80):
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buf.tobytes() if ok else None
