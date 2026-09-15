"""Structural timeline operations.

Everything here works on plain objects that expose ``clips`` (a mutable list of
Clip instances with ``order`` for reordering. Nothing imports the Flet UI, so
these helpers are unit-testable and reusable from the CLI.
"""

from __future__ import annotations


def _resequence(timeline) -> None:
    for i, clip in enumerate(timeline.clips):
        clip.order = i


def clamp_index(timeline, index: int) -> int:
    """Index clamped into ``0..len(clips)-1`` (0 for an empty timeline)."""
    if not timeline.clips:
        return 0
    return max(0, min(int(index), len(timeline.clips) - 1))


def ripple_delete(timeline, index: int) -> bool:
    """Delete ``index`` and pull later clips back (no gap left behind)."""
    if not (0 <= index < len(timeline.clips)):
        return False
    timeline.clips.pop(index)
    _resequence(timeline)
    return True


def insert_at(timeline, index: int, clip) -> int:
    """Insert ``clip`` at ``index`` and return its final position."""
    position = max(0, min(int(index), len(timeline.clips)))
    timeline.clips.insert(position, clip)
    _resequence(timeline)
    return position


def nudge(timeline, index: int, delta: int) -> bool:
    """Swap ``index`` with its neighbour ``delta`` steps away."""
    if not timeline.clips:
        return False
    target = index + int(delta)
    if not (0 <= index < len(timeline.clips)) or not (0 <= target < len(timeline.clips)):
        return False
    clips = timeline.clips
    clips[index], clips[target] = clips[target], clips[index]
    _resequence(timeline)
    return True


def close_gaps(timeline) -> int:
    """Re-number orders to be contiguous. Returns the number re-ordered."""
    changed = 0
    for i, clip in enumerate(timeline.clips):
        if getattr(clip, "order", i) != i:
            changed += 1
        clip.order = i
    return changed


def merge_adjacent(timeline, max_gap: float = 0.0) -> int:
    """Drop zero/negative-length clips and resequence. Returns removed count."""
    keep = []
    removed = 0
    for clip in timeline.clips:
        if getattr(clip, "trim_dur", 0.1) <= max_gap:
            removed += 1
            continue
        keep.append(clip)
    timeline.clips[:] = keep
    _resequence(timeline)
    return removed


def stats(timeline) -> dict:
    """Small summary used by status messages and tests."""
    clips = list(getattr(timeline, "clips", []) or [])
    total = 0.0
    images = 0
    for clip in clips:
        total += float(getattr(clip, "trim_dur", 0.0) or 0.0)
        if getattr(clip, "kind", "video") == "image":
            images += 1
    return {
        "clips": len(clips),
        "images": images,
        "videos": len(clips) - images,
        "duration": round(total, 3),
    }


def move_to_front(timeline, index: int) -> bool:
    """Bring a clip to position 0."""
    if not (0 <= index < len(timeline.clips)):
        return False
    clip = timeline.clips.pop(index)
    timeline.clips.insert(0, clip)
    _resequence(timeline)
    return True
