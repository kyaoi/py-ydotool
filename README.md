# py-ydotool

A small Python wrapper around `ydotool` for Linux desktop automation.

`py-ydotool` is intentionally narrow in scope:

- explicit keyboard helpers
- explicit mouse helpers
- clipboard helpers with backend auto-detection
- predictable failures instead of hidden retries or magic behavior

It does **not** try to be a full PyAutoGUI replacement. The goal is to keep the API small, readable, and friendly to Wayland-oriented setups that already use `ydotool`.

## Features

- keyboard input helpers
- mouse click, repeat-click, button press, and drag helpers
- extended mouse button constants
- broad key constant coverage including media, power, keypad, and IME-related keys
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

## Basic usage

### Type text and press keys

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()
gui.write("hello")
gui.press(Key.ENTER)
gui.hotkey(Key.CTRL, Key.L)
```

### Use key constants directly

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()
gui.press_many([Key.J, Key.L, Key.T, Key.ENTER], interval=0.2)
```

`Key.A`, `Key.ENTER`, `Key.LEFT_CTRL`, and similar values are **keycode constants**.
They are useful when you want to express physical key presses such as `Ctrl+A`, navigation keys, function keys, or media keys.

### Clipboard-aware text input

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool()
gui.type_or_paste("short ascii text")
gui.paste_text("longer text that is safer to paste")
```

By default, clipboard backends are detected in this order:

1. `wl-clipboard`
2. `xclip`
3. `xsel`

You can also pin a backend explicitly:

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool(clipboard_backend="wl-clipboard")
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

### Mouse helpers

```python
from py_ydotool import MouseButton, PyYDoTool

gui = PyYDoTool()

gui.click()
gui.right_click()
gui.double_click_at(400, 220)
gui.drag_between(500, 300, 700, 300)
gui.click_many(MouseButton.LEFT, repeat=3, next_delay_ms=100)
```

### Timeouts and failure handling

```python
from py_ydotool import CommandTimeoutError, PyYDoTool

gui = PyYDoTool(command_timeout=2.0)

try:
    gui.get_clipboard()
except CommandTimeoutError:
    print("clipboard backend timed out")
```

## Key constants

The package includes a broad set of key constants, including:

- letters: `Key.A` … `Key.Z`
- top-row digits: `Key.NUM_0` … `Key.NUM_9`
- keypad digits and operations: `Key.KP_0` … `Key.KP_PLUS`
- modifiers: `Key.LEFT_CTRL`, `Key.RIGHT_CTRL`, `Key.SHIFT`, `Key.ALT`, `Key.META`
- arrows and navigation: `Key.UP`, `Key.DOWN`, `Key.HOME`, `Key.END`
- function keys: `Key.F1` … `Key.F12`
- media / power / IME keys such as `Key.VOLUMEUP`, `Key.POWER`, `Key.HENKAN`

For everyday code, the aliases `Key.CTRL`, `Key.SHIFT`, `Key.ALT`, and `Key.META` point to the left-side variants.

## Versioning and release workflow

The source of truth for the package version is:

```text
src/py_ydotool/VERSION
```

The package exports `__version__` by reading that file at runtime, and repository tooling checks that it stays in sync with `pyproject.toml` and Git release tags.

Useful commands:

```bash
just version
just version-check
just set-version 0.1.1
just release-version 0.1.1
just tag-version
```

Recommended workflow:

### Bump and tag in one step

```bash
just release-version 0.1.1
```

This will:

1. update `src/py_ydotool/VERSION`
2. update `pyproject.toml`
3. create a version bump commit
4. create the matching tag

### Bump manually

```bash
just set-version 0.1.1
git add src/py_ydotool/VERSION pyproject.toml
git commit -m "chore: bump version to 0.1.1"
just tag-version
```

`just tag-version` now refuses to run when the working tree is dirty. This prevents tagging a commit that does not actually contain the version bump.

`just release-check` runs before push through Lefthook. It will fail when:

- `src/py_ydotool/VERSION` and `pyproject.toml` disagree
- `HEAD` has a release tag that does not match the package version
- there are commits after the latest release tag but the package version was not bumped

The version-related `just` commands also run with `PYTHONDONTWRITEBYTECODE=1`, so they do not create fresh `__pycache__` files while you are doing version management.

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
