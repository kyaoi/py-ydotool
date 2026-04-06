from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from py_ydotool import MouseButton, PyYDoTool
from py_ydotool.clipboard import available_clipboard_backends

pytestmark = pytest.mark.integration


def _require_integration_opt_in() -> None:
    if os.environ.get("PY_YDOTOOL_RUN_INTEGRATION") != "1":
        pytest.skip("set PY_YDOTOOL_RUN_INTEGRATION=1 to run integration tests")


def _require_linux() -> None:
    if not sys.platform.startswith("linux"):
        pytest.skip("integration tests require Linux")


def _require_ydotool_prereqs() -> None:
    _require_integration_opt_in()
    _require_linux()
    if shutil.which("ydotool") is None:
        pytest.skip("integration tests require ydotool in PATH")
    if shutil.which("ydotoold") is None:
        pytest.skip("integration tests require ydotoold in PATH")
    if not os.access("/dev/uinput", os.R_OK | os.W_OK):
        pytest.skip("integration tests require read/write access to /dev/uinput")


def _compatible_clipboard_backend_names() -> tuple[str, ...]:
    _require_integration_opt_in()
    _require_linux()
    available_by_name = {backend.name: backend for backend in available_clipboard_backends()}
    backend_names: list[str] = []
    if os.environ.get("WAYLAND_DISPLAY") and "wl-clipboard" in available_by_name:
        backend_names.append("wl-clipboard")
    if os.environ.get("DISPLAY"):
        if "xclip" in available_by_name:
            backend_names.append("xclip")
        if "xsel" in available_by_name:
            backend_names.append("xsel")
    return tuple(backend_names)


def _require_compatible_clipboard_backend(name: str) -> str:
    compatible = _compatible_clipboard_backend_names()
    if not compatible:
        pytest.skip("no clipboard backend matched the current desktop session")
    if name not in compatible:
        pytest.skip(
            f"clipboard backend {name!r} is not compatible with the current desktop session"
        )
    return name


def _wait_for_exit(pid: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} did not exit within {timeout} seconds")


