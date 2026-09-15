# Changelog

## v2.2 — polish, branding and hosting

- favicon set rendered from a new gradient play-mark: `favicon.svg`,
  `favicon.ico` (16→256), `favicon-256.png`, `apple-touch-icon.png`
- hosted mode: a FastAPI front serves brand assets and mounts the Flet app
  (PORT-aware); Procfile fixed — it referenced a nonexistent `app:app`
- header: logo mark, two-tone VIDMAKER2000 title, live version/preset/
  play-state chips, gradient background
- boot splash rebuilt around the brand mark with a feature list
- keyboard: `K` pause and `Ctrl+S` save added; shortcuts no longer hijack
  typing while a text field is focused
- `keymap`, `shortcuts` registry and `docs/KEYBOARD.md` kept in sync
  (19 bindings, conflict-checked)
- README rewritten: badges, feature deep-dives, testing and deploy sections

# Changelog

## v2.1 — integration release (hand-applied)

- app.py: all 11 v2 modules wired in — keymap-driven shortcuts, autosave
  snapshots on save, media library index (search + one-click re-add from
  indexed hits), b-roll folder indexing, timeline ops (close gaps / merge /
  ripple delete / stats), scene auto-split, beat snap, LUT panel, and
  background render-queue exports (UI no longer blocks on EXPORT MP4)
- export: delivery profiles (youtube_4k, youtube_1080p, cinema_24, shorts)
  merged into presets; aspect-aware centre-crop instead of squash
- video_processor: Grade.lut applied in the grade pipeline (preview + export)
- render_queue: fixed jobs truncating at chunk size; full renders now
- autosave: microsecond stamps — same-second snapshots no longer overwrite
- timeline: Grade.lut persisted in save/load
- cleanup: removed plan/scaffolding files (gen_*.py, launch_*.py, *.plan.json)

# Changelog - vidmaker2000

## 0.2.0 - video cut phase
- transitions: fade / wipe / dip
- captions: lower-third + title
- audio strip (mute-aware placeholder)
- thumbnails contact sheet
- themes: neon / midnight / sunset
- preview player with speed
- effects rack one-click looks

## 0.1.0 - rough base
- Flet video UI, OpenCV grade pipeline, trim/split/export

## 7h session - polish pass
- themes: neon_tangerine / midnight_violet / charcoal_mint
- transitions: cut / crossfade / dip_black / dip_white / wipe_left
- captions: bottom bar + title card burn-in
- audio_wave: peak buckets for fast draw
- thumbnails: filmstrip rail + single thumb
- filters: grain / chromatic / scanlines
- utils: format_bytes / clamp_loop / safe_name
- shortcuts: space/J/L/I/O/S + ctrl save/open/export
- export: 720p / 1080p / square / vertical presets

## 0.3.0 - major upgrade

### Playback
- Real-time playback engine (threaded, fps-accurate)
- JKL shuttle + full keyboard shortcut system
- Loop control, speed via grade.speed

### Effects
- Grain, chromatic aberration, scanlines sliders
- 10 one-click looks: noir, vhs, warm, cool, punch, film, dream, retro, glitchy
- New filters wired into grade pipeline

### Transitions
- Crossfade, wipe, dip-to-black, slide-left, zoom-dissolve
- Per-clip transition selection
- Transitions rendered in both preview and export

### Export
- Named presets: 720p, 1080p, square, vertical
- Transition-aware export rendering
- Progress reporting + cancel support
- Caption burn-in during export

### Project
- Atomic saves with .bak rotation
- Rolling autosave backup
- Media bin ghost file purging
- Project statistics on save

### UI
- Timeline zoom (cards scale with px-per-sec)
- Filmstrip thumbnail cards (cached)
- Scope toggle: histogram / RGB parade
- Waveform audio visualization
- Caption input per clip
- Undo / redo (60-level stack)
- Duplicate clip button

### Scopes
- RGB histogram strip
- Luma waveform
- RGB parade (three-band)

### Docs
- Full keyboard shortcuts table in README
- Expanded user guide
- Architecture diagram

## 0.2.0 - video cut phase
- transitions: fade / wipe / dip
- captions: lower-third + title
- audio strip (mute-aware placeholder)
- thumbnails contact sheet
- themes: neon / midnight / sunset
- preview player with speed
- effects rack one-click looks

## 0.1.0 - rough base
- Flet video UI, OpenCV grade pipeline, trim/split/export
## 0.4.0 - automation-safe editing stack

- new modules: `keymap`, `autosave`, `render_queue`, `proxy_cache`,
  `scene_detect`, `beat_detect`, `timeline_ops`, `lut`, `profiles`, `broll`,
  `media_index`
- timeline: ripple delete, insert at index, nudge, gap close, merge and stats
  helpers usable from the CLI and tests
- scopes: vectorscope plus a unified `scope_strip` entry point
- transitions: `flash`, `push_up`, `whip_pan`, `glitch_cut` added to the set
- captions: word wrap, SRT/VTT export and import, caption track model
- thumbnails and audio strips now cache to disk and fall back gracefully
- delivery: manifest v2 with sha256 and byte counts, plus `export_bundle`
- tests: pytest coverage for the pure pipeline modules and an API contract suite
- docs: `docs/KEYBOARD.md`
