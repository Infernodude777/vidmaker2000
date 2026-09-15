import flet as ft
import os
import threading
import copy
import cv2


def _probe_cached(path, **kw):
    from video_processor import probe_media as _pm
    key = (str(path),)
    if key not in video_processor._PROBE_CACHE:
        video_processor._PROBE_CACHE[key] = _pm(path, **kw)
    return video_processor._PROBE_CACHE[key]

import video_processor
import tempfile
from transitions import list_names as list_transition_names
import themes as themes_mod
from themes import set_theme, get_theme as get_theme_colors, list_themes
from effects_rack import list_looks, apply_look
from audio_wave import render_audio_strip
from thumbnails import cached_filmstrip
from export import preset_categories, preset_info, add_custom_preset
from project_store import save_project, load_project_full, default_save_path
from utils import BG, PANEL, INK, MUTED, ORANGE, VIOLET, MINT, RED, sec_to_tc, safe_name, tc_to_sec
from filters import apply_fade
from timeline import Timeline, TimelineSet, Clip, Grade, Marker
from video_processor import probe_media, grab_media_frame, grade_frame, frame_to_png_bytes
from histogram import frame_histogram_strip, rgb_parade
from captions import draw_caption, TEXT_PRESETS

# live UI palette — starts from utils' neon values, updated by the theme
# picker so refresh() and dynamically-built controls never go stale
ui = dict(bg=BG, panel=PANEL, ink=INK, muted=MUTED,
          accent=ORANGE, secondary=VIOLET, good=MINT, warn=RED,
          panel_edge="#232136", soft_ink="#cfc9e8", hit_bg="#12251c")

# v2 integrations
import keymap
import autosave
import media_index
import scene_detect
import beat_detect
import broll
import lut
import timeline_ops
import proxy_cache
from render_queue import RenderQueue

ALLOWED_VIDEO = ("mp4", "mov", "webm", "avi", "mkv")
ALLOWED_IMAGE = ("png", "jpg", "jpeg", "webp", "bmp")
ALLOWED = ALLOWED_VIDEO + ALLOWED_IMAGE
MAX_MB = 200
# Browser picker transfers file bytes over the websocket; above this the UI
# freezes/glitches, so big videos must use ADD LOCAL PATH instead.
WEB_SOFT_MAX_MB = 60
IMAGE_DEFAULT_DUR = 3.0
BIN_CAP = 100

Icons = getattr(ft, "Icons", getattr(ft, "icons", None))
Fit = getattr(ft, "BoxFit", getattr(ft, "ImageFit", None))
EButton = getattr(ft, "ElevatedButton", None) or getattr(ft, "FilledButton", None) or ft.Button

# 1x1 transparent PNG so ft.Image always has a valid src (Flet 1.0 requires src)
import base64 as _b64
PLACEHOLDER_PNG = _b64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _run_flet(main_fn, port=8550):
    import tempfile as _tf
    import os as _os
    view = ft.AppView.WEB_BROWSER
    up = _os.path.join(_tf.gettempdir(), "vidmaker2000_uploads")
    _os.makedirs(up, exist_ok=True)
    if hasattr(ft, "run"):
        ft.run(main_fn, view=view, port=port, assets_dir=None, upload_dir=up)
    elif hasattr(ft, "app"):
        ft.app(target=main_fn, view=view, port=port, assets_dir=None)
    else:
        raise RuntimeError("no flet runner found")


# ---- branding assets served at the server level ----------------------------
# Flet 1.0 has no favicon hook, so the UI is wrapped in a tiny FastAPI app
# that serves /favicon.ico, /favicon.svg and /apple-touch-icon.png. The same
# paths also work via Flet's static assets dir when running desktop.
_BRAND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_BRAND_FILES = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
    "/favicon-256.png": ("favicon-256.png", "image/png"),
}


def _serve_brand(path: str):
    """Starlette response for a brand file, or None when not found."""
    import mimetypes

    from starlette.responses import FileResponse

    entry = _BRAND_FILES.get(path)
    if not entry:
        return None
    fp = os.path.join(_BRAND_DIR, entry[0])
    if not os.path.exists(fp):
        return None
    mt = entry[1] or mimetypes.guess_type(fp)[0] or "application/octet-stream"
    return FileResponse(fp, media_type=mt)


def _wrap_with_brand(asgi_app):
    """Layer favicon routes in front of the Flet ASGI app."""
    try:
        from fastapi import FastAPI as _FA
        from starlette.requests import Request
        from starlette.responses import Response
    except Exception:
        return asgi_app  # deps missing: fall back to plain Flet

    fa = _FA()

    @fa.get("/favicon.ico", include_in_schema=False)
    async def _favicon_ico(request: Request):
        resp = _serve_brand("/favicon.ico")
        return resp or Response(status_code=404)

    @fa.get("/favicon.svg", include_in_schema=False)
    async def _favicon_svg(request: Request):
        resp = _serve_brand("/favicon.svg")
        return resp or Response(status_code=404)

    @fa.get("/apple-touch-icon.png", include_in_schema=False)
    async def _apple_icon(request: Request):
        resp = _serve_brand("/apple-touch-icon.png")
        return resp or Response(status_code=404)

    @fa.get("/favicon-256.png", include_in_schema=False)
    async def _favicon_png(request: Request):
        resp = _serve_brand("/favicon-256.png")
        return resp or Response(status_code=404)

    fa.mount("/", asgi_app, name="flet")
    return fa


def section(title, color=ORANGE):
    return ft.Text(title, color=color, weight="bold", size=12)


def slider(label, lo, hi, val, on_change, div=100.0):
    return ft.Column([
        ft.Text(label, size=11, color=MUTED),
        ft.Slider(min=lo, max=hi, value=val,
                  divisions=int((hi - lo) * div) or None,
                  active_color=ORANGE, inactive_color="#2a2740",
                  thumb_color=ORANGE, height=28,
                  on_change=on_change),
    ], spacing=0, tight=True)


def spill_picked_to_disk(f, tmpdir, seq=0):
    """Web pickers give bytes (no path). Spill to tmp and return local path.

    Returns (path, skipped_reason). skipped_reason is None on success.
    """
    p = getattr(f, "path", None)
    if p and os.path.exists(p):
        return p, None
    data = getattr(f, "bytes", None)
    if isinstance(data, list):
        try:
            data = bytes(data)
        except Exception:
            return None, "bad data"
    if not data:
        return None, "empty (browser gave no bytes; retry or use ADD LOCAL PATH)"
    size_mb = len(data) / (1024 * 1024)
    if size_mb > WEB_SOFT_MAX_MB:
        return None, (f"{size_mb:.0f}MB too big for browser upload "
                      f"(>{WEB_SOFT_MAX_MB}MB); use ADD LOCAL PATH instead")
    raw_name = (getattr(f, "name", "") or "upload").strip() or "upload"
    base, dot, ext = raw_name.rpartition(".")
    if not dot:
        base, ext = raw_name, ""
    keep = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in base)[:16] or "file"
    fname = f"{seq}_{len(data)}_{keep}" + (f".{ext.lower()[:5]}" if ext else "")
    out = os.path.join(tmpdir, fname)
    try:
        with open(out, "wb") as fh:
            fh.write(data)
        return out, None
    except Exception as ex:
        return None, f"write failed: {ex}"


def sanitize_info(info):
    """Clamp probe results; return None if unusable."""
    if not info:
        return None
    try:
        dur = float(info.get("duration", 0) or 0)
        fps = float(info.get("fps", 30.0) or 30.0)
        w = int(info.get("width", 0) or 0)
        h = int(info.get("height", 0) or 0)
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    fps = min(120.0, max(1.0, fps))
    if (info.get("kind") or "video") == "image":
        dur = IMAGE_DEFAULT_DUR
    dur = min(600.0, max(0.5, dur))
    return {"kind": info.get("kind", "video") or "video", "fps": fps,
            "width": w, "height": h, "duration": dur}


def media_to_clip(path, info, order=0):
    kind = info.get("kind", "video")
    base = os.path.basename(path)[:18] or "clip"
    dur = float(info.get("duration", 0) or 0)
    if kind == "image" and dur <= 0:
        dur = IMAGE_DEFAULT_DUR
    return Clip(path=path, name=base, kind=kind, track="V1",
                duration=dur, fps=float(info.get("fps", 30.0) or 30.0),
                width=int(info.get("width", 0) or 0), height=int(info.get("height", 0) or 0),
                in_point=0.0, out_point=dur, order=order)


