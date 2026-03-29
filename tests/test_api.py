import subprocess
from subprocess import CompletedProcess

import pytest

from py_ydotool import CommandTimeoutError, Key, MouseButton, PyYDoTool
from py_ydotool.clipboard import ClipboardBackend


def test_imports() -> None:
    assert PyYDoTool is not None
    assert Key.ENTER == 28
    assert MouseButton.LEFT == "0xC0"


def test_init_without_command_check() -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    assert tool.socket_path is not None
    assert tool.type_delay_ms == 0


def test_init_has_default_command_timeout() -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    assert tool.command_timeout == 5.0


def test_run_uses_configured_timeout(monkeypatch) -> None:
    seen: list[float | None] = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs.get("timeout"))
        return CompletedProcess(["ydotool", "key", "28:1", "28:0"], 0, "", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False, command_timeout=1.25)
    tool.press(Key.ENTER)

    assert seen == [1.25]


def test_run_command_uses_configured_timeout(monkeypatch) -> None:
    seen: list[float | None] = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs.get("timeout"))
        return CompletedProcess(["paste-cmd"], 0, "clipboard text", "")

    def fake_backend(self: PyYDoTool) -> ClipboardBackend:
        return ClipboardBackend(
            name="test",
            copy_command=("copy-cmd",),
            paste_command=("paste-cmd",),
        )

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)
    monkeypatch.setattr(PyYDoTool, "_get_clipboard_backend", fake_backend)

    tool = PyYDoTool(check_commands_on_init=False, command_timeout=2.5)
    tool.get_clipboard()

    assert seen == [2.5]


def test_run_timeout_raises_command_timeout_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["ydotool", "key", "28:1", "28:0"], timeout=1.0)

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False, command_timeout=1.0)

    with pytest.raises(CommandTimeoutError):
        tool.press(Key.ENTER)


def test_run_command_timeout_raises_command_timeout_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["paste-cmd"], timeout=2.0)

    def fake_backend(self: PyYDoTool) -> ClipboardBackend:
        return ClipboardBackend(
            name="test",
            copy_command=("copy-cmd",),
            paste_command=("paste-cmd",),
        )

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)
    monkeypatch.setattr(PyYDoTool, "_get_clipboard_backend", fake_backend)

    tool = PyYDoTool(check_commands_on_init=False, command_timeout=2.0)

    with pytest.raises(CommandTimeoutError):
        tool.get_clipboard()


