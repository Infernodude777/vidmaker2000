from dataclasses import dataclass, asdict
import copy


class ClipError(Exception):
    pass


@dataclass
class Grade:
    exposure: float = 0.0
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    temperature: float = 0.0
    tint: float = 0.0
    highlights: float = 0.0
    shadows: float = 0.0
    vignette: float = 0.25
    blur: float = 0.0
    sharpen: float = 0.0
    pixelate: float = 0.0
    glitch: float = 0.0
    grain: float = 0.0
    chromatic: float = 0.0
    scanlines: float = 0.0
    lut: str = "neutral"
    grayscale: bool = False
    flip_h: bool = False
    flip_v: bool = False
    rotate: int = 0
    speed: float = 1.0
    muted: bool = False
    text: str = ""
    fade_in: float = 0.0
    fade_out: float = 0.0

    def reset(self):
        fresh = Grade()
        self.__dict__.update(asdict(fresh))

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        g = Grade()
        for k, v in (d or {}).items():
            if hasattr(g, k):
                setattr(g, k, v)
        return g


@dataclass
class Clip:
    path: str = ""
    name: str = "clip"
    kind: str = "video"
    track: str = "V1"
    transition: str = "cut"
    trans_dur: float = 0.5
    fade_in: float = 0.0    # per-clip fade-from-black (seconds)
    fade_out: float = 0.0   # per-clip fade-to-black (seconds)
    caption: str = ""
    duration: float = 0.0
    fps: float = 30.0
    width: int = 0
    height: int = 0
    in_point: float = 0.0
    out_point: float = 0.0
    order: int = 0
    # nested-sequence support: when kind == "nested", ``path`` stores the
    # serialized sub-timeline JSON and duration/trim fields work as usual
    nested: dict | None = None
    # per-clip playback rate (2.0 = twice as fast; timeline duration is kept
    # by advancing through source frames ``speed``x faster)
    speed: float = 1.0
    # Ken Burns motion for stills: {"zs": 1.0, "ze": 1.15, "px": -0.1, "py": 0.05}
    # zoom start/end factors and pan as fractions of frame size
    kenburns: dict | None = None

    @property
    def trim_dur(self):
        out = self.out_point if self.out_point > 0 else self.duration
        return max(0.1, out - self.in_point)

    def nested_timeline(self):
        """Materialized sub-Timeline for nested clips (None otherwise)."""
        if self.kind != "nested" or not self.nested:
            return None
        return Timeline.from_dict(self.nested)

    def to_dict(self):
        return asdict(self)


class Marker:
    """A colored flag pinned to a timeline position, with an optional note."""

    COLORS = {"orange": "#ff8906", "violet": "#7f5af0", "mint": "#2cb67d",
              "red": "#d04648", "blue": "#4da3ff"}

    def __init__(self, t: float, color: str = "orange", note: str = ""):
        self.t = max(0.0, float(t))
        self.color = color if color in self.COLORS else "orange"
        self.note = str(note or "")

    def to_dict(self):
        return {"t": self.t, "color": self.color, "note": self.note}

    @staticmethod
    def from_dict(d):
        try:
            return Marker(float((d or {}).get("t", 0.0)),
                          str((d or {}).get("color", "orange")),
                          str((d or {}).get("note", "")))
        except (TypeError, ValueError):
            return None


