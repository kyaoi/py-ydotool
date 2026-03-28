from subprocess import CompletedProcess

import pytest

from py_ydotool import Key, MouseButton, PyYDoTool
from py_ydotool.clipboard import ClipboardBackend


def test_imports() -> None:
    assert PyYDoTool is not None
    assert Key.ENTER == 28
    assert MouseButton.LEFT == "0xC0"


def test_init_without_command_check() -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    assert tool.socket_path is not None
    assert tool.type_delay_ms == 0


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

    assert calls == [
        ("click", "0xC0"),
        ("click", "0xC1"),
        ("click", "0xC2"),
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
