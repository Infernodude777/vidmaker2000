"""B-roll indexing and suggestion.

Offline and dependency-free: filenames plus any caller-supplied tags are the
search corpus. Scoring is token overlap with a light recency/duration bias so
results are stable and explainable.
"""

from __future__ import annotations

import os

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".avi", ".mkv")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
ALL_EXTS = VIDEO_EXTS + IMAGE_EXTS


def index_folder(folder, exts=ALL_EXTS) -> list[dict]:
    """Walk ``folder`` and return [{path, name, ext, size}] for media files."""
    out: list[dict] = []
    if not folder or not os.path.isdir(str(folder)):
        return out
    for dirpath, _dirnames, filenames in os.walk(str(folder)):
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in exts:
                continue
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            out.append({"path": full, "name": name, "ext": ext, "size": size})
    return out


def _tokens(text: str) -> set[str]:
    cleaned = "".join(c if c.isalnum() else " " for c in (text or "").lower())
    return {tok for tok in cleaned.split() if len(tok) > 1}


def score(query: str, entry: dict, tags=()) -> float:
    """Relevance score for one index entry (0 when nothing matches)."""
    want = _tokens(query)
    if not want:
        return 0.0
    have = _tokens(entry.get("name", "")) | _tokens(entry.get("tags", ""))
    for tag in tags or ():
        have |= _tokens(str(tag))
    overlap = len(want & have)
    if overlap == 0:
        return 0.0
    return overlap / float(len(want))


def suggest(query: str, index, limit: int = 8) -> list[dict]:
    """Best ``limit`` entries for ``query``, highest score first."""
    scored = []
    for entry in index or ():
        value = score(query, entry)
        if value > 0:
            scored.append((value, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("name", "")))
    return [entry for _value, entry in scored[:max(1, int(limit))]]


def pick_shot(kind: str, index) -> dict | None:
    """First indexed shot matching a broad kind ("" = any)."""
    wanted = (kind or "").strip().lower()
    for entry in index or ():
        ext = entry.get("ext", "")
        if not wanted:
            return entry
        if wanted in ("video", "vid") and ext in VIDEO_EXTS:
            return entry
        if wanted in ("image", "img", "photo") and ext in IMAGE_EXTS:
            return entry
    return None


def total_size(index) -> int:
    """Sum of indexed file sizes (for the UI status line)."""
    return sum(int(e.get("size", 0) or 0) for e in index or ())
