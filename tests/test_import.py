from importlib import resources

from py_ydotool import (
    DaemonError,
    DaemonReadyTimeoutError,
    DaemonStartError,
    DoctorReport,
    PyYDoTool,
    SetupPlan,
    YDoToolDaemon,
    __version__,
    collect_doctor_report,
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
