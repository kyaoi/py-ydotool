# py-ydotool

A small Python wrapper around `ydotool` for Linux desktop automation.

`py-ydotool` is intentionally narrow in scope:

- explicit keyboard helpers
- explicit mouse helpers
- clipboard helpers with backend auto-detection
- text input fallback that can paste Unicode text when direct typing is not suitable
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

For high-level text input fallback, clipboard access is also what allows
`type()` / `write()` to paste Unicode text when direct typing is not suitable.

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
just fix
just lint
just test
just check
just ci
```

Recommended flow:

- `just fix`: apply safe Ruff autofixes and formatting
- `just lint`: verify Ruff diagnostics **and** formatting without modifying files
- `just check`: local developer loop (`fix` -> `lint` -> `test`)
- `just ci`: CI-style verification (`lint` -> `test`)

That keeps everyday checks friendly to small Ruff autofixes while still giving CI a pure verification command.

After installation, the package also exposes a small CLI:

- `py-ydotool doctor`
- `py-ydotool setup`
- `py-ydotool type "hello"`
- `py-ydotool press ENTER`
- `py-ydotool click --button right`
- `py-ydotool move 400 220`
- `py-ydotool drag 100 100 400 220`
- `py-ydotool copy "hello" --backend wl-clipboard`
- `py-ydotool paste-text "hello"`
- `python -m py_ydotool doctor`
- `python -m py_ydotool setup`

### Implementation rules for this repo

When changing `py-ydotool`, prefer these guardrails:

- keep public API parameters and return values explicit, even without a separate type checker
- normalize optional values at the boundary instead of carrying `None` deep into helper logic
- reject explicit empty-string config values (for example `socket_path=""`, `group=""`, or `target_user=""`) instead of silently falling back to defaults
- reject invalid public API values early (for example, negative or non-finite timeouts/delays, zero repeats, malformed button codes, non-bool feature flags, or non-int key/coordinate values) instead of letting them fail deep inside subprocess handling
- validate composite mouse helpers before the first side effect so `click_at()`, `drag_to()`, `drag_between()`, and similar wrappers do not partially act before raising on a bad argument
- normalize timeout selection and subprocess invocation through small helpers instead of repeating inline fallback logic across methods
- use concrete file-like, process-like, and path-like types instead of vague `object` parameters or attributes
- use small `TypedDict` payloads for stable JSON/report shapes instead of anonymous `dict[str, object]` return contracts
- prefer small helpers with one responsibility over implicit branching inside long methods
- when daemon or command behavior changes, update both README examples and regression tests in the same patch
- keep backend selection and subprocess execution in separate helpers so clipboard failures stay easy to localize
- keep `monkeypatch` focused on the real boundary under test (`subprocess`, `time`, `os`, backend detection) so tests stay readable during refactors

## Quick start

For most users, the shortest path is:

```bash
py-ydotool doctor
py-ydotool setup --dry-run
py-ydotool setup
py-ydotool doctor
```

Then use the library like this:

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()

with gui.daemon():
    gui.write("hello")
    gui.press(Key.ENTER)
```

`doctor` checks what is missing. `setup` applies the one-time Linux changes needed for normal non-root usage. After that, `with gui.daemon():` starts and stops `ydotoold` for the current script.

If you want to surface the same guidance inside your own Python app, you can also call the diagnostic helpers directly:

```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()
print(gui.doctor_text())
print(gui.setup_plan_text(dry_run=True))

with gui.daemon():
    gui.write("hello")
    gui.press(Key.ENTER)
```

Those methods stay non-destructive by default: `doctor_*` inspects the environment and `setup_plan_*` only previews the one-time Linux changes.

## One-shot CLI input helpers

For quick shell-driven automation, the CLI now also exposes small direct input commands:

```bash
py-ydotool type "hello"
py-ydotool press ENTER
py-ydotool press CTRL V --hotkey
py-ydotool click --button right
py-ydotool move 400 220
py-ydotool move 400 220 --duration 0.4
py-ydotool click-at 400 220 --button right
py-ydotool double-click --button left
py-ydotool drag 100 100 400 220
py-ydotool drag 100 100 400 220 --duration 0.5 --steps 12
py-ydotool copy "hello" --backend wl-clipboard
py-ydotool get-clipboard
py-ydotool paste
py-ydotool paste-text "hello"
py-ydotool type "こんにちは" --text-backend paste --backend wl-clipboard
```

