# Keyboard reference

Every binding below is the default. The live map lives in `keymap.py`; the
descriptions live in `shortcuts.py`. Run
`python -c "import shortcuts; print(shortcuts.help_text())"` to print the
sheet that matches the running code.

## Playback

| Key | Action |
| --- | --- |
| `space` | Play / pause the preview |
| `k` | Pause |
| `left` / `right` | Step back / forward half a second |
| `j` / `l` | Jump back / forward two seconds |
| `,` / `.` | Step one frame back / forward |
| `shift+j` / `shift+l` | Slower / faster playback (0.25x – 2x) |

## Editing

| Key | Action |
| --- | --- |
| `i` / `o` | Trim in / out the clip under the playhead |
| `s` | Split at the playhead |
| `d` | Duplicate the selected clip |
| `delete` / `backspace` | Remove the selected clip |
| `[` / `]` | Cycle fade-in / fade-out on the selected clip |
| `ctrl+z` / `ctrl+y` | Undo / redo |
| `ctrl+s` | Save the project (writes an autosave snapshot too) |
| `ctrl+c` / `ctrl+v` | Copy / paste the whole grade between clips |

## Markers

| Key | Action |
| --- | --- |
| `b` | Drop a marker at the playhead |
| `up` / `down` | Jump to the previous / next marker |

## Project and grade

| Key | Action |
| --- | --- |
| `e` | Queue an export of the current timeline |
| `g` | Focus the go-to-timecode field (accepts `90`, `1m30`, `MM:SS`) |
| `p` | Save the current frame as a PNG |
| `m` | Toggle mute |
| `r` | Reset the grade |
| `+` / `-` | Zoom the timeline in / out |

## Notes

* Bindings are matched lowercase; the handler lowercases the incoming key and
  normalises `ctrl` combos to `ctrl+<key>`.
* `keymap.remap("split", "b")` rebinds at runtime, and `keymap.reset()`
  restores the defaults.
* While typing in a text field the handler ignores plain letter keys, so
  captions, paths and search behave normally.
