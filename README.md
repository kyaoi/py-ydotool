# py-ydotool

A small Python wrapper around `ydotool` for Linux desktop automation.

`py-ydotool` is intentionally narrow in scope:

- explicit keyboard helpers
- explicit mouse helpers
- clipboard helpers with backend auto-detection
- predictable failures instead of hidden retries or magic behavior
- optional `ydotoold` lifecycle helpers when you want this library to start and stop the daemon for you

It does **not** try to be a full PyAutoGUI replacement. The goal is to keep the API small, readable, and friendly to Wayland-oriented setups that already use `ydotool`.

## Features

- keyboard input helpers
- mouse click, repeat-click, button press, and drag helpers
- extended mouse button constants
- broad key constant coverage including media, power, keypad, and IME-related keys
- clipboard helpers with backend auto-detection
- context managers for holding keys and mouse buttons
- configurable command timeout for safer automation
- optional daemon lifecycle helper usable as both a context manager and a decorator
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

### Opt-in integration tests

The regular test suite is fast and mock-based.
For real `ydotoold` lifecycle coverage, there is also an opt-in integration test module that starts a real daemon on a temporary socket.

```bash
just test-integration
```

This requires:

- Linux
- `ydotool` and `ydotoold` in `PATH`
- read/write access to `/dev/uinput`

If those prerequisites are missing, the integration tests skip themselves with a short reason.

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

### Start and stop `ydotoold` automatically

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()

with gui.daemon():
    gui.write("hello")
    gui.press(Key.ENTER)
```

`with ...:` uses a **context manager**.
If `ydotoold` is already running on the configured socket, `py-ydotool` reuses it and leaves it running.
If it starts the daemon itself, it stops that daemon automatically when the block exits.

The same helper can also be used as a **decorator** with `@...`:

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()

@gui.daemon()
def type_hello() -> None:
    gui.write("hello")
    gui.press(Key.ENTER)
```

If you prefer manual control, you can keep the manager object and call `start()` / `stop()` yourself:

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool()
daemon = gui.daemon()
daemon.start()
try:
    gui.write("hello")
finally:
    daemon.stop()
```

By default, `gui.daemon()` starts `ydotoold --socket-path <socket>`.
Readiness is checked by running `ydotool debug` against that socket, so custom
socket paths are validated using the actual `ydotool` client instead of a raw
Python socket probe.
If your setup needs additional flags such as `--socket-own`, pass them via `extra_args`.

Before starting its own daemon, the helper also removes a stale Unix socket file at that path when all of the following are true:

- the socket is not currently accepting connections
- the path exists
- the path is actually a socket file

This helps after crashes where `ydotoold` is gone but the old socket pathname remains.
If you do not want that behavior, pass `clean_stale_socket=False`.

`py-ydotool` can manage the daemon lifecycle for you, but it still cannot bypass system permissions.
If `ydotoold` cannot open `/dev/uinput`, create the socket, or access the requested ownership settings,
startup will still fail and the exception now includes any captured `stderr` output from `ydotoold` when available.

For most scripts, `with gui.daemon():` is the safest pattern.
If you call `start()` manually, `py-ydotool` also registers a best-effort `atexit` cleanup for daemons it started itself,
so forgotten `stop()` calls are less likely to leave an extra helper process behind.

### Daemon-specific exceptions

The daemon helper raises more specific exceptions when `ydotoold` startup fails:

- `DaemonStartError`: `ydotoold` exited before the socket became ready
- `DaemonReadyTimeoutError`: `ydotoold` did not become ready before the timeout

These stay backward-compatible with the broader command exceptions:

- `DaemonStartError` is also a `CommandExecutionError`
- `DaemonReadyTimeoutError` is also a `CommandTimeoutError`

```python
from py_ydotool import (
    DaemonReadyTimeoutError,
    DaemonStartError,
    PyYDoTool,
)

gui = PyYDoTool()

try:
    with gui.daemon(ready_timeout=2.0):
        gui.write("hello")