By default these commands use the same daemon helper as the Python API, so short one-shot invocations do not need a separate `ydotoold` bootstrap step. That means the CLI will:

- start `ydotoold` when the requested socket is not already ready
- reuse an already-ready daemon when one is already running on the same socket
- keep a short quiet period after the last input before stopping an owned daemon

Useful options:

- `--no-daemon`: require an already-running daemon instead of auto-starting one
- `--socket-path`: target a custom `ydotoold` socket for commands that talk to `ydotool`
- `--command-timeout`: cap each input command or clipboard subprocess
- `--duration`, `--steps` on `move` / `drag`: use linear interpolation instead of a single immediate pointer jump
- `--ready-timeout`, `--stop-timeout`, `--settle-delay`: tune daemon lifecycle timing for unusual environments
- `py-ydotool press ... --hotkey`: hold all keys together and release them in reverse order
- `py-ydotool move X Y`: treat `X` and `Y` as current-display local absolute coordinates by default
- `py-ydotool move X Y --relative`: treat `X` and `Y` as deltas instead of current-display local absolute coordinates
- `py-ydotool click --button <name>` and related mouse commands: use `left`, `right`, `middle`, `side`, `extra`, `forward`, `back`, or `task`
- `py-ydotool type --text-backend <name>`: force `auto`, `ydotool`, `wtype`, `eitype`, or `paste` for high-level text input
- `py-ydotool copy/get-clipboard/paste-text/type --backend <name>`: force a specific clipboard backend such as `wl-clipboard`, `xclip`, or `xsel` when clipboard-backed paste is involved
- `py-ydotool paste/paste-text/type --paste-shortcut ...`: replace the default `Ctrl+V` hotkey
- `py-ydotool paste-text/type --no-restore-clipboard`: skip clipboard restore after clipboard-backed paste

Key names for `press` are case-insensitive and accept the same constant names as `Key`, so `ENTER`, `CTRL`, `LEFT_SHIFT`, and numeric keycodes all work.

### Clipboard command behavior

The clipboard-related CLI commands have slightly different roles:

- `py-ydotool copy TEXT`: write `TEXT` to the system clipboard only
- `py-ydotool get-clipboard`: print the current clipboard text only
- `py-ydotool paste`: send the configured paste shortcut only; it does not change clipboard contents first
- `py-ydotool paste-text TEXT`: copy `TEXT` with the selected clipboard backend, then send the configured paste shortcut

`copy` and `get-clipboard` do not talk to `ydotoold`, so they do not need `--socket-path` or daemon lifecycle tuning. `type`, `paste`, and `paste-text` can also customize the paste shortcut or force paste fallback from the CLI. When backend auto-detection is not what you want, force one explicitly:

```bash
py-ydotool copy "hello" --backend wl-clipboard
py-ydotool get-clipboard --backend xclip
py-ydotool paste-text "hello" --backend xsel
py-ydotool type "こんにちは" --text-backend wtype
py-ydotool type "こんにちは" --text-backend eitype
py-ydotool type "こんにちは" --text-backend paste --backend wl-clipboard
py-ydotool paste --paste-shortcut SHIFT INSERT
```

### High-level text input behavior

`type()` / `write()` are high-level text input helpers. They prefer direct
typing when a suitable backend is available and can fall back to
clipboard-backed paste when direct Unicode input is unavailable.

Current auto-selection policy:

- ASCII text prefers `ydotool`, then `wtype`, then `eitype`
- non-ASCII / Unicode text prefers `wtype`, then `eitype`
- if no suitable direct backend is available, clipboard-backed paste is used
- if neither direct typing nor clipboard-backed paste is available, `type()` raises an error

Practical backend guidance:

- stay with `auto` unless you are debugging a backend-specific issue
- prefer `wtype` first on Wayland when you want direct Unicode typing
- try `eitype` when your desktop/session exposes it more reliably than `wtype`
- force `paste` when direct typing is not important and you mainly want broad Unicode coverage
- enable `strict_text_timing` when per-character timing matters more than fallback convenience

Important timing contract:

- `type_delay_ms` only applies to direct typing backends
- when paste fallback is selected, the text is inserted atomically
- paste fallback does **not** simulate one-character-at-a-time typing
- set `strict_text_timing=True` (or `--strict-text-timing`) if timing should fail instead of silently falling back to paste

Important clipboard contract:

- `paste_text()` captures and restores the current **text** clipboard by default
- the restore happens after a short `paste_settle_delay` window
- set `restore_clipboard=False` if you prefer speed over clipboard preservation
- set `paste_shortcut=(...)` if your target environment needs something other than `Ctrl+V`

Because paste fallback is still a paste operation, some targets can behave
differently from direct typing. Terminals, Vim, password fields, and unusual UI
widgets may need a different approach.

On Wayland, `wtype` and `eitype` are the preferred direct Unicode backends when
available. `ydotool` remains the default direct backend for simple ASCII typing
and for the broader key / mouse automation API.

### Shell-side press-and-hold sequences

`drag` is the easiest way to express a complete drag in one command. If you instead want to build a shell-side sequence from `mouse-down`, `move`, and `mouse-up`, keep all three commands on the same long-lived daemon/socket. Separate auto-daemon one-shot commands will start and stop their own daemon, so a held button or key will not survive across those restarts.

One workable pattern is:

```bash
ydotoold --socket-path /tmp/py-ydotool-demo.sock &
py-ydotool mouse-down --socket-path /tmp/py-ydotool-demo.sock --no-daemon
py-ydotool move 25 0 --relative --socket-path /tmp/py-ydotool-demo.sock --no-daemon
py-ydotool mouse-up --socket-path /tmp/py-ydotool-demo.sock --no-daemon
```

The same idea applies to longer key-hold or modifier sequences from the shell: reuse one daemon when the pressed state must stay active across multiple commands.

### Common CLI recipes

A few practical shell-side patterns:

```bash
# Hold a modifier combination together.
py-ydotool press CTRL L --hotkey

# Nudge the pointer relative to the current position.
py-ydotool move 25 0 --relative
py-ydotool move 0 25 --relative

# Move more slowly with linear interpolation.
py-ydotool move 400 220 --duration 0.4
py-ydotool move 25 -10 --relative --duration 0.3 --steps 6

# Open a context menu at a specific point.
py-ydotool click-at 640 360 --button right

# Double-click the currently focused target.
py-ydotool double-click

# Drag from one absolute point to another.
py-ydotool drag 100 100 400 220
py-ydotool drag 100 100 400 220 --duration 0.5 --steps 12

# Copy text into the clipboard without touching ydotoold.
py-ydotool copy "hello from py-ydotool" --backend wl-clipboard

# Read clipboard text into a shell variable.
current_clipboard="$(py-ydotool get-clipboard --backend wl-clipboard)"
printf '%s\n' "$current_clipboard"

# Copy text, then send the paste hotkey to the focused app.
py-ydotool paste-text "hello from py-ydotool" --backend wl-clipboard
```

`paste`, `paste-text`, and clipboard-backed `type` use the usual `Ctrl+V` paste
shortcut by default. Override it with `--paste-shortcut ...` on the CLI or
`paste_shortcut=(...)` in Python when your target app expects something else.

More text-oriented examples:

```bash
# Let auto-selection choose the best available backend.
py-ydotool type "こんにちは"

# Force a direct Unicode backend while debugging session-specific behavior.
py-ydotool type "こんにちは" --text-backend wtype
py-ydotool type "こんにちは" --text-backend eitype

# Force clipboard-backed paste and preserve the old clipboard contents.
py-ydotool type "こんにちは" --text-backend paste --backend wl-clipboard

# Fail instead of silently using atomic paste fallback when timing matters.
py-ydotool type "こんにちは" --delay 25 --strict-text-timing

# Use a terminal-friendly paste shortcut.
py-ydotool paste-text "hello" --paste-shortcut SHIFT INSERT
```


## Mouse coordinate model and current limitations

`py-ydotool` currently exposes two mouse coordinate styles, and the next planned movement work keeps that split explicit.

- `move_rel(dx, dy)` and `py-ydotool move X Y --relative` are **relative** helpers. They treat the values as deltas from the current pointer position.
- `move_to(x, y)`, `click_at(x, y)`, `double_click_at(x, y)`, `drag_to(x, y)`, and the absolute CLI forms of `move` / `drag` are documented as **current-display local absolute** helpers.
- `click_at()` and `double_click_at()` are thin wrappers over `move_to()`, so they inherit the same coordinate contract instead of introducing a separate absolute-click coordinate system.