class Timeline:
    def __init__(self, name="Timeline 1"):
        self.name: str = name or "Timeline 1"
        self.clips: list[Clip] = []
        self.playhead: float = 0.0
        self.markers: list[Marker] = []

    def add_clip(self, clip: Clip):
        clip.order = len(self.clips)
        if clip.out_point <= 0:
            clip.out_point = clip.duration
        self.clips.append(clip)
        return clip

    def remove_at(self, idx: int):
        if 0 <= idx < len(self.clips):
            self.clips.pop(idx)
            for i, c in enumerate(self.clips):
                c.order = i

    def move(self, idx: int, delta: int):
        j = idx + delta
        if 0 <= idx < len(self.clips) and 0 <= j < len(self.clips):
            self.clips[idx], self.clips[j] = self.clips[j], self.clips[idx]
            for i, c in enumerate(self.clips):
                c.order = i

    def duplicate_at(self, idx: int) -> Clip | None:
        if not (0 <= idx < len(self.clips)):
            return None
        dup = copy.deepcopy(self.clips[idx])
        self.clips.insert(idx + 1, dup)
        for i, c in enumerate(self.clips):
            c.order = i
        return dup

    def split_at_playhead(self):
        active, local = self.locate(self.playhead)
        if active is None:
            return False
        mid = active.in_point + local
        if mid <= active.in_point + 0.2 or mid >= (active.out_point or active.duration) - 0.2:
            return False
        right = copy.deepcopy(active)
        right.in_point = mid
        active.out_point = mid
        self.clips.insert(active.order + 1, right)
        for i, c in enumerate(self.clips):
            c.order = i
        return True

    def total_duration(self):
        return sum(c.trim_dur for c in self.clips)

    # ---- markers ------------------------------------------------------------
    def add_marker(self, t, color="orange", note="") -> Marker:
        m = Marker(t, color, note)
        self.markers.append(m)
        self.markers.sort(key=lambda mk: mk.t)
        return m

    def remove_marker(self, t, tol=0.15) -> bool:
        for i, m in enumerate(self.markers):
            if abs(m.t - float(t)) <= tol:
                self.markers.pop(i)
                return True
        return False

    def marker_before(self, t):
        prev = [m for m in self.markers if m.t < float(t) - 1e-6]
        return prev[-1] if prev else None

    def marker_after(self, t):
        nxt = [m for m in self.markers if m.t > float(t) + 1e-6]
        return nxt[0] if nxt else None

    def locate(self, t: float):
        acc = 0.0
        for c in self.clips:
            d = c.trim_dur
            if acc <= t < acc + d:
                return c, (t - acc)
            acc += d
        return None, 0.0

    def snapshot(self):
        return copy.deepcopy(self.clips)

    def restore(self, snap):
        self.clips = copy.deepcopy(snap)
        for i, c in enumerate(self.clips):
            c.order = i

    def to_dict(self):
        return {"name": self.name, "playhead": self.playhead,
                "markers": [m.to_dict() for m in self.markers],
                "clips": [c.to_dict() for c in self.clips]}

    @staticmethod
    def from_dict(d):
        tl = Timeline(name=(d or {}).get("name", "Timeline 1"))
        tl.playhead = float((d or {}).get("playhead", 0.0))
        for md in (d or {}).get("markers", []) or []:
            m = Marker.from_dict(md)
            if m:
                tl.markers.append(m)
        for cd in (d or {}).get("clips", []):
            tl.add_clip(Clip(**{k: v for k, v in cd.items() if k in Clip.__dataclass_fields__}))
        return tl


class TimelineSet:
    def __init__(self):
        self.timelines: list[Timeline] = [Timeline(name="Timeline 1")]
        self.active: int = 0
        self._undo: list = []
        self._redo: list = []

    def current(self) -> Timeline:
        if not self.timelines:
            self.timelines = [Timeline(name="Timeline 1")]
            self.active = 0
        self.active = max(0, min(self.active, len(self.timelines) - 1))
        return self.timelines[self.active]

    def push_undo(self):
        tl = self.current()
        self._undo.append(tl.snapshot())
        if len(self._undo) > 60:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> str:
        if not self._undo:
            return "nothing to undo"
        tl = self.current()
        self._redo.append(tl.snapshot())
        tl.restore(self._undo.pop())
        return "undo"

    def redo(self) -> str:
        if not self._redo:
            return "nothing to redo"
        tl = self.current()
        self._undo.append(tl.snapshot())
        tl.restore(self._redo.pop())
        return "redo"

    def add_timeline(self, name=None) -> Timeline:
        n = name or f"Timeline {len(self.timelines) + 1}"
        tl = Timeline(name=n)
        self.timelines.append(tl)
        self.active = len(self.timelines) - 1
        return tl

    def remove_at(self, idx: int) -> bool:
        if len(self.timelines) <= 1 or not (0 <= idx < len(self.timelines)):
            return False
        self.timelines.pop(idx)
        self.active = max(0, min(self.active, len(self.timelines) - 1))
        return True

    def rename(self, idx: int, name: str):
        if 0 <= idx < len(self.timelines) and (name or "").strip():
            self.timelines[idx].name = name.strip()[:28]

    def switch(self, idx: int):
        if 0 <= idx < len(self.timelines):
            self.active = idx
        return self.current()

    def nest_current(self, name=None) -> Clip | None:
        """Serialize the current timeline into a nested clip appended to the
        previous timeline (or a fresh one). Guarded against self-nesting."""
        src = self.current()
        if not src.clips:
            return None
        payload = src.to_dict()
        # choose the destination: the timeline before the source, if any
        if self.active > 0:
            dst = self.timelines[self.active - 1]
        else:
            dst = Timeline(name=f"Comp {src.name}"[:28])
            self.timelines.append(dst)
            self.active = len(self.timelines) - 1
            dst = self.timelines[self.active]
        clip = Clip(kind="nested", name=name or f"⟳ {src.name}",
                    duration=src.total_duration(), fps=30.0,
                    in_point=0.0, out_point=src.total_duration(),
                    order=len(dst.clips), nested=payload)
        clip.path = ""
        dst.add_clip(clip)
        return clip

    def to_dict(self):
        return {"active": self.active, "timelines": [t.to_dict() for t in self.timelines]}

    @staticmethod
    def from_dict(d):
        ts = TimelineSet()
        if not d:
            return ts
        if "timelines" in d:
            tls = []
            for td in d.get("timelines", []) or []:
                tls.append(Timeline.from_dict(td))
            if tls:
                ts.timelines = tls
                ts.active = int(d.get("active", 0) or 0)
                ts.active = max(0, min(ts.active, len(ts.timelines) - 1))
            return ts
        if "clips" in d:
            ts.timelines = [Timeline.from_dict(d)]
            ts.active = 0
            return ts
        return ts
