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

## Requirements

This library is intended for Linux environments and requires:

- `ydotool`
- `ydotoold`

For clipboard support, one of the following is required:

- `wl-copy` / `wl-paste` from `wl-clipboard`
- `xclip`
- `xsel`

## Installation

### From GitHub

```bash
pip install "py-ydotool @ git+https://github.com/kyaoi/py-ydotool.git"
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
