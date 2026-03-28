from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from .clipboard import ClipboardBackend, detect_clipboard_backend
from .exceptions import CommandExecutionError, CommandNotFoundError


class MouseButton:
    LEFT = "0xC0"
    RIGHT = "0xC1"
    MIDDLE = "0xC2"
    SIDE = "0xC3"
    EXTRA = "0xC4"
    FORWARD = "0xC5"
    BACK = "0xC6"
    TASK = "0xC7"


@dataclass(slots=True)
class PyYDoTool:
    socket_path: str | None = None
    check_commands_on_init: bool = True
    type_delay_ms: int = 0
    clipboard_backend: str | None = None
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

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["ydotool", *args],
                text=True,
                capture_output=True,
                check=True,
                env=self._env,
            )
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
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                text=True,
                input=input_text,
                capture_output=True,
                check=True,
            )
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
