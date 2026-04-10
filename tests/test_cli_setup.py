from __future__ import annotations

import grp
import json
import os
import subprocess
from pathlib import Path

import pytest

from py_ydotool import cli
from py_ydotool._system import (
    MODULES_LOAD_CONTENT,
    UDEV_RULE_TEMPLATE,
    DoctorItem,
    DoctorReport,
    SetupOptions,
    SystemPaths,
    apply_setup_plan,
    build_setup_plan,
    collect_doctor_report,
    doctor_report_to_dict,
    render_doctor_report,
    render_setup_plan,
    rerun_setup_with_privileges,
)


def _current_group_name() -> str:
    return grp.getgrgid(os.getgid()).gr_name


def _write_managed_setup_files(paths: SystemPaths, group: str) -> None:
    rule_path = paths.udev_rules_dir / "80-py-ydotool-uinput.rules"
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(UDEV_RULE_TEMPLATE.format(group=group), encoding="utf-8")

    modules_path = paths.modules_load_dir / "py-ydotool-uinput.conf"
    modules_path.parent.mkdir(parents=True, exist_ok=True)
    modules_path.write_text(MODULES_LOAD_CONTENT, encoding="utf-8")


def test_doctor_report_missing_commands_and_uinput(tmp_path, monkeypatch) -> None:
    paths = SystemPaths(
        dev_uinput=tmp_path / "uinput",
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda name: None)

    report = collect_doctor_report(socket_path=str(tmp_path / "ydotool.sock"), paths=paths)

    assert report.overall_status == "ERROR"
    assert report.error_count >= 3
    assert any(item.name == "ydotool" and item.status == "ERROR" for item in report.items)
    assert any(item.name == "/dev/uinput" and item.status == "ERROR" for item in report.items)
    assert "py-ydotool doctor" in render_doctor_report(report)


def test_doctor_report_includes_clipboard_and_text_backend_status(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    def fake_which(name: str) -> str | None:
        mapping = {
            "ydotool": "/usr/bin/ydotool",
            "ydotoold": "/usr/bin/ydotoold",
            "wtype": "/usr/bin/wtype",
            "eitype": "/usr/bin/eitype",
            "wl-copy": "/usr/bin/wl-copy",
            "wl-paste": "/usr/bin/wl-paste",
        }
        return mapping.get(name)

    monkeypatch.setattr("py_ydotool._system.shutil.which", fake_which)
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER") or None,
    )

    clipboard_item = next(item for item in report.items if item.name == "clipboard-backends")
    text_item = next(item for item in report.items if item.name == "text-backends")
    assert clipboard_item.status == "OK"
    assert "wl-clipboard" in clipboard_item.summary
    assert text_item.status == "OK"
    assert "ydotool" in text_item.summary
    assert "wtype" in text_item.summary
    assert "eitype" in text_item.summary
    assert "paste" in text_item.summary


def test_doctor_report_warns_when_clipboard_and_text_backends_are_unavailable(
    tmp_path, monkeypatch
) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    def fake_which(name: str) -> str | None:
        mapping = {"ydotoold": "/usr/bin/ydotoold"}
        return mapping.get(name)

    monkeypatch.setattr("py_ydotool._system.shutil.which", fake_which)
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER") or None,
    )

    clipboard_item = next(item for item in report.items if item.name == "clipboard-backends")
    text_item = next(item for item in report.items if item.name == "text-backends")
    assert clipboard_item.status == "WARN"
    assert "clipboard-backed paste" in (clipboard_item.action or "")
    assert text_item.status == "WARN"
    assert "paste fallback" in (text_item.action or "")


