import flet as ft

Icons = getattr(ft, "Icons", getattr(ft, "icons", None))
EButton = getattr(ft, "ElevatedButton", None) or getattr(ft, "FilledButton", None) or ft.Button
Fit = getattr(ft, "BoxFit", getattr(ft, "ImageFit", None))


def clip_card(name, dur, active, on_tap, kind="video", on_delete=None,
             on_left=None, on_right=None, on_dup=None, width=None):
    tag = "IMG" if (kind or "video") == "image" else "VID"
    btns = []
    if on_left:
        btns.append(ft.IconButton(Icons.CHEVRON_LEFT, icon_size=14, icon_color="#a7a9be",
                                  tooltip="move left", on_click=lambda e: on_left()))
    if on_right:
        btns.append(ft.IconButton(Icons.CHEVRON_RIGHT, icon_size=14, icon_color="#a7a9be",
                                  tooltip="move right", on_click=lambda e: on_right()))
    if on_dup:
        btns.append(ft.IconButton(Icons.CONTENT_COPY, icon_size=14, icon_color="#a7a9be",
                                  tooltip="duplicate", on_click=lambda e: on_dup()))
    if on_delete:
        btns.append(ft.IconButton(Icons.CLOSE, icon_size=14, icon_color="#ff8906",
                                  tooltip="remove", on_click=lambda e: on_delete()))
    return ft.Container(
        content=ft.Column([
            ft.Text(f"{tag} {name[:14]}", size=11, color="white", weight="bold"),
            ft.Text(f"{dur:.1f}s", size=10, color="#a7a9be"),
            ft.Row(btns, spacing=0, tight=True),
        ], spacing=2, tight=True),
        width=width or max(90, int(dur * 24)),
        height=68,
        bgcolor="#7f5af0" if active else "#2a2740",
        border_radius=10,
        padding=8,
        on_click=lambda e: on_tap(),
    )


def empty_timeline(on_open):
    return ft.Container(
        content=ft.Column([
            ft.Text("No clips yet - open a video to start cutting", color="#a7a9be"),
            EButton("OPEN VIDEO", on_click=lambda e: on_open()),
        ], tight=True),
        padding=16,
        bgcolor="#191827",
        border_radius=12,
    )
