import math
import os
import stat
import subprocess
from contextlib import contextmanager
from subprocess import CompletedProcess

import pytest

from py_ydotool import (
    CommandExecutionError,
    CommandNotFoundError,
    CommandTimeoutError,
    DaemonReadyTimeoutError,
    DaemonStartError,
    Key,
    MouseButton,
    PyYDoTool,
)
from py_ydotool.client import _build_linear_motion_steps, _run_motion_steps
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


def test_init_rejects_empty_socket_path() -> None:
    with pytest.raises(ValueError, match="socket_path must not be empty"):
        PyYDoTool(socket_path="", check_commands_on_init=False)


def test_init_rejects_negative_command_timeout() -> None:
    with pytest.raises(ValueError, match="command_timeout must be >= 0"):
        PyYDoTool(check_commands_on_init=False, command_timeout=-0.1)


@pytest.mark.parametrize("value", [True, False, "1.0"])
def test_init_rejects_non_numeric_command_timeout(value: object) -> None:
    with pytest.raises(TypeError, match="command_timeout must be a real number"):
        PyYDoTool(check_commands_on_init=False, command_timeout=value)


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_init_rejects_non_finite_command_timeout(value: float) -> None:
    with pytest.raises(ValueError, match="command_timeout must be finite"):
        PyYDoTool(check_commands_on_init=False, command_timeout=value)


def test_init_rejects_empty_clipboard_backend() -> None:
    with pytest.raises(ValueError, match="clipboard_backend must not be empty"):
        PyYDoTool(check_commands_on_init=False, clipboard_backend="")


def test_doctor_report_rejects_empty_group() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="group must not be empty"):
        tool.doctor_report(group="")


def test_doctor_report_uses_tool_socket_path(monkeypatch) -> None:
    tool = PyYDoTool(socket_path="/tmp/custom.sock", check_commands_on_init=False)
    seen: dict[str, object] = {}

    def fake_collect_doctor_report(**kwargs):
        seen.update(kwargs)
        return "report"

    monkeypatch.setattr("py_ydotool._system.collect_doctor_report", fake_collect_doctor_report)

    report = tool.doctor_report(user="alice", group="uinput-users")

    assert report == "report"
    assert seen["socket_path"] == "/tmp/custom.sock"
    assert seen["user"] == "alice"
    assert seen["group"] == "uinput-users"


def test_doctor_text_renders_report(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    monkeypatch.setattr(
        "py_ydotool.client.PyYDoTool.doctor_report",
        lambda self, **_: "report",
    )
    monkeypatch.setattr(
        "py_ydotool._system.render_doctor_report",
        lambda report, stream=None: f"text:{report}",
    )

    assert tool.doctor_text() == "text:report"


def test_setup_plan_uses_tool_socket_path() -> None:
    tool = PyYDoTool(socket_path="/tmp/custom.sock", check_commands_on_init=False)

    plan = tool.setup_plan(target_user="alice", group="uinput-users", dry_run=True)

    assert plan.target_user == "alice"
    assert plan.group == "uinput-users"


def test_setup_plan_rejects_empty_target_user() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="target_user must not be empty"):
        tool.setup_plan(target_user="", dry_run=True)


def test_setup_plan_text_renders_plan(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    monkeypatch.setattr(
        "py_ydotool.client.PyYDoTool.setup_plan",
        lambda self, **_: "plan",
    )
    monkeypatch.setattr(
        "py_ydotool._system.render_setup_plan",
        lambda plan, dry_run: f"text:{plan}:{dry_run}",
    )

    assert tool.setup_plan_text(dry_run=True) == "text:plan:True"


def test_run_uses_configured_timeout(monkeypatch) -> None:
    seen: list[float | None] = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs.get("timeout"))
        return CompletedProcess(["ydotool", "key", "28:1", "28:0"], 0, "", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False, command_timeout=1.25)
    tool.press(Key.ENTER)

    assert seen == [1.25]


def test_run_clipboard_command_uses_backend_command_for(monkeypatch) -> None:
    seen_commands: list[list[str]] = []

    def fake_run(*args, **kwargs):
        seen_commands.append(args[0])
        return CompletedProcess(args[0], 0, "", "")

    backend = ClipboardBackend(
        name="test",
        copy_command=("copy-cmd",),
        paste_command=("paste-cmd",),
        required_commands=("copy-cmd",),
    )

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)
    tool._clipboard = backend

    tool.copy("hello")
    tool.get_clipboard()

    assert seen_commands == [["copy-cmd"], ["paste-cmd"]]


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


def test_missing_command_error_includes_doctor_hint(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool.client.shutil.which", lambda _: None)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(CommandNotFoundError) as exc_info:
        tool._ensure_command("ydotool")

    message = str(exc_info.value)
    assert "py-ydotool doctor" in message
    assert "PATH" in message


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


def test_daemon_rejects_negative_timing_values() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="ready_timeout must be >= 0"):
        tool.daemon(ready_timeout=-0.1)

    with pytest.raises(ValueError, match="stop_timeout must be >= 0"):
        tool.daemon(stop_timeout=-0.1)

    with pytest.raises(ValueError, match="settle_delay must be >= 0"):
        tool.daemon(settle_delay=-0.1)


