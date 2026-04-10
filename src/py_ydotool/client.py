from __future__ import annotations

import atexit
import math
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import ContextDecorator, contextmanager
from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING, TextIO

from .clipboard import ClipboardBackend, ClipboardOperation, detect_clipboard_backend
from .text_input import (
    TextInputBackend,
    detect_text_backend,
    direct_text_backends,
    get_text_backend,
)

if TYPE_CHECKING:
    from ._system import DoctorReport, SetupPlan, SystemPaths

from .exceptions import (
    ClipboardUnavailableError,
    CommandExecutionError,
    CommandNotFoundError,
    CommandTimeoutError,
    DaemonReadyTimeoutError,
    DaemonStartError,
    TextInputUnavailableError,
)


class MouseButton:
    LEFT = "0xC0"
    RIGHT = "0xC1"
    MIDDLE = "0xC2"
    SIDE = "0xC3"
    EXTRA = "0xC4"
    FORWARD = "0xC5"
    BACK = "0xC6"
    TASK = "0xC7"


def _format_help_block(*items: str) -> str:
    lines = [f"- {item}" for item in items]
    return "\n\nNext steps:\n" + "\n".join(lines)


def _doctor_setup_help() -> str:
    return _format_help_block(
        "Run `py-ydotool doctor` to inspect the current environment.",
        "Review the planned changes with `py-ydotool setup --dry-run`.",
        "Apply the one-time setup with `py-ydotool setup`.",
        "If setup changed group membership, log out and back in before retrying.",
    )


def _missing_command_help(name: str) -> str:
    return _format_help_block(
        f"Install `{name}` and ensure it is available in `PATH`.",
        "Run `py-ydotool doctor` to confirm the command is now visible.",
    )


def _socket_help() -> str:
    return _format_help_block(
        "Start a daemon with `with gui.daemon():` or ensure `ydotoold` is already running.",
        "Run `py-ydotool doctor` to confirm the socket path is writable.",
    )


ProcessOutputValue = str | bytes | None


@dataclass(frozen=True, slots=True)
class _MotionStep:
    offset: float
    dx: int
    dy: int


