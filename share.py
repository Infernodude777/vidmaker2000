"""Delivery helpers: manifests, bundles and log lines.

The original three helpers keep working; manifest v2 adds checksums, byte sizes
and a stable schema version for downstream tooling.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time

MANIFEST_VERSION = 2


def share_path(name="vidmaker2000_cut.mp4"):
    """Default output path for a delivery file."""
    return os.path.join(tempfile.gettempdir(), name)


def export_log_line(frames, out, elapsed=0):
    """One-line human log entry for an export."""
    rate = (frames / elapsed) if elapsed else 0.0
    return f"exported {int(frames)} frames -> {out} ({elapsed:.1f}s, {rate:.1f} fps)"


def _sha256(path) -> str:
    """Hex digest of a file, or "" when it cannot be read."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 256), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def write_manifest(out_path, frames, fps, elapsed, grade_dict=None):
    """Write a sidecar .manifest.json next to an export. Returns its path."""
    manifest_path = str(out_path) + ".manifest.json"
    size = 0
    checksum = ""
    if os.path.exists(str(out_path)):
        try:
            size = os.path.getsize(str(out_path))
        except OSError:
            size = 0
        checksum = _sha256(out_path)
    payload = {
        "version": MANIFEST_VERSION,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "output": str(out_path),
        "frames": int(frames or 0),
        "fps": float(fps or 30.0),
        "elapsed_s": float(elapsed or 0.0),
        "bytes": size,
        "sha256": checksum,
        "grade": dict(grade_dict or {}),
    }
    try:
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError:
        return ""
    return manifest_path


def manifest_summary(manifest_path) -> str:
    """Readable one-liner from a manifest ("" when unreadable)."""
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ""
    return (f"v{data.get('version', 1)} {data.get('frames', 0)}f "
            f"{data.get('bytes', 0)}B sha256:{(data.get('sha256') or '')[:12]}")


def export_bundle(out_path, export_fn, manifest_args=None):
    """Run an export and always write a manifest beside it.

    ``export_fn`` is any zero-argument callable returning a dict with at least
    an "ok" key and optionally "frames"/"error".
    """
    started = time.time()
    try:
        result = export_fn() or {}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    elapsed = time.time() - started
    args = dict(manifest_args or {})
    manifest = write_manifest(
        out_path,
        result.get("frames", 0),
        args.get("fps", 30.0),
        elapsed,
        args.get("grade"),
    )
    result.setdefault("elapsed_s", round(elapsed, 2))
    if manifest:
        result["manifest"] = manifest
    return result
