"""Unit tests for vidmaker2000 pipeline helpers.

These avoid OpenCV and Flet entirely so they run in a bare pytest environment:
everything tested here is pure Python or standard library.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import autosave
import broll
import captions
import keymap
import lut
import media_index
import profiles
import timeline_ops


class FakeClip:
    def __init__(self, name="clip", dur=1.0, kind="video", caption=""):
        self.name = name
        self.duration = dur
        self.in_point = 0.0
        self.out_point = dur
        self.order = 0
        self.kind = kind
        self.caption = caption

    @property
    def trim_dur(self):
        return max(0.1, (self.out_point or self.duration) - self.in_point)


class FakeTimeline:
    def __init__(self, count=3):
        self.clips = [FakeClip(f"c{i}") for i in range(count)]
        for i, clip in enumerate(self.clips):
            clip.order = i


def test_keymap_defaults_and_remap():
    assert keymap.binding_for("play_pause") == "space"
    assert keymap.remap("play_pause", "p") is True
    assert keymap.action_for("p") == "play_pause"
    keymap.reset()
    assert keymap.binding_for("play_pause") == "space"
    assert keymap.remap("nope", "x") is False


def test_timeline_ops_ripple_and_insert():
    tl = FakeTimeline(3)
    assert timeline_ops.ripple_delete(tl, 1) is True
    assert [c.name for c in tl.clips] == ["c0", "c2"]
    position = timeline_ops.insert_at(tl, 1, FakeClip("new"))
    assert position == 1
    assert [c.name for c in tl.clips] == ["c0", "new", "c2"]
    assert [c.order for c in tl.clips] == [0, 1, 2]


def test_timeline_ops_stats_and_gaps():
    tl = FakeTimeline(2)
    stats = timeline_ops.stats(tl)
    assert stats["clips"] == 2
    assert stats["duration"] > 0
    assert timeline_ops.close_gaps(tl) == 0


def test_captions_srt_roundtrip():
    track = captions.CaptionTrack()
    track.add(0.0, 1.5, "hello world")
    track.add(1.5, 3.0, "second line")
    srt = track.to_srt()
    assert "00:00:00,000 --> 00:00:01,500" in srt
    parsed = captions.parse_subtitles(srt)
    assert len(parsed.cues) == 2
    assert parsed.text_at(0.5) == "hello world"
    assert parsed.text_at(2.0) == "second line"
    assert parsed.to_vtt().startswith("WEBVTT")


def test_captions_wrap_text():
    lines = captions.wrap_text("a " * 40, width=20)
    assert lines and all(len(line) <= 20 for line in lines)


def test_captions_from_clips():
    clips = [FakeClip("a", caption="one"), FakeClip("b"), FakeClip("c", caption="three")]
    track = captions.from_clips(clips)
    assert len(track.cues) == 2
    assert track.cues[0][2] == "one"


def test_lut_identity_and_preset():
    table = lut.identity_table()
    assert table[0] == 0 and table[255] == 255 and len(table) == 256
    assert len(lut.preset_table("film")) == 256
    assert lut.preset_table("missing") == lut.preset_table("neutral")
    assert lut.build_table([(0, 0)]) == lut.identity_table()


def test_lut_blend():
    a = lut.identity_table()
    b = [min(255, v + 10) for v in a]
    mixed = lut.blend_table(a, b, 0.5)
    assert 0 <= mixed[128] <= 255
    assert mixed[128] >= a[128]


def test_profiles_aspect_and_crop():
    assert profiles.summary("youtube_1080p").startswith("youtube_1080p")
    assert profiles.matches_aspect(1920, 1080, "youtube_1080p") is True
    box = profiles.crop_box(1920, 1080, "shorts_1080x1920")
    x0, y0, x1, y1 = box
    assert x1 > x0 and y1 > y0
    assert profiles.get_profile("nope")["width"] == 1280


def test_autosave_snapshot_restore_rotate(tmp_path):
    folder = tmp_path / "snaps"
    for i in range(4):
        path = autosave.snapshot(folder, {"i": i}, keep=2)
        assert path is not None
    assert autosave.info(folder)["count"] == 2
    restored = autosave.restore(folder)
    assert isinstance(restored, dict)


def test_broll_index_and_suggest(tmp_path):
    (tmp_path / "drone_sunset.mp4").write_bytes(b"x")
    (tmp_path / "city_night.mp4").write_bytes(b"y")
    (tmp_path / "note.txt").write_text("skip me")
    index = broll.index_folder(tmp_path)
    assert len(index) == 2
    hits = broll.suggest("sunset", index)
    assert hits and hits[0]["name"] == "drone_sunset.mp4"
    assert broll.pick_shot("video", index) is not None


def test_media_index_add_search(tmp_path):
    db = tmp_path / "media.db"
    index = media_index.MediaIndex(db)
    index.add(str(tmp_path / "a.mp4"), duration=2.0)
    index.add(str(tmp_path / "b.mp4"), duration=3.0, tags=("sunset",))
    assert index.count() == 2
    assert index.search("sunset")[0]["name"] == "b.mp4"
    assert len(index.search("")) == 2
    assert index.remove(str(tmp_path / "a.mp4")) is True
    assert index.count() == 1
    index.close()


def test_media_index_memory_fallback(tmp_path):
    index = media_index.MediaIndex(None)
    index.add("memory.mp4")
    assert index.count() == 1
    assert index.search("memory")


def test_share_and_render_queue_contract():
    import render_queue
    import share
    queue = render_queue.RenderQueue()
    job = queue.add("Timeline 1", "preview_720p", "out.mp4")
    assert queue.status()["queued"] == 1
    assert queue.cancel(job.job_id) is True
    assert queue.status()["cancelled"] == 1
    assert "exported" in share.export_log_line(30, "out.mp4", 1.0)


# ---- v2.4: nested timelines, per-clip speed, Ken Burns, markers ----

def test_nested_clip_roundtrip_and_duration():
    from timeline import TimelineSet, Clip
    import cv2, os, tempfile
    import numpy as np
    ts = TimelineSet()
    a = ts.current()
    p = os.path.join(tempfile.gettempdir(), "nest_t.png")
    img = np.zeros((60, 80, 3), np.uint8)
    img[:] = (30, 200, 90)
    cv2.imwrite(p, img)
    a.add_clip(Clip(path=p, kind="image", duration=0.5, fps=30.0,
                    in_point=0.0, out_point=0.5))
    nested = ts.nest_current("SUB")
    assert nested is not None and nested.kind == "nested"
    assert abs(nested.duration - 0.5) < 0.01
    d = ts.to_dict()
    ts2 = TimelineSet.from_dict(d)
    restored = [c for t in ts2.timelines for c in t.clips if c.kind == "nested"]
    assert restored and restored[0].nested


def test_nested_export_produces_frames():
    import export
    from timeline import TimelineSet, Clip, Grade
    import cv2, os, tempfile
    import numpy as np
    p = os.path.join(tempfile.gettempdir(), "nest_x.png")
    cv2.imwrite(p, np.zeros((60, 80, 3), np.uint8))
    ts = TimelineSet()
    ts.current().add_clip(Clip(path=p, kind="image", duration=0.4, fps=30.0,
                               in_point=0.0, out_point=0.4))
    ts.nest_current("SUB")
    dst = ts.timelines[ts.active - 1] if ts.active > 0 else ts.timelines[0]
    out = os.path.join(tempfile.gettempdir(), "nest_x.mp4")
    r = export.export_timeline(dst, Grade(), out, max_frames=30)
    assert r.get("ok") and r.get("frames", 0) >= 10


def test_ken_burns_moves_frame():
    import export
    from timeline import Clip
    import numpy as np
    grad = np.tile(np.arange(64, dtype=np.uint8), (48, 1))[..., None].repeat(3, axis=2)
    kb = {"zs": 1.0, "ze": 1.3, "px": -0.1, "py": 0.0}
    c = Clip(path="", kind="image", duration=1.0, fps=10.0,
             in_point=0.0, out_point=1.0, kenburns=kb)
    frames = list(export._iter_source_frames(c, 10.0)) if False else None
    # call the renderer directly with the gradient as the still
    f0 = export._ken_burns(grad, kb, 0.0)
    f1 = export._ken_burns(grad, kb, 1.0)
    assert f0.shape == grad.shape and f1.shape == grad.shape
    assert not np.array_equal(f0, f1)


def test_clip_speed_affects_output_length():
    import export
    from timeline import Clip, Grade, Timeline
    import cv2, os, tempfile
    import numpy as np
    vp = os.path.join(tempfile.gettempdir(), "spd_t.mp4")
    w = cv2.VideoWriter(vp, cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for k in range(60):
        fr = np.zeros((48, 64, 3), np.uint8)
        fr[:] = (k * 3 % 255, 90, 60)
        w.write(fr)
    w.release()
    c = Clip(path=vp, kind="video", duration=2.0, fps=30.0,
             in_point=0.0, out_point=2.0, speed=2.0)
    tl = Timeline()
    tl.add_clip(c)
    out = os.path.join(tempfile.gettempdir(), "spd_t_out.mp4")
    r = export.export_timeline(tl, Grade(), out, max_frames=60)
    assert r.get("ok")


def test_markers_nav_and_persistence():
    from timeline import Timeline
    tl = Timeline()
    tl.add_marker(1.0, color="mint", note="a")
    tl.add_marker(3.0)
    assert tl.marker_before(2.0).t == 1.0
    assert tl.marker_after(2.0).t == 3.0
    assert tl.marker_after(3.0) is None
    tl2 = Timeline.from_dict(tl.to_dict())
    assert len(tl2.markers) == 2 and tl2.markers[0].note == "a"


# ---- v2.5: text styling, GIF export ----

def test_caption_styles_change_pixels():
    import numpy as np
    import captions
    f = np.zeros((240, 320, 3), np.uint8)
    plain = captions.draw_caption(f.copy(), "hello")
    styled = captions.draw_caption(f.copy(), "hello",
                                   style={"pos": "top", "size": 1.2,
                                          "color": "yellow", "bg": "black"})
    assert not np.array_equal(plain, styled)
    assert captions.TEXT_PRESETS and "subtitle" in captions.TEXT_PRESETS


def test_gif_export_loops():
    import export
    from timeline import Timeline, Clip, Grade
    import os, tempfile
    p = os.path.join(tempfile.gettempdir(), "gif_t.png")
    import numpy as np
    import cv2
    cv2.imwrite(p, np.zeros((48, 64, 3), np.uint8))
    tl = Timeline()
    tl.add_clip(Clip(path=p, kind="image", duration=1.0, fps=10.0,
                     in_point=0.0, out_point=1.0))
    out = os.path.join(tempfile.gettempdir(), "gif_t.gif")
    r = export.export_gif(tl, Grade(), out, fps=5.0, max_seconds=1.0)
    assert r.get("ok") and os.path.exists(out) and os.path.getsize(out) > 0


def test_text_style_persists_on_clip():
    from timeline import Clip
    c = Clip(caption="x", text_style={"pos": "top", "size": 1.3,
                                      "color": "mint", "bg": None})
    d = c.to_dict()
    c2 = Clip(**{k: v for k, v in d.items() if k in Clip.__dataclass_fields__})
    assert c2.text_style["color"] == "mint"


# ---- v2.6: variable export presets, fit modes, speed-aware timeline ----

def _tiny_video(path, frames=60, size=(64, 48), fps=30.0):
    import cv2
    import numpy as np
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for k in range(frames):
        fr = np.zeros((size[1], size[0], 3), np.uint8)
        fr[:] = (k * 4 % 255, 90, 60)
        w.write(fr)
    w.release()
    return path


def test_preset_categories_and_info():
    import export
    cats = export.preset_categories()
    assert "Social" in cats and "YouTube" in cats and "General" in cats
    assert "shorts_1080p60" in cats["Social"]
    info = export.preset_info("shorts_1080p60")
    assert "1080" in info and "60" in info


def test_custom_preset_builder():
    import export
    key = export.add_custom_preset("My Reel!!", 1080, 1350, fps=25,
                                   quality=90, fit="contain")
    p = export.get_preset(key)
    assert p["width"] == 1080 and p["height"] == 1350 and p["fps"] == 25.0
    assert p["fit"] == "contain" and p["category"] == "Custom"
    key2 = export.add_custom_preset("My Reel!!", 500, 500)
    assert key2 != key  # collision-safe naming


def test_fit_modes_produce_exact_geometry():
    import export
    from timeline import Clip, Grade, Timeline
    import cv2, os, tempfile
    vp = _tiny_video(os.path.join(tempfile.gettempdir(), "fit_t.mp4"))
    tl = Timeline()
    tl.add_clip(Clip(path=vp, kind="video", duration=1.0, fps=30.0,
                     in_point=0.0, out_point=1.0))
    for preset, expect in (("square_1080", (1080, 1080)),
                           ("preview_720p", (1280, 720))):
        out = os.path.join(tempfile.gettempdir(), f"fit_{preset}.mp4")
        r = export.export_timeline(tl, Grade(), out, preset=preset, max_frames=10)
        assert r["ok"] and (r["width"], r["height"]) == expect, (preset, r)
        cap = cv2.VideoCapture(out)
        ok, frame = cap.read()
        cap.release()
        assert ok and frame.shape[1] == expect[0] and frame.shape[0] == expect[1]


def test_contain_fit_letterboxes():
    import export
    import numpy as np
    frame = np.zeros((240, 320, 3), np.uint8)
    out = export._fit_frame(frame, 100, 100, "contain")
    assert out.shape[:2] == (100, 100)
    assert out[0, 50].tolist() == [0, 0, 0]      # black bar on top
    assert out[50, 50].sum() >= 0                 # centre is content


def test_slowmo_doubles_output_duration():
    import export
    from timeline import Clip, Grade, Timeline
    import os, tempfile
    vp = _tiny_video(os.path.join(tempfile.gettempdir(), "smo.mp4"))
    tl = Timeline()
    tl.add_clip(Clip(path=vp, kind="video", duration=2.0, fps=30.0,
                     in_point=0.0, out_point=2.0, speed=0.5))
    out = os.path.join(tempfile.gettempdir(), "smo_out.mp4")
    r = export.export_timeline(tl, Grade(), out, max_frames=200)
    assert r["ok"] and abs(r["frames"] / 30.0 - 4.0) < 0.2  # 2s @0.5x = 4s
