from __future__ import annotations

import atexit
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Iterable, Iterator
from contextlib import ContextDecorator, contextmanager
from dataclasses import dataclass, field

from .clipboard import ClipboardBackend, detect_clipboard_backend
from .exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    CommandTimeoutError,
    DaemonReadyTimeoutError,
    DaemonStartError,
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


class YDoToolDaemon(ContextDecorator):
    def __init__(
        self,
        tool: PyYDoTool,
        *,
        ready_timeout: float = 5.0,
        stop_timeout: float = 1.0,
        extra_args: Iterable[str] = (),
        clean_stale_socket: bool = True,
    ) -> None:
        self._tool = tool
        self.ready_timeout = ready_timeout
        self.stop_timeout = stop_timeout
        self.extra_args = tuple(extra_args)
        self.clean_stale_socket = clean_stale_socket
        self._process: subprocess.Popen[str] | None = None
        self._owns_process = False
        self._stderr_file: object | None = None
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

    def _open_stderr_file(self):
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
                raise DaemonStartError(
                    f"ydotoold exited before becoming ready (exit code {exit_code})"
                    f"{self._format_socket_state()}{stderr}"
                )
            if self._is_socket_ready():
                return self
            time.sleep(0.05)

        stderr = self._format_stderr()
        self.stop()
        raise DaemonReadyTimeoutError(
            f"ydotoold did not become ready within {self.ready_timeout} seconds"
            f"{self._format_socket_state()}{stderr}"
        )

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
            self._process = None
            self._owns_process = False
            self._unregister_atexit()
            self._close_stderr_file()
            return

        process = self._process
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self.stop_timeout)
        finally:
            self._cleanup_socket_after_stop()
            self._process = None
            self._owns_process = False
            self._unregister_atexit()
            self._close_stderr_file()

    def __enter__(self) -> YDoToolDaemon:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False