def test_daemon_rejects_non_string_extra_args() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(TypeError, match=r"extra_args\[1\] must be a str"):
        tool.daemon(extra_args=("--socket-own", 123))


def test_daemon_stop_waits_for_remaining_quiet_period(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon(settle_delay=0.25)

    sleep_calls: list[float] = []
    events: list[str] = []

    class FakeProcess:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            events.append("terminate")

        def wait(self, timeout: float | None = None) -> int:
            events.append(f"wait:{timeout}")
            return 0

    monkeypatch.setattr("py_ydotool.client.time.monotonic", lambda: 10.1)
    monkeypatch.setattr(
        "py_ydotool.client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    monkeypatch.setattr(
        daemon,
        "_cleanup_socket_after_stop",
        lambda: events.append("cleanup"),
    )
    monkeypatch.setattr(
        daemon,
        "_unregister_atexit",
        lambda: events.append("unregister"),
    )
    monkeypatch.setattr(
        daemon,
        "_close_stderr_file",
        lambda: events.append("close-stderr"),
    )

    daemon._last_activity_at = 10.0
    daemon._process = FakeProcess()
    daemon._owns_process = True

    daemon.stop()

    assert sleep_calls == [pytest.approx(0.15)]
    assert events == ["terminate", "wait:1.0", "cleanup", "unregister", "close-stderr"]


def test_daemon_stop_skips_quiet_period_without_recent_activity(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon(settle_delay=0.25)

    sleep_calls: list[float] = []
    events: list[str] = []

    class FakeProcess:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            events.append("terminate")

        def wait(self, timeout: float | None = None) -> int:
            events.append(f"wait:{timeout}")
            return 0

    monkeypatch.setattr(
        "py_ydotool.client.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    monkeypatch.setattr(
        daemon,
        "_cleanup_socket_after_stop",
        lambda: events.append("cleanup"),
    )
    monkeypatch.setattr(
        daemon,
        "_unregister_atexit",
        lambda: events.append("unregister"),
    )
    monkeypatch.setattr(
        daemon,
        "_close_stderr_file",
        lambda: events.append("close-stderr"),
    )

    daemon._process = FakeProcess()
    daemon._owns_process = True

    daemon.stop()

    assert sleep_calls == []
    assert events == ["terminate", "wait:1.0", "cleanup", "unregister", "close-stderr"]


def test_run_records_input_activity_for_active_daemon(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()

    monkeypatch.setattr(
        "py_ydotool.client.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(["ydotool", "key", "28:1"], 0, "", ""),
    )
    monkeypatch.setattr("py_ydotool.client.time.monotonic", lambda: 123.45)

    tool._register_daemon_context(daemon)
    tool._run("key", "28:1")

    assert daemon._last_activity_at == 123.45


def test_run_does_not_record_debug_as_input_activity(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()

    monkeypatch.setattr(
        "py_ydotool.client.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(["ydotool", "debug"], 0, "", ""),
    )
    monkeypatch.setattr("py_ydotool.client.time.monotonic", lambda: 456.0)

    tool._register_daemon_context(daemon)
    tool._run("debug")

    assert daemon._last_activity_at is None


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

    def fake_move_to(
        self: PyYDoTool,
        x: int,
        y: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        calls.append(("move_to", (x, y, duration, steps)))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_to(100, 200)

    assert calls == [
        ("mouse_down", MouseButton.LEFT),
        ("move_to", (100, 200, 0.0, None)),
        ("mouse_up", MouseButton.LEFT),
    ]


def test_drag_rel_calls_down_move_up(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_rel(
        self: PyYDoTool,
        dx: int,
        dy: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        calls.append(("move_rel", (dx, dy, duration, steps)))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_rel", fake_move_rel)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_rel(-5, 8, MouseButton.RIGHT)

    assert calls == [
        ("mouse_down", MouseButton.RIGHT),
        ("move_rel", (-5, 8, 0.0, None)),
        ("mouse_up", MouseButton.RIGHT),
    ]


def test_drag_to_releases_button_when_move_fails(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_to(
        self: PyYDoTool,
        x: int,
        y: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        calls.append(("move_to", (x, y, duration, steps)))
        raise RuntimeError("move failed")

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(RuntimeError, match="move failed"):
        tool.drag_to(100, 200, duration=0.5, steps=4)

    assert calls == [
        ("mouse_down", MouseButton.LEFT),
        ("move_to", (100, 200, 0.5, 4)),
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


def test_move_rel_with_duration_uses_interpolated_relative_steps(monkeypatch) -> None:
    commands: list[tuple[str, ...]] = []
    captured_steps: list[tuple[float, int, int]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        commands.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    def fake_run_motion_steps(motion_steps, *, move, monotonic=None, sleep=None) -> None:
        steps_tuple = tuple(motion_steps)
        captured_steps.extend((step.offset, step.dx, step.dy) for step in steps_tuple)
        for step in steps_tuple:
            move(step.dx, step.dy)

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)
    monkeypatch.setattr("py_ydotool.client._run_motion_steps", fake_run_motion_steps)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.move_rel(5, -3, duration=0.5, steps=4)

    assert captured_steps == [
        (0.125, 1, -1),
        (0.25, 1, -1),
        (0.375, 2, 0),
        (0.5, 1, -1),
    ]
    assert commands == [
        ("mousemove", "1", "-1"),
        ("mousemove", "1", "-1"),
        ("mousemove", "2", "0"),
        ("mousemove", "1", "-1"),
    ]


def test_move_to_with_duration_resets_to_current_display_origin(monkeypatch) -> None:
    commands: list[tuple[str, ...]] = []
    captured_steps: list[tuple[float, int, int]] = []

    def fake_run(self: PyYDoTool, *args: str) -> CompletedProcess[str]:
        commands.append(args)
        return CompletedProcess(["ydotool", *args], 0, "", "")

    def fake_run_motion_steps(motion_steps, *, move, monotonic=None, sleep=None) -> None:
        steps_tuple = tuple(motion_steps)
        captured_steps.extend((step.offset, step.dx, step.dy) for step in steps_tuple)
        for step in steps_tuple:
            move(step.dx, step.dy)

    monkeypatch.setattr(PyYDoTool, "_run", fake_run)
    monkeypatch.setattr("py_ydotool.client._run_motion_steps", fake_run_motion_steps)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.move_to(5, -3, duration=0.5, steps=4)

    assert captured_steps == [
        (0.125, 1, -1),
        (0.25, 1, -1),
        (0.375, 2, 0),
        (0.5, 1, -1),
    ]
    assert commands == [
        ("mousemove", "--absolute", "0", "0"),
        ("mousemove", "1", "-1"),
        ("mousemove", "1", "-1"),
        ("mousemove", "2", "0"),
        ("mousemove", "1", "-1"),
    ]


def test_drag_rel_with_duration_uses_interpolated_relative_steps(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_down", button))

    def fake_move_rel(
        self: PyYDoTool,
        dx: int,
        dy: int,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        calls.append(("move_rel", (dx, dy, duration, steps)))

    def fake_mouse_up(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        calls.append(("mouse_up", button))

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)
    monkeypatch.setattr(PyYDoTool, "move_rel", fake_move_rel)
    monkeypatch.setattr(PyYDoTool, "mouse_up", fake_mouse_up)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_rel(5, -3, MouseButton.MIDDLE, duration=0.5, steps=4)

    assert calls == [
        ("mouse_down", MouseButton.MIDDLE),
        ("move_rel", (5, -3, 0.5, 4)),
        ("mouse_up", MouseButton.MIDDLE),
    ]


def test_click_at_rejects_invalid_button_before_move(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    move_calls: list[tuple[int, int]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        move_calls.append((x, y))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)

    with pytest.raises(ValueError, match="button must be a hexadecimal string"):
        tool.click_at(10, 20, "left")

    assert move_calls == []


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


def test_double_click_at_rejects_invalid_interval_before_move(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    move_calls: list[tuple[int, int]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        move_calls.append((x, y))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)

    with pytest.raises(ValueError, match="interval must be >= 0"):
        tool.double_click_at(10, 20, interval=-0.1)

    assert move_calls == []


def test_double_click_at_rejects_invalid_button_before_move(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    move_calls: list[tuple[int, int]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        move_calls.append((x, y))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)

    with pytest.raises(ValueError, match="button must be a hexadecimal string"):
        tool.double_click_at(10, 20, "middle")

    assert move_calls == []


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


def test_drag_to_rejects_invalid_coordinates_before_mouse_down(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    mouse_down_calls: list[str] = []

    def fake_mouse_down(self: PyYDoTool, button: str = MouseButton.LEFT) -> None:
        mouse_down_calls.append(button)

    monkeypatch.setattr(PyYDoTool, "mouse_down", fake_mouse_down)

    with pytest.raises(TypeError, match="x must be an int"):
        tool.drag_to(10.5, 20)

    assert mouse_down_calls == []


def test_drag_between_rejects_invalid_button_before_initial_move(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    move_calls: list[tuple[int, int]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        move_calls.append((x, y))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)

    with pytest.raises(ValueError, match="button must be a hexadecimal string"):
        tool.drag_between(1, 2, 10, 20, "right")

    assert move_calls == []


def test_drag_between_moves_then_drags(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def fake_move_to(self: PyYDoTool, x: int, y: int) -> None:
        calls.append(("move_to", (x, y)))

    def fake_drag_to(
        self: PyYDoTool,
        x: int,
        y: int,
        button: str = MouseButton.LEFT,
        *,
        duration: float = 0.0,
        steps: int | None = None,
    ) -> None:
        calls.append(("drag_to", (x, y, button, duration, steps)))

    monkeypatch.setattr(PyYDoTool, "move_to", fake_move_to)
    monkeypatch.setattr(PyYDoTool, "drag_to", fake_drag_to)

    tool = PyYDoTool(check_commands_on_init=False)
    tool.drag_between(1, 2, 10, 20, MouseButton.RIGHT, duration=0.5, steps=4)

    assert calls == [
        ("move_to", (1, 2)),
        ("drag_to", (10, 20, MouseButton.RIGHT, 0.5, 4)),
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


def test_daemon_removes_stale_socket_before_start(monkeypatch, tmp_path) -> None:
    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            self.args = args[0]

        def poll(self):
            return None

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    class FakeStatResult:
        st_mode = stat.S_IFSOCK

    socket_path = tmp_path / "ydotool.sock"
    removed: list[str] = []
    socket_exists = True

    ready_states = iter([False, True, False])

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return next(ready_states)

    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = False):
        nonlocal socket_exists
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            assert follow_symlinks is False
            return FakeStatResult()
        return real_stat(path, follow_symlinks=follow_symlinks)

    real_unlink = os.unlink

    def fake_unlink(path: str) -> None:
        nonlocal socket_exists
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            socket_exists = False
            removed.append(os.fspath(path))
            return
        real_unlink(path)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.os.stat", fake_stat)
    monkeypatch.setattr("py_ydotool.client.os.unlink", fake_unlink)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
    daemon = tool.daemon()
    daemon.start()

    assert removed == [str(socket_path)]

    daemon.stop()


def test_daemon_keeps_non_socket_path_before_start(monkeypatch, tmp_path) -> None:
    class FakePopen:
        returncode = 2

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return 2

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def kill(self) -> None:
            return None

    socket_path = tmp_path / "ydotool.sock"
    socket_path.write_text("not a socket", encoding="utf-8")

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)

    with pytest.raises(DaemonStartError):
        tool.daemon().start()

    assert socket_path.read_text(encoding="utf-8") == "not a socket"


def test_daemon_can_disable_stale_socket_cleanup(monkeypatch, tmp_path) -> None:
    class FakePopen:
        returncode = 2

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return 2

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def kill(self) -> None:
            return None

    class FakeStatResult:
        st_mode = stat.S_IFSOCK

    socket_path = tmp_path / "ydotool.sock"
    removed: list[str] = []
    socket_exists = True

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = False):
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            assert follow_symlinks is False
            return FakeStatResult()
        return real_stat(path, follow_symlinks=follow_symlinks)

    real_unlink = os.unlink

    def fake_unlink(path: str) -> None:
        if os.fspath(path) == str(socket_path):
            removed.append(os.fspath(path))
            return
        real_unlink(path)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.os.stat", fake_stat)
    monkeypatch.setattr("py_ydotool.client.os.unlink", fake_unlink)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)

    with pytest.raises(DaemonStartError):
        tool.daemon(clean_stale_socket=False).start()

    assert removed == [str(socket_path)]


def test_daemon_socket_ready_uses_ydotool_debug(monkeypatch, tmp_path) -> None:
    socket_path = tmp_path / "ydotool.sock"
    socket_path.touch()

    def fake_run(self: PyYDoTool, *args: str, timeout: float | None = None):
        assert args == ("debug",)
        assert timeout == 0.2
        return object()

    def fake_socket_stat(*args, **kwargs):
        return type("S", (), {"st_mode": stat.S_IFSOCK})()

    monkeypatch.setattr("py_ydotool.client.os.stat", fake_socket_stat)
    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
    assert tool.daemon()._is_socket_ready() is True


def test_daemon_socket_ready_is_false_when_debug_fails(monkeypatch, tmp_path) -> None:
    socket_path = tmp_path / "ydotool.sock"
    socket_path.touch()

    def fake_run(self: PyYDoTool, *args: str, timeout: float | None = None):
        raise CommandExecutionError("debug failed")

    def fake_socket_stat(*args, **kwargs):
        return type("S", (), {"st_mode": stat.S_IFSOCK})()

    monkeypatch.setattr("py_ydotool.client.os.stat", fake_socket_stat)
    monkeypatch.setattr(PyYDoTool, "_run", fake_run)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
    assert tool.daemon()._is_socket_ready() is False


def test_daemon_stop_removes_owned_socket_when_not_ready(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    socket_path = tmp_path / "ydotool.sock"

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return None

        def terminate(self) -> None:
            calls.append("terminate")
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            calls.append(f"wait:{timeout}")
            self.returncode = 0
            return 0

        def kill(self) -> None:
            calls.append("kill")
            self.returncode = -9

    socket_exists = False
    ready_calls = 0
    removed: list[str] = []

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        nonlocal ready_calls, socket_exists
        ready_calls += 1
        if ready_calls == 1:
            return False
        if ready_calls == 2:
            socket_exists = True
            return True
        return False

    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = False):
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            return type("S", (), {"st_mode": stat.S_IFSOCK})()
        return real_stat(path, follow_symlinks=follow_symlinks)

    real_unlink = os.unlink

    def fake_unlink(path: str) -> None:
        nonlocal socket_exists
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            socket_exists = False
            removed.append(os.fspath(path))
            return
        real_unlink(path)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.os.stat", fake_stat)
    monkeypatch.setattr("py_ydotool.client.os.unlink", fake_unlink)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
    daemon = tool.daemon(stop_timeout=0.25)
    daemon.start()
    daemon.stop()

    assert calls == ["terminate", "wait:0.25"]
    assert removed == [str(socket_path)]


def test_daemon_stop_keeps_socket_when_it_is_still_ready(monkeypatch, tmp_path) -> None:
    socket_path = tmp_path / "ydotool.sock"

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return None

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    socket_exists = False
    ready_calls = 0
    removed: list[str] = []

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        nonlocal ready_calls, socket_exists
        ready_calls += 1
        if ready_calls == 1:
            return False
        socket_exists = True
        return True

    real_stat = os.stat

    def fake_stat(path: str, *, follow_symlinks: bool = False):
        if os.fspath(path) == str(socket_path):
            if not socket_exists:
                raise FileNotFoundError
            return type("S", (), {"st_mode": stat.S_IFSOCK})()
        return real_stat(path, follow_symlinks=follow_symlinks)

    real_unlink = os.unlink

    def fake_unlink(path: str) -> None:
        if os.fspath(path) == str(socket_path):
            removed.append(os.fspath(path))
            return
        real_unlink(path)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.os.stat", fake_stat)
    monkeypatch.setattr("py_ydotool.client.os.unlink", fake_unlink)

    tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
    daemon = tool.daemon()
    daemon.start()
    daemon.stop()

    assert removed == []


def test_daemon_reuses_existing_socket(monkeypatch) -> None:
    started: list[bool] = []

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return True

    def fake_popen(*args, **kwargs):
        started.append(True)
        raise AssertionError("ydotoold should not be started when socket is already ready")

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", fake_popen)

    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()
    with daemon:
        assert daemon._owns_process is False

    assert started == []


def test_daemon_reused_socket_is_registered_only_inside_context(monkeypatch) -> None:
    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return True

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)

    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()

    assert tool._active_daemons == []
    with daemon:
        assert tool._active_daemons == [daemon]

    assert tool._active_daemons == []


def test_daemon_reused_socket_does_not_register_atexit(monkeypatch) -> None:
    register_calls: list[object] = []
    unregister_calls: list[object] = []

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return True

    def fake_register(callback: object) -> object:
        register_calls.append(callback)
        return callback

    def fake_unregister(callback: object) -> None:
        unregister_calls.append(callback)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.atexit.register", fake_register)
    monkeypatch.setattr("py_ydotool.client.atexit.unregister", fake_unregister)

    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()
    daemon.start()
    daemon.stop()

    assert register_calls == []
    assert unregister_calls == []


def test_daemon_registers_and_unregisters_atexit_for_owned_process(monkeypatch) -> None:
    register_calls: list[object] = []
    unregister_calls: list[object] = []

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            self.args = args[0]

        def poll(self):
            return None

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    ready_states = iter([False, True, False])

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return next(ready_states)

    def fake_register(callback: object) -> object:
        register_calls.append(callback)
        return callback

    def fake_unregister(callback: object) -> None:
        unregister_calls.append(callback)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.atexit.register", fake_register)
    monkeypatch.setattr("py_ydotool.client.atexit.unregister", fake_unregister)

    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon()
    daemon.start()
    callback = daemon._atexit_callback
    daemon.stop()

    assert register_calls == [callback]
    assert unregister_calls == [callback]


def test_daemon_starts_and_stops_owned_process(monkeypatch) -> None:
    calls: list[str] = []

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            self.args = args[0]

        def poll(self):
            return None

        def terminate(self) -> None:
            calls.append("terminate")
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            calls.append(f"wait:{timeout}")
            self.returncode = 0
            return 0

        def kill(self) -> None:
            calls.append("kill")
            self.returncode = -9

    ready_states = iter([False, True, False])

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return next(ready_states)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(check_commands_on_init=False)
    daemon = tool.daemon(stop_timeout=0.25)
    with daemon:
        assert daemon._owns_process is True
        assert daemon._process is not None

    assert calls == ["terminate", "wait:0.25"]


def test_daemon_decorator_starts_and_stops(monkeypatch) -> None:
    calls: list[str] = []

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return None

        def terminate(self) -> None:
            calls.append("terminate")
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            calls.append("wait")
            self.returncode = 0
            return 0

        def kill(self) -> None:
            calls.append("kill")
            self.returncode = -9

    ready_states = iter([False, True, False])

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return next(ready_states)

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(check_commands_on_init=False)

    @tool.daemon()
    def run() -> str:
        calls.append("body")
        return "ok"

    assert run() == "ok"
    assert calls == ["body", "terminate", "wait"]


def test_daemon_timeout_stops_owned_process(monkeypatch) -> None:
    calls: list[str] = []

    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return None

        def terminate(self) -> None:
            calls.append("terminate")
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            calls.append("wait")
            self.returncode = 0
            return 0

        def kill(self) -> None:
            calls.append("kill")
            self.returncode = -9

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.time.sleep", lambda _: None)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(DaemonReadyTimeoutError):
        tool.daemon(ready_timeout=0.0).__enter__()

    assert calls == ["terminate", "wait"]


def test_daemon_timeout_includes_stderr(monkeypatch) -> None:
    class FakePopen:
        returncode: int | None = None

        def __init__(self, *args, **kwargs) -> None:
            kwargs["stderr"].write("permission denied")
            kwargs["stderr"].flush()

        def poll(self):
            return None

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout: float | None = None) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)
    monkeypatch.setattr("py_ydotool.client.time.sleep", lambda _: None)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(DaemonReadyTimeoutError, match="permission denied"):
        tool.daemon(ready_timeout=0.0).start()


def test_daemon_exit_early_includes_stderr(monkeypatch) -> None:
    class FakePopen:
        returncode = 2

        def __init__(self, *args, **kwargs) -> None:
            kwargs["stderr"].write("cannot open /dev/uinput")
            kwargs["stderr"].flush()

        def poll(self):
            return 2

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def kill(self) -> None:
            return None

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(DaemonStartError, match="cannot open /dev/uinput"):
        tool.daemon().start()


def test_daemon_exit_early_includes_setup_hint(monkeypatch) -> None:
    class FakePopen:
        returncode = 2

        def __init__(self, *args, **kwargs) -> None:
            kwargs["stderr"].write("cannot open /dev/uinput")
            kwargs["stderr"].flush()

        def poll(self):
            return 2

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def kill(self) -> None:
            return None

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(DaemonStartError) as exc_info:
        tool.daemon().start()

    message = str(exc_info.value)
    assert "py-ydotool setup --dry-run" in message
    assert "py-ydotool setup" in message


def test_run_command_error_includes_socket_hint(monkeypatch) -> None:
    def fake_backend(self: PyYDoTool) -> ClipboardBackend:
        return ClipboardBackend(
            name="test",
            copy_command=("copy-cmd",),
            paste_command=("paste-cmd",),
        )

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["paste-cmd"],
            output="",
            stderr="failed to connect to socket /tmp/.ydotool_socket",
        )

    monkeypatch.setattr(PyYDoTool, "_get_clipboard_backend", fake_backend)
    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(CommandExecutionError) as exc_info:
        tool.get_clipboard()

    message = str(exc_info.value)
    assert "with gui.daemon():" in message
    assert "py-ydotool doctor" in message


def test_daemon_raises_when_process_exits_early(monkeypatch) -> None:
    class FakePopen:
        returncode = 2

        def __init__(self, *args, **kwargs) -> None:
            return None

        def poll(self):
            return 2

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 2

        def kill(self) -> None:
            return None

    def fake_ensure_command(self: PyYDoTool, name: str) -> None:
        return None

    def fake_socket_ready(self) -> bool:
        return False

    monkeypatch.setattr(PyYDoTool, "_ensure_command", fake_ensure_command)
    monkeypatch.setattr("py_ydotool.client.YDoToolDaemon._is_socket_ready", fake_socket_ready)
    monkeypatch.setattr("py_ydotool.client.subprocess.Popen", FakePopen)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(DaemonStartError):
        tool.daemon().start()


def test_daemon_exceptions_preserve_backward_compatibility() -> None:
    assert issubclass(DaemonStartError, CommandExecutionError)
    assert issubclass(DaemonReadyTimeoutError, CommandTimeoutError)


def test_init_rejects_negative_type_delay_ms() -> None:
    with pytest.raises(ValueError, match="type_delay_ms must be >= 0"):
        PyYDoTool(check_commands_on_init=False, type_delay_ms=-1)


def test_press_many_rejects_negative_interval() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="interval must be >= 0"):
        tool.press_many([Key.ENTER], interval=-0.1)


def test_type_or_paste_rejects_negative_paste_threshold() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="paste_threshold must be >= 0"):
        tool.type_or_paste("hello", paste_threshold=-1)


def test_click_rejects_invalid_button() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="button must be a hexadecimal string"):
        tool.click("left")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"repeat": 0}, "repeat must be > 0"),
        ({"repeat": -1}, "repeat must be > 0"),
        ({"next_delay_ms": -1}, "next_delay_ms must be >= 0"),
    ],
)
def test_click_rejects_invalid_count_like_arguments(kwargs: dict[str, int], message: str) -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match=message):
        tool.click(**kwargs)


def test_double_click_rejects_negative_interval() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="interval must be >= 0"):
        tool.double_click(interval=-0.1)


@pytest.mark.parametrize("method_name", ["copy_selected", "cut_selected"])
def test_selection_helpers_reject_negative_wait(method_name: str) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    method = getattr(tool, method_name)

    with pytest.raises(ValueError, match="wait must be >= 0"):
        method(wait=-0.1)


def test_click_with_modifiers_rejects_invalid_button_before_key_hold(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    hold_key_calls: list[tuple[int, ...]] = []

    @contextmanager
    def fake_hold_keys(self: PyYDoTool, *keycodes: int):
        hold_key_calls.append(keycodes)
        yield

    monkeypatch.setattr(PyYDoTool, "hold_keys", fake_hold_keys)

    with pytest.raises(ValueError, match="button must be a hexadecimal string"):
        tool.click_with_modifiers(Key.CTRL, button="left")

    assert hold_key_calls == []


@pytest.mark.parametrize(
    ("method_name", "args", "message"),
    [
        ("key_down", ("28",), "keycode must be an int"),
        ("press", (3.14,), "keycode must be an int"),
        ("press_many", ([Key.ENTER, "29"],), "keycode must be an int"),
        ("click", (), "button must be a str"),
        ("move_to", (10.5, 20), "x must be an int"),
        ("move_rel", (10, True), "dy must be an int"),
        ("move_to", (10, 2), "duration must be a real number"),
        ("move_rel", (10, 2), "duration must be a real number"),
        ("drag_to", (10, 2), "duration must be a real number"),
        ("drag_rel", (10, 2), "duration must be a real number"),
        ("type", (123,), "text must be a str"),
        ("type_or_paste", (123,), "text must be a str"),
        ("copy", (b"hello",), "text must be a str"),
    ],
)
def test_public_api_rejects_invalid_argument_types(
    method_name: str,
    args: tuple[object, ...],
    message: str,
) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    method = getattr(tool, method_name)

    with pytest.raises(TypeError, match=message):
        if method_name == "click":
            method(123)
        elif (
            method_name in {"move_to", "move_rel", "drag_to", "drag_rel"}
            and message == "duration must be a real number"
        ):
            method(*args, duration="slow")
        else:
            method(*args)


def test_sleep_rejects_negative_seconds(monkeypatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("py_ydotool.client.time.sleep", lambda seconds: sleep_calls.append(seconds))

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="seconds must be >= 0"):
        tool.sleep(-0.1)

    assert sleep_calls == []


@pytest.mark.parametrize(
    ("factory", "name"),
    [
        (lambda tool: tool.daemon(ready_timeout=True), "ready_timeout"),
        (lambda tool: tool.daemon(stop_timeout=False), "stop_timeout"),
        (lambda tool: tool.daemon(settle_delay="0.1"), "settle_delay"),
        (lambda tool: tool.press_many([Key.ENTER], interval=True), "interval"),
        (lambda tool: tool.double_click(interval=False), "interval"),
        (lambda tool: tool.copy_selected(wait=True), "wait"),
        (lambda tool: tool.cut_selected(wait="0.1"), "wait"),
        (lambda tool: tool.sleep(True), "seconds"),
    ],
)
def test_time_like_public_api_rejects_non_numeric_values(
    factory,
    name: str,
) -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(TypeError, match=rf"{name} must be a real number"):
        factory(tool)


@pytest.mark.parametrize(
    ("factory", "name"),
    [
        (lambda tool: tool.daemon(ready_timeout=math.inf), "ready_timeout"),
        (lambda tool: tool.daemon(stop_timeout=-math.inf), "stop_timeout"),
        (lambda tool: tool.daemon(settle_delay=math.nan), "settle_delay"),
        (lambda tool: tool.press_many([Key.ENTER], interval=math.inf), "interval"),
        (lambda tool: tool.double_click(interval=math.nan), "interval"),
        (lambda tool: tool.copy_selected(wait=math.inf), "wait"),
        (lambda tool: tool.cut_selected(wait=math.nan), "wait"),
        (lambda tool: tool.sleep(math.inf), "seconds"),
    ],
)
def test_time_like_public_api_rejects_non_finite_values(
    factory,
    name: str,
) -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match=rf"{name} must be finite"):
        factory(tool)


def test_paste_text_rejects_non_string_before_copy(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    copy_calls: list[str] = []

    def fake_copy(self: PyYDoTool, text: str) -> None:
        copy_calls.append(text)

    monkeypatch.setattr(PyYDoTool, "copy", fake_copy)

    with pytest.raises(TypeError, match="text must be a str"):
        tool.paste_text(123)

    assert copy_calls == []


@pytest.mark.parametrize(
    ("factory", "name"),
    [
        (lambda: PyYDoTool(check_commands_on_init=1), "check_commands_on_init"),
        (
            lambda: PyYDoTool(check_commands_on_init=False).daemon(
                clean_stale_socket="yes",
            ),
            "clean_stale_socket",
        ),
        (
            lambda: PyYDoTool(check_commands_on_init=False).setup_plan(
                ensure_module_loaded_on_boot=1,
            ),
            "ensure_module_loaded_on_boot",
        ),
        (
            lambda: PyYDoTool(check_commands_on_init=False).setup_plan(
                add_user_to_group="yes",
            ),
            "add_user_to_group",
        ),
        (
            lambda: PyYDoTool(check_commands_on_init=False).setup_plan(dry_run=1),
            "dry_run",
        ),
        (
            lambda: PyYDoTool(check_commands_on_init=False).setup_plan(privileged=None),
            "privileged",
        ),
    ],
)
def test_boolean_like_public_api_rejects_non_bool_values(factory, name: str) -> None:
    with pytest.raises(TypeError, match=rf"{name} must be a bool"):
        factory()


def test_type_or_paste_rejects_non_bool_prefer_paste_before_side_effects(monkeypatch) -> None:
    tool = PyYDoTool(check_commands_on_init=False)
    calls: list[tuple[str, str]] = []

    def fake_write(self: PyYDoTool, text: str) -> None:
        calls.append(("write", text))

    def fake_paste_text(self: PyYDoTool, text: str) -> None:
        calls.append(("paste_text", text))

    monkeypatch.setattr(PyYDoTool, "write", fake_write)
    monkeypatch.setattr(PyYDoTool, "paste_text", fake_paste_text)

    with pytest.raises(TypeError, match="prefer_paste must be a bool"):
        tool.type_or_paste("hello", prefer_paste=1)

    assert calls == []


def test_run_rejects_invalid_timeout_override_before_subprocess(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(TypeError, match="timeout must be a real number"):
        tool._run("debug", timeout=True)

    assert calls == []


def test_run_command_rejects_non_finite_timeout_override_before_subprocess(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr("py_ydotool.client.subprocess.run", fake_run)

    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="timeout must be finite"):
        tool._run_command(["clipboard-paste"], timeout=math.inf)

    assert calls == []


def test_move_to_rejects_invalid_duration_and_steps() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="duration must be >= 0"):
        tool.move_to(10, 0, duration=-0.1)

    with pytest.raises(ValueError, match="steps must be > 0"):
        tool.move_to(10, 0, duration=0.2, steps=0)

    with pytest.raises(ValueError, match="steps requires duration > 0"):
        tool.move_to(10, 0, steps=2)


def test_move_rel_rejects_invalid_duration_and_steps() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="duration must be >= 0"):
        tool.move_rel(10, 0, duration=-0.1)

    with pytest.raises(ValueError, match="steps must be > 0"):
        tool.move_rel(10, 0, duration=0.2, steps=0)

    with pytest.raises(ValueError, match="steps requires duration > 0"):
        tool.move_rel(10, 0, steps=2)


def test_drag_methods_reject_invalid_duration_and_steps() -> None:
    tool = PyYDoTool(check_commands_on_init=False)

    with pytest.raises(ValueError, match="duration must be >= 0"):
        tool.drag_to(10, 0, duration=-0.1)

    with pytest.raises(ValueError, match="steps must be > 0"):
        tool.drag_rel(10, 0, duration=0.2, steps=0)

    with pytest.raises(ValueError, match="steps requires duration > 0"):
        tool.drag_between(1, 2, 10, 20, duration=0.0, steps=2)


def test_build_linear_motion_steps_returns_single_step_for_zero_duration() -> None:
    motion_steps = _build_linear_motion_steps(10, -4, duration=0.0)

    assert [(step.offset, step.dx, step.dy) for step in motion_steps] == [(0.0, 10, -4)]


def test_build_linear_motion_steps_rejects_invalid_timing() -> None:
    with pytest.raises(ValueError, match="duration must be >= 0"):
        _build_linear_motion_steps(10, 0, duration=-0.1)

    with pytest.raises(ValueError, match="steps must be > 0"):
        _build_linear_motion_steps(10, 0, duration=0.2, steps=0)

    with pytest.raises(ValueError, match="steps requires duration > 0"):
        _build_linear_motion_steps(10, 0, duration=0.0, steps=2)


def test_build_linear_motion_steps_sums_to_requested_delta() -> None:
    motion_steps = _build_linear_motion_steps(10, -4, duration=0.4, steps=4)

    assert [step.offset for step in motion_steps] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert sum(step.dx for step in motion_steps) == 10
    assert sum(step.dy for step in motion_steps) == -4


def test_build_linear_motion_steps_limits_auto_steps_by_distance() -> None:
    motion_steps = _build_linear_motion_steps(2, 0, duration=1.0)

    assert [(step.offset, step.dx, step.dy) for step in motion_steps] == [
        (0.5, 1, 0),
        (1.0, 1, 0),
    ]


def test_build_linear_motion_steps_skips_zero_deltas() -> None:
    assert _build_linear_motion_steps(0, 0, duration=0.5, steps=5) == ()


def test_run_motion_steps_uses_offsets_as_deadlines() -> None:
    motion_steps = _build_linear_motion_steps(3, 0, duration=0.3, steps=3)
    current_time = 0.0
    sleeps: list[float] = []
    moves: list[tuple[int, int, float]] = []

    def fake_monotonic() -> float:
        return current_time

    def fake_sleep(amount: float) -> None:
        nonlocal current_time
        sleeps.append(amount)
        current_time += amount

    def fake_move(dx: int, dy: int) -> None:
        moves.append((dx, dy, current_time))

    _run_motion_steps(
        motion_steps,
        move=fake_move,
        monotonic=fake_monotonic,
        sleep=fake_sleep,
    )

    assert sleeps == pytest.approx([0.1, 0.1, 0.1])
    assert moves == [
        (1, 0, pytest.approx(0.1)),
        (1, 0, pytest.approx(0.2)),
        (1, 0, pytest.approx(0.3)),
    ]