def test_doctor_report_warns_when_user_is_configured_but_session_lacks_access(
    tmp_path, monkeypatch
) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    def fake_which(name: str) -> str:
        return f"/usr/bin/{name}"

    def fake_access(path: os.PathLike[str] | str, mode: int) -> bool:
        return Path(path) != dev_uinput

    monkeypatch.setattr("py_ydotool._system.shutil.which", fake_which)
    monkeypatch.setattr("py_ydotool._system._likely_user_can_access", lambda path, user: True)
    monkeypatch.setattr("py_ydotool._system.os.access", fake_access)

    report = collect_doctor_report(socket_path=str(tmp_path / "ydotool.sock"), paths=paths)

    uinput_item = next(item for item in report.items if item.name == "/dev/uinput")
    assert uinput_item.status == "WARN"
    assert "log out and back in" in (uinput_item.action or "").lower()


def test_doctor_report_flags_non_socket_path(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    socket_path = tmp_path / "not-a-socket"
    socket_path.write_text("hello", encoding="utf-8")

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda name: f"/usr/bin/{name}")

    report = collect_doctor_report(
        socket_path=str(socket_path),
        paths=paths,
        user=os.environ.get("USER") or None,
    )

    socket_item = next(item for item in report.items if item.name == "socket-path")
    assert socket_item.status == "ERROR"
    assert "not a socket" in socket_item.summary


def test_doctor_report_warns_when_no_privilege_helper_exists(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda _name: None)
    monkeypatch.setattr("py_ydotool._system.os.geteuid", lambda: 1000)
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER") or None,
    )

    helper_item = next(item for item in report.items if item.name == "setup-privileges")
    assert helper_item.status == "WARN"
    assert "sudo" in (helper_item.action or "")


def test_doctor_report_warns_when_user_is_not_in_expected_group(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )
    monkeypatch.setattr(
        "py_ydotool._system._user_group_names",
        lambda user: {"wheel"} if user == "alice" else set(),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user="alice",
        group="input",
    )

    group_item = next(item for item in report.items if item.name == "user-group")
    assert group_item.status == "WARN"
    assert "not a member" in group_item.summary
    assert "setup --group input" in (group_item.action or "")


def test_doctor_report_warns_when_managed_setup_files_are_missing(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER") or None,
    )

    rule_item = next(item for item in report.items if item.name == "udev-rule")
    modules_item = next(item for item in report.items if item.name == "modules-load")
    assert rule_item.status == "WARN"
    assert modules_item.status == "WARN"
    assert report.next_actions


def test_doctor_report_reports_managed_setup_files_as_ok(tmp_path, monkeypatch) -> None:
    group = _current_group_name()
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )
    _write_managed_setup_files(paths, group)

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER") or None,
        group=group,
    )

    rule_item = next(item for item in report.items if item.name == "udev-rule")
    modules_item = next(item for item in report.items if item.name == "modules-load")
    group_item = next(item for item in report.items if item.name == "user-group")
    assert rule_item.status == "OK"
    assert modules_item.status == "OK"
    assert group_item.status == "OK"


