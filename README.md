# py-ydotool

A small Python wrapper around `ydotool` for Linux automation, with Wayland-friendly defaults.

## Features

- keyboard input helpers
- mouse click helpers
- clipboard helpers with backend auto-detection
- simple Python API for personal automation scripts

## Requirements

This library requires:

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
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()
gui.write("hello")
gui.press(Key.ENTER)
```

## Status

Early personal project. APIs may change.