For the absolute helpers, `(0, 0)` means the origin of the **current display**, not a guaranteed global origin for the whole virtual desktop. On Wayland with `ydotool`, multi-display global absolute positioning is environment-dependent, so this project does **not** promise one consistent coordinate space across every monitor.

Practical guidance:

- prefer relative moves when you need the safest behavior across compositor setups
- keep absolute-style moves inside the current display unless you have verified your environment manually
- do not assume `move_to()`, `click_at()`, or `double_click_at()` can target the full multi-display desktop reliably

`position()` is intentionally unsupported right now. `ydotool` is good at injecting pointer movement and clicks, but by itself it does not provide a reliable, portable way for this library to query the real current pointer position under Wayland-oriented environments.

This contract also applies to timed absolute-like moves such as `move_to(x, y, duration=...)` and `drag_to(x, y, duration=...)`: they stay current-display local. For `duration > 0`, the implementation may first move to the current display origin `(0, 0)` and then use relative interpolation to reach `(x, y)`, so it does **not** promise a straight-line move from the original pointer position.

## Setup and doctor

`py-ydotool` separates **one-time system setup** from **normal Python usage**:

- `py-ydotool doctor` inspects the current environment and explains what is missing
- `py-ydotool doctor` also reports whether clipboard helpers and high-level text backends look available
- it checks the runtime prerequisites (`ydotool`, `ydotoold`, `/dev/uinput`, socket path)
- it also checks whether the managed udev rule, modules-load entry, and target user group membership look correct
- `py-ydotool doctor --json` emits the same diagnosis in a machine-readable form for scripts or CI
- `py-ydotool doctor --strict` makes WARN items fail with a non-zero exit status too
- `py-ydotool doctor` also reports whether setup can self-escalate via `sudo` or `pkexec`
- `py-ydotool setup` performs the explicit one-time Linux setup needed for non-root use
- normal scripts then use `with gui.daemon():` or `@gui.daemon()` without needing `sudo` each time

A typical first-run flow is:

```bash
py-ydotool doctor
py-ydotool setup --dry-run
py-ydotool setup
py-ydotool doctor
```

The same flow is also available through the local development shortcuts:

```bash
just doctor
just setup-dry-run
just doctor-json
just doctor-strict
just doctor-strict-json
```

What to expect after `setup`:

- if the managed files and runtime checks are all green, you can move on to `with gui.daemon():`
- if setup had to add your user to the target group, the post-setup summary may still warn about
  `/dev/uinput` or user-group state until you **log out and back in**
- after logging back in, run `py-ydotool doctor --group <your-group>` once more to confirm the new
  session is ready

If you used a custom group during setup, pass the same group to doctor so the managed checks match your intent, including target-user membership:

```bash
py-ydotool doctor --group uinput-users
```

For scripts or CI checks, `doctor` can also emit JSON:

```bash
py-ydotool doctor --json
```

That JSON includes the overall summary, a small readiness block, per-check items, and deduplicated next actions.

If you want CI to fail on warnings too (for example, when the runtime looks usable but the managed
persistent setup is still missing), use strict mode:

```bash
py-ydotool doctor --strict
```

`doctor` also prints a short readiness summary before the detailed checks, so it is easier to tell whether the current shell looks usable now, whether the managed setup looks complete, and how `setup` would obtain administrator access.

If you prefer discovering the workflow from the CLI, the built-in help now includes concrete examples too:

```bash
py-ydotool --help
py-ydotool doctor --help
py-ydotool setup --help
```

Example dry-run output:

```text
py-ydotool setup

Setup targets:
- target_user=alice
- target_group=input
- udev_rule_path=/etc/udev/rules.d/80-py-ydotool-uinput.rules
- modules_load_path=/etc/modules-load.d/py-ydotool-uinput.conf

Planned changes:
1. Write the udev rule to /etc/udev/rules.d/80-py-ydotool-uinput.rules
   preview: write /etc/udev/rules.d/80-py-ydotool-uinput.rules
   detail: reason=missing or different managed rule for group `input`
   detail: content=KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
```

