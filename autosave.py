"""Crash-safe autosave for vidmaker2000 projects.

Snapshots are written with the same staging+rename trick used elsewhere in the
codebase so a crash mid-write can never leave a half-written project on disk.
Old snapshots are rotated out so a long editing session cannot fill the disk.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable, Optional


def _stamp() -> str:
    # microsecond precision: rapid consecutive snapshots (autosave + manual
    # save in the same second) must not overwrite each other
    return time.strftime("%Y%m%d-%H%M%S-") + f"{time.time() % 1 * 1_000_000:06.0f}"


def ensure_dir(folder) -> Path:
    p = Path(folder)
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshot(folder, payload: dict, keep: int = 10, tag: str = "autosave") -> Optional[str]:
    """Atomically write ``payload`` as a timestamped snapshot.

    Returns the snapshot path, or None when the payload is not serialisable.
    """
    try:
        data = json.dumps(payload, indent=2)
    except (TypeError, ValueError):
        return None
    base = ensure_dir(folder)
    target = base / f"{tag}-{_stamp()}.json"
    staging = base / f".{target.name}.tmp"
    try:
        with open(staging, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(staging, target)
    except OSError:
        try:
            staging.unlink()
        except OSError:
            pass
        return None
    rotate(base, keep=keep, tag=tag)
    return str(target)


def list_snapshots(folder, tag: str = "autosave") -> list[Path]:
    """Newest-first list of snapshots in ``folder``."""
    base = Path(folder)
    if not base.exists():
        return []
    files: Iterable[Path] = (p for p in base.glob(f"{tag}-*.json") if p.is_file())
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def latest(folder, tag: str = "autosave") -> Optional[Path]:
    """Newest snapshot path, or None when there is nothing to restore."""
    found = list_snapshots(folder, tag=tag)
    return found[0] if found else None


def load(path) -> Optional[dict]:
    """Read a snapshot back into a dict (None when unreadable)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def restore(folder, tag: str = "autosave") -> Optional[dict]:
    """Load the newest snapshot, falling back through older ones.

    A corrupt newest snapshot must not lose the session: every candidate is
    tried in order until one parses.
    """
    for candidate in list_snapshots(folder, tag=tag):
        data = load(candidate)
        if data is not None:
            return data
    return None


def rotate(folder, keep: int = 10, tag: str = "autosave") -> int:
    """Delete all but the newest ``keep`` snapshots. Returns deleted count."""
    removed = 0
    for stale in list_snapshots(folder, tag=tag)[max(1, int(keep)):]:
        try:
            stale.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def info(folder, tag: str = "autosave") -> dict:
    """Small status dict for the UI (count, newest, total bytes)."""
    snaps = list_snapshots(folder, tag=tag)
    total = 0
    for s in snaps:
        try:
            total += s.stat().st_size
        except OSError:
            continue
    return {
        "count": len(snaps),
        "newest": snaps[0].name if snaps else None,
        "bytes": total,
    }