def test_build_setup_plan_is_noop_when_system_is_already_configured(tmp_path) -> None:
    group = _current_group_name()
    user = os.environ.get("USER") or "root"
    paths = SystemPaths(
        dev_uinput=tmp_path / "uinput",
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    paths.dev_uinput.write_text("device", encoding="utf-8")
    paths.dev_uinput.chmod(0o660)
    _write_managed_setup_files(paths, group)

    plan = build_setup_plan(
        SetupOptions(
            target_user=user,
            group=group,
            ensure_module_loaded_on_boot=True,
            add_user_to_group=True,
            dry_run=True,
        ),
        paths=paths,
    )

    assert plan.has_work is False
    assert plan.steps == ()


def test_apply_setup_plan_writes_files_and_updates_runtime_permissions(
    tmp_path, monkeypatch
) -> None:
    group = _current_group_name()
    user = os.environ.get("USER") or "root"
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o600)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    seen: list[list[str]] = []

    def fake_run(command: list[str], *, text: bool, check: bool, capture_output: bool):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("py_ydotool._system.subprocess.run", fake_run)

    options = SetupOptions(
        target_user=user,
        group=group,
        ensure_module_loaded_on_boot=True,
        add_user_to_group=True,
        dry_run=False,
        privileged=True,
    )
    plan = build_setup_plan(options, paths=paths)
    apply_setup_plan(plan, options=options, paths=paths)

    assert (paths.udev_rules_dir / "80-py-ydotool-uinput.rules").read_text(encoding="utf-8") == (
        UDEV_RULE_TEMPLATE.format(group=group)
    )
    assert (paths.modules_load_dir / "py-ydotool-uinput.conf").read_text(encoding="utf-8") == (
        MODULES_LOAD_CONTENT
    )
    assert stat_mode(paths.dev_uinput) == 0o660
    assert ["udevadm", "control", "--reload-rules"] in seen


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_render_setup_plan_mentions_missing_privilege_helper(tmp_path, monkeypatch) -> None:
    group = _current_group_name()
    user = os.environ.get("USER") or "root"
    paths = SystemPaths(
        dev_uinput=tmp_path / "uinput",
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda _name: None)
    monkeypatch.setattr("py_ydotool._system.os.geteuid", lambda: 1000)

    plan = build_setup_plan(
        SetupOptions(
            target_user=user,
            group=group,
            ensure_module_loaded_on_boot=True,
            add_user_to_group=True,
            dry_run=False,
        ),
        paths=paths,
    )

    rendered = render_setup_plan(plan, dry_run=False)

    assert "No sudo/pkexec helper was detected here" in rendered


def test_render_setup_plan_dry_run_includes_targets_and_step_details(tmp_path) -> None:
    group = _current_group_name()
    plan = build_setup_plan(
        SetupOptions(
            target_user="alice",
            group=group,
            ensure_module_loaded_on_boot=True,
            add_user_to_group=True,
            dry_run=True,
        ),
        paths=SystemPaths(
            dev_uinput=tmp_path / "uinput",
            udev_rules_dir=tmp_path / "udev-rules.d",
            modules_load_dir=tmp_path / "modules-load.d",
        ),
    )

    rendered = render_setup_plan(plan, dry_run=True)

    assert "Setup targets:" in rendered
    assert f"target_group={group}" in rendered
    assert "detail: reason=missing or different managed rule" in rendered
    assert "detail: content=KERNEL==" in rendered
    assert "Review the targets, previews, and details above" in rendered


def test_rerun_setup_with_privileges_prefers_sudo(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name == "sudo":
            return "/usr/bin/sudo"
        return None

    def fake_run(command: list[str]):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("py_ydotool._system.shutil.which", fake_which)
    monkeypatch.setattr("py_ydotool._system.subprocess.run", fake_run)

    exit_code = rerun_setup_with_privileges(["setup", "--group", "input"])

    assert exit_code == 0
    assert seen == [
        [
            "sudo",
            os.sys.executable,
            "-m",
            "py_ydotool",
            "setup",
            "--group",
            "input",
            "--as-root",
        ]
    ]


def test_doctor_report_to_dict_uses_stable_json_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda _name: None)
    monkeypatch.setattr("py_ydotool._system.os.geteuid", lambda: 1000)
    paths = SystemPaths(
        dev_uinput=tmp_path / "missing-uinput",
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )

    report = collect_doctor_report(socket_path=str(tmp_path / "ydotool.sock"), paths=paths)

    payload = doctor_report_to_dict(report)

    assert payload["socket_path"] == str(tmp_path / "ydotool.sock")
    assert payload["summary"]["overall_status"] == "ERROR"
    assert payload["readiness"]["usable_now"] is False
    assert payload["readiness"]["managed_setup_complete"] is False
    assert payload["readiness"]["setup_apply_path"] == "manual-root-shell"
    assert isinstance(payload["items"], list)
    assert payload["items"][0]["name"] == "/dev/uinput"
    assert payload["next_actions"]


