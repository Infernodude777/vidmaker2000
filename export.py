import cv2
import os
from video_processor import grade_frame, render_frame
from filters import apply_fade
from profiles import PROFILES as _PROFILES, crop_box


EXPORT_PRESETS = {
    "preview_720p": {"width": 1280, "height": 720, "fps": 30.0, "codec": "mp4v"},
    "full_1080p": {"width": 1920, "height": 1080, "fps": 30.0, "codec": "mp4v"},
    "square_1080": {"width": 1080, "height": 1080, "fps": 30.0, "codec": "mp4v"},
    "vertical_1080x1920": {"width": 1080, "height": 1920, "fps": 30.0, "codec": "mp4v"},
}


# delivery profiles (profiles.py) merge into the export presets, preserving
# any hand-tuned entry with the same name
for _pname, _prof in _PROFILES.items():
    EXPORT_PRESETS.setdefault(_pname, {"width": _prof["width"], "height": _prof["height"],
                                       "fps": float(_prof["fps"]), "codec": "mp4v"})


def get_preset(name="preview_720p"):
    return EXPORT_PRESETS.get(name, EXPORT_PRESETS["preview_720p"])


def list_presets():
    return sorted(EXPORT_PRESETS.keys())


def _iter_source_frames(clip, fps):
    kind = getattr(clip, "kind", "video") or "video"
    dur = float(getattr(clip, "trim_dur", 0) or 0)
    if dur <= 0:
        dur = float(getattr(clip, "duration", 0) or 0)
    n_out = max(1, int(dur * fps))
    if kind == "image":
        still = cv2.imread(clip.path, cv2.IMREAD_COLOR)
        if still is None:
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
    last_frame = None
    for _ in range(n_out):
        ok, frame = cap.read()
        if not ok:
            if last_frame is not None:
                yield last_frame
            continue
        last_frame = frame
        yield frame
    cap.release()


def export_timeline(timeline, grade, out_path, progress_cb=None,
                    max_frames=1800, preset=None, cancel_flag=None):
    clips = [c for c in timeline.clips if getattr(c, "path", "") and os.path.exists(c.path)]
    if not clips:
        return {"ok": False, "error": "no clips"}
    w = h = 0
    fps = 30.0
    for c in clips:
        kind = getattr(c, "kind", "video") or "video"
        if kind == "image":
            still = cv2.imread(c.path, cv2.IMREAD_COLOR)
            if still is not None:
                h, w = still.shape[:2]
                fps = float(getattr(c, "fps", 0) or 30.0)
                break
        else:
            cap0 = cv2.VideoCapture(c.path)
            if cap0.isOpened():
                w = int(cap0.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                h = int(cap0.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                fps = float(cap0.get(cv2.CAP_PROP_FPS) or 30.0)
                cap0.release()
                if w > 0 and h > 0:
                    break
    if w <= 0 or h <= 0:
        return {"ok": False, "error": "unreadable media"}
    if preset:
        p = get_preset(preset)
        w, h = int(p["width"]), int(p["height"])
        fps = float(p.get("fps", 30.0))
    if getattr(grade, "rotate", 0) in (90, 270):
        w, h = h, w
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    if not out.isOpened():
        return {"ok": False, "error": "writer failed"}
    done = 0
    prev_last = None
    for clip in clips:
        if done >= max_frames:
            break
        if cancel_flag and cancel_flag():
            break
        kind = getattr(clip, "kind", "video") or "video"
        dur = float(getattr(clip, "trim_dur", 0) or 0)
        if dur <= 0:
            dur = float(getattr(clip, "duration", 0) or 0)
        n_out = max(1, int(dur * fps))
        trans = getattr(clip, "transition", "cut") or "cut"
        trans_dur = float(getattr(clip, "trans_dur", 0.5) or 0.5)
        caption = str(getattr(clip, "caption", "") or "")
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
                             trans_dur=trans_dur, caption=caption)
            if fade_in > 0 or fade_out > 0:
                g = apply_fade(g, fade_in, fade_out, local, dur)
            prev_last = g.copy()
            if preset and (g.shape[1], g.shape[0]) != (w, h):
                # aspect-aware: centre-crop to the profile aspect instead of squashing
                x0, y0, x1, y1 = crop_box(g.shape[1], g.shape[0], preset)
                if (x0, y0, x1, y1) != (0, 0, g.shape[1], g.shape[0]):
                    g = g[y0:y1, x0:x1]
            if (g.shape[1], g.shape[0]) != (w, h):
                g = cv2.resize(g, (w, h))
            out.write(g)
            done += 1
            if progress_cb and done % 30 == 0:
                progress_cb(done)
    out.release()
    return {"ok": True, "frames": done, "path": out_path, "muted": bool(grade.muted)}
