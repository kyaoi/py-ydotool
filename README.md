# py-ydotool

A small Python wrapper around `ydotool` for Wayland automation.

## Features

- keyboard input helpers
- mouse click, repeat-click, button press, and drag helpers
- extended mouse button constants
- broad key constant coverage including media, power, and IME-related keys
- clipboard helpers with backend auto-detection
- context managers for holding keys and mouse buttons
- configurable command timeout for safer automation
- file-based version management with pre-push release checks

## Requirements

This library is intended for Linux environments and requires:

- `ydotool`
- `ydotoold`

For clipboard support, one of the following is required:

- `wl-copy` / `wl-paste` from `wl-clipboard`
- `xclip`
- `xsel`

## Installation

### From GitHub with pip

```bash
pip install "py-ydotool @ git+https://github.com/kyaoi/py-ydotool.git"
```

### From GitHub with uv

```bash
uv add "py-ydotool @ git+https://github.com/kyaoi/py-ydotool.git"
```

### Development

```bash
uv sync
```

## Quick examples

### Type and hotkeys

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()
gui.write("hello")
gui.press(Key.ENTER)
gui.hotkey(Key.CTRL, Key.L)
```

### Clipboard and paste fallback

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool(clipboard_backend="wl-clipboard")
gui.type_or_paste("a short string")
gui.paste_text("long text that is safer to paste")
```

### Hold keys and mouse buttons

```python
from py_ydotool import Key, MouseButton, PyYDoTool

gui = PyYDoTool()

with gui.hold_keys(Key.CTRL, Key.SHIFT):
    gui.press(Key.T)

with gui.hold_button(MouseButton.LEFT):
    gui.move_rel(120, 0)
```

### Coordinate helpers

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool()
gui.click_at(300, 200)
gui.double_click_at(400, 220)
gui.drag_between(500, 300, 700, 300)
```

### Safety timeout

```python
from py_ydotool import CommandTimeoutError, PyYDoTool

gui = PyYDoTool(command_timeout=2.0)

try:
    gui.get_clipboard()
except CommandTimeoutError:
    print("clipboard backend timed out")
```

## Versioning

The source of truth for the package version is:

```text
src/py_ydotool/VERSION
```

The package exports `__version__` by reading that file at runtime, and the repository checks that it stays in sync with `pyproject.toml` and Git release tags.

Useful commands:

```bash
just version
just version-check
just set-version 0.1.1
just tag-version
```

`just release-check` runs before push through Lefthook. It will fail when:

- `src/py_ydotool/VERSION` and `pyproject.toml` disagree
- `HEAD` has a release tag that does not match the package version
- there are commits after the latest release tag but the package version was not bumped

## Public API

Top-level exports are:

- `PyYDoTool`
- `Key`
- `MouseButton`
- `ClipboardBackend`
- `detect_clipboard_backend`
- `PyYDoToolError`
- `CommandNotFoundError`
- `CommandExecutionError`
- `CommandTimeoutError`
- `ClipboardUnavailableError`
- `__version__`

## Unsupported / intentionally missing

These are intentionally not implemented right now:

- `position()`
- scroll helpers
- image recognition / screen search

The library stays focused on explicit keyboard, mouse, and clipboard automation built on top of `ydotool`.

## Status

Early personal project. APIs may change.

## License

MIT