def test_render_doctor_report_includes_readiness_summary(tmp_path, monkeypatch) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("device", encoding="utf-8")
    dev_uinput.chmod(0o660)

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )
    _write_managed_setup_files(paths, _current_group_name())

    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda _name: "/usr/bin/fake")
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )

    rendered = render_doctor_report(
        collect_doctor_report(
            socket_path=str(tmp_path / "ydotool.sock"),
            paths=paths,
            user=os.environ.get("USER") or None,
            group=_current_group_name(),
        )
    )

    assert "Readiness:" in rendered
    assert "usable_now=yes" in rendered
    assert "managed_setup_complete=yes" in rendered


def test_cli_doctor_json_output(monkeypatch, capsys) -> None:
    report = collect_doctor_report(
        socket_path="/tmp/test.sock",
        paths=SystemPaths(dev_uinput=Path("/definitely-missing-uinput")),
    )

    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_kwargs: report)

    exit_code = cli.main(["doctor", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["socket_path"] == "/tmp/test.sock"
    assert payload["summary"]["overall_status"] == report.overall_status
    assert payload["items"]


def test_cli_doctor_forwards_group_option(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_collect_doctor_report(**kwargs):
        seen.update(kwargs)
        return collect_doctor_report(
            socket_path="/tmp/test.sock",
            paths=SystemPaths(dev_uinput=Path("/definitely-missing-uinput")),
            group=kwargs["group"],
        )

    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", fake_collect_doctor_report)

    cli.main(["doctor", "--group", "uinput-users"])

    assert seen["group"] == "uinput-users"


def test_cli_doctor_json_output_returns_zero_when_report_is_clean(
    monkeypatch, tmp_path, capsys
) -> None:
    dev_uinput = tmp_path / "uinput"
    dev_uinput.write_text("", encoding="utf-8")
    dev_uinput.chmod(0o660)

    current_gid = os.getgid()
    monkeypatch.setattr(
        "py_ydotool._system._safe_group_name",
        lambda gid: _current_group_name() if gid == current_gid else str(gid),
    )
    monkeypatch.setattr(
        "py_ydotool._system._safe_user_name",
        lambda uid: os.environ.get("USER", "user") if uid == os.getuid() else str(uid),
    )
    monkeypatch.setattr(
        "py_ydotool._system._existing_socket_state",
        lambda _socket_path: (False, None),
    )
    monkeypatch.setattr("py_ydotool._system.shutil.which", lambda _name: "/usr/bin/fake")

    paths = SystemPaths(
        dev_uinput=dev_uinput,
        udev_rules_dir=tmp_path / "udev-rules.d",
        modules_load_dir=tmp_path / "modules-load.d",
    )
    _write_managed_setup_files(paths, _current_group_name())

    report = collect_doctor_report(
        socket_path=str(tmp_path / "ydotool.sock"),
        paths=paths,
        user=os.environ.get("USER", "user"),
        group=_current_group_name(),
    )
    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_kwargs: report)

    exit_code = cli.main(["doctor", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["summary"]["overall_status"] == "OK"


def test_cli_doctor_strict_returns_one_for_warn(monkeypatch) -> None:
    report = collect_doctor_report(
        socket_path=str(Path("/tmp/ydotool.sock")),
        paths=SystemPaths(dev_uinput=Path("/tmp/missing-uinput")),
    )

    warn_only_report = type(report)(
        items=(DoctorItem(name="warn-only", status="WARN", summary="warning only"),),
        socket_path=report.socket_path,
    )
    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_kwargs: warn_only_report)

    exit_code = cli.main(["doctor", "--strict"])

    assert exit_code == 1


def test_cli_doctor_non_strict_returns_zero_for_warn(monkeypatch) -> None:
    warn_only_report = collect_doctor_report(
        socket_path=str(Path("/tmp/ydotool.sock")),
        paths=SystemPaths(
            dev_uinput=Path("/tmp/missing-uinput"),
            udev_rules_dir=Path("/tmp/udev-rules"),
            modules_load_dir=Path("/tmp/modules-load"),
        ),
    )
    warn_only_report = type(warn_only_report)(
        items=(DoctorItem(name="warn-only", status="WARN", summary="warning only"),),
        socket_path=warn_only_report.socket_path,
    )
    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_kwargs: warn_only_report)

    exit_code = cli.main(["doctor"])

    assert exit_code == 0


def test_main_help_includes_quick_start_examples(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert "Normal Python usage should stay non-root." in captured.out
    assert "setup" in captured.out
    assert "doctor" in captured.out
    assert "type" in captured.out
    assert "press" in captured.out
    assert "click" in captured.out
    assert "copy" in captured.out
    assert "paste-text" in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_snippets"),
    [
        (
            ["copy", "--help"],
            [
                "selected backend",
                "without touching ydotoold",
                "--backend BACKEND",
            ],
        ),
        (
            ["get-clipboard", "--help"],
            [
                "selected backend",
                "without touching ydotoold",
                "--backend BACKEND",
            ],
        ),
        (
            ["paste", "--help"],
            [
                "usual Ctrl+V paste hotkey",
                "This does not modify clipboard contents first",
                "--paste-shortcut KEY",
            ],
        ),
        (
            ["paste-text", "--help"],
            [
                "selected backend",
                "usual Ctrl+V paste hotkey",
                "--backend BACKEND",
                "--no-restore-clipboard",
            ],
        ),
    ],
)
def test_clipboard_command_help_explains_runtime_behavior(
    argv: list[str],
    expected_snippets: list[str],
    capsys,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)

    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    for snippet in expected_snippets:
        assert snippet in captured.out


def test_doctor_help_includes_examples(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["doctor", "--help"])

    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert "py-ydotool doctor --json" in captured.out
    assert "py-ydotool doctor --strict" in captured.out
    assert "py-ydotool doctor --group uinput-users" in captured.out


def test_setup_help_includes_examples(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["setup", "--help"])

    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert "py-ydotool setup --dry-run" in captured.out
    assert "py-ydotool setup --group uinput-users" in captured.out
    assert "py-ydotool setup --user alice --group uinput-users" in captured.out


def test_setup_postcheck_reports_ready_for_normal_usage(capsys, monkeypatch) -> None:
    report = DoctorReport(items=(), socket_path="/tmp/test.sock")

    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_: report)

    cli._print_setup_postcheck(
        SetupOptions(target_user="alice", group="input", socket_path="/tmp/test.sock")
    )

    out = capsys.readouterr().out
    assert "Post-setup doctor summary:" in out
    assert "Setup looks ready for normal non-root usage." in out
    assert "with gui.daemon():" in out


def test_setup_postcheck_explains_relogin_when_group_change_is_pending(capsys, monkeypatch) -> None:
    report = DoctorReport(
        items=(
            DoctorItem(
                name="user-group",
                status="WARN",
                summary="alice is not a member of input yet",
            ),
        ),
        socket_path="/tmp/test.sock",
    )

    monkeypatch.setattr("py_ydotool.cli.collect_doctor_report", lambda **_: report)

    cli._print_setup_postcheck(
        SetupOptions(target_user="alice", group="input", socket_path="/tmp/test.sock")
    )

    out = capsys.readouterr().out
    assert "The current login session may still be using the old group membership." in out
    assert "Log out and back in as `alice`" in out
    assert "doctor --group input" in out


def test_cli_rejects_empty_group_argument(capsys) -> None:
    parser = cli._build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["doctor", "--group", ""])

    assert "group must not be empty" in capsys.readouterr().err


def test_cli_rejects_empty_socket_path_argument(capsys) -> None:
    parser = cli._build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["setup", "--socket-path", ""])

    assert "socket_path must not be empty" in capsys.readouterr().err
