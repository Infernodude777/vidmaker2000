"""Sequential render queue for vidmaker2000 exports.

Jobs are plain dicts so they survive a project save/load round trip without a
custom serialiser. Actual frames are produced by ``export.export_timeline``,
imported lazily so this module stays importable in headless test runs.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class RenderJob:
    """One queued export."""
    timeline_name: str = ""
    preset: str = "preview_720p"
    out_path: str = ""
    state: str = "queued"          # queued | running | done | failed | cancelled
    frames: int = 0
    error: str = ""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class RenderQueue:
    """Append-only FIFO queue with a single worker step per call.

    ``run_next`` is deliberately non-blocking-by-default (max_frames capped) so
    the Flet UI thread can drive it one chunk at a time and stay responsive.
    """

    def __init__(self, max_chunk_frames: int = 120):
        self.jobs: list[RenderJob] = []
        self.max_chunk_frames = int(max_chunk_frames)

    def add(self, timeline_name: str, preset: str, out_path: str) -> RenderJob:
        job = RenderJob(timeline_name=timeline_name, preset=preset, out_path=out_path)
        self.jobs.append(job)
        return job

    def pending(self) -> list[RenderJob]:
        return [j for j in self.jobs if j.state == "queued"]

    def cancel(self, job_id: str) -> bool:
        for job in self.jobs:
            if job.job_id == job_id and job.state in ("queued", "running"):
                job.state = "cancelled"
                return True
        return False

    def clear_finished(self) -> int:
        before = len(self.jobs)
        self.jobs[:] = [j for j in self.jobs if j.state in ("queued", "running")]
        return before - len(self.jobs)

    def run_next(self, timeline, grade, exporter=None, max_frames: Optional[int] = None) -> Optional[RenderJob]:
        """Run the next queued job to completion.

        NOTE: ``export_timeline`` cannot resume mid-stream, so a "chunked"
        run would restart from frame 0 each call and truncate the output.
        Instead the job renders fully; callers should invoke ``run_next``
        from a background thread (see app.py) to keep the UI responsive.
        """
        queue = self.pending()
        if not queue:
            return None
        job = queue[0]
        if exporter is None:
            from export import export_timeline as exporter  # type: ignore
        job.state = "running"
        limit = int(max_frames or 10 ** 9)  # default: no truncation
        try:
            result = exporter(timeline, grade, job.out_path,
                              max_frames=limit, preset=job.preset)
        except Exception as exc:  # a broken job must not stall the queue
            job.state = "failed"
            job.error = str(exc)
            return job
        if not isinstance(result, dict):
            job.state = "failed"
            job.error = "exporter returned no result"
            return job
        if result.get("ok"):
            job.frames = int(result.get("frames", 0) or 0)
            job.state = "done"
        else:
            job.state = "failed"
            job.error = str(result.get("error", "export failed"))
        return job

    def status(self) -> dict:
        counts = {"queued": 0, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
        for job in self.jobs:
            counts[job.state] = counts.get(job.state, 0) + 1
        return {"total": len(self.jobs), **counts}
