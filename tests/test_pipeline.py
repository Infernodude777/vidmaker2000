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
