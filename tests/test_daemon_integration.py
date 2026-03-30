from __future__ import annotations

import os
import shutil
import stat
import sys
import time
from pathlib import Path

import pytest

from py_ydotool import PyYDoTool

pytestmark = pytest.mark.integration


def _require_integration_prereqs() -> None:
    if os.environ.get("PY_YDOTOOL_RUN_INTEGRATION") != "1":
        pytest.skip("set PY_YDOTOOL_RUN_INTEGRATION=1 to run integration tests")
    if not sys.platform.startswith("linux"):
        pytest.skip("integration tests require Linux")
    if shutil.which("ydotool") is None:
        pytest.skip("integration tests require ydotool in PATH")
    if shutil.which("ydotoold") is None:
        pytest.skip("integration tests require ydotoold in PATH")
    if not os.access("/dev/uinput", os.R_OK | os.W_OK):
        pytest.skip("integration tests require read/write access to /dev/uinput")


def _wait_for_exit(pid: int, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} did not exit within {timeout} seconds")


@pytest.fixture
def socket_path(tmp_path: Path) -> str:
    _require_integration_prereqs()
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
