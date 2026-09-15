# Keyboard reference

Every binding below is the default. The live map lives in `keymap.py`; the
descriptions live in `shortcuts.py`. Run `python -c "import shortcuts; print(shortcuts.help_text())"`
to print the sheet that matches the running code.

## Playback

| Key | Action |
| --- | --- |
| `space` | Play / pause the preview |
| `left` | Step back half a second |
| `right` | Step forward half a second |
| `j` | Jump back two seconds |
| `l` | Jump forward two seconds |

## Editing

| Key | Action |
| --- | --- |
| `i` | Trim in the clip under the playhead |
| `o` | Trim out the clip under the playhead |
| `s` | Split at the playhead |
| `d` | Duplicate the selected clip |
| `delete` / `backspace` | Remove the selected clip |
| `ctrl+z` | Undo |
| `ctrl+y` | Redo |

## Grade and view

| Key | Action |
| --- | --- |
| `m` | Toggle mute |
| `r` | Reset the grade |
| `+` / `-` | Zoom the timeline in / out |
| `e` | Export the current timeline |

## Notes

* Bindings are matched lowercase; the handler lowercases the incoming key.
* `keymap.remap("split", "b")` rebinds at runtime, and `keymap.reset()` restores
  the defaults.
* Jimbibo's own typing automation must never be interrupted by these keys; the
  editor taps it sends are filtered by `editor.suppress_esc`.
