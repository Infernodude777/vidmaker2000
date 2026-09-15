import cv2
import os
from video_processor import render_frame
from filters import apply_fade
from profiles import PROFILES as _PROFILES


# preset fields: width, height, fps, codec, quality (mp4v 0-100),
# fit ("contain" letterbox | "cover" centre-crop | "stretch"),
# category (UI grouping), platform (UI tag)
EXPORT_PRESETS = {
    "preview_720p": {"width": 1280, "height": 720, "fps": 30.0, "codec": "mp4v",
                     "quality": 70, "fit": "cover", "category": "General",
                     "platform": "Editor preview"},
    "full_1080p": {"width": 1920, "height": 1080, "fps": 30.0, "codec": "mp4v",
                   "quality": 85, "fit": "cover", "category": "General",
                   "platform": "Master"},
    "full_4k": {"width": 3840, "height": 2160, "fps": 30.0, "codec": "mp4v",
                "quality": 90, "fit": "cover", "category": "General",
                "platform": "4K master"},
    "square_1080": {"width": 1080, "height": 1080, "fps": 30.0, "codec": "mp4v",
                    "quality": 80, "fit": "cover", "category": "Social",
                    "platform": "Instagram feed"},
    "vertical_1080x1920": {"width": 1080, "height": 1920, "fps": 30.0, "codec": "mp4v",
                           "quality": 80, "fit": "cover", "category": "Social",
                           "platform": "Stories / Reels / TikTok"},
    "tiktok_1080p30": {"width": 1080, "height": 1920, "fps": 30.0, "codec": "mp4v",
                       "quality": 85, "fit": "cover", "category": "Social",
                       "platform": "TikTok"},
    "reels_1080p30": {"width": 1080, "height": 1920, "fps": 30.0, "codec": "mp4v",
                      "quality": 85, "fit": "cover", "category": "Social",
                      "platform": "Instagram Reels"},
    "shorts_1080p60": {"width": 1080, "height": 1920, "fps": 60.0, "codec": "mp4v",
                       "quality": 85, "fit": "cover", "category": "Social",
                       "platform": "YouTube Shorts (60fps)"},
    "youtube_1080p60": {"width": 1920, "height": 1080, "fps": 60.0, "codec": "mp4v",
                        "quality": 90, "fit": "cover", "category": "YouTube",
                        "platform": "1080p60"},
    "youtube_4k": {"width": 3840, "height": 2160, "fps": 30.0, "codec": "mp4v",
                   "quality": 95, "fit": "cover", "category": "YouTube",
                   "platform": "2160p"},
    "cinema_24": {"width": 1920, "height": 1080, "fps": 24.0, "codec": "mp4v",
                  "quality": 85, "fit": "cover", "category": "Film",
                  "platform": "24fps cinematic"},
    "cinema_4k_dc": {"width": 4096, "height": 2160, "fps": 24.0, "codec": "mp4v",
                     "quality": 95, "fit": "cover", "category": "Film",
                     "platform": "DCI 4K"},
}


# delivery profiles (profiles.py) merge into the export presets, preserving
# any hand-tuned entry with the same name
for _pname, _prof in _PROFILES.items():
    EXPORT_PRESETS.setdefault(_pname, {"width": _prof["width"], "height": _prof["height"],
                                       "fps": float(_prof["fps"]), "codec": "mp4v"})


def get_preset(name="preview_720p"):
    return dict(EXPORT_PRESETS.get(name, EXPORT_PRESETS["preview_720p"]))


def list_presets():
    return sorted(EXPORT_PRESETS.keys())


def preset_categories():
    """Category -> [preset names] for grouped UI menus."""
    out: dict[str, list[str]] = {}
    for name, p in EXPORT_PRESETS.items():
        out.setdefault(p.get("category", "General"), []).append(name)
    return {k: sorted(v) for k, v in out.items()}


