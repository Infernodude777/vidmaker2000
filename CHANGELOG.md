# Changelog

## v2.5 — CapCut-style polish

- text styling engine: per-clip caption presets (minimal, subtitle box,
  title, neon, pop, brand) with color, size, position and translucent
  background box; rendered in preview and export
- GIF export: looping 8-second GIF of the timeline with grades, transitions
  and captions baked in (EXPORT GIF button)
- title-card generator: type a title + subtitle, MAKE OPENER builds a branded
  opener image and adds it to the timeline
- live render-queue panel with per-job state icons, CLEAR DONE action
- background autosave loop: crash-protection snapshot every 60s when the
  project changed (separate from the manual-save snapshots)
- richer bin rows (resolution + duration), clip badges for speed / fades /
  motion, caption center position
- tests grew to 25 (caption styles, GIF export, text-style persistence)

# Changelog

## v2.4 — nested timelines, motion and speed

- nested sequences: collapse an entire timeline into a single clip on another
  tab (NEST button); renders recursively in export and preview, persists in
  projects, guarded against self-nesting
- per-clip playback speed 0.5x-4x (SPEED button) — export advances source
  frames faster/slower, preview resolves accordingly
- Ken Burns motion for stills: zoom in/out, pan left/right presets, applied
  in both preview and export
- grade copy/paste (Ctrl+C / Ctrl+V) transfers the whole look between clips
- theme-aware dynamic UI: bin rows, cards, chips, markers and dividers now
  recolor under every theme (daylight light mode fully supported)
- fixes: undefined frame_bgr in captions.draw_timecode, dead imports across
  10 modules, broken Procfile reference kept fixed, pyflakes-clean codebase
- tests grew to 22 (nested roundtrip + export, Ken Burns motion, clip speed,
  marker persistence), contract updated for new APIs

# Changelog

## v2.3 — markers, fades and craft tools

- timeline markers: colored flags with notes, B to drop, Up/Down to jump,
  click to seek; stored in projects and autosave
- per-clip fade-in/fade-out from black, rendered in preview AND export
  (cycled with [ and ], 0.25s-3s)
- frame-accurate stepping (, / .) and go-to timecode (G) accepting 90,
  1m30 or MM:SS; time display toggles TC <-> seconds
- snapshot (P): saves the current graded frame as a PNG
- playback rate cycling 0.25x-2x (Shift+J / Shift+L)
- duplicate-to-new-timeline copies clips + markers to a fresh tab
- theme picker wired to themes.py with persistence; new daylight (light)
  palette; live recolor of header and panels
- keyboard map grew to 28 conflict-checked bindings; docs updated

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
