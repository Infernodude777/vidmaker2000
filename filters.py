import cv2
import numpy as np
import random


def apply_vignette(frame, strength=0.0):
    if strength <= 0.01:
        return frame
    h, w = frame.shape[:2]
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max(w, h)
    mask = 1.0 - np.clip(dist * strength * 1.6, 0, 0.85)
    mask = mask[:, :, None].astype(np.float32)
    return np.clip(frame.astype(np.float32) * mask, 0, 255).astype(np.uint8)


def apply_blur(frame, amount=0.0):
    if amount <= 0.01:
        return frame
    k = int(1 + amount * 12)
    if k % 2 == 0:
        k += 1
    return cv2.GaussianBlur(frame, (k, k), 0)


def apply_sharpen(frame, amount=0.0):
    if amount <= 0.01:
        return frame
    blur = cv2.GaussianBlur(frame, (0, 0), 2.0)
    return cv2.addWeighted(frame, 1.0 + amount * 1.4, blur, -amount * 1.4, 0)


def apply_pixelate(frame, amount=0.0):
    if amount <= 0.01:
        return frame
    h, w = frame.shape[:2]
    div = int(1 + amount * 24)
    tiny = cv2.resize(frame, (max(1, w // div), max(1, h // div)), interpolation=cv2.INTER_NEAREST)
    return cv2.resize(tiny, (w, h), interpolation=cv2.INTER_NEAREST)


def apply_glitch(frame, amount=0.0, seed=7):
    if amount <= 0.01:
        return frame
    out = frame.copy()
    h, w = out.shape[:2]
    rnd = random.Random(seed)
    n = int(1 + amount * 8)
    for _ in range(n):
        y0 = rnd.randrange(0, h)
        bh = rnd.randrange(4, max(6, int(h * 0.08)))
        dx = rnd.randrange(-int(w * 0.08), int(w * 0.08))
        y1 = min(h, y0 + bh)
        row = out[y0:y1, :].copy()
        out[y0:y1, :] = np.roll(row, dx, axis=1)
    if amount > 0.45:
        out[:, :, 1] = np.roll(out[:, :, 1], 2, axis=1)
    return out


def apply_fade(frame, fade_in=0.0, fade_out=0.0, t=0.0, dur=1.0):
    f = 1.0
    if fade_in > 0 and t < fade_in:
        f = min(f, t / max(1e-3, fade_in))
    if fade_out > 0 and t > dur - fade_out:
        f = min(f, max(0.0, (dur - t) / max(1e-3, fade_out)))
    if f >= 0.999:
        return frame
    return (frame.astype(np.float32) * f).astype(np.uint8)


def apply_grain(frame, amount=0.0, seed=11):
    if amount <= 0.01:
        return frame
    rnd = np.random.RandomState(seed)
    noise = rnd.normal(0, 12 * amount, frame.shape[:2])
    out = frame.astype(np.float32) + noise[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_chromatic(frame, amount=0.0):
    if amount <= 0.01:
        return frame
    dx = int(1 + amount * 6)
    b, g, r = cv2.split(frame)
    b = np.roll(b, -dx, axis=1)
    r = np.roll(r, dx, axis=1)
    return cv2.merge([b, g, r])


def apply_scanlines(frame, amount=0.0):
    if amount <= 0.01:
        return frame
    out = frame.copy()
    out[::3, :] = (out[::3, :].astype(np.float32) * (1.0 - 0.35 * amount)).astype(np.uint8)
    return out
