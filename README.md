# vidmaker2000

A browser video editor built with Flet + OpenCV. Neon aesthetic, multi-timeline, per-frame grading.

## Features

- **Import**: drag-and-drop mp4/mov/webm/avi + png/jpg/webp images (up to 200MB)
- **Timeline**: multi-timeline tabs, trim in/out, split, reorder, duplicate, undo/redo
- **Grade**: exposure, brightness, contrast, saturation, temperature, tint, highlights, shadows
- **Effects**: vignette, blur, sharpen, pixelate, glitch, grain, chromatic aberration, scanlines
- **Transitions**: crossfade, wipe, dip-to-black, slide, zoom dissolve between clips
- **Captions**: burn text overlays onto clips
- **Looks**: one-click presets (noir, vhs, warm, cool, punch, film, dream, retro, glitchy)
- **Scopes**: RGB histogram, luma waveform, RGB parade
- **Export**: 720p, 1080p, square, vertical presets with transition-aware rendering
- **Autosave**: rolling backup every save
- **Keyboard**: full shortcut support (JKL shuttle, IO trims, split, undo)
- **Zoom**: timeline card zoom for precision editing

## Run

```
pip install -r requirements.txt
python app.py
```

Opens at http://localhost:8550

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play / Pause |
| J | Shuttle left |
| K | Pause |
| L | Shuttle right |
| I | Set trim in |
| O | Set trim out |
| S | Split at playhead |
| D | Duplicate clip |
| E | Export MP4 |
| M | Toggle mute |
| R | Reset grade |
| Delete | Remove clip |
| Ctrl+S | Save project |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| +/- | Zoom timeline |

## Architecture

```
app.py              Flet UI, transport, sliders, timeline view
video_processor.py  frame-accurate OpenCV pipeline + grade + transitions
timeline.py         clip + timeline model with undo
filters.py          vignette / blur / sharpen / pixelate / glitch / grain / chromatic / scanlines
transitions.py      crossfade / wipe / dip / slide / zoom
captions.py         text overlay burn-in
effects_rack.py     one-click look presets
project_store.py    save / load / autosave with atomic writes
export.py           presets, transitions, progress
captions.py         text overlays
audio_wave.py       waveform visualization
thumbnails.py       filmstrip contact sheet with cache
histogram.py        RGB histogram + luma waveform + RGB parade
preview_player.py   FPS playback engine with speed + loop
timeline_view.py    clip card components
shortcuts.py        keyboard shortcut definitions
themes.py           neon / midnight / charcoal palettes
utils.py            timecode, clamp, helpers
```

## Deploy (Render)

```
web: uvicorn app:app --host 0.0.0.0 --port $PORT
```
Single instance only (Flet sessions in memory).
