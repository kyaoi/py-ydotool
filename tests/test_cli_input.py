from __future__ import annotations

from contextlib import nullcontext

import pytest

from py_ydotool import Key, MouseButton, cli


class _FakeTool:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[object, ...]] = []

    def daemon(self, **kwargs):
        self.calls.append(("daemon", kwargs))
        return nullcontext()

    def type(self, text: str) -> None:
        self.calls.append(("type", text))

    def hotkey(self, *keycodes: int) -> None:
        self.calls.append(("hotkey", *keycodes))

    def press_many(self, keycodes: list[int], *, interval: float = 0.0) -> None:
        self.calls.append(("press_many", list(keycodes), interval))

    def click(
        self,
        *,
        button: str = MouseButton.LEFT,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        self.calls.append(("click", button, repeat, next_delay_ms))

    def move_to(
        self,
        x: int,
        y: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        self.calls.append(("move_to", x, y, duration, steps))

    def move_rel(
        self,
        dx: int,
        dy: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        self.calls.append(("move_rel", dx, dy, duration, steps))

    def click_at(
        self,
        x: int,
        y: int,
        *,
        button: str = MouseButton.LEFT,
        repeat: int | None = None,
        next_delay_ms: int | None = None,
    ) -> None:
        self.calls.append(("click_at", x, y, button, repeat, next_delay_ms))

    def double_click(self, *, button: str = MouseButton.LEFT, interval: float = 0.1) -> None:
        self.calls.append(("double_click", button, interval))

    def mouse_down(self, *, button: str = MouseButton.LEFT) -> None:
        self.calls.append(("mouse_down", button))

    def mouse_up(self, *, button: str = MouseButton.LEFT) -> None:
        self.calls.append(("mouse_up", button))

    def drag_between(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        *,
        button: str = MouseButton.LEFT,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        self.calls.append(("drag_between", start_x, start_y, end_x, end_y, button, duration, steps))

    def copy(self, text: str) -> None:
        self.calls.append(("copy", text))

    def get_clipboard(self) -> str:
        self.calls.append(("get_clipboard",))
        return "clipboard text"

    def paste(self) -> None:
        self.calls.append(("paste",))

    def paste_text(self, text: str) -> None:
        self.calls.append(("paste_text", text))


@pytest.fixture
def fake_tool_factory(monkeypatch: pytest.MonkeyPatch):
    instances: list[_FakeTool] = []

    def factory(**kwargs):
        tool = _FakeTool(**kwargs)
        instances.append(tool)
        return tool

    monkeypatch.setattr(cli, "PyYDoTool", factory)
    return instances


def _last_tool(instances: list[_FakeTool]) -> _FakeTool:
    assert instances, "PyYDoTool was not constructed"
    return instances[-1]


def test_cli_type_invokes_tool_type(fake_tool_factory) -> None:
    exit_code = cli.main(["type", "hello"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("type", "hello")


def test_cli_press_invokes_hotkey_for_named_keys(fake_tool_factory) -> None:
    exit_code = cli.main(["press", "CTRL", "V", "--hotkey"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("hotkey", Key.CTRL, Key.V)


def test_cli_press_invokes_press_many_for_numeric_keycodes(fake_tool_factory) -> None:
    exit_code = cli.main(["press", str(Key.J), str(Key.ENTER), "--interval", "0.2"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("press_many", [Key.J, Key.ENTER], 0.2)


def test_cli_click_invokes_click_with_named_button(fake_tool_factory) -> None:
    exit_code = cli.main(["click", "--button", "right", "--repeat", "2", "--next-delay-ms", "50"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("click", MouseButton.RIGHT, 2, 50)


def test_cli_move_invokes_move_to_by_default(fake_tool_factory) -> None:
    exit_code = cli.main(["move", "400", "220"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("move_to", 400, 220, 0.0, None)


def test_cli_move_invokes_move_rel_with_relative_flag(fake_tool_factory) -> None:
    exit_code = cli.main(["move", "25", "-10", "--relative"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("move_rel", 25, -10, 0.0, None)


def test_cli_move_forwards_duration_and_steps_to_move_to(fake_tool_factory) -> None:
    exit_code = cli.main(["move", "400", "220", "--duration", "0.4", "--steps", "6"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("move_to", 400, 220, 0.4, 6)


def test_cli_click_at_invokes_click_at(fake_tool_factory) -> None:
    exit_code = cli.main(
        [
            "click-at",
            "400",
            "220",
            "--button",
            "middle",
            "--repeat",
            "2",
            "--next-delay-ms",
            "50",
        ]
    )

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("click_at", 400, 220, MouseButton.MIDDLE, 2, 50)


def test_cli_double_click_invokes_double_click(fake_tool_factory) -> None:
    exit_code = cli.main(["double-click", "--button", "right", "--interval", "0.2"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("double_click", MouseButton.RIGHT, 0.2)


def test_cli_mouse_down_and_mouse_up_invoke_tool_methods(fake_tool_factory) -> None:
    down_exit_code = cli.main(["mouse-down", "--button", "left"])
    up_exit_code = cli.main(["mouse-up", "--button", "task"])

    assert down_exit_code == 0
    assert up_exit_code == 0
    assert fake_tool_factory[0].calls[-1] == ("mouse_down", MouseButton.LEFT)
    assert fake_tool_factory[1].calls[-1] == ("mouse_up", MouseButton.TASK)


def test_cli_drag_invokes_drag_between(fake_tool_factory) -> None:
    exit_code = cli.main(["drag", "10", "20", "300", "400", "--button", "right"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == (
        "drag_between",
        10,
        20,
        300,
        400,
        MouseButton.RIGHT,
        0.0,
        None,
    )


def test_cli_move_forwards_duration_and_steps_to_move_rel(fake_tool_factory) -> None:
    exit_code = cli.main(["move", "25", "-10", "--relative", "--duration", "0.3", "--steps", "5"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("move_rel", 25, -10, 0.3, 5)


def test_cli_copy_invokes_copy_and_forwards_backend(fake_tool_factory) -> None:
    exit_code = cli.main(["copy", "hello", "--backend", "xclip"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert "socket_path" not in tool.kwargs
    assert tool.kwargs["clipboard_backend"] == "xclip"
    assert tool.calls == [("copy", "hello")]


def test_cli_get_clipboard_prints_output_and_forwards_backend(
    fake_tool_factory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["get-clipboard", "--backend", "wl-clipboard"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert "socket_path" not in tool.kwargs
    assert tool.kwargs["clipboard_backend"] == "wl-clipboard"
    assert tool.calls == [("get_clipboard",)]
    assert capsys.readouterr().out == "clipboard text"


def test_cli_paste_invokes_paste(fake_tool_factory) -> None:
    exit_code = cli.main(["paste"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == ("paste",)


def test_cli_paste_text_invokes_paste_text_and_forwards_backend(fake_tool_factory) -> None:
    exit_code = cli.main(["paste-text", "hello", "--backend", "xsel"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.kwargs["clipboard_backend"] == "xsel"
    assert tool.calls[-1] == ("paste_text", "hello")


def test_cli_copy_normalizes_backend_name(fake_tool_factory) -> None:
    exit_code = cli.main(["copy", "hello", "--backend", "XCLIP"])

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.kwargs["clipboard_backend"] == "xclip"


def test_cli_copy_rejects_unknown_backend(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["copy", "hello", "--backend", "banana"])

    assert excinfo.value.code == 2
    stderr = capsys.readouterr().err
    assert "unknown clipboard backend" in stderr
    assert "Supported backends: wl-clipboard, xclip, xsel" in stderr


def test_cli_press_rejects_interval_with_hotkey() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["press", "CTRL", "V", "--hotkey", "--interval", "0.2"])

    assert excinfo.value.code == 2


def test_cli_click_rejects_unknown_button() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["click", "--button", "banana"])

    assert excinfo.value.code == 2


def test_cli_drag_rejects_unknown_button() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["drag", "1", "2", "3", "4", "--button", "banana"])

    assert excinfo.value.code == 2


def test_cli_drag_forwards_duration_and_steps(fake_tool_factory) -> None:
    exit_code = cli.main(
        [
            "drag",
            "10",
            "20",
            "300",
            "400",
            "--button",
            "right",
            "--duration",
            "0.5",
            "--steps",
            "12",
        ]
    )

    assert exit_code == 0
    tool = _last_tool(fake_tool_factory)
    assert tool.calls[-1] == (
        "drag_between",
        10,
        20,
        300,
        400,
        MouseButton.RIGHT,
        0.5,
        12,
    )


def test_cli_move_rejects_negative_duration(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["move", "400", "220", "--duration", "-0.1"])

    assert excinfo.value.code == 2
    assert "duration must be >= 0" in capsys.readouterr().err


def test_cli_drag_rejects_non_positive_steps(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["drag", "10", "20", "300", "400", "--steps", "0"])

    assert excinfo.value.code == 2
    assert "steps must be > 0" in capsys.readouterr().err


def test_cli_move_rejects_steps_without_duration(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["move", "400", "220", "--steps", "6"])

    assert excinfo.value.code == 2
    assert "--steps requires --duration > 0" in capsys.readouterr().err


def test_cli_drag_rejects_steps_without_duration(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["drag", "10", "20", "300", "400", "--steps", "12"])

    assert excinfo.value.code == 2
    assert "--steps requires --duration > 0" in capsys.readouterr().err


def test_cli_copy_rejects_socket_path_option() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["copy", "hello", "--socket-path", "/tmp/demo.sock"])

    assert excinfo.value.code == 2


def test_cli_get_clipboard_rejects_socket_path_option() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["get-clipboard", "--socket-path", "/tmp/demo.sock"])

    assert excinfo.value.code == 2