def preset_info(name):
    """One-line human summary used in UI tooltips."""
    p = get_preset(name)
    return (f"{p['width']}x{p['height']} @ {p['fps']:g}fps · q{p.get('quality', 80)} · "
            f"{p.get('fit', 'cover')} · {p.get('platform', '')}")


def add_custom_preset(name, width, height, fps=30.0, quality=80, fit="cover"):
    """Register a session custom preset (not persisted)."""
    key = safe_preset_name(name)
    EXPORT_PRESETS[key] = {"width": max(16, int(width)), "height": max(16, int(height)),
                           "fps": max(1.0, min(120.0, float(fps))),
                           "codec": "mp4v", "quality": max(10, min(100, int(quality))),
                           "fit": fit if fit in ("contain", "cover", "stretch") else "cover",
                           "category": "Custom", "platform": "Custom"}
    return key


def safe_preset_name(name):
    keep = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (name or "custom"))
    base = (keep.strip("_") or "custom").lower()
    key, n = base, 2
    while key in EXPORT_PRESETS:
        key = f"{base}_{n}"
        n += 1
    return key


def target_geometry(src_w, src_h, preset, grade=None):
    """Output (w, h, fps) honouring rotation and even-dimension rules."""
    w = int(preset["width"]); h = int(preset["height"])
    fps = float(preset.get("fps", 30.0))
    if grade is not None and getattr(grade, "rotate", 0) in (90, 270):
        w, h = h, w
    return max(2, w - w % 2), max(2, h - h % 2), fps


def _fit_frame(frame, tw, th, mode):
    """Resize ``frame`` to (tw, th) using contain/cover/stretch semantics."""
    h, w = frame.shape[:2]
    if w == tw and h == th:
        return frame
    if mode == "stretch":
        return cv2.resize(frame, (tw, th))
    scale = min(tw / w, th / h) if mode == "contain" else max(tw / w, th / h)
    nw, nh = max(2, int(w * scale)) // 2 * 2, max(2, int(h * scale)) // 2 * 2
    resized = cv2.resize(frame, (nw, nh))
    if mode == "cover":
        x0 = max(0, (nw - tw) // 2); y0 = max(0, (nh - th) // 2)
        return resized[y0:y0 + th, x0:x0 + tw]
    # contain: letterbox onto black
    canvas = __import__("numpy").zeros((th, tw, 3), dtype=frame.dtype)
    x0 = (tw - nw) // 2; y0 = (th - nh) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = resized
    return canvas


def _ken_burns(frame, kb, t01):
    """Apply Ken Burns pan/zoom to a still frame at progress t01 (0..1)."""
    if frame is None or not kb:
        return frame
    t = max(0.0, min(1.0, float(t01)))
    h, w = frame.shape[:2]
    zs = float(kb.get("zs", 1.0)); ze = float(kb.get("ze", 1.15))
    px = float(kb.get("px", 0.0)); py = float(kb.get("py", 0.0))
    z = zs + (ze - zs) * t
    z = max(1.0, min(4.0, z))
    # pan target in source pixels, eased
    tx = px * w * t
    ty = py * h * t
    # crop window at zoom z centred on pan target
    cw, ch = w / z, h / z
    cx = max(cw / 2, min(w - cw / 2, w / 2 + tx))
    cy = max(ch / 2, min(h - ch / 2, h / 2 + ty))
    x0 = int(max(0, cx - cw / 2)); y0 = int(max(0, cy - ch / 2))
    x1 = int(min(w, x0 + cw)); y1 = int(min(h, y0 + ch))
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return frame
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)


