# py-ydotool

A small Python wrapper around `ydotool` for Wayland automation.

## Features

- keyboard input helpers
- mouse click, repeat-click, button press, and drag helpers
- extended mouse button constants
- clipboard helpers with backend auto-detection
- simple Python API for personal automation scripts
- context managers for holding keys and mouse buttons

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

## Example

```python
from py_ydotool import MouseButton, PyYDoTool

gui = PyYDoTool()
gui.click_many(3, next_delay_ms=50)
gui.forward_click()
gui.mouse_down(MouseButton.LEFT)
gui.move_rel(100, 0)
gui.mouse_up(MouseButton.LEFT)
```

## Status

Early personal project. APIs may change.