The dry-run output intentionally includes the target paths, command previews, and the content that would be written so users can review the one-time setup before approving it.

## Permission and setup troubleshooting

If your script fails with a permission-like startup error, the first thing to run is:

```bash
py-ydotool doctor
```

Typical symptoms and fixes:

| Symptom | What it usually means | What to do |
| --- | --- | --- |
| `ydotoold exited before becoming ready` | `ydotoold` could not open `/dev/uinput` or create the requested socket | Run `py-ydotool doctor`, then `py-ydotool setup --dry-run` and `py-ydotool setup` |
| `Permission denied: /dev/uinput` | Your current user session still does not have the needed group access | Re-run setup if needed, then **log out and back in** and run `py-ydotool doctor` again |
| `Required command not found: ydotool` or `ydotoold` | The package is not installed or not in `PATH` | Install `ydotool`, ensure both commands are in `PATH`, and re-run `doctor` |
| Runtime exception includes `Next steps:` | `py-ydotool` recognized a common environment issue while raising the error | Follow the printed `doctor` / `setup` guidance in the exception message |
| `socket-path` is `ERROR` in doctor | The chosen socket path is not writable or is blocked by another file | Pick a writable socket path or remove the conflicting file |

## Common doctor outcomes

| doctor result | What it usually means | Next step |
| --- | --- | --- |
| `ydotool` / `ydotoold` is `ERROR` | The package is not installed or not in `PATH` | Install `ydotool`, then re-run `py-ydotool doctor` |
| `/dev/uinput` is `ERROR` | The device node is missing or the `uinput` module is not loaded yet | Run `py-ydotool setup --dry-run`, then `py-ydotool setup` |
| `/dev/uinput` is `WARN` after setup | The current login session probably has stale group membership | Log out and back in, then re-run `py-ydotool doctor --group <your-group>` |
| `user-group` is `WARN` | The target user is not in the expected managed group | Re-run setup with the intended `--group`, or add the user to that group explicitly |
| `setup-privileges` is `WARN` | `setup` cannot self-escalate with `sudo` or `pkexec` | Re-run `py-ydotool setup` from a root shell |
| `socket-path` is `ERROR` | The configured socket path cannot be used as-is | Pick a writable location or remove the conflicting file |

For automated checks, prefer these combinations:

- `py-ydotool doctor --json` for machine-readable diagnostics
- `py-ydotool doctor --strict` when warnings should fail CI too
- `just doctor-json` / `just doctor-strict-json` during local iteration

What `setup` is allowed to automate:

- create or update a dedicated udev rule for `/dev/uinput`
- optionally create `/etc/modules-load.d/py-ydotool-uinput.conf` so `uinput` is available after reboot
- load the `uinput` kernel module immediately with `modprobe`
- apply group ownership and mode `0660` to `/dev/uinput`
- add the chosen user to the chosen group when needed

What `setup` intentionally does **not** do:

- it does not install a hidden background `ydotoold` service
- it does not use `setuid`
- it does not silently elevate privileges during normal library calls

`setup` is explicit on purpose. When it needs administrator access, it requests that access once via `sudo` or `pkexec`, applies the planned changes, and then returns to normal non-root usage.

If neither helper is available, both `doctor` and `setup` will tell you to rerun setup from a root shell instead of failing later at privilege escalation time.

If the chosen user is newly added to a group, you will usually need to **log out and back in** before `doctor` reports full access for that session.

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

If those prerequisites are missing, the integration tests skip themselves with a
short reason. The current integration module covers real daemon lifecycle
checks, one-shot CLI mouse/paste smoke, and clipboard round-trips for
session-compatible backends.

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

Once the one-time `setup` step is done, the most ergonomic pattern is usually:

```python
from py_ydotool import PyYDoTool

gui = PyYDoTool()

with gui.daemon():
    gui.write("hello")
```

That keeps `ydotoold` lifecycle local to the script while still avoiding root-only daily usage.


```python
from py_ydotool import Key, PyYDoTool

gui = PyYDoTool()

with gui.daemon():
    gui.write("hello")
    gui.press(Key.ENTER)
```

By default, the daemon helper now tracks the most recent `ydotool` input command and waits only for the **remaining quiet period** before stopping an owned daemon. In practice this means short one-shot scripts usually do **not** need an extra manual `sleep(...)` at the end, while longer scripts avoid paying that delay twice.

