from importlib import resources

from py_ydotool import (
    DaemonError,
    DaemonReadyTimeoutError,
    DaemonStartError,
    DoctorReport,
    PyYDoTool,
    SetupPlan,
    TextInputBackend,
    TextInputUnavailableError,
    YDoToolDaemon,
    __version__,
    available_clipboard_backends,
    available_text_backends,
    collect_doctor_report,
    detect_text_backend,
    render_doctor_report,
)


def test_package_import() -> None:
    assert PyYDoTool is not None


def test_version_string_matches_version_file() -> None:
    version_path = resources.files("py_ydotool").joinpath("VERSION")
    version_text = version_path.read_text(encoding="utf-8").strip()
    assert __version__ == version_text


def test_daemon_export() -> None:
    assert YDoToolDaemon is not None


def test_daemon_exceptions_export() -> None:
    assert DaemonError is not None
    assert DaemonStartError is not None
    assert DaemonReadyTimeoutError is not None


def test_system_helpers_export() -> None:
    assert DoctorReport is not None
    assert SetupPlan is not None
    assert collect_doctor_report is not None
    assert render_doctor_report is not None


def test_clipboard_helpers_export() -> None:
    assert available_clipboard_backends is not None


def test_text_input_helpers_export() -> None:
    assert TextInputBackend is not None
    assert TextInputUnavailableError is not None
    assert available_text_backends is not None
    assert detect_text_backend is not None
