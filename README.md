# VIDMAKER2000

![python](https://img.shields.io/badge/python-3.12%2B-3776ab)
![flet](https://img.shields.io/badge/UI-flet%201.0-ff8906)
![opencv](https://img.shields.io/badge/engine-OpenCV-5c3ee8)
![tests](https://img.shields.io/badge/tests-17%20passing-2cb67d)

A browser video editor with a neon heart. Multi-timeline cutting, per-frame
grading, LUTs, transitions, captions, scene detection, beat snapping and a
background render queue — all in one Python process with zero external
services.

```
pip install -r requirements.txt
python app.py            # → http://localhost:8550
```

---

## Why it's different

| | vidmaker2000 | typical web editors |
|---|---|---|
| Grading | per-frame OpenCV pipeline: exposure → color → FX → LUT | preset filters |
| Media | indexed library with SQLite search + one-click re-add | flat bin |
| Editing | ripple delete, gap closing, merge, scene auto-split | manual only |
| Music sync | beat detection snaps cuts to the waveform | — |
| Export | delivery profiles up to 4K, queue renders in background | blocks the UI |
| Safety | autosave snapshots (microsecond-stamped, rotating) | manual save |

## Features

**Import** — mp4/mov/webm/avi + png/jpg/webp/bmp, up to 200MB. Browser
uploads are spilled to disk and probed automatically; big files can be added
by local path. A one-click **sample generator** produces test media so the
whole pipeline works with zero assets.**Timelines** — unlimited timeline tabs, duplicate/delete, **duplicate-to-new-tab**, **nested sequences** (collapse a whole timeline into a single clip on another tab — grades, transitions and fades compose through it), 60-level undo, zoomable clip cards with filmstrip thumbnails, transitions and caption tags.

**Clip motion & speed** — per-clip playback rate (0.5×–4×) and **Ken Burns** pan/zoom presets for stills (zoom in/out, pan left/right), rendered identically in preview and export. Grade copy/paste (`Ctrl+C`/`Ctrl+V`) transfers a whole look between clips.

**Markers** — colored flags with notes, pinned per timeline and saved with the project. Drop with `B`, jump with `↑`/`↓`, click a flag to seek. **Go-to timecode** accepts `90`, `1m30` or `MM:SS`; time display toggles between TC and raw seconds.

**Fades** — per-clip fade-in/out from black (0.25s–3s), rendered identically in preview and export. **Frame stepping** with `,`/`.` gives single-frame accuracy; **snapshot** (`P`) saves the current graded frame as a PNG; playback rate cycles 0.25×–2×.

**Grade & FX** — exposure, brightness, contrast, saturation, temperature,
tint, vignette, blur, sharpen, pixelate, glitch, grain, chromatic aberration,
scanlines — then a **LUT** on top (film, punch, night, fade). One-click looks:
noir, vhs, warm, cool, punch, film, dream, retro, glitchy. Live RGB histogram
and parade scopes plus an audio strip.

**Transitions & captions** — crossfade, dip-to-black, wipe, slide and zoom
dissolve render identically in preview and export; captions burn in
(top/bottom) and export as SRT/VTT.

**Smart tools** — scene auto-split slices a clip at detected cuts; beat snap
aligns the playhead to detected music beats; close-gaps / merge / ripple
delete keep the timeline tight; timeline stats in one click.

**Media library** — every import is indexed (path, kind, duration, geometry,
tags). The bin search falls back to library hits so removed files come back
with one click. Index any local folder as a b-roll pool.

**Delivery** — preview_720p, full_1080p, square, vertical, youtube_1080p,
youtube_4k, cinema_24, shorts. Exports are queued and rendered in a
background thread with aspect-aware centre-cropping — the UI never blocks.

**Persistence** — atomic project saves plus rotating autosave snapshots with
microsecond stamps (rapid consecutive saves never overwrite each other).

**Themes** — neon (default), midnight, sunset and a true light **daylight** palette, switchable in-app and persisted to `~/.vidmaker2000/theme.json`.

## Keyboard

Full map lives in `keymap.py` — every binding is remappable at runtime via
`keymap.remap(action, key)` and restored with `keymap.reset()`.

| Key | Action | Key | Action |
|-----|--------|-----|--------|
| `Space` | Play / pause | `J` / `L` | Shuttle ±2s |
| `K` | Pause | `←` / `→` | Step ±0.5s |
| `,` / `.` | Frame step | `I` / `O` | Trim in / out |
| `S` | Split at playhead | `D` | Duplicate clip |
| `B` | Drop marker | `↑` / `↓` | Prev / next marker |
| `[` / `]` | Cycle fade in / out | `Del` | Remove clip |
| `G` | Go-to timecode | `P` | Snapshot frame PNG |
| `Ctrl+C` / `Ctrl+V` | Copy / paste grade | | |
| `E` | Queue export | `Ctrl+S` | Save |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo | `M` | Mute |
| `R` | Reset grade | `+` / `-` | Zoom timeline |

Shortcuts never hijack typing — while a text field is focused, plain letter
keys go to the field.

## Architecture

```
app.py               Flet UI: transport, panels, bin, keyboard, render worker
video_processor.py   frame-accurate OpenCV pipeline (grade + FX + LUT + transitions)
timeline.py          Clip / Timeline / TimelineSet model with undo
timeline_ops.py      ripple delete, gap closing, merge, stats
filters.py           vignette / blur / sharpen / pixelate / glitch / grain / chromatic / scanlines
lut.py               curve-based LUT engine (film, punch, night, fade, neutral)
transitions.py       crossfade / dip / wipe / slide / zoom dissolve
captions.py          burn-in text + SRT/VTT export & import
effects_rack.py      one-click look presets
scene_detect.py      fingerprint-based scene change detection
beat_detect.py       WAV energy-envelope beat detection + snapping
broll.py             folder indexing + token-scored shot suggestions
media_index.py       SQLite media library (searchable, tagged)
keymap.py            single source of truth for shortcuts
shortcuts.py         grouped shortcut registry + cheat-sheet text
autosave.py          atomic timestamped snapshots with rotation
project_store.py     project save / load / validation
render_queue.py      FIFO export queue (background worker)
proxy_cache.py       540p viewing proxies for big media
export.py            delivery presets + transition-aware renderer
preview_player.py    FPS playback engine with speed + loop
histogram.py         RGB histogram, luma waveform, parade
thumbnails.py        cached filmstrip contact sheets
audio_wave.py        mute/speed-aware audio strips
themes.py            neon / midnight / charcoal palettes
timeline_view.py     clip card components
utils.py             timecode, clamping, formatting helpers
```

## Testing

```bash
python -m pytest tests/ -q
```

`tests/test_pipeline.py` covers the pure media modules; `tests/test_modules_contract.py`
locks the public API of every module so refactors stay honest.

## Deploy (Render / any container)

```
web: python app.py
```

When a `PORT` env var is present the app starts in ASGI mode: a small
FastAPI front serves the favicon set (`/favicon.ico`, `/favicon.svg`,
`/apple-touch-icon.png`) and mounts the Flet app behind it. Single instance
only — sessions live in memory.

## Branding

`assets/` holds the identity: `favicon.svg` (master), `favicon.ico`
(16→256), `favicon-256.png` and `apple-touch-icon.png`, all rendered from
the orange→violet gradient badge with the white play mark. The boot splash
and in-app header reuse the same mark.
