# vidmaker2000 - User Guide

## Getting Started

1. Run `python app.py` and open http://localhost:8550
2. Click **IMPORT MEDIA** to add video/image files
3. Files appear in the MEDIA BIN (left panel) and auto-add to the active timeline
4. Click a clip card to select it, or use JKL keys to shuttle

## Timeline

- **Scrub** the timeline slider to move the playhead
- **Trim In** (I key): set the in-point at playhead
- **Trim Out** (O key): set the out-point at playhead
- **Split** (S key): split selected clip at playhead
- **Duplicate** (D key): duplicate selected clip
- **Delete** (Delete/Backspace): remove selected clip
- **Move Left/Right**: reorder clips on the timeline
- **Zoom** (+/- keys): scale timeline card widths

## Grading

Use the right panel sliders:

- **Exposure**: overall brightness via log scale
- **Brightness**: linear offset
- **Contrast**: center-point contrast stretch
- **Saturation**: color intensity
- **Temperature**: warm/cool shift
- **Tint**: green/magenta shift
- **Highlights/Shadows**: targeted adjustments

### Effects

- **Vignette**: darkened edges
- **Blur / Sharpen**: Gaussian blur or unsharp mask
- **Pixelate**: mosaic effect
- **Glitch**: digital corruption slices
- **Grain**: film grain overlay
- **Chromatic**: RGB channel split
- **Scanlines**: horizontal line darkening

### Looks

Click a look name to apply:
- **Noir**: B&W high contrast
- **VHS**: retro tape degradation
- **Warm / Cool**: temperature shift
- **Punch**: high contrast + saturation
- **Film**: soft grain + low saturation
- **Dream**: soft blur + brightness

## Transitions

Select a clip, then click a transition name in the TRANSITION section:
- **Cut**: instant (default)
- **Crossfade**: blend between clips
- **Dip Black**: fade to black between clips
- **Wipe Left**: horizontal wipe
- **Slide Left**: incoming clip slides over
- **Zoom Dissolve**: scale-blend transition

## Captions

Type text in the Caption field, then click a clip to apply.
Text burns into the video during preview and export.

## Export

1. Click **EXPORT MP4** or press E
2. Choose a preset (720p, 1080p, square, vertical)
3. Export runs in background; status shown in header
4. Output file saved to system temp directory

## Save / Load

- **SAVE**: saves project to ~/vidmaker2000/
- **LOAD**: opens a .vidmaker project file
- Autosave runs on every save

## Scopes

Toggle between Histogram and Parade views in the SCOPE section.
- **Histogram**: RGB distribution
- **Parade**: per-channel waveform

## Tips

- Keep clips under 200MB
- Browser upload works best under 60MB
- For bigger files, paste the local file path
- Single instance only on Render deployment
- Use keyboard shortcuts for speed
- Undo (Ctrl+Z) / Redo (Ctrl+Y) support 60 levels
