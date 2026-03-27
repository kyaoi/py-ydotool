# py-ydotool

A small Python wrapper around `ydotool` for Wayland automation.

## Features

* keyboard input helpers
* mouse click helpers
* clipboard helpers
* simple Python API for personal automation scripts

## Requirements

This library is intended for Linux Wayland environments and expects:

* `ydotool`
* `ydotoold`
* `wl-copy` / `wl-paste` for clipboard support

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
from py_ydotool import PyYDoTool, Key

gui = PyYDoTool()
gui.type("hello")
gui.press(Key.ENTER)
```

## Status

Early personal project. APIs may change.