def main(page: ft.Page):
    page.title = "vidmaker2000"
    page.bgcolor = BG
    page.padding = 12
    page.spacing = 10
    try:
        page.theme_mode = ft.ThemeMode.DARK
    except Exception:
        pass

    ts = TimelineSet()
    grade = Grade()
    media_bin: list[dict] = []
    state = {"playing": False, "t": 0.0, "sel": 0, "importing": False, "import_seq": 0,
             "tc_mode": "tc"}
    state["zoom"] = 1.0
    state["cap_pos"] = "bottom"
    state["preset"] = "preview_720p"
    tmp_upload = os.path.join(tempfile.gettempdir(), "vidmaker2000_uploads")
    os.makedirs(tmp_upload, exist_ok=True)

    # restore the saved theme before any control is built
    state["light"] = False
    try:
        themes_mod.load(themes_mod.default_path())
    except Exception:
        pass
    try:
        page.bgcolor = get_theme_colors()["bg"]
    except Exception:
        pass

    # ---- v2 services: media library index, render queue, autosave, proxies ----
    media_idx = media_index.MediaIndex()
    render_q = RenderQueue()
    render_thread = {"worker": None}
    autosave_dir = os.path.join(os.path.expanduser("~"), ".vidmaker2000", "autosave")
    os.makedirs(autosave_dir, exist_ok=True)
    proxy_dir = os.path.join(tempfile.gettempdir(), "vidmaker2000_proxies")
    os.makedirs(proxy_dir, exist_ok=True)

    # ---- controls (all with valid initial values) ----
    preview = ft.Image(src=PLACEHOLDER_PNG, fit=Fit.CONTAIN, expand=True)
    hist_img = ft.Image(src=PLACEHOLDER_PNG, width=240, height=64)
    wave_img = ft.Image(src=PLACEHOLDER_PNG, width=240, height=48)
    scope_mode = {"m": "hist"}
    tc = ft.Text("00:00:00", color=INK, font_family="monospace", size=12, expand=True)
    empty_hint = ft.Text("No clips — use IMPORT MEDIA to add video/images",
                         color=MUTED, size=12)
    msg = ft.Text("", color=MINT, size=11)
    clip_row = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)
    markers_row = ft.Row(spacing=6, wrap=True)
    tabs_row = ft.Row(spacing=6, wrap=True)
    bin_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
    queue_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)

    def _render_queue_panel():
        """Compact render-queue status (shown in PROJECT section)."""
        rows = []
        for j in render_q.jobs[-5:]:
            color = {"queued": MUTED, "running": ORANGE, "done": MINT,
                     "failed": RED, "cancelled": MUTED}.get(j.state, MUTED)
            icon = {"queued": "◌", "running": "◐", "done": "●", "failed": "✕",
                    "cancelled": "⊘"}.get(j.state, "·")
            rows.append(ft.Row([
                ft.Text(icon, size=11, color=color),
                ft.Text(f"{j.preset}", size=10, color=ui["soft_ink"], expand=True),
                ft.Text(f"{j.frames}f" if j.state == "done" else j.state,
                        size=10, color=color),
            ], spacing=4, tight=True))
        queue_col.controls = rows or [ft.Text("queue empty — E to export",
                                              size=10, color=MUTED)]
    bin_search = ft.TextField(label="Search bin / indexed library", dense=True,
                              on_submit=lambda e: refresh())
    folder_field = ft.TextField(label="Folder to index for b-roll", dense=True,
                                hint_text="C:\\Videos\\broll")

    def cur() -> Timeline:
        return ts.current()

    def _index_media(path, info, source="import"):
        """Record a newly imported file in the library index + kick a proxy build."""
        try:
            media_idx.add(path, kind=info.get("kind", "video"),
                          duration=float(info.get("duration", 0) or 0),
                          fps=float(info.get("fps", 30.0) or 30.0),
                          width=int(info.get("width", 0) or 0),
                          height=int(info.get("height", 0) or 0),
                          tags=(source,))
        except Exception:
            pass
        if info.get("kind") == "video":
            try:
                threading.Thread(target=proxy_cache.ensure_proxy,
                                 args=(path, proxy_dir), daemon=True).start()
            except Exception:
                pass

    # ---- file pickers: one picker per action (Flet 1.0 web) ----
    # Sharing a single FilePicker across several PickFiles actions glitches;
    # each import button gets its own picker + action instead.
    def ingest_files(files, source="browser"):
        """Probe + bin + timeline a list of picked files. Returns summary msg."""
        added, skipped = [], []
        tl = cur()
        first_new_idx = len(tl.clips)
        for f in files or []:
            fname = (getattr(f, "name", "") or "").strip() or "upload"
            try:
                if (getattr(f, "size", 0) or 0) > MAX_MB * 1024 * 1024:
                    skipped.append(f"{fname}: over {MAX_MB}MB cap")
                    continue
            except Exception:
                pass
            state["import_seq"] += 1
            local, reason = spill_picked_to_disk(f, tmp_upload, state["import_seq"])
            if not local or not os.path.exists(local):
                skipped.append(f"{fname}: {reason or 'unreadable'}")
                continue
            info = sanitize_info(probe_media(local, image_duration=IMAGE_DEFAULT_DUR))
            if not info:
                skipped.append(f"{fname}: unsupported/unreadable "
                               f"({os.path.basename(local)})")
                continue
            if len(media_bin) >= BIN_CAP:
                skipped.append(f"{fname}: bin full ({BIN_CAP})")
                continue
            entry = {"path": local, "name": fname[:24],
                     "kind": info["kind"], "duration": info["duration"],
                     "fps": info["fps"], "width": info["width"],
                     "height": info["height"]}
            media_bin.append(entry)
            _index_media(local, info, source)
            tl.add_clip(media_to_clip(local, info, order=len(tl.clips)))
            added.append(f"{fname[:18]} ({info['duration']:.1f}s)")
        if added:
            # jump playhead to the first newly added clip so import is visible
            state["sel"] = min(first_new_idx, len(tl.clips) - 1)
            state["t"] = sum(c.trim_dur for c in tl.clips[:state["sel"]]) + 0.01
        parts = []
        if added:
            parts.append(f"added {len(added)} via {source}: " + ", ".join(added[:6])
                         + ("…" if len(added) > 6 else ""))
        if skipped:
            parts.append(f"skipped {len(skipped)}: " + "; ".join(skipped[:4])
                         + ("…" if len(skipped) > 4 else ""))
        return " · ".join(parts) if parts else "nothing imported"

    def on_media_picked(e):
        if state["importing"]:
            return
        files = getattr(e, "files", None) or []
        if not files:
            refresh("import cancelled")
            return
        state["importing"] = True
        msg.value = f"importing {len(files)} file(s)…"
        try:
            page.update()
        except Exception:
            pass
        try:
            summary = ingest_files(files, source="browser")
        finally:
            state["importing"] = False
        refresh(summary)

    def ingest_local_path(raw):
        raw = (raw or "").strip().strip("'\"")
        if not raw:
            return "paste a file path first"
        if not os.path.exists(raw):
            return f"not found: {raw[:80]}"
        ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
        if ext not in ALLOWED:
            return f".{ext or '?'} not supported (use {', '.join(sorted(ALLOWED)[:6])}…)"
        try:
            if os.path.getsize(raw) > MAX_MB * 1024 * 1024:
                return f"over {MAX_MB}MB cap"
        except Exception:
            pass
        info = sanitize_info(probe_media(raw, image_duration=IMAGE_DEFAULT_DUR))
        if not info:
            return f"unreadable: {os.path.basename(raw)}"
        if len(media_bin) >= BIN_CAP:
            return f"bin full ({BIN_CAP})"
        tl = cur()
        media_bin.append({"path": raw, "name": os.path.basename(raw)[:24],
                          "kind": info["kind"], "duration": info["duration"],
                          "fps": info["fps"], "width": info["width"],
                          "height": info["height"]})
        _index_media(raw, info, "path")
        tl.add_clip(media_to_clip(raw, info, order=len(tl.clips)))
        state["sel"] = len(tl.clips) - 1
        state["t"] = sum(c.trim_dur for c in tl.clips[:state["sel"]]) + 0.01
        return f"added {os.path.basename(raw)[:24]} ({info['duration']:.1f}s) -> {tl.name}"

    def add_sample():
        """Generate a test image + video locally so the pipeline works with no picker."""
        try:
            import cv2
            import numpy as np
        except Exception as ex:
            return f"sample needs opencv: {ex}"
        try:
            n = state["import_seq"] + 1
            state["import_seq"] = n
            img_p = os.path.join(tmp_upload, f"sample_{n}.png")
            vid_p = os.path.join(tmp_upload, f"sample_{n}.mp4")
            bars = np.zeros((240, 320, 3), dtype=np.uint8)
            for i, col in enumerate([(0, 0, 255), (0, 255, 0), (255, 0, 0),
                                     (0, 255, 255), (255, 0, 255), (255, 255, 0)]):
                bars[:, i * 53:(i + 1) * 53] = col
            cv2.imwrite(img_p, bars)
            out = cv2.VideoWriter(vid_p, cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
            if not out.isOpened():
                return "sample video writer failed"
            for k in range(60):
                frame = np.roll(bars, k * 4, axis=1)
                out.write(frame)
            out.release()
            tl = cur()
            first = len(tl.clips)
            for p in (img_p, vid_p):
                info = sanitize_info(probe_media(p, image_duration=IMAGE_DEFAULT_DUR))
                if not info:
                    continue
                media_bin.append({"path": p, "name": os.path.basename(p),
                                  "kind": info["kind"], "duration": info["duration"],
                                  "fps": info["fps"], "width": info["width"],
                                  "height": info["height"]})
                _index_media(p, info, "sample")
                tl.add_clip(media_to_clip(p, info, order=len(tl.clips)))
            if len(tl.clips) == first:
                return "sample probe failed"
            state["sel"] = first
            state["t"] = sum(c.trim_dur for c in tl.clips[:first]) + 0.01
            return f"sample image+video -> {tl.name} (playhead on new clips)"
        except Exception as ex:
            return f"sample failed: {ex}"

    def scan_uploads():
        found, added = 0, 0
        try:
            names = sorted(os.listdir(tmp_upload))
        except Exception as ex:
            return f"scan failed: {ex}"
        have = {m.get("path") for m in media_bin}
        tl = cur()
        for nm in names:
            ext = nm.rsplit(".", 1)[-1].lower() if "." in nm else ""
            if ext not in ALLOWED:
                continue
            full = os.path.join(tmp_upload, nm)
            if full in have or not os.path.isfile(full):
                continue
            found += 1
            info = sanitize_info(probe_media(full, image_duration=IMAGE_DEFAULT_DUR))
            if not info or len(media_bin) >= BIN_CAP:
                continue
            media_bin.append({"path": full, "name": nm[:24],
                              "kind": info["kind"], "duration": info["duration"],
                              "fps": info["fps"], "width": info["width"],
                              "height": info["height"]})
            tl.add_clip(media_to_clip(full, info, order=len(tl.clips)))
            added += 1
        if added:
            state["sel"] = len(tl.clips) - 1
        return f"scan: {added}/{found} new file(s) from uploads folder"

    def purge_ghost_bin():
        """Remove bin entries and timeline clips whose source files are missing."""
        before = len(media_bin)
        media_bin[:] = [m for m in media_bin if os.path.exists(m.get("path", ""))]
        removed_bin = before - len(media_bin)
        removed_clips = 0
        for tl in ts.timelines:
            keep = [c for c in tl.clips if getattr(c, "path", "") and os.path.exists(c.path)]
            removed_clips += len(tl.clips) - len(keep)
            tl.clips[:] = keep
            for i, c in enumerate(tl.clips):
                c.order = i
        n = removed_bin + removed_clips
        return f"purged {removed_bin} bin + {removed_clips} clip ghost entr{'y' if n == 1 else 'ies'}"

    def fit_to_range(clip, lo=0.0, hi=None):
        """Clamp clip in/out to source bounds while preserving span."""
        hi = hi or clip.duration
        span = clip.out_point - clip.in_point
        clip.in_point = max(lo, min(clip.in_point, hi - 0.2))
        clip.out_point = clip.in_point + span
        clip.out_point = max(clip.in_point + 0.1, min(clip.out_point, hi))

    def set_preset(k):
        state["preset"] = k
        refresh(f"preset: {k}")

    def set_transition(k):
        tl = cur()
        if tl.clips:
            tl.clips[max(0, min(state["sel"], len(tl.clips) - 1))].transition = k
            refresh(f"transition -> {k}")

    def set_caption_text(text):
        tl = cur()
        if tl.clips:
            tl.clips[max(0, min(state["sel"], len(tl.clips) - 1))].caption = text
            refresh("caption set")

    def set_caption_style(k):
        state["cap_pos"] = k
        refresh(f"caption: {k}")

    def set_text_preset(name):
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return "select a clip first"
        c = tl.clips[state["sel"]]
        if not getattr(c, "caption", ""):
            return "type a caption first"
        preset = dict(TEXT_PRESETS.get(name) or {})
        if preset.get("pos"):
            state["cap_pos"] = preset["pos"]
        c.text_style = preset or None
        return f"text style: {name}"

    def set_scope(m):
        scope_mode["m"] = m
        refresh()

    def on_project_picked(e):
        files = getattr(e, "files", None) or []
        if not files:
            return
        state["import_seq"] += 1
        local, reason = spill_picked_to_disk(files[0], tmp_upload, state["import_seq"])
        if not local:
            refresh(f"cannot read project file: {reason}")
            return
        try:
            nts, ng, nbin = load_project_full(local)
            ts.timelines = nts.timelines
            ts.active = nts.active
            grade.__dict__.update(ng.to_dict())
            media_bin.clear()
            media_bin.extend(nbin or [])
            state["t"] = 0.0
            state["sel"] = 0
            sync_grade_ui()
            refresh(f"loaded project {os.path.basename(local)}")
        except Exception as ex:
            refresh(f"load failed: {ex}")

    media_picker_all = ft.FilePicker(on_result=on_media_picked)
    media_picker_img = ft.FilePicker(on_result=on_media_picked)
    media_picker_vid = ft.FilePicker(on_result=on_media_picked)
    project_picker = ft.FilePicker(on_result=on_project_picked)
    page.services.append(media_picker_all)
    page.services.append(media_picker_img)
    page.services.append(media_picker_vid)
    page.services.append(project_picker)

    def _pick_action(picker, exts):
        return ft.PickFiles(picker, allow_multiple=True,
                            file_type=ft.FilePickerFileType.CUSTOM,
                            allowed_extensions=list(exts), with_data=True,
                            cancel_upload_on_window_blur=False)

    pick_all = _pick_action(media_picker_all, ALLOWED)
    pick_img = _pick_action(media_picker_img, ALLOWED_IMAGE)
    pick_vid = _pick_action(media_picker_vid, ALLOWED_VIDEO)
    pick_proj = ft.PickFiles(project_picker, allow_multiple=False,
                             file_type=ft.FilePickerFileType.CUSTOM,
                             allowed_extensions=["vidmaker", "json"], with_data=True,
                             cancel_upload_on_window_blur=False)

    # ---- refresh ----
    # ---- v2 actions: library, b-roll, timeline ops, scene/beat, LUT, render ----
    def bin_add_path(p):
        if not p or not os.path.exists(p):
            return "file missing"
        info = sanitize_info(probe_media(p, image_duration=IMAGE_DEFAULT_DUR))
        if not info:
            return f"unreadable: {os.path.basename(p)}"
        if len(media_bin) >= BIN_CAP:
            return f"bin full ({BIN_CAP})"
        tl = cur()
        media_bin.append({"path": p, "name": os.path.basename(p)[:24],
                          "kind": info["kind"], "duration": info["duration"],
                          "fps": info["fps"], "width": info["width"],
                          "height": info["height"]})
        _index_media(p, info, "hit")
        tl.add_clip(media_to_clip(p, info, order=len(tl.clips)))
        return f"added {os.path.basename(p)[:24]} -> {tl.name}"

    def index_folder_action():
        folder = (folder_field.value or "").strip().strip("'\"")
        if not folder or not os.path.isdir(folder):
            return "type a valid folder path first"
        try:
            found = broll.index_folder(folder)
        except Exception as ex:
            return f"index failed: {ex}"
        n_new = 0
        for it in found:
            p = it.get("path", "")
            if not p:
                continue
            try:
                media_idx.add(p, kind=it.get("kind", "video"),
                              duration=float(it.get("duration", 0) or 0),
                              width=int(it.get("width", 0) or 0),
                              height=int(it.get("height", 0) or 0),
                              tags=("folder",))
                n_new += 1
            except Exception:
                pass
        return f"indexed {n_new} file(s) from {os.path.basename(folder) or folder}"

    def timeline_action(which):
        tl = cur()
        if not tl.clips:
            return "timeline empty"
        try:
            if which == "close_gaps":
                n = timeline_ops.close_gaps(tl)
                return f"closed {n} gap(s)" if n else "no gaps found"
            if which == "merge":
                n = timeline_ops.merge_adjacent(tl)
                return f"merged {n} clip(s)" if n else "nothing adjacent"
            if which == "ripple":
                if timeline_ops.ripple_delete(tl, state["sel"]):
                    state["sel"] = max(0, min(state["sel"], len(tl.clips) - 1))
                    return "clip deleted (ripple)"
                return "nothing to delete"
            if which == "stats":
                s = timeline_ops.stats(tl)
                return (f"{s['clips']} clips · {s['videos']}v/{s['images']}i "
                        f"· {s['duration']:.1f}s")
        except Exception as ex:
            return f"{which} failed: {ex}"
        return "unknown action"

    def scene_split_action():
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return "select a clip first"
        c = tl.clips[state["sel"]]
        if getattr(c, "kind", "video") != "video":
            return "scene split needs a video clip"
        try:
            points = scene_detect.auto_split_points(c.path)
        except Exception as ex:
            return f"scene detect failed: {ex}"
        if not points:
            return "no scene changes found"
        acc = sum(x.trim_dur for x in tl.clips[:state["sel"]])
        keep_t = state["t"]
        made = 0
        for pt in sorted(float(p) for p in points):
            state["t"] = acc + pt + 0.01
            tl.playhead = state["t"]
            if tl.split_at_playhead():
                made += 1
        state["t"] = keep_t
        return f"scene split: {made} cut(s)" if made else "split failed"

    def beat_snap_action():
        wav = None
        try:
            for nm in sorted(os.listdir(tmp_upload)):
                if nm.lower().endswith(".wav"):
                    wav = os.path.join(tmp_upload, nm)
                    break
        except Exception:
            pass
        if not wav:
            return "no .wav in uploads to analyse"
        try:
            beats = beat_detect.beat_markers(wav)
        except Exception as ex:
            return f"beat detect failed: {ex}"
        if not beats:
            return "no beats found"
        state["t"] = beat_detect.snap_to_beats(state["t"], beats)
        return f"playhead snapped to beat ({len(beats)} beats)"

    def set_lut(name):
        grade.lut = name
        refresh(f"LUT: {name}")

    def _kick_render_worker():
        if render_thread.get("worker") and render_thread["worker"].is_alive():
            return

        def _worker():
            while True:
                job = render_q.run_next(cur(), grade)
                if job is None:
                    break
                if job.state == "done":
                    refresh(f"export done: {job.frames}f -> {job.out_path}")
                else:
                    refresh(f"export failed: {job.error}")

        w = threading.Thread(target=_worker, daemon=True)
        render_thread["worker"] = w
        w.start()

    def refresh(msg_text=""):
        if msg_text:
            msg.value = msg_text
        try:
            preset_chip.content.value = (state.get("preset") or "preview_720p").replace("_", " ")
            play_chip.content.value = "PLAYING" if state.get("playing") else "PAUSED"
            play_chip.content.color = MINT if state.get("playing") else MUTED
            _render_queue_panel()
        except Exception:
            pass
        # timeline tabs
        tabs = []
        for i, t in enumerate(ts.timelines):
            tabs.append(EButton(f"{'▶ ' if i == ts.active else ''}{t.name} ({len(t.clips)})",
                                bgcolor=VIOLET if i == ts.active else ui["panel_edge"],
                                color="white",
                                on_click=lambda e, k=i: switch_timeline(k)))
        tabs.append(ft.IconButton(Icons.ADD, icon_color=MINT, tooltip="Add timeline",
                                 on_click=lambda e: add_timeline()))
        tabs.append(ft.IconButton(Icons.CONTENT_COPY, icon_color=INK, tooltip="Duplicate timeline",
                                 on_click=lambda e: duplicate_timeline()))
        tabs.append(ft.IconButton(Icons.DELETE, icon_color=ORANGE, tooltip="Delete timeline",
                                 on_click=lambda e: delete_timeline()))
        tabs_row.controls = tabs

        # bin (filtered by bin_search; falls back to indexed-library hits)
        rows = []
        q = (bin_search.value or "").strip().lower()
        for bi, m in enumerate(media_bin):
            if q and q not in m.get("name", "").lower():
                continue
            tag = "IMG" if m.get("kind") == "image" else "VID"
            rows.append(ft.Container(
                content=ft.Row([
                    ft.Text(f"{tag}", size=10, color=VIOLET, weight="bold"),
                    ft.Column([
                        ft.Text(m.get("name", "")[:16], size=11, color=INK),
                        ft.Text(f"{float(m.get('duration', 0)):.1f}s · "
                                f"{int(m.get('width', 0) or 0)}x{int(m.get('height', 0) or 0)}",
                                size=9, color=MUTED),
                    ], spacing=0, tight=True, expand=True),
                    ft.IconButton(Icons.ADD, icon_size=16, icon_color=MINT,
                                  tooltip="Add to timeline",
                                  on_click=lambda e, k=bi: bin_to_timeline(k)),
                    ft.IconButton(Icons.CLOSE, icon_size=14, icon_color=ORANGE,
                                  tooltip="Remove",
                                  on_click=lambda e, k=bi: bin_remove(k)),
                ], spacing=4, tight=True),
                bgcolor=ui["panel_edge"], border_radius=8, padding=6))
        if q and not rows:
            for hit in media_idx.search(q, limit=6):
                hp = hit.get("path", "")
                if not hp or not os.path.exists(hp):
                    continue
                rows.append(ft.Container(
                    content=ft.Row([
                        ft.Text("HIT", size=10, color=MINT, weight="bold"),
                        ft.Text(hit.get("name", "")[:16], size=11, color=INK, expand=True),
                        ft.IconButton(Icons.ADD, icon_size=16, icon_color=MINT,
                                      tooltip="Add to timeline",
                                      on_click=lambda e, k=hp: refresh(bin_add_path(k))),
                    ], spacing=4, tight=True),
                    bgcolor=ui["hit_bg"], border_radius=8, padding=6))
        bin_col.controls = rows or [ft.Text("Bin empty — IMPORT MEDIA above", size=11, color=MUTED)]

        tl = cur()
        if not tl.clips:
            tc.value = f"{tl.name} · 00:00:00 · no clips"
            empty_hint.visible = True
            preview.src = PLACEHOLDER_PNG
            clip_row.controls = [ft.Text("Timeline empty — IMPORT auto-adds, or + from bin",
                                         size=11, color=MUTED)]
            page.update()
            return
        empty_hint.visible = False
        total = tl.total_duration()
        state["t"] = max(0.0, min(max(0.05, total - 0.05), state["t"]))
        state["sel"] = max(0, min(state["sel"], len(tl.clips) - 1))
        clip, local = tl.locate(state["t"])
        if clip is None:
            clip = tl.clips[state["sel"]]
            local = 0.0
        raw, rlocal = _resolve_preview(clip, local)
        if raw is None:
            msg.value = f"could not read {clip.name}"
            page.update()
            return
        graded = grade_frame(raw, grade, rlocal, clip.trim_dur)
        png = frame_to_png_bytes(graded)
        if png:
            preview.src = png
        sm = scope_mode["m"]
        strip = rgb_parade(graded) if sm == "parade" else frame_histogram_strip(graded)
        if strip:
            hist_img.src = strip
        aw = render_audio_strip(grade.muted, getattr(grade, "speed", 1.0), width=240)
        if aw:
            wave_img.src = aw
        tc.value = f"{tl.name} · {_fmt_t(state['t'], clip.fps)} / {_fmt_t(total, clip.fps)} · {clip.name}"
        zoom = state.get("zoom", 1.0)
        cards = []
        for i, c in enumerate(tl.clips):
            w = max(110, min(340, int(c.trim_dur * 22 * zoom)))
            active = (i == state["sel"])
            kind = getattr(c, "kind", "video")
            tag = "IMG" if kind == "image" else "VID"
            try:
                thumbs = [] if kind == "image" else cached_filmstrip(c.path, count=4, thumb_w=72)
            except Exception:
                thumbs = []
            trans = getattr(c, "transition", "cut") or "cut"
            tag2 = "" if trans == "cut" else f" [{trans}]"
            badges = ""
            spd = float(getattr(c, "speed", 1.0) or 1.0)
            if abs(spd - 1.0) > 1e-6:
                badges += f" · {spd:g}x"
            if float(getattr(c, "fade_in", 0) or 0) > 0:
                badges += " · fade-in"
            if float(getattr(c, "fade_out", 0) or 0) > 0:
                badges += " · fade-out"
            if getattr(c, "kenburns", None):
                badges += " · motion"
            cards.append(ft.Container(
                content=ft.Column([
                    ft.Text(f"{i+1} · {tag} · {c.name[:12]}", size=10, color="white", weight="bold"),
                    ft.Text(f"{c.trim_dur:.1f}s{tag2}{badges}", size=10, color=ui["soft_ink"]),
                    *([ft.Row([ft.Image(src=b, width=64, height=36, fit=Fit.CONTAIN)
                               for b in thumbs[:4]], spacing=2, tight=True)] if thumbs else []),
                    *([ft.Text(c.caption[:22], size=9, color=MINT)]
                      if getattr(c, "caption", "") else []),
                    *([ft.Text("⤒ fade in", size=9, color=ORANGE)]
                      if float(getattr(c, "fade_in", 0) or 0) > 0 else []),
                    *([ft.Text("⤓ fade out", size=9, color=ORANGE)]
                      if float(getattr(c, "fade_out", 0) or 0) > 0 else []),
                    ft.Row([
                        ft.IconButton(Icons.CHEVRON_LEFT, icon_size=14, icon_color=ui["soft_ink"],
                                      tooltip="Move left",
                                      on_click=lambda e, k=i: move_clip(k, -1)),
                        ft.IconButton(Icons.CHEVRON_RIGHT, icon_size=14, icon_color=ui["soft_ink"],
                                      tooltip="Move right",
                                      on_click=lambda e, k=i: move_clip(k, 1)),
                        ft.IconButton(Icons.CLOSE, icon_size=14, icon_color=ORANGE,
                                      tooltip="Remove clip",
                                      on_click=lambda e, k=i: delete_clip(k)),
                    ], spacing=0, tight=True),
                ], spacing=2, tight=True),
                width=w, bgcolor=VIOLET if active else ui["panel_edge"],
                border_radius=10, padding=8,
                on_click=lambda e, k=i: select_clip(k)))
        clip_row.controls = cards
        # markers row (click a flag to jump, ✕ removes it)
        mrow = []
        for m in tl.markers:
            mc = Marker.COLORS.get(m.color, ORANGE)
            mrow.append(ft.Container(
                content=ft.Row([
                    ft.IconButton(Icons.PLACE, icon_size=14, icon_color=mc,
                                  tooltip=f"jump to {m.t:.2f}s" + (f" · {m.note}" if m.note else ""),
                                  on_click=lambda e, mk=m: go_to_time(mk.t)),
                    *([ft.Text(m.note[:14], size=9, color=INK)] if m.note else []),
                    ft.IconButton(Icons.CLOSE, icon_size=12, icon_color=MUTED,
                                  tooltip="remove marker",
                                  on_click=lambda e, mk=m: (tl.remove_marker(mk.t), refresh("marker removed"))),
                ], spacing=0, tight=True),
                bgcolor=ui["panel_edge"], border_radius=99, padding=ft.padding.only(left=2, right=4)))
        markers_row.controls = mrow or [ft.Text("no markers — press M to drop one",
                                                size=10, color=MUTED)]
        try:
            scrub.value = (state["t"] / total * 100.0) if total > 0 else 0
        except Exception:
            pass
        page.update()

    # ---- ops ----
    def select_clip(i):
        state["sel"] = i
        acc = sum(c.trim_dur for c in cur().clips[:i])
        state["t"] = acc + 0.01
        refresh()

    def delete_clip(i):
        cur().remove_at(i)
        state["sel"] = max(0, min(state["sel"], len(cur().clips) - 1))
        state["t"] = 0.0
        refresh(f"clip {i+1} removed")

    def move_clip(i, delta):
        cur().move(i, delta)
        state["sel"] = max(0, min(len(cur().clips) - 1, i + delta))
        refresh("moved")

    def switch_timeline(i):
        ts.switch(i)
        state["t"] = 0.0
        state["sel"] = 0
        refresh(f"switched to {ts.current().name}")

    def add_timeline():
        ts.add_timeline()
        state["t"] = 0.0
        state["sel"] = 0
        refresh(f"added {ts.current().name}")

    def duplicate_timeline():
        src = cur()
        dst = ts.add_timeline(name=src.name + " copy")
        dst.clips = copy.deepcopy(src.clips)
        for i, c in enumerate(dst.clips):
            c.order = i
        state["t"] = 0.0
        state["sel"] = 0
        refresh(f"duplicated -> {dst.name}")

    def delete_timeline():
        refresh("timeline deleted" if ts.remove_at(ts.active) else "cannot delete last timeline")
        state["t"] = 0.0
        state["sel"] = 0
        refresh()

    def bin_to_timeline(bi):
        if not (0 <= bi < len(media_bin)):
            return
        m = media_bin[bi]
        cur().add_clip(Clip(path=m["path"], name=m["name"][:18], kind=m.get("kind", "video"),
                            track="V1", duration=m["duration"], fps=m["fps"],
                            width=m["width"], height=m["height"],
                            in_point=0.0, out_point=m["duration"]))
        state["sel"] = len(cur().clips) - 1
        refresh(f"added to {cur().name}")

    def bin_remove(bi):
        if 0 <= bi < len(media_bin):
            media_bin.pop(bi)
            refresh("removed from bin")

    def bin_clear():
        media_bin.clear()
        refresh("bin cleared")

    def trim(is_in):
        clip, local = cur().locate(state["t"])
        if not clip:
            return
        if is_in:
            clip.in_point = min(clip.in_point + local, (clip.out_point or clip.duration) - 0.2)
        else:
            clip.out_point = max(clip.in_point + 0.2, clip.in_point + local)
        refresh("trimmed")

    def do_split():
        cur().playhead = state["t"]
        refresh("split ok" if cur().split_at_playhead() else "cannot split here")

    def do_save():
        try:
            out = default_save_path("vidmaker2000_multi")
            save_project(out, ts, grade, media_bin=media_bin)
        except Exception as ex:
            refresh(f"save failed: {ex}")
            return
        note = ""
        try:
            autosave.snapshot(autosave_dir,
                              {"project": ts.to_dict(), "media_bin": media_bin},
                              tag="manual")
            kept = autosave.rotate(autosave_dir, tag="manual")
            note = f" · {kept} snapshot(s)"
        except Exception:
            pass
        refresh(f"saved -> {out}{note}")

    def do_export():
        if not cur().clips:
            refresh("nothing to export")
            return
        out = os.path.join(tempfile.gettempdir(), f"vidmaker2000_{safe_name(cur().name)}_cut.mp4")
        job = render_q.add(cur().name, state.get("preset") or "preview_720p", out)
        refresh(f"queued export {job.job_id} ({state.get('preset')})")
        _kick_render_worker()

    def do_export_gif():
        if not cur().clips:
            return "nothing to export"
        from export import export_gif
        out = os.path.join(tempfile.gettempdir(), f"vidmaker2000_{safe_name(cur().name)}.gif")
        r = export_gif(cur(), grade, out, fps=10.0, max_seconds=8.0)
        return f"GIF -> {out}" if r.get("ok") else f"GIF failed: {r.get('error')}"

    def make_title_card():
        """Generate an opener image from the title field and add it to the bin."""
        title = (title_field.value or "").strip()
        if not title:
            return "type a title first"
        from captions import draw_title
        img = _blank_card()
        img = draw_title(img, title, subtitle_field.value or "")
        p = os.path.join(tmp_upload, f"title_{state['import_seq'] + 1}.png")
        state["import_seq"] += 1
        cv2.imwrite(p, img)
        info = sanitize_info(probe_media(p, image_duration=IMAGE_DEFAULT_DUR))
        if not info:
            return "title card failed"
        tl = cur()
        media_bin.append({"path": p, "name": os.path.basename(p)[:24],
                          "kind": "image", "duration": info["duration"],
                          "fps": info["fps"], "width": info["width"],
                          "height": info["height"]})
        _index_media(p, info, "title")
        tl.add_clip(media_to_clip(p, info, order=len(tl.clips)))
        return f"title card -> {tl.name}"

    def _blank_card(w=1280, h=720):
        import numpy as np
        img = np.zeros((h, w, 3), np.uint8)
        img[:] = (23, 14, 15)  # vidmaker neon BG
        return img

    def toggle():
        state["playing"] = not state["playing"]
        refresh("playing" if state["playing"] else "paused")

    def step(d):
        state["t"] += d * 0.5
        c, _ = cur().locate(state["t"])
        if c is not None:
            state["sel"] = c.order
        refresh()

    def scrub_to(v):
        total = cur().total_duration() or 1.0
        state["t"] = float(v) / 100.0 * total
        c, _ = cur().locate(state["t"])
        if c is not None:
            state["sel"] = c.order
        refresh()

    # ---- v2.3 features: markers, frame-step, goto, snapshot, fades ----
    def _fmt_t(sec, fps=30.0):
        """Timecode or raw seconds depending on the display mode."""
        if state.get("tc_mode", "tc") == "sec":
            return f"{max(0.0, float(sec)):.2f}s"
        return sec_to_tc(sec, fps)

    def go_to_time(t=None):
        """Jump the playhead to ``t`` (or parse the goto field)."""
        if t is None:
            raw = (goto_field.value or "").strip()
            t = tc_to_sec(raw) if ":" in raw else _parse_loose_time(raw)
            if t <= 0 and raw:
                return f"could not parse time: {raw}"
        total = cur().total_duration()
        state["t"] = max(0.0, min(t, total)) if total > 0 else 0.0
        c, _ = cur().locate(state["t"])
        if c is not None:
            state["sel"] = c.order
        refresh("playhead -> " + _fmt_t(state["t"]))
        return state["t"]

    def _parse_loose_time(raw):
        """'90', '1m30', '2:05' -> seconds (best effort)."""
        try:
            raw = (raw or "").strip().lower().replace("s", "")
            if "m" in raw:
                m, s = raw.split("m", 1)
                return float(m or 0) * 60.0 + float(s or 0)
            return float(raw or 0)
        except ValueError:
            return 0.0

    def drop_marker(color="orange"):
        tl = cur()
        m = tl.add_marker(state["t"], color=color)
        refresh(f"marker at {_fmt_t(m.t)}")

    def jump_marker(dir=1):
        tl = cur()
        m = tl.marker_after(state["t"]) if dir > 0 else tl.marker_before(state["t"])
        if m is None:
            return "no marker in that direction"
        state["t"] = m.t
        c, _ = tl.locate(state["t"])
        if c is not None:
            state["sel"] = c.order
        refresh("marker: " + (m.note or _fmt_t(m.t)))

    def frame_step(dir=1):
        tl = cur()
        clip, local = tl.locate(state["t"])
        fps = float(getattr(clip, "fps", 30.0) or 30.0) if clip else 30.0
        state["t"] = max(0.0, state["t"] + dir / fps)
        c, _ = tl.locate(state["t"])
        if c is not None:
            state["sel"] = c.order
        refresh()

    def snapshot_png():
        tl = cur()
        clip, local = tl.locate(state["t"])
        if clip is None:
            return "nothing under the playhead"
        raw, rlocal = _resolve_preview(clip, local)
        if raw is None:
            return "frame unreadable"
        graded = _finish_preview(clip, raw, rlocal)
        if graded is None:
            return "frame unreadable"
        out = os.path.join(tempfile.gettempdir(),
                           f"vidmaker2000_frame_{safe_name(tl.name)}_{int(state['t']*1000)}.png")
        ok, buf = cv2.imencode(".png", graded)
        if not ok:
            return "encode failed"
        with open(out, "wb") as fh:
            fh.write(buf.tobytes())
        return f"frame saved -> {out}"

    def set_fade(which, val):
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return "select a clip first"
        c = tl.clips[state["sel"]]
        setattr(c, which, max(0.0, min(3.0, float(val))))
        refresh(f"{which} = {getattr(c, which):.2f}s")

    _FADE_STEPS = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0)

    def _cycle_fade(which):
        """Rotate the selected clip's fade through preset lengths."""
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return None
        c = tl.clips[state["sel"]]
        vals = _FADE_STEPS
        i = min(range(len(vals)), key=lambda k: abs(vals[k] - float(getattr(c, which, 0.0) or 0.0)))
        nv = vals[(i + 1) % len(vals)]
        setattr(c, which, nv)
        return nv

    def _cycle_fade_msg(which):
        v = _cycle_fade(which)
        return "select a clip first" if v is None else f"{which} = {v:.2f}s"

    _SPEED_STEPS = (0.5, 1.0, 2.0, 4.0)
    _KB_PRESETS = {
        "zoom in": {"zs": 1.0, "ze": 1.25, "px": 0.0, "py": 0.0},
        "zoom out": {"zs": 1.25, "ze": 1.0, "px": 0.0, "py": 0.0},
        "pan right": {"zs": 1.15, "ze": 1.15, "px": -0.12, "py": 0.0},
        "pan left": {"zs": 1.15, "ze": 1.15, "px": 0.12, "py": 0.0},
        "off": None,
    }

    def nest_timeline_action():
        clip = ts.nest_current()
        if clip is None:
            return "nothing to nest"
        ts.switch(max(0, ts.active - 1)) if ts.active > 0 else None
        return f"nested -> {clip.name} ({clip.duration:.1f}s)"

    def cycle_clip_speed():
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return "select a clip first"
        c = tl.clips[state["sel"]]
        cur_v = float(getattr(c, "speed", 1.0) or 1.0)
        i = min(range(len(_SPEED_STEPS)), key=lambda k: abs(_SPEED_STEPS[k] - cur_v))
        c.speed = _SPEED_STEPS[(i + 1) % len(_SPEED_STEPS)]
        return f"clip speed {c.speed:g}x"

    def copy_grade():
        state["grade_clipboard"] = grade.to_dict()
        return "grade copied"

    def paste_grade():
        snap = state.get("grade_clipboard")
        if not snap:
            return "copy a grade first"
        grade.__dict__.update(Grade.from_dict(snap).__dict__)
        sync_grade_ui()
        return "grade pasted"

    def set_kenburns(name):
        tl = cur()
        if not tl.clips or not (0 <= state["sel"] < len(tl.clips)):
            return "select a clip first"
        c = tl.clips[state["sel"]]
        if getattr(c, "kind", "video") != "image":
            return "Ken Burns needs an image clip"
        c.kenburns = _KB_PRESETS.get(name)
        return f"motion: {name}" if c.kenburns else "motion off"

    def dup_to_new_timeline():
        src = cur()
        if not src.clips:
            return "nothing to copy"
        dst = ts.add_timeline(f"{src.name[:20]} copy")
        dst.clips = copy.deepcopy(src.clips)
        dst.markers = copy.deepcopy(src.markers)
        for i, c in enumerate(dst.clips):
            c.order = i
        ts.active = len(ts.timelines) - 1
        refresh(f"copied to {dst.name}")

    def cycle_speed(dir=1):
        steps = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        cur_idx = min(range(len(steps)), key=lambda i: abs(steps[i] - float(getattr(grade, "speed", 1.0) or 1.0)))
        grade.speed = steps[max(0, min(len(steps) - 1, cur_idx + dir))]
        refresh(f"speed {grade.speed:g}x")

    # ---- undo / redo / duplicate / zoom ----
    def undo():
        ts.undo()
        refresh("undo")

    def redo():
        ts.redo()
        refresh("redo")

    def dup_clip():
        if cur().clips:
            cur().duplicate_at(state["sel"])
            state["sel"] = min(state["sel"] + 1, len(cur().clips) - 1)
            refresh("duplicated")

    def set_zoom(delta):
        state["zoom"] = max(0.4, min(4.0, state.get("zoom", 1.0) + delta))
        refresh()

    # ---- frame resolution: nested clips + Ken Burns aware previews ----
    def _resolve_preview(clip, local, depth=0):
        """Return (bgr_frame_or_None, local_t_on_real_clip) for any clip kind."""
        if depth > 3:
            return None, local
        kind = getattr(clip, "kind", "video")
        if kind == "nested":
            sub = clip.nested_timeline()
            if sub is None:
                return None, local
            t = float(getattr(clip, "in_point", 0.0) or 0.0) + local
            sc, s_local = sub.locate(t)
            if sc is None:
                return None, local
            return _resolve_preview(sc, s_local, depth + 1)
        spd = max(0.25, min(4.0, float(getattr(clip, "speed", 1.0) or 1.0)))
        src_t = float(getattr(clip, "in_point", 0.0) or 0.0) + local * spd
        raw, _ = grab_media_frame(clip.path, kind, src_t)
        return raw, local

    def _finish_preview(clip, raw, local):
        """Grade + caption + fade + Ken Burns for a resolved preview frame."""
        if raw is None:
            return None
        graded = grade_frame(raw, grade, local, clip.trim_dur)
        cap = getattr(clip, "caption", "")
        if cap:
            graded = draw_caption(graded, cap, style=getattr(clip, "text_style", None)
                                  or {"pos": state.get("cap_pos", "bottom")})
        fi = float(getattr(clip, "fade_in", 0) or 0)
        fo = float(getattr(clip, "fade_out", 0) or 0)
        if fi > 0 or fo > 0:
            graded = apply_fade(graded, fi, fo, local, clip.trim_dur)
        if getattr(clip, "kind", "video") == "image" and getattr(clip, "kenburns", None):
            from export import _ken_burns
            t01 = min(1.0, max(0.0, local / max(0.01, clip.trim_dur)))
            graded = _ken_burns(graded, clip.kenburns, t01)
        return graded

    # ---- 30fps playback engine (the loop below paces itself at 1/30s) ----

    def _paint_frame():
        tl = cur()
        if not tl.clips:
            return
        total = tl.total_duration()
        clip, local = tl.locate(state["t"])
        if clip is None:
            return
        raw, rlocal = _resolve_preview(clip, local)
        if raw is None:
            return
        graded = _finish_preview(clip, raw, rlocal)
        if graded is None:
            return
        png = frame_to_png_bytes(graded)
        if png:
            preview.src = png
        tc.value = f"{tl.name} · {_fmt_t(state['t'], clip.fps)} / {_fmt_t(total, clip.fps)} · {clip.name}"
        try:
            scrub.value = (state["t"] / total * 100.0) if total > 0 else 0
        except Exception:
            pass
        page.update()

    def _playback_loop():
        import time as _time
        last = _time.time()
        while state.get("alive", True):
            _time.sleep(1.0 / 30.0)
            try:
                now = _time.time()
                dt = now - last
                last = now
                if not state.get("playing"):
                    continue
                tl = cur()
                total = tl.total_duration()
                if total <= 0:
                    continue
                spd = float(getattr(grade, "speed", 1.0) or 1.0)
                state["t"] += dt * spd
                if state["t"] >= total:
                    state["t"] = 0.0
                c, _ = tl.locate(state["t"])
                if c is not None:
                    state["sel"] = c.order
                _paint_frame()
            except Exception:
                continue

    state["alive"] = True
    threading.Thread(target=_playback_loop, daemon=True).start()

    # ---- background autosave: crash protection every 60s when dirty ----
    def _autosave_loop():
        import time as _time
        dirty_flag = {"last": ""}
        while state.get("alive", True):
            _time.sleep(60.0)
            try:
                tl = cur()
                sig = (len(tl.clips), round(state["t"], 1),
                       len(media_bin), ts.active)
                if sig == dirty_flag["last"]:
                    continue  # nothing changed since the last snapshot
                dirty_flag["last"] = sig
                autosave.snapshot(autosave_dir,
                                  {"project": ts.to_dict(), "media_bin": media_bin},
                                  tag="autosave")
                autosave.rotate(autosave_dir, keep=5, tag="autosave")
            except Exception:
                continue

    threading.Thread(target=_autosave_loop, daemon=True).start()

    # ---- keyboard shortcuts (page-level, web mode) ----
    def on_key(e):
        k = (getattr(e, "key", "") or "").lower()
        if getattr(e, "ctrl", False) and not k.startswith("ctrl"):
            k = f"ctrl+{k}"
        act = keymap.action_for(k)
        # don't hijack typing inside text fields (captions, paths, search)
        try:
            focused = getattr(page, "focused_control", None)
        except Exception:
            focused = None
        typing_somewhere = isinstance(focused, ft.TextField)
        try:
            if k in ("space", " "):
                if not typing_somewhere:
                    toggle()
            elif act == "pause":
                if state.get("playing"):
                    toggle()
            elif act == "save":
                do_save()
            elif act == "trim_in":
                trim(True)
            elif act == "trim_out":
                trim(False)
            elif act == "split":
                do_split()
            elif act == "duplicate":
                dup_clip()
            elif act == "export":
                do_export()
            elif act == "mute":
                grade.muted = not grade.muted
                refresh("muted" if grade.muted else "unmuted")
            elif act == "reset_grade":
                grade.reset()
                sync_grade_ui()
                refresh("grade reset")
            elif act == "step_back":
                step(-1)
            elif act == "step_fwd":
                step(1)
            elif act == "jump_back":
                step(-4)
            elif act == "jump_fwd":
                step(4)
            elif act == "delete" or k in ("delete", "backspace"):
                if not typing_somewhere:
                    delete_clip(state["sel"])
            elif act == "undo":
                undo()
            elif act == "redo":
                redo()
            elif act == "zoom_in":
                set_zoom(0.2)
            elif act == "zoom_out":
                set_zoom(-0.2)
            elif act == "marker":
                if not typing_somewhere:
                    drop_marker()
            elif act == "marker_prev":
                jump_marker(-1)
            elif act == "marker_next":
                jump_marker(1)
            elif act == "frame_back":
                frame_step(-1)
            elif act == "frame_fwd":
                frame_step(1)
            elif act == "goto":
                try:
                    goto_field.focus()
                except Exception:
                    pass
            elif act == "snapshot":
                refresh(snapshot_png())
            elif act == "fade_in":
                c = _cycle_fade("fade_in")
                if c is not None:
                    refresh(f"fade_in = {c:.2f}s")
            elif act == "fade_out":
                c = _cycle_fade("fade_out")
                if c is not None:
                    refresh(f"fade_out = {c:.2f}s")
            elif k == "shift+j":
                cycle_speed(-1)
            elif k == "shift+l":
                cycle_speed(1)
            elif k == "ctrl+c":
                refresh(copy_grade())
            elif k == "ctrl+v":
                refresh(paste_grade())
        except Exception:
            pass

    try:
        page.on_keyboard_event = on_key
    except Exception:
        pass

    # ---- grade sliders (keep refs to sync on project load) ----
    grade_sliders = {}

    def bind(attr, scale=1.0):
        def h(e):
            setattr(grade, attr, float(e.control.value) * scale)
            refresh()
        return h

    def grade_slider(key, label, lo, hi, val, s=1.0):
        sl = ft.Slider(min=lo, max=hi, value=val,
                       divisions=int((hi - lo) * 100.0) or None,
                       active_color=ORANGE, inactive_color="#2a2740",
                       thumb_color=ORANGE, height=28,
                       on_change=bind(key, s))
        grade_sliders[key] = (sl, val)
        return ft.Column([ft.Text(label, size=11, color=MUTED), sl],
                         spacing=0, tight=True)

    def sync_grade_ui():
        for k, (sl, default) in grade_sliders.items():
            try:
                sl.value = float(getattr(grade, k, default))
            except Exception:
                pass

    # ---- layout ----
    scrub = ft.Slider(min=0, max=100, value=0, active_color=VIOLET,
                      inactive_color="#2a2740", height=28,
                      on_change=lambda e: scrub_to(e.control.value))

    path_field = ft.TextField(label="Local file path (best for big videos)",
                                hint_text="C:\\Videos\\clip.mp4",
                                dense=True, expand=True)

    caption_field = ft.TextField(label="Caption text (burns into preview + export)",
                                 hint_text="type, press Enter",
                                 dense=True,
                                 on_submit=lambda e: set_caption_text(e.control.value or ""))

    goto_field = ft.TextField(label="Go to (MM:SS / 90 / 1m30)", dense=True,
                              expand=True,
                              on_submit=lambda e: go_to_time())

    title_field = ft.TextField(label="Title (opener card)", dense=True,
                               hint_text="VIDMAKER2000")
    subtitle_field = ft.TextField(label="Subtitle", dense=True,
                                  hint_text="neon cuts, zero friction")

    def _chip(label, color):
        return ft.Container(content=ft.Text(label, size=10, weight="bold", color=color),
                            bgcolor=ui["panel_edge"], border_radius=99,
                            padding=ft.padding.symmetric(4, 10))

    preset_chip = _chip("720p", VIOLET)
    play_chip = _chip("PAUSED", MUTED)
    ver_chip = _chip("v2.1", MINT)
    _logo_b64 = ""
    try:
        with open(os.path.join(_BRAND_DIR, "favicon-256.png"), "rb") as _fh:
            _logo_b64 = _b64.b64encode(_fh.read()).decode()
    except Exception:
        _logo_b64 = ""
    logo = ft.Image(src_base64=_logo_b64, width=30, height=30,
                    border_radius=8) if _logo_b64 else None

    header = ft.Container(
        content=ft.Row([
            *([logo] if logo else []),
            ft.Row([
                ft.Text("VID", color=ORANGE, weight="bold", size=18),
                ft.Text("MAKER", color=VIOLET, weight="bold", size=18),
                ft.Text("2000", color=INK, weight="bold", size=18),
            ], spacing=0, tight=True),
            ver_chip, preset_chip, play_chip,
            msg,
        ], spacing=12, wrap=True),
        gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                                   colors=["#191827", "#221d38"]),
        border_radius=12, padding=12)

    # ---- theme picker (persisted via themes.py, live recolor) ----
    theme_row = ft.Row(spacing=4, wrap=True)

    # ---- export presets: categorized column + custom builder ----
    presets_col = ft.Column(spacing=2)
    cw_field = ft.TextField(label="W", dense=True, width=64)
    ch_field = ft.TextField(label="H", dense=True, width=64)
    cfps_field = ft.TextField(label="fps", dense=True, width=56)
    cq_field = ft.TextField(label="q", dense=True, width=48)
    custom_fit = {"m": "cover"}

    def _custom_fit(mode):
        custom_fit["m"] = mode
        refresh("custom fit: " + mode)

    def _make_custom_preset():
        try:
            w = int(float(cw_field.value or 0)); h = int(float(ch_field.value or 0))
            fps = float(cfps_field.value or 30); q = int(float(cq_field.value or 80))
        except ValueError:
            return "preset fields must be numbers"
        if w < 16 or h < 16:
            return "enter width and height (min 16)"
        key = add_custom_preset(f"custom_{w}x{h}", w, h, fps=fps,
                                quality=q, fit=custom_fit["m"])
        state["preset"] = key
        _rebuild_presets_col()
        return f"custom preset {key} active"

    def _rebuild_presets_col():
        rows = []
        for cat, names in preset_categories().items():
            rows.append(ft.Text(f"{cat}  ({len(names)})", size=10,
                                color=VIOLET, weight="bold"))
            rows.append(ft.Row(
                [ft.TextButton(n, tooltip=preset_info(n),
                               on_click=lambda e, k=n: set_preset(k))
                 for n in names], spacing=2, wrap=True))
        presets_col.controls = rows

    _rebuild_presets_col()

    def _apply_theme_colors(pal):
        # keep the live palette in sync so everything built after this
        # (bin rows, cards, chips) picks up the theme automatically
        light = themes_mod.active_name() in themes_mod.LIGHT_THEMES
        ui.update(bg=pal["bg"], panel=pal["panel"], ink=pal["ink"],
                  muted=pal["muted"], accent=pal["accent"],
                  secondary=pal["secondary"], good=pal["good"], warn=pal["warn"],
                  panel_edge="#2a2740" if not light else "#d8d8e2",
                  soft_ink="#cfc9e8" if not light else "#4a4a5e",
                  hit_bg="#12251c" if not light else "#d9efe2")
        """Recolor the shared chrome that uses module-level constants."""
        try:
            page.bgcolor = pal["bg"]
        except Exception:
            pass
        for c in (header, left, right):
            try:
                c.bgcolor = pal["panel"]
            except Exception:
                pass
        try:
            header.content.controls[1].controls[0].color = pal["accent"]
            header.content.controls[1].controls[1].color = pal["secondary"]
            header.content.controls[1].controls[2].color = pal["ink"]
            ver_chip.content.color = pal["good"]
        except Exception:
            pass
        try:
            section.__defaults__ = (pal["accent"],)
        except Exception:
            pass

    def on_theme(name):
        pal = set_theme(name)
        state["light"] = name in themes_mod.LIGHT_THEMES
        _apply_theme_colors(pal)
        try:
            themes_mod.save(themes_mod.default_path())
        except Exception:
            pass
        refresh(f"theme: {name}")

    for name in list_themes():
        theme_row.controls.append(ft.TextButton(
            name, tooltip=f"switch to the {name} theme",
            on_click=lambda e, k=name: on_theme(k)))

    left = ft.Container(
        content=ft.Column([
            section("THEME"),
            theme_row,
            ft.Divider(height=1, color=ui["panel_edge"]),
            section("MEDIA BIN"),
            EButton("IMPORT MEDIA", bgcolor=ORANGE, color="black",
                    expand=True, action=pick_all),
            ft.Row([
                ft.TextButton("IMG", tooltip="Images only", action=pick_img),
                ft.TextButton("VID", tooltip="Videos only", action=pick_vid),
                ft.TextButton("CLEAR", on_click=lambda e: bin_clear()),
            ], spacing=4, tight=True),
            ft.Text(f"Browser upload best under {WEB_SOFT_MAX_MB}MB per file — "
                    "bigger videos: paste path below.",
                    size=10, color=MUTED),
            ft.Row([
                path_field,
                EButton("ADD", on_click=lambda e: refresh(
                    ingest_local_path(path_field.value))),
            ], spacing=6, tight=True),
            ft.Row([
                ft.TextButton("ADD SAMPLE", tooltip="Generate test image+video locally",
                              on_click=lambda e: refresh(add_sample())),
                ft.TextButton("SCAN UPLOADS", tooltip="Pick up files already uploaded",
                              on_click=lambda e: refresh(scan_uploads())),
                ft.TextButton("PURGE", tooltip="Drop missing files from bin + timelines",
                              on_click=lambda e: refresh(purge_ghost_bin())),
            ], spacing=4, tight=True),
            ft.Row([
                folder_field,
                EButton("INDEX", on_click=lambda e: refresh(index_folder_action())),
            ], spacing=6, tight=True),
            bin_search,
            ft.Container(content=bin_col, height=190, bgcolor="#0f0e17",
                         border_radius=8, padding=8),
            ft.Divider(height=1, color=ui["panel_edge"]),
            section("EDIT"),
            ft.Row([
                EButton("TRIM IN", expand=True, on_click=lambda e: trim(True)),
                EButton("TRIM OUT", expand=True, on_click=lambda e: trim(False)),
            ], tight=True),
            ft.Row([
                EButton("SPLIT", expand=True, on_click=lambda e: do_split()),
                EButton("DEL CLIP", expand=True,
                        on_click=lambda e: delete_clip(state["sel"])),
            ], tight=True),
            ft.Row([
                ft.TextButton("CLOSE GAPS", tooltip="Remove gaps between clips",
                              on_click=lambda e: refresh(timeline_action("close_gaps"))),
                ft.TextButton("MERGE", tooltip="Merge adjacent same-source clips",
                              on_click=lambda e: refresh(timeline_action("merge"))),
                ft.TextButton("RIPPLE DEL", tooltip="Delete selected clip and close the gap",
                              on_click=lambda e: refresh(timeline_action("ripple"))),
                ft.TextButton("STATS", tooltip="Timeline summary",
                              on_click=lambda e: refresh(timeline_action("stats"))),
            ], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton("SCENE SPLIT", tooltip="Split selected clip at detected scene changes",
                              on_click=lambda e: refresh(scene_split_action())),
                ft.TextButton("BEAT SNAP", tooltip="Snap playhead to music beats (.wav in uploads)",
                              on_click=lambda e: refresh(beat_snap_action())),
            ], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton("MARKER", tooltip="Drop marker at playhead (B)",
                              on_click=lambda e: drop_marker()),
                ft.TextButton("SNAPSHOT", tooltip="Save current frame as PNG (P)",
                              on_click=lambda e: refresh(snapshot_png())),
                ft.TextButton("DUP → NEW TL", tooltip="Copy this timeline to a new tab",
                              on_click=lambda e: dup_to_new_timeline()),
            ], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton("NEST → UP", tooltip="Collapse this timeline into a nested clip on the previous tab",
                              on_click=lambda e: refresh(nest_timeline_action())),
                ft.TextButton("SPEED", tooltip="Cycle per-clip speed (0.5x / 1x / 2x / 4x)",
                              on_click=lambda e: refresh(cycle_clip_speed())),
            ], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton(n, tooltip="Ken Burns motion for the selected image clip",
                              on_click=lambda e, k=n: refresh(set_kenburns(k)))
                for n in _KB_PRESETS], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton("COPY GRADE", tooltip="Copy the current grade (Ctrl+C)",
                              on_click=lambda e: refresh(copy_grade())),
                ft.TextButton("PASTE GRADE", tooltip="Apply the copied grade (Ctrl+V)",
                              on_click=lambda e: refresh(paste_grade())),
            ], spacing=2, wrap=True, tight=True),
            ft.Row([
                ft.TextButton("FADE IN ＋", tooltip="Cycle fade-in on selected clip ([)",
                              on_click=lambda e, w="fade_in": refresh(_cycle_fade_msg(w))),
                ft.TextButton("FADE OUT ＋", tooltip="Cycle fade-out on selected clip (])",
                              on_click=lambda e, w="fade_out": refresh(_cycle_fade_msg(w))),
            ], spacing=2, wrap=True, tight=True),
            ft.Divider(height=1, color=ui["panel_edge"]),
            section("PROJECT"),
            ft.Text("PRESET", size=11, color=MUTED),
            presets_col,
            ft.Row([
                cw_field, ch_field, cfps_field, cq_field,
            ], spacing=4, tight=True),
            ft.Row([
                ft.TextButton("contain", tooltip="letterbox fit (black bars)",
                              on_click=lambda e: _custom_fit("contain")),
                ft.TextButton("cover", tooltip="centre-crop fit",
                              on_click=lambda e: _custom_fit("cover")),
                ft.TextButton("stretch", tooltip="stretch to fill",
                              on_click=lambda e: _custom_fit("stretch")),
                EButton("CUSTOM", tooltip="Build a custom preset from the fields",
                        on_click=lambda e: refresh(_make_custom_preset())),
            ], spacing=2, tight=True),
            ft.Row([
                EButton("SAVE", expand=True, on_click=lambda e: do_save()),
                EButton("LOAD", expand=True, action=pick_proj),
            ], tight=True),
            EButton("EXPORT MP4", bgcolor=MINT, color="black",
                    expand=True, on_click=lambda e: do_export()),
            ft.Text("RENDER QUEUE", size=10, color=MUTED),
            ft.Container(content=queue_col, bgcolor=ui["panel_edge"],
                         border_radius=8, padding=6),
            ft.Row([
                ft.TextButton("EXPORT GIF", tooltip="Looping GIF of the first 8 seconds",
                              on_click=lambda e: refresh(do_export_gif())),
                ft.TextButton("CLEAR DONE", tooltip="Remove finished jobs from the queue",
                              on_click=lambda e: (render_q.clear_finished(), refresh("queue cleared"))),
            ], spacing=2, wrap=True, tight=True),
            ft.Divider(height=1, color=ui["panel_edge"]),
            section("TITLE CARD", color=MINT),
            title_field,
            subtitle_field,
            EButton("MAKE OPENER", bgcolor=VIOLET, color="white", expand=True,
                    on_click=lambda e: refresh(make_title_card())),
            ft.Divider(height=1, color=ui["panel_edge"]),
            section("SCOPE", color=VIOLET),
            ft.Container(content=hist_img, bgcolor="black", border_radius=8,
                         padding=4, alignment=ft.Alignment.CENTER),
            ft.Row([
                ft.TextButton("HIST", tooltip="RGB histogram",
                              on_click=lambda e: set_scope("hist")),
                ft.TextButton("PARADE", tooltip="RGB parade",
                              on_click=lambda e: set_scope("parade")),
            ], spacing=4, tight=True),
            ft.Container(content=wave_img, bgcolor="black", border_radius=8, padding=4),
            ft.Text("AUDIO (mute-aware)", size=10, color=MUTED),
        ], spacing=8, scroll=ft.ScrollMode.AUTO),
        width=300, bgcolor=PANEL, border_radius=12, padding=12)

    transport = ft.Row([
        ft.IconButton(Icons.PLAY_ARROW, icon_color=MINT, tooltip="Play/pause (space)",
                      on_click=lambda e: toggle()),
        ft.IconButton(Icons.SKIP_PREVIOUS, icon_color=INK, tooltip="-0.5s",
                      on_click=lambda e: step(-1)),
        ft.IconButton(Icons.SKIP_NEXT, icon_color=INK, tooltip="+0.5s",
                      on_click=lambda e: step(1)),
        tc,
        ft.IconButton(Icons.FLIP, icon_color=VIOLET, tooltip="Timecode / seconds",
                      on_click=lambda e: _toggle_tc_mode()),
    ], spacing=4)

    def _toggle_tc_mode():
        state["tc_mode"] = "sec" if state.get("tc_mode", "tc") == "tc" else "tc"
        refresh("time display: " + state["tc_mode"])

    center = ft.Column([
        ft.Container(content=transport, bgcolor=PANEL, border_radius=12, padding=10),
        ft.Container(content=preview, bgcolor="black", border_radius=12,
                     expand=True, padding=8, alignment=ft.Alignment.CENTER),
        empty_hint,
        ft.Container(
            content=ft.Column([scrub, tabs_row, clip_row, markers_row], spacing=8,
                              scroll=ft.ScrollMode.AUTO),
            bgcolor=PANEL, border_radius=12, padding=10, height=250),
        ft.Container(content=ft.Row([goto_field,
                                     EButton("GO", on_click=lambda e: go_to_time())],
                                    spacing=6, tight=True),
                     bgcolor=PANEL, border_radius=12, padding=8),
    ], expand=True, spacing=10)

    right = ft.Container(
        content=ft.Column([
            section("GRADE"),
            grade_slider("exposure", "exposure", -3, 3, 0),
            grade_slider("brightness", "brightness", -100, 100, 0),
            grade_slider("contrast", "contrast", 0, 2, 1),
            grade_slider("saturation", "saturation", 0, 2, 1),
            section("COLOR"),
            grade_slider("temperature", "temperature", -1, 1, 0),
            grade_slider("tint", "tint", -1, 1, 0),
            section("VIDEO FX", color=VIOLET),
            grade_slider("vignette", "vignette", 0, 1, 0.25),
            grade_slider("blur", "blur", 0, 1, 0),
            grade_slider("sharpen", "sharpen", 0, 1, 0),
            grade_slider("pixelate", "pixelate", 0, 1, 0),
            grade_slider("glitch", "glitch", 0, 1, 0),
            grade_slider("grain", "grain", 0, 1, 0),
            grade_slider("chromatic", "chromatic", 0, 1, 0),
            grade_slider("scanlines", "scanlines", 0, 1, 0),
            section("LUT", color=ORANGE),
            ft.Row([ft.TextButton(n, tooltip="apply LUT preset",
                                  on_click=lambda e, k=n: set_lut(k))
                    for n in lut.list_presets()], spacing=2, wrap=True),
            section("LOOK", color=MINT),
            ft.Row([ft.TextButton(n, tooltip="apply look",
                                  on_click=lambda e, k=n: (apply_look(grade, k), sync_grade_ui(), refresh(f"look: {k}")))
                    for n in list_looks()], spacing=2, wrap=True),
            section("TRANSITION", color=VIOLET),
            ft.Row([ft.TextButton(n, tooltip="transition into selected clip",
                                  on_click=lambda e, k=n: set_transition(k))
                    for n in list_transition_names()], spacing=2, wrap=True),
            section("CAPTION", color=MINT),
            caption_field,
            ft.Row([ft.TextButton(s, tooltip="caption position",
                                  on_click=lambda e, k=s: set_caption_style(k))
                    for s in ("bottom", "center", "top")], spacing=2, wrap=True),
            ft.Text("TEXT STYLE (CapCut-style presets)", size=10, color=MUTED),
            ft.Row([ft.TextButton(n, tooltip=f"apply the {n} text look",
                                  on_click=lambda e, k=n: refresh(set_text_preset(k)))
                    for n in TEXT_PRESETS], spacing=2, wrap=True),
        ], spacing=4, scroll=ft.ScrollMode.AUTO),
        width=280, bgcolor=PANEL, border_radius=12, padding=12)

    page.add(header, ft.Row([left, center, right], expand=True, spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.START))
    refresh("IMPORT MEDIA to start — images + videos, multi-select")
    try:
        last = autosave.latest(autosave_dir, tag="manual")
        if last:
            msg.value = f"ready · last snapshot: {os.path.basename(str(last))}"
    except Exception:
        pass


if __name__ == "__main__":
    _port = int(os.environ.get("PORT", 8550))
    if os.environ.get("VMDK_ASGI") == "1" or os.environ.get("PORT"):
        # hosted mode (or opt-in): FastAPI front serves the favicon set and
        # mounts the Flet app; falls back gracefully if deps are missing
        try:
            import uvicorn

            flet_asgi = ft.run(main, view=ft.AppView.WEB_BROWSER,
                               assets_dir=None,
                               upload_dir=os.path.join(tempfile.gettempdir(),
                                                       "vidmaker2000_uploads"),
                               port=_port,
                               export_asgi_app=True)
            uvicorn.run(_wrap_with_brand(flet_asgi), host="0.0.0.0", port=_port,
                        log_level="warning")
        except Exception:
            _run_flet(main, port=_port)  # graceful fallback
    else:
        _run_flet(main, port=_port)