def _run_cli(args: list[str], *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "py_ydotool", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


@pytest.fixture
def socket_path(tmp_path: Path) -> str:
    _require_ydotool_prereqs()
    return str(tmp_path / "ydotool-test.sock")


def test_daemon_context_manager_starts_and_stops_owned_process(socket_path: str) -> None:
    tool = PyYDoTool(socket_path=socket_path, check_commands_on_init=False)
    daemon = tool.daemon(ready_timeout=5.0, stop_timeout=1.0)

    owned_pid: int | None = None
    with daemon:
        assert daemon._owns_process is True
        assert daemon._process is not None
        assert daemon._process.poll() is None
        assert os.path.exists(socket_path) is True
        assert stat.S_ISSOCK(os.stat(socket_path, follow_symlinks=False).st_mode) is True
        assert daemon._is_socket_ready() is True
        owned_pid = daemon._process.pid

    assert daemon._owns_process is False
    assert daemon._process is None
    assert owned_pid is not None
    _wait_for_exit(owned_pid)
    assert daemon._is_socket_ready() is False
    assert os.path.exists(socket_path) is False


def test_daemon_decorator_starts_and_stops_owned_process(socket_path: str) -> None:
    tool = PyYDoTool(socket_path=socket_path, check_commands_on_init=False)
    daemon = tool.daemon(ready_timeout=5.0, stop_timeout=1.0)

    @daemon
    def run_under_daemon() -> tuple[bool, bool, bool, int | None]:
        return (
            daemon._owns_process,
            daemon._process is not None,
            daemon._is_socket_ready(),
            None if daemon._process is None else daemon._process.pid,
        )

    owns_process, has_process, socket_ready, owned_pid = run_under_daemon()

    assert owns_process is True
    assert has_process is True
    assert socket_ready is True
    assert daemon._owns_process is False
    assert daemon._process is None
    assert owned_pid is not None
    _wait_for_exit(owned_pid)
    assert daemon._is_socket_ready() is False
    assert os.path.exists(socket_path) is False


def test_daemon_reuses_existing_daemon_without_stopping_it(socket_path: str) -> None:
    owner_tool = PyYDoTool(socket_path=socket_path, check_commands_on_init=False)
    owner = owner_tool.daemon(ready_timeout=5.0, stop_timeout=1.0)
    owner_pid: int | None = None
    owner.start()
    try:
        assert owner._owns_process is True
        assert owner._process is not None
        owner_pid = owner._process.pid

        reused_tool = PyYDoTool(socket_path=socket_path, check_commands_on_init=False)
        reused = reused_tool.daemon(ready_timeout=5.0, stop_timeout=1.0)
        with reused:
            assert reused._owns_process is False
            assert reused._process is None
            assert reused._is_socket_ready() is True
            assert owner._process is not None
            assert owner._process.poll() is None
            assert owner._process.pid == owner_pid

        assert owner._process is not None
        assert owner._process.poll() is None
        assert owner._process.pid == owner_pid
    finally:
        owner.stop()
        assert owner_pid is not None
        _wait_for_exit(owner_pid)
        assert owner._is_socket_ready() is False
        assert os.path.exists(socket_path) is False


@pytest.mark.parametrize(
    ("command_args", "timeout"),
    [
        (["press", "LEFT_SHIFT"], 10.0),
        (["move", "0", "0", "--relative"], 10.0),
        (["click-at", "0", "0"], 10.0),
        (["double-click"], 10.0),
        (["drag", "0", "0", "1", "1"], 10.0),
        (["paste"], 10.0),
    ],
)
def test_cli_one_shot_commands_start_and_stop_owned_process(
    socket_path: str,
    command_args: list[str],
    timeout: float,
) -> None:
    result = _run_cli(
        [
            *command_args,
            "--socket-path",
            socket_path,
            "--settle-delay",
            "0",
            "--ready-timeout",
            "5.0",
            "--stop-timeout",
            "1.0",
        ],
        timeout=timeout,
    )

    assert result.returncode == 0, result.stderr
    assert os.path.exists(socket_path) is False


def test_cli_mouse_down_move_and_mouse_up_work_with_existing_daemon(socket_path: str) -> None:
    owner_tool = PyYDoTool(socket_path=socket_path, check_commands_on_init=False)
    owner = owner_tool.daemon(ready_timeout=5.0, stop_timeout=1.0)
    owner_pid: int | None = None
    mouse_down_succeeded = False

    owner.start()
    try:
        assert owner._owns_process is True
        assert owner._process is not None
        owner_pid = owner._process.pid

        for command_args in (
            ["mouse-down", "--button", "left"],
            ["move", "0", "0", "--relative"],
            ["mouse-up", "--button", "left"],
        ):
            result = _run_cli([*command_args, "--socket-path", socket_path, "--no-daemon"])
            assert result.returncode == 0, result.stderr
            assert owner._process is not None
            assert owner._process.poll() is None
            assert owner._process.pid == owner_pid
            assert owner._is_socket_ready() is True
            assert os.path.exists(socket_path) is True
            if command_args[0] == "mouse-down":
                mouse_down_succeeded = True
            if command_args[0] == "mouse-up":
                mouse_down_succeeded = False
    finally:
        if mouse_down_succeeded and owner._is_socket_ready():
            owner_tool.mouse_up(MouseButton.LEFT)
        owner.stop()
        assert owner_pid is not None
        _wait_for_exit(owner_pid)
        assert owner._is_socket_ready() is False
        assert os.path.exists(socket_path) is False


@pytest.mark.parametrize("backend_name", ["wl-clipboard", "xclip", "xsel"])
def test_cli_clipboard_round_trip_with_compatible_backends(backend_name: str) -> None:
    backend_name = _require_compatible_clipboard_backend(backend_name)
    text = f"py-ydotool clipboard integration {backend_name} {time.monotonic_ns()}"

    copy_result = _run_cli(["copy", text, "--backend", backend_name])
    assert copy_result.returncode == 0, copy_result.stderr

    paste_result = _run_cli(["get-clipboard", "--backend", backend_name])
    assert paste_result.returncode == 0, paste_result.stderr
    assert paste_result.stdout == text