If your target app still needs a bit more time after the last event, you can tune that explicitly:

```python
with gui.daemon(settle_delay=0.2):
    gui.write("hello")
    gui.press(Key.ENTER)
```

Set `settle_delay=0` if you want the old immediate-stop behavior. When left at the default, it acts as a post-input quiet-period target rather than an unconditional fixed sleep on every shutdown. Negative timing values are rejected early so bad configuration fails at the Python API boundary instead of later during shutdown.

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
gui.type("こんにちは")

direct_gui = PyYDoTool(text_backend="wtype")
direct_gui.type("こんにちは")

paste_gui = PyYDoTool(text_backend="paste", clipboard_backend="wl-clipboard")
paste_gui.type("こんにちは")

strict_gui = PyYDoTool(type_delay_ms=15, strict_text_timing=True)
strict_gui.type("こんにちは")  # raises instead of using atomic paste fallback
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

Or inspect what the current machine can use before choosing one:

```python
from py_ydotool import available_clipboard_backends

print([backend.name for backend in available_clipboard_backends()])
```

If you want to inspect direct text backends too:

```python
from py_ydotool import available_text_backends

print([backend.name for backend in available_text_backends()])
```

#### Troubleshooting clipboard backends

`py-ydotool doctor` focuses on `ydotool` / `ydotoold` / `/dev/uinput`. Clipboard issues are usually a separate boundary, so prefer checking the clipboard backend directly when copy/paste fails.

- if backend auto-detection picked the wrong tool for the current session, pin `clipboard_backend=...` explicitly
- if you pin a backend that is not installed, `ClipboardUnavailableError` now includes both the missing commands and the backends that *are* available
- under native Wayland sessions, prefer `wl-clipboard` when possible
- `xclip` and `xsel` still depend on an X11 / XWayland clipboard being available to the process
- backend detection only checks command availability; it does not bypass display/session permissions

#### Troubleshooting text backends

When high-level text input behaves differently from what you expected, narrow the problem down in this order:

1. run `py-ydotool doctor` and confirm that the reported text backends match what is installed
2. force the backend once with `--text-backend ...` or `text_backend=...` to see whether the issue is selection or execution
3. if timing matters, enable `strict_text_timing` so a hidden paste fallback becomes an explicit error
4. if direct Unicode typing is unavailable in the current session, use `paste` plus an explicit clipboard backend as the stable fallback

Useful rules of thumb:

- if ASCII works but Unicode does not, you are usually on the `ydotool` path and need `wtype`, `eitype`, or paste fallback
- if `wtype` or `eitype` is installed but unavailable, the missing piece is usually the current session/compositor integration rather than Python itself
- if `paste` works but direct typing does not, keep using `type(..., text_backend="paste")` for that target app instead of forcing a fragile direct path
- if a target app only accepts `Shift+Insert` or another shortcut, change `paste_shortcut` instead of changing the clipboard backend first

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
gui.drag_rel(120, 0, duration=0.4)
gui.click_many(3, button=MouseButton.LEFT, next_delay_ms=100)
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

If the matching release tag already exists but still points at an older commit, `just tag-version` now reattaches that tag to the current `HEAD`. This is useful after amending or rebasing a release commit on `main`.

When you move an already-published tag to a rewritten release commit, push that tag explicitly:

```bash
git push --force origin refs/tags/v0.1.1
```

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

- `position()` or other real cursor-position queries
- global multi-display absolute positioning guarantees
- scroll helpers
- image recognition / screen search

The library stays focused on explicit keyboard, mouse, and clipboard automation built on top of `ydotool`. Absolute-style mouse helpers are documented as current-display local helpers unless future backend work makes a stronger guarantee possible.

## Status

Early personal project. APIs may change.

## License

MIT


## Versioning workflow

- `just set-version 0.1.2` updates `src/py_ydotool/VERSION`, `pyproject.toml`, and refreshes `uv.lock`.
- `just tag-version` requires a clean working tree, and if the matching version tag already exists on another commit it moves that tag to the current `HEAD`.
- `just release-version 0.1.2` is the recommended path for a release bump because it updates version files, commits `VERSION` / `pyproject.toml` / `uv.lock`, and then creates the matching tag.