except DaemonStartError:
    print("ydotoold exited early")
except DaemonReadyTimeoutError:
    print("ydotoold did not become ready in time")
```

### Choosing between a long-running daemon and `gui.daemon()`

There are two common ways to work with `ydotoold`:

- **Long-running daemon**: start `ydotoold` yourself, for example from a login shell, user service, or system configuration.
  This is a good fit when you use `ydotool` often and want one shared socket that stays available across many scripts.
- **Library-managed daemon**: use `with gui.daemon():` or `@gui.daemon()` and let `py-ydotool` manage a temporary daemon for a single script or function call.
  This is a good fit for small automation scripts, tests, and one-shot tools that should clean up after themselves.

A good rule of thumb is:

- prefer a **long-running daemon** for frequent daily use or when multiple tools share the same socket
- prefer **`gui.daemon()`** for self-contained scripts where setup and cleanup should happen automatically

If you already have a long-running daemon on the configured socket, `gui.daemon()` simply reuses it and does not stop it on exit.
When `py-ydotool` owns the daemon process, it also removes the owned socket path on clean shutdown if it is no longer serving requests.


#### Quick chooser

| Pattern | Good fit |
|---|---|
| Long-running `ydotoold` | You use `ydotool` regularly and want one shared socket for many scripts or tools. |
| `with gui.daemon():` | You want setup and cleanup to happen automatically for one script block. |
| `@gui.daemon()` | You want the same automatic lifecycle, but attached to one function call. |
| Manual `start()` / `stop()` | You need finer control over exactly when the daemon starts and stops. |

#### Ownership rules

The daemon helper is intentionally conservative about shutdown:

- if a daemon is already running on the configured socket, `gui.daemon()` reuses it
- reused daemons are **not** stopped when the helper exits
- only daemons started by `py-ydotool` itself are stopped automatically
- when `py-ydotool` owns the daemon, it also removes the owned socket path on clean shutdown if it is no longer serving requests

This makes `gui.daemon()` safe to use even when another service or login hook already manages `ydotoold` for the whole session.

#### Troubleshooting daemon startup

A few environment issues are common when working with `ydotoold`:

- **`/dev/uinput` permissions**: `ydotoold` needs read/write access to `/dev/uinput`. If that device cannot be opened, daemon startup and integration tests will fail.
- **`sudo` and `PATH`**: if you run integration tests with `sudo`, preserve `PATH` so `ydotool` and `ydotoold` stay discoverable. For example: `sudo env "PATH=$PATH" PY_YDOTOOL_RUN_INTEGRATION=1 uv run pytest -m integration -rs`
- **stale socket files**: if `ydotoold` crashed previously, the old Unix socket pathname may remain. `gui.daemon()` removes a stale socket file automatically by default before starting its own daemon.
- **custom socket paths**: readiness is checked against the configured socket path by using the actual `ydotool` client, so custom socket paths are supported, but the daemon still must be able to create and serve that socket.

When startup fails, prefer catching `DaemonStartError` or `DaemonReadyTimeoutError` first. Those exceptions include daemon-specific context and, when available, captured `stderr` from `ydotoold`.

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

# ydotoold lifecycle helpers also expose more specific daemon errors
# while remaining compatible with the broader command error types.
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
- `YDoToolDaemon`
- `Key`
- `MouseButton`
- `ClipboardBackend`
- `detect_clipboard_backend`
- `PyYDoToolError`
- `CommandNotFoundError`
- `CommandExecutionError`
- `CommandTimeoutError`
- `DaemonError`
- `DaemonStartError`
- `DaemonReadyTimeoutError`
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


## Versioning workflow

- `just set-version 0.1.2` updates `src/py_ydotool/VERSION`, `pyproject.toml`, and refreshes `uv.lock`.
- `just tag-version` requires a clean working tree and will refuse to tag if version files are still uncommitted.
- `just release-version 0.1.2` is the recommended path for a release bump because it updates version files, commits `VERSION` / `pyproject.toml` / `uv.lock`, and then creates the matching tag.