def _iter_source_frames(clip, fps, depth=0):
    kind = getattr(clip, "kind", "video") or "video"
    dur = float(getattr(clip, "trim_dur", 0) or 0)
    if dur <= 0:
        dur = float(getattr(clip, "duration", 0) or 0)
    spd = max(0.25, min(4.0, float(getattr(clip, "speed", 1.0) or 1.0)))
    kb = getattr(clip, "kenburns", None)
    # dur (trim_dur) already encodes speed — occupancy on the timeline
    n_out = max(1, int(dur * fps))
    if kind == "nested":
        # a nested clip plays its sub-timeline; in_point/out_point trim it.
        # depth guard stops pathological self-nesting at render time.
        sub = getattr(clip, "nested_timeline", lambda: None)()
        if sub is None or depth > 3:
            return
        skip = int(round(float(getattr(clip, "in_point", 0.0) or 0.0) * fps))
        produced = 0

        def _walk(tl, d):
            for sc in tl.clips:
                yield from _iter_source_frames(sc, fps, d)

        for idx, fr in enumerate(_walk(sub, depth + 1)):
            if idx < skip:
                continue
            if produced >= n_out:
                break
            yield fr
            produced += 1
        return
    if kind == "image":
        still = cv2.imread(clip.path, cv2.IMREAD_COLOR)
        if still is None:
            return
        if kb:
            for i in range(n_out):
                yield _ken_burns(still, kb, i / max(1, n_out - 1))
            return
        for _ in range(n_out):
            yield still
        return
    cap = cv2.VideoCapture(clip.path)
    if not cap.isOpened():
        return
    cfps = float(getattr(clip, "fps", 0) or fps) or fps
    start = int(clip.in_point * cfps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    # per-clip speed: source position advances ``spd``x per output frame.
    # spd > 1 skips source frames; spd < 1 holds frames for smooth slow-mo.
    src_per_out = spd * cfps / max(1.0, fps)
    last_frame = None
    src_pos = 0.0
    for _ in range(n_out):
        target = int(src_pos)
        ok, frame = cap.read()
        while ok and cap.get(cv2.CAP_PROP_POS_FRAMES) - 1 < target:
            ok, frame = cap.read()
        if not ok:
            if last_frame is not None:
                yield last_frame
            src_pos += src_per_out
            continue
        last_frame = frame
        yield frame
        src_pos += src_per_out
    cap.release()


def _source_geometry(clips):
    """First usable source geometry (w, h, fps), looking inside nested clips."""
    for c in clips:
        kind = getattr(c, "kind", "video") or "video"
        if kind == "nested":
            sub = getattr(c, "nested_timeline", lambda: None)()
            if sub is not None and getattr(sub, "clips", None):
                got = _source_geometry(sub.clips)
                if got[0] > 0:
                    return got
            continue
        if kind == "image":
            still = cv2.imread(c.path, cv2.IMREAD_COLOR)
            if still is not None:
                h, w = still.shape[:2]
                return w, h, float(getattr(c, "fps", 0) or 30.0) or 30.0
        else:
            cap0 = cv2.VideoCapture(c.path)
            if cap0.isOpened():
                w = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                h = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                fps = float(cap0.get(cv2.CAP_PROP_FPS) or 30.0)
                cap0.release()
                if w > 0 and h > 0:
                    return w, h, fps or 30.0
    return 0, 0, 30.0


def export_timeline(timeline, grade, out_path, progress_cb=None,
                    max_frames=1800, preset=None, cancel_flag=None):
    clips = [c for c in timeline.clips
             if (getattr(c, "path", "") and os.path.exists(c.path))
             or getattr(c, "kind", "") == "nested"]
    if not clips:
        return {"ok": False, "error": "no clips"}
    sw, sh, sfps = _source_geometry(clips)
    if sw <= 0 or sh <= 0:
        return {"ok": False, "error": "unreadable media"}
    if preset:
        p = get_preset(preset)
        w, h, fps = target_geometry(sw, sh, p, grade)
        fit = p.get("fit", "cover")
        quality = int(p.get("quality", 80))
    else:
        w, h = sw - sw % 2, sh - sh % 2
        fps = sfps or 30.0
        fit, quality = "cover", 80
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    try:
        # best-effort quality hint (honoured by backends that support it)
        out.set(cv2.VIDEOWRITER_PROP_QUALITY, quality)
    except Exception:
        pass
    if not out.isOpened():
        return {"ok": False, "error": "writer failed"}
    done = 0
    prev_last = None
    for clip in clips:
        if done >= max_frames:
            break
        if cancel_flag and cancel_flag():
            break
        dur = float(getattr(clip, "trim_dur", 0) or 0)
        if dur <= 0:
            dur = float(getattr(clip, "duration", 0) or 0)
        trans = getattr(clip, "transition", "cut") or "cut"
        trans_dur = float(getattr(clip, "trans_dur", 0.5) or 0.5)
        caption = str(getattr(clip, "caption", "") or "")
        caption_style = getattr(clip, "text_style", None)
        fade_in = float(getattr(clip, "fade_in", 0.0) or 0.0)
        fade_out = float(getattr(clip, "fade_out", 0.0) or 0.0)
        for fidx, frame in enumerate(_iter_source_frames(clip, fps)):
            if done >= max_frames:
                break
            if cancel_flag and cancel_flag():
                break
            local = fidx / max(1, fps)
            g = render_frame(frame, grade, local, dur,
                             prev_frame=prev_last, trans=trans,
                             trans_dur=trans_dur, caption=caption,
                             caption_style=caption_style)
            if fade_in > 0 or fade_out > 0:
                g = apply_fade(g, fade_in, fade_out, local, dur)
            prev_last = g.copy()
            if (g.shape[1], g.shape[0]) != (w, h):
                g = _fit_frame(g, w, h, fit)
            out.write(g)
            done += 1
            if progress_cb and done % 30 == 0:
                progress_cb(done)
    out.release()
    info = {"ok": True, "frames": done, "path": out_path,
            "muted": bool(grade.muted), "width": w, "height": h, "fps": fps}
    if preset:
        info["preset"] = preset
    return info


def export_gif(timeline, grade, out_path, fps=10.0, max_seconds=10.0,
               width=320, progress_cb=None):
    """Looping GIF of the timeline (grades/transitions/captions applied).

    Capped at ``max_seconds`` of output so a long timeline cannot produce a
    gigantic GIF by accident. Uses Pillow, which is already a dependency.
    """
    clips = [c for c in timeline.clips
             if (getattr(c, "path", "") and os.path.exists(c.path))
             or getattr(c, "kind", "") == "nested"]
    if not clips:
        return {"ok": False, "error": "no clips"}
    budget = max(1, int(max_seconds * fps))
    frames = []
    prev_last = None
    for clip in clips:
        for fidx, frame in enumerate(_iter_source_frames(clip, fps)):
            if len(frames) >= budget:
                break
            local = fidx / max(1.0, fps)
            g = render_frame(frame, grade, local, float(getattr(clip, "trim_dur", 1) or 1),
                             prev_frame=prev_last,
                             trans=getattr(clip, "transition", "cut") or "cut",
                             trans_dur=float(getattr(clip, "trans_dur", 0.5) or 0.5),
                             caption=str(getattr(clip, "caption", "") or ""),
                             caption_style=getattr(clip, "text_style", None))
            prev_last = g.copy()
            h, w0 = g.shape[:2]
            if w0 != width:
                nh = max(1, int(h * width / w0))
                g = cv2.resize(g, (width, nh))
            frames.append(cv2.cvtColor(g, cv2.COLOR_BGR2RGB))
            if progress_cb and len(frames) % 20 == 0:
                progress_cb(len(frames))
        if len(frames) >= budget:
            break
    if not frames:
        return {"ok": False, "error": "no frames rendered"}
    try:
        from PIL import Image
        imgs = [Image.fromarray(f) for f in frames]
        imgs[0].save(out_path, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / max(1.0, fps)), loop=0)
    except Exception as ex:
        return {"ok": False, "error": f"gif encode failed: {ex}"}
    return {"ok": True, "frames": len(frames), "path": out_path}