@dataclass(slots=True)
class PyYDoTool:
    socket_path: str | None = None
    check_commands_on_init: bool = True
    type_delay_ms: int = 0
    clipboard_backend: str | None = None
    command_timeout: float | None = 5.0
    _env: dict[str, str] = field(init=False, repr=False)
    _clipboard: ClipboardBackend | None = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        self.socket_path = self.socket_path or os.environ.get(
            "YDOTOOL_SOCKET",
            "/tmp/.ydotool_socket",
        )
        self._env = os.environ.copy()
        self._env["YDOTOOL_SOCKET"] = self.socket_path

        if self.check_commands_on_init:
            self._ensure_command("ydotool")

    def _ensure_command(self, name: str) -> None:
        if shutil.which(name) is None:
            raise CommandNotFoundError(f"Required command not found: {name}")

    def _run(
        self,
        *args: str,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["ydotool", *args],
                text=True,
                capture_output=True,
                check=True,
                env=self._env,
                timeout=self.command_timeout if timeout is None else timeout,
            )
        except subprocess.TimeoutExpired as exc:
            cmd = exc.cmd if isinstance(exc.cmd, list) else [str(exc.cmd)]
            raise CommandTimeoutError(
                f"ydotool timed out after {exc.timeout} seconds: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise CommandNotFoundError("Required command not found: ydotool") from exc
        except subprocess.CalledProcessError as exc:
            raise CommandExecutionError(
                f"ydotool failed: {' '.join(exc.cmd)}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
            ) from exc

    def _run_command(
        self,
        command: list[str],
        *,
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                text=True,
                input=input_text,
                capture_output=True,
                check=True,
                timeout=self.command_timeout if timeout is None else timeout,
            )
        except subprocess.TimeoutExpired as exc:
            cmd = exc.cmd if isinstance(exc.cmd, list) else [str(exc.cmd)]
            raise CommandTimeoutError(
                f"command timed out after {exc.timeout} seconds: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError as exc:
            raise CommandNotFoundError(f"Required command not found: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            raise CommandExecutionError(
                f"command failed: {' '.join(exc.cmd)}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
            ) from exc

    def _get_clipboard_backend(self) -> ClipboardBackend:
        if self._clipboard is None:
            self._clipboard = detect_clipboard_backend(self.clipboard_backend)
        return self._clipboard

    def daemon(
        self,
        *,
        ready_timeout: float = 5.0,
        stop_timeout: float = 1.0,
        extra_args: Iterable[str] = (),
        clean_stale_socket: bool = True,
    ) -> YDoToolDaemon:
        return YDoToolDaemon(
            self,
            ready_timeout=ready_timeout,
            stop_timeout=stop_timeout,
            extra_args=extra_args,
            clean_stale_socket=clean_stale_socket,
        )

    @staticmethod
    def _event(keycode: int, pressed: bool) -> str:
        return f"{keycode}:{1 if pressed else 0}"

    @staticmethod
    def _mouse_event(button: str, *, down: bool = False, up: bool = False) -> str:
        base = int(button, 16) & 0x3F
        mask = 0
        if down:
            mask |= 0x40
        if up:
            mask |= 0x80
        return f"0x{base | mask:02X}"

    def sleep(self, seconds: float) -> None:
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
        for keycode in keycodes:
            self.press(keycode)
            if interval > 0:
                time.sleep(interval)

    @contextmanager
    def hold_keys(self, *keycodes: int) -> Iterator[None]:
        pressed: list[int] = []
        try:
            for keycode in keycodes:
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
        args = ["type"]
        if self.type_delay_ms > 0:
            args.extend(["--key-delay", str(self.type_delay_ms)])
        args.append(text)
        self._run(*args)

    write = type

    def type_or_paste(
        self,
        text: str,
        *,
        prefer_paste: bool = False,
        paste_threshold: int = 128,
    ) -> None:
        if prefer_paste or "\n" in text or len(text) >= paste_threshold:
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
        self.click_many(2, button=button, next_delay_ms=int(interval * 1000))

    def mouse_down(self, button: str = MouseButton.LEFT) -> None:
        self._run("click", self._mouse_event(button, down=True))

    def mouse_up(self, button: str = MouseButton.LEFT) -> None:
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
        with self.hold_keys(*keycodes):
            self.click(button)

    def move_to(self, x: int, y: int) -> None:
        self._run("mousemove", "--absolute", str(x), str(y))

    def move_rel(self, dx: int, dy: int) -> None:
        self._run("mousemove", str(dx), str(dy))

    def drag_to(self, x: int, y: int, button: str = MouseButton.LEFT) -> None:
        with self.hold_button(button):
            self.move_to(x, y)

    def drag_rel(self, dx: int, dy: int, button: str = MouseButton.LEFT) -> None:
        with self.hold_button(button):
            self.move_rel(dx, dy)

    def click_at(
        self,
        x: int,
        y: int,
        button: str = MouseButton.LEFT,
        *,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        self.move_to(x, y)
        self.click(button, repeat=repeat, next_delay_ms=next_delay_ms)

    def double_click_at(
        self, x: int, y: int, button: str = MouseButton.LEFT, interval: float = 0.1
    ) -> None:
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
    ) -> None:
        self.move_to(start_x, start_y)
        self.drag_to(end_x, end_y, button)

    def copy(self, text: str) -> None:
        backend = self._get_clipboard_backend()
        self._run_command(list(backend.copy_command), input_text=text)

    def get_clipboard(self) -> str:
        backend = self._get_clipboard_backend()
        result = self._run_command(list(backend.paste_command))
        return result.stdout

    def paste(self) -> None:
        from .keys import Key

        self.hotkey(Key.CTRL, Key.V)

    def paste_text(self, text: str) -> None:
        self.copy(text)
        self.paste()

    def select_all(self) -> None:
        from .keys import Key

        self.hotkey(Key.CTRL, Key.A)

    def copy_selected(self, wait: float = 0.05) -> str:
        from .keys import Key

        self.hotkey(Key.CTRL, Key.C)
        if wait > 0:
            time.sleep(wait)
        return self.get_clipboard()

    def cut_selected(self, wait: float = 0.05) -> str:
        from .keys import Key

        self.hotkey(Key.CTRL, Key.X)
        if wait > 0:
            time.sleep(wait)
        return self.get_clipboard()

    def position(self) -> tuple[int, int]:
        raise NotImplementedError("Current mouse position is not supported yet.")