def _output_to_text(value: ProcessOutputValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _join_output(stdout: ProcessOutputValue, stderr: ProcessOutputValue) -> str:
    return "\n".join(
        part.strip() for part in (_output_to_text(stdout), _output_to_text(stderr)) if part.strip()
    )


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    return value


def _require_non_empty_text(name: str, value: str) -> str:
    value = _require_text(name, value)
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _require_bool(name: str, value: bool) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool")
    return value


def _normalize_optional_text(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _require_non_empty_text(name, value)


def _normalize_text_sequence(name: str, values: Iterable[str]) -> tuple[str, ...]:
    return tuple(_require_text(f"{name}[{index}]", value) for index, value in enumerate(values))


def _normalize_socket_path(socket_path: str | None) -> str:
    if socket_path is not None:
        return _require_non_empty_text("socket_path", socket_path)

    env_socket_path = os.environ.get("YDOTOOL_SOCKET")
    if env_socket_path:
        return env_socket_path
    return "/tmp/.ydotool_socket"


def _require_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def _require_real_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a real number")
    real_value = float(value)
    if not math.isfinite(real_value):
        raise ValueError(f"{name} must be finite")
    return real_value


def _require_non_negative(name: str, value: float) -> float:
    real_value = _require_real_number(name, value)
    if real_value < 0:
        raise ValueError(f"{name} must be >= 0")
    return real_value


def _normalize_timeout(name: str, value: float | None) -> float | None:
    if value is None:
        return None
    return _require_non_negative(name, value)


def _resolve_timeout(
    configured_timeout: float | None,
    timeout: float | None,
) -> float | None:
    if timeout is None:
        return configured_timeout
    return _normalize_timeout("timeout", timeout)


def _require_non_negative_int(name: str, value: int) -> int:
    value = _require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_positive_int(name: str, value: int) -> int:
    value = _require_int(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _normalize_delay_ms(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    return _require_non_negative_int(name, value)


def _normalize_repeat(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    return _require_positive_int(name, value)


def _normalize_keycodes(keycodes: Iterable[int]) -> list[int]:
    return [_require_non_negative_int("keycode", keycode) for keycode in keycodes]


def _default_paste_shortcut() -> tuple[int, ...]:
    from .keys import Key

    return (Key.CTRL, Key.V)


def _normalize_paste_shortcut(keycodes: Iterable[int] | None) -> tuple[int, ...]:
    if keycodes is None:
        return _default_paste_shortcut()
    normalized = tuple(_normalize_keycodes(keycodes))
    if not normalized:
        raise ValueError("paste_shortcut must not be empty")
    return normalized


def _normalize_mouse_button(button: str) -> str:
    _require_text("button", button)
    try:
        int(button, 16)
    except ValueError as exc:
        raise ValueError(
            "button must be a hexadecimal string like MouseButton.LEFT or '0xC0'"
        ) from exc
    return button


def _normalize_point(x_name: str, x: int, y_name: str, y: int) -> tuple[int, int]:
    return _require_int(x_name, x), _require_int(y_name, y)


def _normalize_click_arguments(
    button: str,
    *,
    repeat: int | None = None,
    next_delay_ms: int | None = None,
) -> tuple[str, int | None, int | None]:
    return (
        _normalize_mouse_button(button),
        _normalize_repeat("repeat", repeat),
        _normalize_delay_ms("next_delay_ms", next_delay_ms),
    )


def _normalize_motion_timing(
    *, duration: float = 0.0, steps: int | None = None
) -> tuple[float, int | None]:
    duration = _require_non_negative("duration", duration)
    if steps is None:
        return duration, None
    steps = _require_positive_int("steps", steps)
    if duration == 0:
        raise ValueError("steps requires duration > 0")
    return duration, steps


def _suggest_motion_steps(dx: int, dy: int, *, duration: float) -> int:
    if duration == 0:
        return 1

    max_axis = max(abs(dx), abs(dy))
    if max_axis == 0:
        return 1

    return max(1, min(max_axis, math.ceil(duration * 120)))


def _build_linear_motion_steps(
    dx: int,
    dy: int,
    *,
    duration: float = 0.0,
    steps: int | None = None,
) -> tuple[_MotionStep, ...]:
    dx, dy = _normalize_point("dx", dx, "dy", dy)
    duration, steps = _normalize_motion_timing(duration=duration, steps=steps)

    if duration == 0:
        if dx == 0 and dy == 0:
            return ()
        return (_MotionStep(offset=0.0, dx=dx, dy=dy),)

    step_count = steps if steps is not None else _suggest_motion_steps(dx, dy, duration=duration)

    motion_steps: list[_MotionStep] = []
    previous_x = 0
    previous_y = 0
    for index in range(1, step_count + 1):
        current_x = round(dx * index / step_count)
        current_y = round(dy * index / step_count)
        step_dx = current_x - previous_x
        step_dy = current_y - previous_y
        previous_x = current_x
        previous_y = current_y
        if step_dx == 0 and step_dy == 0:
            continue
        motion_steps.append(
            _MotionStep(
                offset=duration * index / step_count,
                dx=step_dx,
                dy=step_dy,
            )
        )

    return tuple(motion_steps)


def _run_motion_steps(
    motion_steps: Iterable[_MotionStep],
    *,
    move: Callable[[int, int], None],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    steps_tuple = tuple(motion_steps)
    if not steps_tuple:
        return

    if len(steps_tuple) == 1 and steps_tuple[0].offset == 0:
        step = steps_tuple[0]
        move(step.dx, step.dy)
        return

    started_at = monotonic()
    for step in steps_tuple:
        remaining = started_at + step.offset - monotonic()
        if remaining > 0:
            sleep(remaining)
        move(step.dx, step.dy)


def _help_for_message(message: str) -> str:
    lower = message.lower()
    if any(
        token in lower
        for token in (
            "/dev/uinput",
            "permission denied",
            "operation not permitted",
        )
    ):
        return _doctor_setup_help()
    if "socket" in lower and any(
        token in lower
        for token in (
            "no such file",
            "not a socket",
            "failed to connect",
            "cannot connect",
        )
    ):
        return _socket_help()
    return ""


class YDoToolDaemon(ContextDecorator):
    _NON_INPUT_COMMANDS = frozenset({"debug"})

    def __init__(
        self,
        tool: PyYDoTool,
        *,
        ready_timeout: float = 5.0,
        stop_timeout: float = 1.0,
        settle_delay: float = 0.1,
        extra_args: Iterable[str] = (),
        clean_stale_socket: bool = True,
    ) -> None:
        self._tool = tool
        self.ready_timeout = _require_non_negative("ready_timeout", ready_timeout)
        self.stop_timeout = _require_non_negative("stop_timeout", stop_timeout)
        self.settle_delay = _require_non_negative("settle_delay", settle_delay)
        self.extra_args = _normalize_text_sequence("extra_args", extra_args)
        self.clean_stale_socket = _require_bool("clean_stale_socket", clean_stale_socket)
        self._process: subprocess.Popen[str] | None = None
        self._owns_process = False
        self._stderr_file: TextIO | None = None
        self._last_activity_at: float | None = None
        self._atexit_registered = False
        self._atexit_callback = self._stop_at_exit

    @property
    def socket_path(self) -> str:
        return self._tool.socket_path or "/tmp/.ydotool_socket"

    def _socket_stat_mode(self) -> int | None:
        if not self.socket_path:
            return None
        try:
            return os.stat(self.socket_path, follow_symlinks=False).st_mode
        except FileNotFoundError:
            return None

    def _socket_file_exists(self) -> bool:
        return self._socket_stat_mode() is not None

    def _is_socket_file(self) -> bool:
        mode = self._socket_stat_mode()
        return mode is not None and stat.S_ISSOCK(mode)

    def _is_socket_ready(self) -> bool:
        if not self.socket_path or not self._is_socket_file():
            return False
        try:
            self._tool._run("debug", timeout=0.2)
        except (CommandExecutionError, CommandTimeoutError, CommandNotFoundError):
            return False
        return True

    def _build_command(self) -> list[str]:
        return ["ydotoold", "--socket-path", self.socket_path, *self.extra_args]

    def _clean_stale_socket_if_needed(self) -> None:
        if not self.clean_stale_socket or not self.socket_path:
            return

        if not self._is_socket_file():
            return

        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            return

    def _open_stderr_file(self) -> TextIO:
        self._close_stderr_file()
        self._stderr_file = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
        return self._stderr_file

    def _close_stderr_file(self) -> None:
        if self._stderr_file is None:
            return
        self._stderr_file.close()
        self._stderr_file = None

    def _read_stderr(self) -> str:
        if self._stderr_file is None:
            return ""
        self._stderr_file.flush()
        self._stderr_file.seek(0)
        return self._stderr_file.read().strip()

    def _format_stderr(self) -> str:
        stderr = self._read_stderr()
        if not stderr:
            return ""
        return f"\nstderr: {stderr}"

    @classmethod
    def _is_input_command(cls, command_name: str) -> bool:
        return command_name not in cls._NON_INPUT_COMMANDS

    def _note_tool_activity(self, command_name: str, *, completed_at: float) -> None:
        if not self._is_input_command(command_name):
            return
        self._last_activity_at = completed_at

    def _wait_for_quiet_period(self) -> None:
        if self.settle_delay <= 0 or self._last_activity_at is None:
            return

        elapsed = time.monotonic() - self._last_activity_at
        remaining = self.settle_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _format_socket_state(self) -> str:
        exists = self._socket_file_exists()
        is_socket = self._is_socket_file() if exists else False
        return (
            f"\nsocket_path: {self.socket_path}"
            f"\nsocket_exists: {'yes' if exists else 'no'}"
            f"\nsocket_is_socket: {'yes' if is_socket else 'no'}"
        )

    def _stop_at_exit(self) -> None:
        self.stop()

    def _register_atexit(self) -> None:
        if self._atexit_registered:
            return
        atexit.register(self._atexit_callback)
        self._atexit_registered = True

    def _unregister_atexit(self) -> None:
        if not self._atexit_registered:
            return
        atexit.unregister(self._atexit_callback)
        self._atexit_registered = False

    def start(self) -> YDoToolDaemon:
        if self._process is not None or self._owns_process:
            return self

        self._tool._ensure_command("ydotool")
        self._tool._ensure_command("ydotoold")

        if self._is_socket_ready():
            self._owns_process = False
            self._tool._register_daemon_context(self)
            self._unregister_atexit()
            return self

        self._clean_stale_socket_if_needed()

        self._process = subprocess.Popen(
            self._build_command(),
            env=self._tool._env,
            stdout=subprocess.DEVNULL,
            stderr=self._open_stderr_file(),
            text=True,
        )
        self._owns_process = True
        self._register_atexit()

        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                exit_code = self._process.returncode
                stderr = self._format_stderr()
                self.stop()
                message = (
                    f"ydotoold exited before becoming ready (exit code {exit_code})"
                    f"{self._format_socket_state()}{stderr}"
                )
                raise DaemonStartError(f"{message}{_help_for_message(message)}")
            if self._is_socket_ready():
                self._tool._register_daemon_context(self)
                return self
            time.sleep(0.05)

        stderr = self._format_stderr()
        self.stop()
        message = (
            f"ydotoold did not become ready within {self.ready_timeout} seconds"
            f"{self._format_socket_state()}{stderr}"
        )
        raise DaemonReadyTimeoutError(f"{message}{_help_for_message(message)}")

    def _cleanup_socket_after_stop(self) -> None:
        if not self.socket_path or not self._is_socket_file():
            return
        if self._is_socket_ready():
            return
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            return

    def stop(self) -> None:
        if not self._owns_process or self._process is None:
            self._tool._unregister_daemon_context(self)
            self._last_activity_at = None
            self._process = None
            self._owns_process = False
            self._unregister_atexit()
            self._close_stderr_file()
            return

        process = self._process
        try:
            if process.poll() is None:
                self._wait_for_quiet_period()
                process.terminate()
                try:
                    process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.stop_timeout)
        finally:
            self._cleanup_socket_after_stop()
            self._tool._unregister_daemon_context(self)
            self._last_activity_at = None
            self._process = None
            self._owns_process = False
            self._unregister_atexit()
            self._close_stderr_file()

    def __enter__(self) -> YDoToolDaemon:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self.stop()
        return False


@dataclass(slots=True)
class PyYDoTool:
    socket_path: str | None = None
    check_commands_on_init: bool = True
    type_delay_ms: int = 0
    clipboard_backend: str | None = None
    text_backend: str | None = None
    strict_text_timing: bool = False
    restore_clipboard: bool = True
    paste_settle_delay: float = 0.05
    paste_shortcut: tuple[int, ...] | None = None
    command_timeout: float | None = 5.0
    _env: dict[str, str] = field(init=False, repr=False)
    _clipboard: ClipboardBackend | None = field(init=False, repr=False, default=None)
    _text_input: TextInputBackend | None = field(init=False, repr=False, default=None)
    _active_daemons: list[YDoToolDaemon] = field(init=False, repr=False, default_factory=list)

    def __post_init__(self) -> None:
        self.socket_path = _normalize_socket_path(self.socket_path)
        self.clipboard_backend = _normalize_optional_text(
            "clipboard_backend",
            self.clipboard_backend,
        )
        self.text_backend = _normalize_optional_text(
            "text_backend",
            self.text_backend,
        )
        self.strict_text_timing = _require_bool(
            "strict_text_timing",
            self.strict_text_timing,
        )
        self.restore_clipboard = _require_bool(
            "restore_clipboard",
            self.restore_clipboard,
        )
        self.paste_settle_delay = _require_non_negative(
            "paste_settle_delay",
            self.paste_settle_delay,
        )
        self.paste_shortcut = _normalize_paste_shortcut(self.paste_shortcut)
        self._env = os.environ.copy()
        self._env["YDOTOOL_SOCKET"] = self.socket_path
        self.type_delay_ms = _require_non_negative_int(
            "type_delay_ms",
            self.type_delay_ms,
        )
        self.command_timeout = _normalize_timeout("command_timeout", self.command_timeout)
        self.check_commands_on_init = _require_bool(
            "check_commands_on_init",
            self.check_commands_on_init,
        )

        if self.check_commands_on_init:
            self._ensure_primary_commands()

    def _ensure_command(self, name: str) -> None:
        if shutil.which(name) is None:
            raise CommandNotFoundError(
                f"Required command not found: {name}{_missing_command_help(name)}"
            )

    def _ensure_primary_commands(self) -> None:
        if self.text_backend in {"wtype", "eitype"}:
            self._ensure_command(self.text_backend)
            return
        self._ensure_command("ydotool")

    def _register_daemon_context(self, daemon: YDoToolDaemon) -> None:
        if daemon not in self._active_daemons:
            self._active_daemons.append(daemon)

    def _unregister_daemon_context(self, daemon: YDoToolDaemon) -> None:
        if daemon in self._active_daemons:
            self._active_daemons.remove(daemon)

    def _record_daemon_activity(self, command_name: str) -> None:
        if not self._active_daemons:
            return

        completed_at = time.monotonic()
        for daemon in tuple(self._active_daemons):
            daemon._note_tool_activity(command_name, completed_at=completed_at)

    def _run_subprocess(
        self,
        command: list[str],
        *,
        input_text: str | None = None,
        timeout: float | None = None,
        missing_command_name: str,
        error_prefix: str,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        resolved_timeout = _resolve_timeout(self.command_timeout, timeout)
        run_kwargs: dict[str, object] = {
            "text": True,
            "input": input_text,
            "check": True,
            "env": self._env,
            "timeout": resolved_timeout,
        }
        if capture_output:
            run_kwargs["capture_output"] = True
        else:
            run_kwargs["stdout"] = subprocess.DEVNULL
            run_kwargs["stderr"] = subprocess.DEVNULL
        try:
            return subprocess.run(command, **run_kwargs)
        except subprocess.TimeoutExpired as exc:
            cmd = exc.cmd if isinstance(exc.cmd, list) else [str(exc.cmd)]
            raise CommandTimeoutError(
                f"{error_prefix} timed out after {exc.timeout} seconds: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise CommandNotFoundError(
                "Required command not found: "
                f"{missing_command_name}{_missing_command_help(missing_command_name)}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            help_text = _help_for_message(_join_output(exc.stdout, exc.stderr))
            raise CommandExecutionError(
                f"{error_prefix} failed: {' '.join(exc.cmd)}\n"
                f"stdout: {exc.stdout}\nstderr: {exc.stderr}{help_text}"
            ) from exc

    def _run(
        self,
        *args: str,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = self._run_subprocess(
            ["ydotool", *args],
            timeout=timeout,
            missing_command_name="ydotool",
            error_prefix="ydotool",
        )
        if args:
            self._record_daemon_activity(args[0])
        return completed

    def _run_command(
        self,
        command: list[str],
        *,
        input_text: str | None = None,
        timeout: float | None = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self._run_subprocess(
            command,
            input_text=input_text,
            timeout=timeout,
            missing_command_name=command[0],
            error_prefix="command",
            capture_output=capture_output,
        )

    def _get_clipboard_backend(self) -> ClipboardBackend:
        if self._clipboard is None:
            self._clipboard = detect_clipboard_backend(self.clipboard_backend)
        return self._clipboard

    def _run_clipboard_command(
        self,
        operation: ClipboardOperation,
        *,
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        backend = self._get_clipboard_backend()
        command = backend.command_for(operation)
        capture_output = operation == "paste"
        if timeout is None:
            return self._run_command(
                command,
                input_text=input_text,
                capture_output=capture_output,
            )
        return self._run_command(
            command,
            input_text=input_text,
            timeout=timeout,
            capture_output=capture_output,
        )

    def _clipboard_is_available(self) -> bool:
        try:
            self._get_clipboard_backend()
        except ClipboardUnavailableError:
            return False
        return True

    def _get_text_backend(self, text: str) -> TextInputBackend:
        text = _require_text("text", text)
        clipboard_available = self._clipboard_is_available()

        if self.text_backend is not None:
            return detect_text_backend(
                self.text_backend,
                clipboard_available=clipboard_available,
            )

        unicode_required = not text.isascii()
        if not unicode_required and not self.check_commands_on_init:
            return get_text_backend("ydotool")

        if unicode_required:
            preferred_direct = ("wtype", "eitype")
        else:
            preferred_direct = ("ydotool", "wtype", "eitype")

        direct_candidates = {backend.name: backend for backend in direct_text_backends()}
        for name in preferred_direct:
            backend = direct_candidates[name]
            if backend.is_available(clipboard_available=clipboard_available):
                return backend

        if clipboard_available:
            return detect_text_backend("paste", clipboard_available=clipboard_available)

        if unicode_required:
            raise TextInputUnavailableError(
                "No Unicode-capable text backend is available. Install wtype or eitype, "
                "or enable a clipboard backend for paste fallback."
            )

        raise TextInputUnavailableError(
            "No direct text backend is available. Install ydotool, wtype, or eitype, "
            "or enable a clipboard backend for paste fallback."
        )

    def _ensure_text_timing_supported(self, backend: TextInputBackend) -> None:
        if not self.strict_text_timing or self.type_delay_ms == 0:
            return
        if backend.supports_timing_per_char:
            return
        raise TextInputUnavailableError(
            "Per-character timing requires a direct typing backend, but text input would use "
            "clipboard-backed paste. Set type_delay_ms=0, install wtype or eitype, choose "
            "a direct text backend, or disable strict_text_timing."
        )

    def _capture_clipboard_for_restore(self) -> str | None:
        if not self.restore_clipboard:
            return None
        return self.get_clipboard()

    def _restore_clipboard_after_paste(self, text: str | None) -> None:
        if text is None:
            return
        if self.paste_settle_delay > 0:
            time.sleep(self.paste_settle_delay)
        self.copy(text)

    def daemon(
        self,
        *,
        ready_timeout: float = 5.0,
        stop_timeout: float = 1.0,
        settle_delay: float = 0.1,
        extra_args: Iterable[str] = (),
        clean_stale_socket: bool = True,
    ) -> YDoToolDaemon:
        return YDoToolDaemon(
            self,
            ready_timeout=ready_timeout,
            stop_timeout=stop_timeout,
            settle_delay=settle_delay,
            extra_args=extra_args,
            clean_stale_socket=_require_bool("clean_stale_socket", clean_stale_socket),
        )

    @staticmethod
    def _event(keycode: int, pressed: bool) -> str:
        keycode = _require_non_negative_int("keycode", keycode)
        return f"{keycode}:{1 if pressed else 0}"

    @staticmethod
    def _mouse_event(button: str, *, down: bool = False, up: bool = False) -> str:
        button = _normalize_mouse_button(button)
        base = int(button, 16) & 0x3F
        mask = 0
        if down:
            mask |= 0x40
        if up:
            mask |= 0x80
        return f"0x{base | mask:02X}"

    def doctor_report(
        self,
        *,
        user: str | None = None,
        group: str = "input",
        paths: SystemPaths | None = None,
    ) -> DoctorReport:
        from ._system import SystemPaths, collect_doctor_report

        resolved_paths = SystemPaths() if paths is None else paths
        resolved_user = _normalize_optional_text("user", user)
        resolved_group = _require_non_empty_text("group", group)
        return collect_doctor_report(
            socket_path=self.socket_path,
            paths=resolved_paths,
            user=resolved_user,
            group=resolved_group,
        )

    def doctor_text(
        self,
        *,
        user: str | None = None,
        group: str = "input",
        paths: SystemPaths | None = None,
        stream: TextIO | None = None,
    ) -> str:
        from ._system import render_doctor_report

        report = self.doctor_report(user=user, group=group, paths=paths)
        return render_doctor_report(report, stream=stream)

    def doctor_json(
        self,
        *,
        user: str | None = None,
        group: str = "input",
        paths: SystemPaths | None = None,
        stream: TextIO | None = None,
    ) -> str:
        from ._system import render_doctor_report_json

        report = self.doctor_report(user=user, group=group, paths=paths)
        return render_doctor_report_json(report, stream=stream)

    def setup_plan(
        self,
        *,
        target_user: str | None = None,
        group: str = "input",
        ensure_module_loaded_on_boot: bool = True,
        add_user_to_group: bool = True,
        dry_run: bool = False,
        privileged: bool = False,
        paths: SystemPaths | None = None,
    ) -> SetupPlan:
        from ._system import SetupOptions, SystemPaths, build_setup_plan

        resolved_paths = SystemPaths() if paths is None else paths
        resolved_target_user = _normalize_optional_text("target_user", target_user)
        resolved_group = _require_non_empty_text("group", group)
        options = SetupOptions(
            target_user=resolved_target_user,
            group=resolved_group,
            ensure_module_loaded_on_boot=_require_bool(
                "ensure_module_loaded_on_boot",
                ensure_module_loaded_on_boot,
            ),
            add_user_to_group=_require_bool("add_user_to_group", add_user_to_group),
            dry_run=_require_bool("dry_run", dry_run),
            privileged=_require_bool("privileged", privileged),
            socket_path=self.socket_path,
        )
        return build_setup_plan(options, paths=resolved_paths)

    def setup_plan_text(
        self,
        *,
        target_user: str | None = None,
        group: str = "input",
        ensure_module_loaded_on_boot: bool = True,
        add_user_to_group: bool = True,
        dry_run: bool = True,
        privileged: bool = False,
        paths: SystemPaths | None = None,
    ) -> str:
        from ._system import render_setup_plan

        plan = self.setup_plan(
            target_user=target_user,
            group=group,
            ensure_module_loaded_on_boot=ensure_module_loaded_on_boot,
            add_user_to_group=add_user_to_group,
            dry_run=dry_run,
            privileged=privileged,
            paths=paths,
        )
        return render_setup_plan(plan, dry_run=dry_run)

    def sleep(self, seconds: float) -> None:
        seconds = _require_non_negative("seconds", seconds)
        time.sleep(seconds)

    def key_down(self, keycode: int) -> None:
        self._run("key", self._event(keycode, True))

    def key_up(self, keycode: int) -> None:
        self._run("key", self._event(keycode, False))

    def press(self, keycode: int) -> None:
        self._run(
            "key",
            self._event(keycode, True),
            self._event(keycode, False),
        )

    def press_many(self, keycodes: Iterable[int], interval: float = 0.0) -> None:
        interval = _require_non_negative("interval", interval)
        normalized_keycodes = _normalize_keycodes(keycodes)
        for keycode in normalized_keycodes:
            self.press(keycode)
            if interval > 0:
                time.sleep(interval)

    @contextmanager
    def hold_keys(self, *keycodes: int) -> Iterator[None]:
        normalized_keycodes = _normalize_keycodes(keycodes)
        pressed: list[int] = []
        try:
            for keycode in normalized_keycodes:
                self.key_down(keycode)
                pressed.append(keycode)
            yield
        finally:
            for keycode in reversed(pressed):
                self.key_up(keycode)

    def hotkey(self, *keycodes: int) -> None:
        with self.hold_keys(*keycodes):
            return None

    def type(self, text: str) -> None:
        """Input text using the most appropriate backend for the given string.

        ``type_delay_ms`` only applies to direct typing backends. When the
        clipboard paste fallback is selected, the text is inserted atomically
        and per-character timing is ignored unless ``strict_text_timing`` is
        enabled, in which case the operation fails instead of pasting.
        """
        text = _require_text("text", text)
        backend = self._get_text_backend(text)
        if backend.mode == "paste":
            self._ensure_text_timing_supported(backend)
            self.paste_text(text)
            return
        command = backend.command_for_text(text, delay_ms=self.type_delay_ms)
        if backend.name == "ydotool":
            self._run(*command[1:])
            return
        self._run_command(command)

    write = type

    def type_or_paste(
        self,
        text: str,
        *,
        prefer_paste: bool = False,
        paste_threshold: int = 128,
    ) -> None:
        text = _require_text("text", text)
        paste_threshold = _require_non_negative_int("paste_threshold", paste_threshold)
        prefer_paste = _require_bool("prefer_paste", prefer_paste)
        if prefer_paste or "\n" in text or len(text) >= paste_threshold:
            self._ensure_text_timing_supported(get_text_backend("paste"))
            self.paste_text(text)
        else:
            self.write(text)

    def click(
        self,
        button: str = MouseButton.LEFT,
        *,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        button, repeat, next_delay_ms = _normalize_click_arguments(
            button,
            repeat=repeat,
            next_delay_ms=next_delay_ms,
        )

        args = ["click"]
        if next_delay_ms is not None:
            args.extend(["--next-delay", str(next_delay_ms)])
        if repeat is not None:
            args.extend(["--repeat", str(repeat)])
        args.append(button)
        self._run(*args)

    def click_many(
        self,
        repeat: int,
        button: str = MouseButton.LEFT,
        *,
        next_delay_ms: int | None = None,
    ) -> None:
        self.click(button, repeat=repeat, next_delay_ms=next_delay_ms)

    def double_click(self, button: str = MouseButton.LEFT, interval: float = 0.1) -> None:
        interval = _require_non_negative("interval", interval)
        self.click_many(2, button=button, next_delay_ms=int(interval * 1000))

    def mouse_down(self, button: str = MouseButton.LEFT) -> None:
        button = _normalize_mouse_button(button)
        self._run("click", self._mouse_event(button, down=True))

    def mouse_up(self, button: str = MouseButton.LEFT) -> None:
        button = _normalize_mouse_button(button)
        self._run("click", self._mouse_event(button, up=True))

    def right_click(self) -> None:
        self.click(MouseButton.RIGHT)

    def middle_click(self) -> None:
        self.click(MouseButton.MIDDLE)

    def side_click(self) -> None:
        self.click(MouseButton.SIDE)

    def extra_click(self) -> None:
        self.click(MouseButton.EXTRA)

    def forward_click(self) -> None:
        self.click(MouseButton.FORWARD)

    def back_click(self) -> None:
        self.click(MouseButton.BACK)

    def task_click(self) -> None:
        self.click(MouseButton.TASK)

    @contextmanager
    def hold_button(self, button: str = MouseButton.LEFT) -> Iterator[None]:
        self.mouse_down(button)
        try:
            yield
        finally:
            self.mouse_up(button)

    def click_with_modifiers(self, *keycodes: int, button: str = MouseButton.LEFT) -> None:
        button = _normalize_mouse_button(button)
        with self.hold_keys(*keycodes):
            self.click(button)

    def _move_to_absolute_once(self, x: int, y: int) -> None:
        self._run("mousemove", "--absolute", str(x), str(y))

    def move_to(
        self,
        x: int,
        y: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        """Move to a current-display local absolute point.

        ``x`` and ``y`` are documented as coordinates inside the display that
        currently contains the pointer, not as guaranteed virtual-desktop global
        coordinates across every monitor.

        ``duration=0`` keeps the underlying absolute ydotool move.
        ``duration>0`` keeps the same current-display contract, but it may first
        move to the current display origin ``(0, 0)`` and then use relative
        interpolation to reach ``(x, y)``. This is an absolute-like helper, not
        a guarantee of a straight-line move from the original pointer position.
        """
        x, y = _normalize_point("x", x, "y", y)
        duration, steps = _normalize_motion_timing(duration=duration, steps=steps)
        if duration == 0:
            self._move_to_absolute_once(x, y)
            return
        self._move_to_absolute_once(0, 0)
        self.move_rel(x, y, duration=duration, steps=steps)

    def _move_rel_once(self, dx: int, dy: int) -> None:
        self._run("mousemove", str(dx), str(dy))

    def move_rel(
        self,
        dx: int,
        dy: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        """Move relative to the current pointer position.

        ``duration`` adds linear interpolation over multiple relative motions.
        ``steps`` can be used to override the automatically suggested split count.
        """
        motion_steps = _build_linear_motion_steps(dx, dy, duration=duration, steps=steps)
        _run_motion_steps(motion_steps, move=self._move_rel_once)

    def drag_to(
        self,
        x: int,
        y: int,
        button: str = MouseButton.LEFT,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        """Drag to a current-display local absolute point.

        This keeps the same coordinate contract as :meth:`move_to` and uses the
        same timed absolute-like behavior when ``duration > 0``.
        """
        x, y = _normalize_point("x", x, "y", y)
        button = _normalize_mouse_button(button)
        duration, steps = _normalize_motion_timing(duration=duration, steps=steps)
        with self.hold_button(button):
            self.move_to(x, y, duration=duration, steps=steps)

    def drag_rel(
        self,
        dx: int,
        dy: int,
        button: str = MouseButton.LEFT,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        """Drag relative to the current pointer position."""
        dx, dy = _normalize_point("dx", dx, "dy", dy)
        button = _normalize_mouse_button(button)
        duration, steps = _normalize_motion_timing(duration=duration, steps=steps)
        with self.hold_button(button):
            self.move_rel(dx, dy, duration=duration, steps=steps)

    def click_at(
        self,
        x: int,
        y: int,
        button: str = MouseButton.LEFT,
        *,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        """Move with :meth:`move_to`, then click at that point.

        The coordinate contract is exactly the same current-display local
        absolute contract documented for :meth:`move_to`.
        """
        x, y = _normalize_point("x", x, "y", y)
        button, repeat, next_delay_ms = _normalize_click_arguments(
            button,
            repeat=repeat,
            next_delay_ms=next_delay_ms,
        )
        self.move_to(x, y)
        self.click(button, repeat=repeat, next_delay_ms=next_delay_ms)

    def double_click_at(
        self, x: int, y: int, button: str = MouseButton.LEFT, interval: float = 0.1
    ) -> None:
        """Move with :meth:`move_to`, then double-click at that point.

        The coordinate contract is exactly the same current-display local
        absolute contract documented for :meth:`move_to`.
        """
        x, y = _normalize_point("x", x, "y", y)
        button = _normalize_mouse_button(button)
        interval = _require_non_negative("interval", interval)
        self.move_to(x, y)
        self.double_click(button, interval=interval)

    def right_click_at(self, x: int, y: int) -> None:
        self.click_at(x, y, MouseButton.RIGHT)

    def middle_click_at(self, x: int, y: int) -> None:
        self.click_at(x, y, MouseButton.MIDDLE)

    def drag_between(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = MouseButton.LEFT,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        """Drag between two current-display local absolute points."""
        start_x, start_y = _normalize_point("start_x", start_x, "start_y", start_y)
        end_x, end_y = _normalize_point("end_x", end_x, "end_y", end_y)
        button = _normalize_mouse_button(button)
        duration, steps = _normalize_motion_timing(duration=duration, steps=steps)
        self.move_to(start_x, start_y)
        self.drag_to(end_x, end_y, button, duration=duration, steps=steps)

    def copy(self, text: str) -> None:
        text = _require_text("text", text)
        self._run_clipboard_command("copy", input_text=text)

    def get_clipboard(self) -> str:
        result = self._run_clipboard_command("paste")
        return result.stdout

    def paste(self) -> None:
        """Send the configured paste shortcut."""
        self.hotkey(*self.paste_shortcut)

    def paste_text(self, text: str) -> None:
        """Paste text via the clipboard backend and configured paste shortcut.

        When ``restore_clipboard`` is enabled, the current text clipboard is
        captured before the paste operation and restored afterwards. The
        restoration happens after ``paste_settle_delay`` seconds so the target
        application has a small window to consume the pasted contents.
        """
        text = _require_text("text", text)
        original_clipboard: str | None = None
        if self.restore_clipboard:
            original_clipboard = self._capture_clipboard_for_restore()
        try:
            self.copy(text)
            self.paste()
        except Exception:
            if original_clipboard is not None:
                try:
                    self.copy(original_clipboard)
                except Exception:
                    pass
            raise
        if original_clipboard is not None:
            self._restore_clipboard_after_paste(original_clipboard)

    def select_all(self) -> None:
        from .keys import Key

        self.hotkey(Key.CTRL, Key.A)

    def copy_selected(self, wait: float = 0.05) -> str:
        from .keys import Key

        wait = _require_non_negative("wait", wait)
        self.hotkey(Key.CTRL, Key.C)
        if wait > 0:
            time.sleep(wait)
        return self.get_clipboard()

    def cut_selected(self, wait: float = 0.05) -> str:
        from .keys import Key

        wait = _require_non_negative("wait", wait)
        self.hotkey(Key.CTRL, Key.X)
        if wait > 0:
            time.sleep(wait)
        return self.get_clipboard()

    def position(self) -> tuple[int, int]:
        """Return the real current pointer position.

        This is intentionally unsupported for now because ``ydotool`` alone does
        not provide a reliable portable way for this library to query the actual
        current pointer position.
        """
        raise NotImplementedError(
            "Current mouse position is not supported by py-ydotool yet; "
            "see the README for current Wayland/ydotool limitations."
        )