def test_press_calls_key_events(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.press(Key.ENTER)

    assert calls == [("key", "28:1", "28:0")]


def test_hotkey_calls_down_then_up(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.hotkey(Key.CTRL, Key.V)

    assert calls == [
        ("key", "29:1"),
        ("key", "47:1"),
        ("key", "47:0"),
        ("key", "29:0"),
    ]


def test_type_without_delay(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.type("hello")

    assert calls == [("type", "hello")]


def test_type_with_delay(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False, type_delay_ms=12)
    tool.type("hello")

    assert calls == [("type", "--key-delay", "12", "hello")]


def test_write_alias(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.write("hello")

    assert calls == [("type", "hello")]


def test_type_or_paste_prefers_type_for_short_text(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_write(self: PyYDoTool, text: str) -> None:
        calls.append(("write", text))

    def fake_paste_text(self: PyYDoTool, text: str) -> None:
        calls.append(("paste_text", text))

    monkeypatch.setattr(PyYDoTool, "write", fake_write)
    monkeypatch.setattr(PyYDoTool, "paste_text", fake_paste_text)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.type_or_paste("hello")

    assert calls == [("write", "hello")]


def test_type_or_paste_prefers_paste_for_multiline(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_write(self: PyYDoTool, text: str) -> None:
        calls.append(("write", text))

    def fake_paste_text(self: PyYDoTool, text: str) -> None:
        calls.append(("paste_text", text))

    monkeypatch.setattr(PyYDoTool, "write", fake_write)
    monkeypatch.setattr(PyYDoTool, "paste_text", fake_paste_text)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.type_or_paste("hello\nworld")

    assert calls == [("paste_text", "hello\nworld")]


def test_click_many_passes_repeat_and_delay(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.click_many(3, next_delay_ms=50)

    assert calls == [("click", "--next-delay", "50", "--repeat", "3", "0xC0")]


def test_double_click_uses_click_many(monkeypatch) -> None:
    calls: list[tuple[int, str, int | None]] = []

    def fake_click_many(
        self: PyYDoTool,
        repeat: int,
        button: str = MouseButton.LEFT,
        *,
        next_delay_ms: int | None = None,
    ) -> None:
        calls.append((repeat, button, next_delay_ms))

    monkeypatch.setattr(PyYDoTool, "click_many", fake_click_many)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.double_click(MouseButton.RIGHT, interval=0.25)

    assert calls == [(2, MouseButton.RIGHT, 250)]


def test_click_helpers(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.click()
    tool.right_click()
    tool.middle_click()
    tool.side_click()
    tool.extra_click()
    tool.forward_click()
    tool.back_click()
    tool.task_click()

    assert calls == [
        ("click", "0xC0"),
        ("click", "0xC1"),
        ("click", "0xC2"),
        ("click", "0xC3"),
        ("click", "0xC4"),
        ("click", "0xC5"),
        ("click", "0xC6"),
        ("click", "0xC7"),
    ]


def test_mouse_down_and_mouse_up(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.mouse_down()
    tool.mouse_up()
    tool.mouse_down(MouseButton.RIGHT)
    tool.mouse_up(MouseButton.MIDDLE)

    assert calls == [
        ("click", "0x40"),
        ("click", "0x80"),
        ("click", "0x41"),
        ("click", "0x82"),
    ]


def test_drag_to_calls_down_move_up(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_to(100, 200)

    assert calls == [
        ("mouse_down", MouseButton.LEFT),
        ("move_to", (100, 200)),
        ("mouse_up", MouseButton.LEFT),
    ]


def test_drag_rel_calls_down_move_up(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_rel(self: PyYDoTool, dx: int, dy: int) -> None:
        calls.append(("move_rel", (dx, dy)))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_rel", fake_move_rel)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_rel(-5, 8, MouseButton.RIGHT)

    assert calls == [
        ("mouse_down", MouseButton.RIGHT),
        ("move_rel", (-5, 8)),
        ("mouse_up", MouseButton.RIGHT),
    ]


def test_drag_to_releases_button_when_move_fails(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))
        raise RuntimeError("move failed")

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(RuntimeError, match="move failed"):
        tool.drag_to(100, 200)

    assert calls == [
        ("mouse_down", MouseButton.LEFT),
        ("move_to", (100, 200)),
        ("mouse_up", MouseButton.LEFT),
    ]


def test_move_helpers(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        calls.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.move_to(100, 200)
    tool.move_rel(-5, 8)

    assert calls == [
        ("mousemove", "--absolute", "100", "200"),
        ("mousemove", "-5", "8"),
    ]


def test_click_at_moves_then_clicks(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))

    def fake_click(
        self: PyYDoTool,
        button: str = MouseButton.LEFT,
        *,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        calls.append(("click", (button, repeat, next_delay_ms)))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "click", fake_click)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.click_at(10, 20, MouseButton.RIGHT, repeat=2, next_delay_ms=30)

    assert calls == [
        ("move_to", (10, 20)),
        ("click", (MouseButton.RIGHT, 2, 30)),
    ]


def test_double_click_at_moves_then_double_clicks(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))

    def fake_double_click(
        self: PyYDoTool,
        button: str = MouseButton.LEFT,
        interval: float = 0.1,
    ) -> None:
        calls.append(("double_click", (button, interval)))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "double_click", fake_double_click)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.double_click_at(10, 20, MouseButton.MIDDLE, interval=0.25)

    assert calls == [
        ("move_to", (10, 20)),
        ("double_click", (MouseButton.MIDDLE, 0.25)),
    ]


def test_click_at_helpers(monkeypatch) -> None:
    calls: list[tuple[int, int, str]] = []

    def fake_click_at(
        self: PyYDoTool,
        x: int,
        y: int,
        button: str = MouseButton.LEFT,
        *,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        calls.append((x, y, button))

    monkeypatch.setattr(PyYDoTool, "click_at", fake_click_at)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.right_click_at(1, 2)
    tool.middle_click_at(3, 4)

    assert calls == [
        (1, 2, MouseButton.RIGHT),
        (3, 4, MouseButton.MIDDLE),
    ]


def test_drag_between_moves_then_drags(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))

    def fake_drag_to(self: PyYDoTool, x: int, y: int, button: str = MouseButton.LEFT) -> None:
        calls.append(("drag_to", (x, y, button)))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "drag_to", fake_drag_to)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_between(1, 2, 10, 20, MouseButton.RIGHT)

    assert calls == [
        ("move_to", (1, 2)),
        ("drag_to", (10, 20, MouseButton.RIGHT)),
    ]


def test_press_many(monkeypatch) -> None:
    calls: list[int] = []

    def fake_press(self: PyYDoTool, keycode: int) -> None:
        calls.append(keycode)

    monkeypatch.setattr(PyYDoTool, "press", fake_press)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.press_many([Key.J, Key.L, Key.T])

    assert calls == [Key.J, Key.L, Key.T]


def test_copy_calls_backend_command(monkeypatch) -> None:
    calls: list[tuple[list[str], str | None]] = []

    def fake_get_clipboard_backend(self: PyYDoTool) -> ClipboardBackend:
        return ClipboardBackend(
            name="test",
            copy_command=("copy-cmd", "--copy"),
            paste_command=("paste-cmd", "--paste"),
        )

    def fake_run_command(
        self: PyYDoTool,
        command: list[str],
        *,
        input_text: str | None = None,
    ) -> CompletedProcess[str]:
        calls.append((command, input_text))
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(PyYDoTool, "_get_clipboard_backend", fake_get_clipboard_backend)
    monkeypatch.setattr(PyYDoTool, "_run_command", fake_run_command)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.copy("abc")

    assert calls == [(["copy-cmd", "--copy"], "abc")]


def test_get_clipboard_returns_stdout(monkeypatch) -> None:
    def fake_get_clipboard_backend(self: PyYDoTool) -> ClipboardBackend:
        return ClipboardBackend(
            name="test",
            copy_command=("copy-cmd",),
            paste_command=("paste-cmd", "--paste"),
        )

    def fake_run_command(
        self: PyYDoTool,
        command: list[str],
        *,
        input_text: str | None = None,
    ) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, "clipboard text", "")

    monkeypatch.setattr(PyYDoTool, "_get_clipboard_backend", fake_get_clipboard_backend)
    monkeypatch.setattr(PyYDoTool, "_run_command", fake_run_command)

    tool = PyYDoTool(check_commands_on_init=False)

    assert tool.get_clipboard() == "clipboard text"


def test_paste_text_uses_copy_and_hotkey(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_copy(self: PyYDoTool, text: str) -> None:
        calls.append(("copy", text))

    def fake_hotkey(self: PyYDoTool, *keycodes: int) -> None:
        calls.append(("hotkey", keycodes))

    monkeypatch.setattr(PyYDoTool, "copy", fake_copy)
    monkeypatch.setattr(PyYDoTool, "hotkey", fake_hotkey)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.paste_text("hello")

    assert calls == [
        ("copy", "hello"),
        ("hotkey", (Key.CTRL, Key.V)),
    ]


def test_paste_uses_hotkey(monkeypatch) -> None:
    calls: list[tuple[int, ...]] = []

    def fake_hotkey(self: PyYDoTool, *keycodes: int) -> None:
        calls.append(keycodes)

    monkeypatch.setattr(PyYDoTool, "hotkey", fake_hotkey)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.paste()

    assert calls == [(Key.CTRL, Key.V)]


def test_select_all_uses_hotkey(monkeypatch) -> None:
    calls: list[tuple[int, ...]] = []

    def fake_hotkey(self: PyYDoTool, *keycodes: int) -> None:
        calls.append(keycodes)

    monkeypatch.setattr(PyYDoTool, "hotkey", fake_hotkey)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.select_all()

    assert calls == [(Key.CTRL, Key.A)]


def test_copy_selected_uses_hotkey_and_clipboard(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_hotkey(self: PyYDoTool, *keycodes: int) -> None:
        calls.append(("hotkey", keycodes))

    def fake_get_clipboard(self: PyYDoTool) -> str:
        calls.append(("get_clipboard", None))
        return "selected text"

    monkeypatch.setattr(PyYDoTool, "hotkey", fake_hotkey)
    monkeypatch.setattr(PyYDoTool, "get_clipboard", fake_get_clipboard)

    tool = PyYDoTool(check_commands_on_init=False)
    assert tool.copy_selected(wait=0.0) == "selected text"
    assert calls == [
        ("hotkey", (Key.CTRL, Key.C)),
        ("get_clipboard", None),
    ]


def test_cut_selected_uses_hotkey_and_clipboard(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_hotkey(self: PyYDoTool, *keycodes: int) -> None:
        calls.append(("hotkey", keycodes))

    def fake_get_clipboard(self: PyYDoTool) -> str:
        calls.append(("get_clipboard", None))
        return "cut text"

    monkeypatch.setattr(PyYDoTool, "hotkey", fake_hotkey)
    monkeypatch.setattr(PyYDoTool, "get_clipboard", fake_get_clipboard)

    tool = PyYDoTool(check_commands_on_init=False)
    assert tool.cut_selected(wait=0.0) == "cut text"
    assert calls == [
        ("hotkey", (Key.CTRL, Key.X)),
        ("get_clipboard", None),
    ]


def test_hold_keys_calls_down_then_up(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_key_down(self: PyYDoTool, keycode: int) -> None:
        calls.append(("down", str(keycode)))

    def fake_key_up(self: PyYDoTool, keycode: int) -> None:
        calls.append(("up", str(keycode)))

    monkeypatch.setattr(PyYDoTool, "key_down", fake_key_down)
    monkeypatch.setattr(PyYDoTool, "key_up", fake_key_up)

    tool = PyYDoTool(check_commands_on_init=False)
    with tool.hold_keys(Key.CTRL, Key.SHIFT, Key.ALT):
        calls.append(("inside",))

    assert calls == [
        ("down", "29"),
        ("down", "42"),
        ("down", "56"),
        ("inside",),
        ("up", "56"),
        ("up", "42"),
        ("up", "29"),
    ]


def test_hold_keys_releases_on_error(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_key_down(self: PyYDoTool, keycode: int) -> None:
        calls.append(("down", str(keycode)))

    def fake_key_up(self: PyYDoTool, keycode: int) -> None:
        calls.append(("up", str(keycode)))

    monkeypatch.setattr(PyYDoTool, "key_down", fake_key_down)
    monkeypatch.setattr(PyYDoTool, "key_up", fake_key_up)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(RuntimeError, match="boom"):
        with tool.hold_keys(Key.CTRL, Key.C):
            raise RuntimeError("boom")

    assert calls == [
        ("down", "29"),
        ("down", "46"),
        ("up", "46"),
        ("up", "29"),
    ]


def test_hold_button_calls_down_then_up(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("down", button))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    with tool.hold_button(MouseButton.RIGHT):
        calls.append(("inside", MouseButton.RIGHT))

    assert calls == [
        ("down", MouseButton.RIGHT),
        ("inside", MouseButton.RIGHT),
        ("up", MouseButton.RIGHT),
    ]


def test_hold_button_releases_on_error(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("down", button))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(RuntimeError, match="boom"):
        with tool.hold_button(MouseButton.MIDDLE):
            raise RuntimeError("boom")

    assert calls == [
        ("down", MouseButton.MIDDLE),
        ("up", MouseButton.MIDDLE),
    ]


def test_click_with_modifiers_holds_then_clicks(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class _HoldContext:
        def __enter__(self) -> None:
            calls.append(("hold_keys", (Key.CTRL, Key.SHIFT)))
            return None

        def __exit__(self, exc_type, exc, tb) -> None:
            calls.append(("hold_keys_done", (Key.CTRL, Key.SHIFT)))
            return None

    def fake_hold_keys(self: PyYDoTool, *keycodes: int):
        assert keycodes == (Key.CTRL, Key.SHIFT)
        return _HoldContext()

    def fake_click(self: PyYDoTool, button: str = MouseButton.LEFT, **_: object) -> None:
        calls.append(("click", button))

    monkeypatch.setattr(PyYDoTool, "hold_keys", fake_hold_keys)
    monkeypatch.setattr(PyYDoTool, "click", fake_click)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.click_with_modifiers(Key.CTRL, Key.SHIFT, button=MouseButton.RIGHT)

    assert calls == [
        ("hold_keys", (Key.CTRL, Key.SHIFT)),
        ("click", MouseButton.RIGHT),
        ("hold_keys_done", (Key.CTRL, Key.SHIFT)),
    ]
