import json
import os
import time
import shutil

EXT = ".vidmaker"


def save_project(path, timeline_or_set, grade, media_bin=None):
    from timeline import Timeline, TimelineSet
    if isinstance(timeline_or_set, TimelineSet):
        timelines_data = timeline_or_set.to_dict()
    elif isinstance(timeline_or_set, Timeline):
        ts = TimelineSet()
        ts.timelines = [timeline_or_set]
        ts.active = 0
        timelines_data = ts.to_dict()
    else:
        timelines_data = timeline_or_set
    data = {
        "app": "vidmaker2000",
        "v": 2,
        "timelines": timelines_data,
        "timeline": (timelines_data.get("timelines", [{}])[0]
                     if isinstance(timelines_data, dict) else {}),
        "grade": grade.to_dict() if hasattr(grade, "to_dict") else dict(grade or {}),
        "media_bin": list(media_bin or []),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    if os.path.exists(path):
        bak = path + ".bak"
        try:
            shutil.copy2(path, bak)
        except Exception:
            pass
    os.replace(tmp, path)
    return path


def load_project_full(path):
    from timeline import TimelineSet, Grade as GradeCls
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    g = GradeCls.from_dict(data.get("grade", {}))
    media_bin = data.get("media_bin", []) or []
    if "timelines" in data:
        ts = TimelineSet.from_dict(data.get("timelines", {}))
    elif "timeline" in data:
        ts = TimelineSet.from_dict(data.get("timeline", {}))
    else:
        ts = TimelineSet.from_dict(data)
    return ts, g, media_bin


def load_project(path):
    ts, g, _bin = load_project_full(path)
    return ts, g


def default_save_path(name="untitled"):
    base = os.path.expanduser("~/vidmaker2000")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, name + EXT)


def autosave_path():
    base = os.path.expanduser("~/vidmaker2000")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "autosave" + EXT)


def save_autosave(ts, grade, media_bin=None):
    return save_project(autosave_path(), ts, grade, media_bin=media_bin)


def load_autosave():
    path = autosave_path()
    if not os.path.exists(path):
        return None, None, None
    return load_project_full(path)


def validate_media_bin(media_bin):
    out = []
    for m in media_bin or []:
        p = m.get("path", "") if isinstance(m, dict) else ""
        if p and os.path.exists(p):
            out.append(m)
    return out


def project_stats(ts):
    total = 0.0
    nclips = 0
    for t in getattr(ts, "timelines", []):
        nclips += len(t.clips)
        total += t.total_duration()
    return {
        "timelines": len(getattr(ts, "timelines", [])),
        "clips": nclips,
        "duration_sec": round(total, 2),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
