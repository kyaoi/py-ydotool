from __future__ import annotations

import getpass
import grp
import json
import os
import pwd
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from .client import PyYDoTool

DEFAULT_SOCKET_PATH = "/tmp/.ydotool_socket"
DEFAULT_UDEV_GROUP = "input"
DEFAULT_UDEV_RULE_FILENAME = "80-py-ydotool-uinput.rules"
DEFAULT_MODULES_LOAD_FILENAME = "py-ydotool-uinput.conf"
UDEV_RULE_TEMPLATE = (
    'KERNEL=="uinput", GROUP="{group}", MODE="0660", OPTIONS+="static_node=uinput"\n'
)
MODULES_LOAD_CONTENT = "uinput\n"

_STATUS_ORDER = {"ERROR": 2, "WARN": 1, "OK": 0}


_MANAGED_ITEM_NAMES = ("udev-rule", "modules-load", "user-group")
_CORE_ITEM_NAMES = ("ydotool", "ydotoold", "/dev/uinput", "socket-path")


@dataclass(frozen=True)
class SystemPaths:
    dev_uinput: Path = Path("/dev/uinput")
    udev_rules_dir: Path = Path("/etc/udev/rules.d")
    modules_load_dir: Path = Path("/etc/modules-load.d")


@dataclass(frozen=True)
class DoctorItem:
    name: str
    status: str
    summary: str
    details: tuple[str, ...] = ()
    action: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    items: tuple[DoctorItem, ...]
    socket_path: str

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.items if item.status == "OK")

    @property
    def warn_count(self) -> int:
        return sum(1 for item in self.items if item.status == "WARN")

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.items if item.status == "ERROR")

    @property
    def overall_status(self) -> str:
        if self.error_count:
            return "ERROR"
        if self.warn_count:
            return "WARN"
        return "OK"

    @property
    def next_actions(self) -> tuple[str, ...]:
        actions: list[str] = []
        for item in self.items:
            if item.action and item.action not in actions:
                actions.append(item.action)
        return tuple(actions)


@dataclass(frozen=True)
class SetupOptions:
    target_user: str | None = None
    group: str = DEFAULT_UDEV_GROUP
    ensure_module_loaded_on_boot: bool = True
    add_user_to_group: bool = True
    dry_run: bool = False
    privileged: bool = False
    socket_path: str = DEFAULT_SOCKET_PATH


@dataclass(frozen=True)
class SetupStep:
    description: str
    command_preview: str | None = None
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupPlan:
    steps: tuple[SetupStep, ...]
    target_user: str | None
    group: str
    rule_path: Path
    modules_load_path: Path | None
    will_create_group: bool
    will_add_user_to_group: bool
    will_write_rule: bool
    will_write_modules_load: bool
    will_run_modprobe: bool
    will_reload_udev_rules: bool
    will_update_runtime_permissions: bool
    needs_relogin: bool

    @property
    def has_work(self) -> bool:
        return bool(self.steps)


def default_socket_path() -> str:
    return os.environ.get("YDOTOOL_SOCKET", DEFAULT_SOCKET_PATH)


def resolve_target_user(explicit_user: str | None = None, *, allow_root: bool = True) -> str | None:
    if explicit_user:
        return explicit_user

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        return sudo_user

    pkexec_uid = os.environ.get("PKEXEC_UID")
    if pkexec_uid:
        try:
            return pwd.getpwuid(int(pkexec_uid)).pw_name
        except (KeyError, ValueError):
            return None

    try:
        user = getpass.getuser()
    except OSError:
        return None

    if user == "root" and not allow_root:
        return None
    return user


def _safe_group_name(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def _safe_user_name(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _mode_string(mode: int) -> str:
    return stat.filemode(mode)


def _permission_string(mode: int) -> str:
    return format(stat.S_IMODE(mode), "04o")


def _user_group_names(user: str) -> set[str]:
    pw_record = pwd.getpwnam(user)
    groups = {grp.getgrgid(pw_record.pw_gid).gr_name}
    for group in grp.getgrall():
        if user in group.gr_mem:
            groups.add(group.gr_name)
    return groups


def _available_privilege_helper() -> str | None:
    if os.geteuid() == 0:
        return "root"
    if shutil.which("sudo"):
        return "sudo"
    if shutil.which("pkexec"):
        return "pkexec"
    return None


def _collect_privilege_helper_status() -> DoctorItem:
    helper = _available_privilege_helper()
    if helper == "root":
        return DoctorItem(
            name="setup-privileges",
            status="OK",
            summary="Administrator privileges are already available in this shell",
        )
    if helper == "sudo":
        return DoctorItem(
            name="setup-privileges",
            status="OK",
            summary="`sudo` is available for one-time setup escalation",
        )
    if helper == "pkexec":
        return DoctorItem(
            name="setup-privileges",
            status="OK",
            summary="`pkexec` is available for one-time setup escalation",
        )
    return DoctorItem(
        name="setup-privileges",
        status="WARN",
        summary="No `sudo` or `pkexec` helper was found for one-time setup escalation",
        action=(
            "Install sudo/pkexec, or re-run `py-ydotool setup` from a root shell when setup "
            "changes are needed."
        ),
    )


def _likely_user_can_access(path: Path, user: str) -> bool:
    try:
        st = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False

    try:
        pw_record = pwd.getpwnam(user)
    except KeyError:
        return False

    mode = stat.S_IMODE(st.st_mode)
    if pw_record.pw_uid == st.st_uid:
        return bool(mode & stat.S_IRUSR and mode & stat.S_IWUSR)

    try:
        group_names = _user_group_names(user)
    except KeyError:
        return False

    group_name = _safe_group_name(st.st_gid)
    if group_name in group_names:
        return bool(mode & stat.S_IRGRP and mode & stat.S_IWGRP)

    return bool(mode & stat.S_IROTH and mode & stat.S_IWOTH)


def _existing_socket_state(socket_path: Path) -> tuple[bool, str | None]:
    if not socket_path.exists() and not socket_path.is_socket():
        return False, None

    if socket_path.is_socket():
        tool = PyYDoTool(socket_path=str(socket_path), check_commands_on_init=False)
        try:
            ready = tool.daemon()._is_socket_ready()
        except OSError:
            ready = False
        return True, "ready" if ready else "stale"

    return True, "non-socket"


def _collect_rule_status(paths: SystemPaths, group: str) -> DoctorItem:
    rule_path = paths.udev_rules_dir / DEFAULT_UDEV_RULE_FILENAME
    expected_text = _build_rule_text(group)
    current_text = _read_text_if_exists(rule_path)

    if current_text == expected_text:
        return DoctorItem(
            name="udev-rule",
            status="OK",
            summary=f"Managed udev rule is installed at {rule_path}",
            details=(f"group={group}",),
        )

    if current_text is None:
        return DoctorItem(
            name="udev-rule",
            status="WARN",
            summary=(
                "Managed udev rule is not installed; current runtime access may work, "
                "but persistence is not verified"
            ),
            details=(f"expected_path={rule_path}", f"expected_group={group}"),
            action=(
                "Run `py-ydotool setup` once to install the managed udev rule, "
                "or verify your existing distro-specific rule manually."
            ),
        )

    return DoctorItem(
        name="udev-rule",
        status="WARN",
        summary=f"Managed udev rule at {rule_path} differs from the expected py-ydotool rule",
        details=(f"expected_group={group}",),
        action=(f"Review {rule_path} or rerun `py-ydotool setup --group {group}` to rewrite it."),
    )


def _collect_modules_load_status(paths: SystemPaths) -> DoctorItem:
    modules_load_path = paths.modules_load_dir / DEFAULT_MODULES_LOAD_FILENAME
    current_text = _read_text_if_exists(modules_load_path)

    if current_text == MODULES_LOAD_CONTENT:
        return DoctorItem(
            name="modules-load",
            status="OK",
            summary=f"Managed boot-time uinput load is configured at {modules_load_path}",
        )

    if current_text is None:
        return DoctorItem(
            name="modules-load",
            status="WARN",
            summary=(
                "Managed boot-time uinput loading is not configured; the current session may work, "
                "but future boots are not verified"
            ),
            details=(f"expected_path={modules_load_path}",),
            action=(
                "Run `py-ydotool setup` once to install the modules-load entry, "
                "or ensure your system loads `uinput` another way."
            ),
        )

    return DoctorItem(
        name="modules-load",
        status="WARN",
        summary=(
            "Managed modules-load entry at "
            f"{modules_load_path} differs from the expected uinput config"
        ),
        action=(
            f"Review {modules_load_path} or rerun "
            "`py-ydotool setup --skip-modules-load` only if you intend "
            "to manage it elsewhere."
        ),
    )


def _collect_user_group_status(user: str | None, group: str) -> DoctorItem:
    if not user:
        return DoctorItem(
            name="user-group",
            status="WARN",
            summary="Could not determine which user should have managed /dev/uinput access",
            details=(f"expected_group={group}",),
            action=(
                "Pass `py-ydotool doctor --user <name>` to verify the intended user, "
                "or rerun `py-ydotool setup --user <name>` if needed."
            ),
        )

    try:
        group_names = _user_group_names(user)
    except KeyError:
        return DoctorItem(
            name="user-group",
            status="WARN",
            summary=f"User `{user}` was not found on this system",
            details=(f"expected_group={group}",),
            action=(
                "Choose an existing local user with `--user`, or rerun "
                f"`py-ydotool setup --user <name> --group {group}`."
            ),
        )

    if group in group_names:
        return DoctorItem(
            name="user-group",
            status="OK",
            summary=f"User `{user}` is a member of the expected `{group}` group",
            details=(f"user={user}", f"expected_group={group}"),
        )

    return DoctorItem(
        name="user-group",
        status="WARN",
        summary=f"User `{user}` is not a member of the expected `{group}` group",
        details=(f"user={user}", f"expected_group={group}"),
        action=(
            f"Run `py-ydotool setup --group {group}` to add `{user}` to that group, "
            "then log out and back in."
        ),
    )


def collect_doctor_report(
    *,
    socket_path: str | None = None,
    paths: SystemPaths = SystemPaths(),
    user: str | None = None,
    group: str = DEFAULT_UDEV_GROUP,
) -> DoctorReport:
    resolved_socket_path = socket_path or default_socket_path()
    resolved_user = user or resolve_target_user()
    items: list[DoctorItem] = [
        _collect_rule_status(paths, group),
        _collect_modules_load_status(paths),
        _collect_user_group_status(resolved_user, group),
        _collect_privilege_helper_status(),
    ]

    ydotool_path = shutil.which("ydotool")
    if ydotool_path:
        items.append(
            DoctorItem(
                name="ydotool",
                status="OK",
                summary=f"ydotool found at {ydotool_path}",
            )
        )
    else:
        items.append(
            DoctorItem(
                name="ydotool",
                status="ERROR",
                summary="ydotool was not found in PATH",
                action=(
                    "Install the ydotool package so both ydotool and ydotoold "
                    "are available in PATH."
                ),
            )
        )

    ydotoold_path = shutil.which("ydotoold")
    if ydotoold_path:
        items.append(
            DoctorItem(
                name="ydotoold",
                status="OK",
                summary=f"ydotoold found at {ydotoold_path}",
            )
        )
    else:
        items.append(
            DoctorItem(
                name="ydotoold",
                status="ERROR",
                summary="ydotoold was not found in PATH",
                action=(
                    "Install the ydotool package so both ydotool and ydotoold "
                    "are available in PATH."
                ),
            )
        )

    dev_uinput = paths.dev_uinput
    if not dev_uinput.exists():
        items.append(
            DoctorItem(
                name="/dev/uinput",
                status="ERROR",
                summary="/dev/uinput does not exist",
                details=(
                    "The uinput kernel module is not loaded, or the device node was not created.",
                ),
                action=(
                    "Run `py-ydotool setup` once with administrator privileges "
                    "to install the udev rule and load the uinput module."
                ),
            )
        )
    else:
        st = dev_uinput.stat(follow_symlinks=False)
        owner = _safe_user_name(st.st_uid)
        group = _safe_group_name(st.st_gid)
        mode = _permission_string(st.st_mode)
        details = [
            f"owner={owner}",
            f"group={group}",
            f"mode={mode} ({_mode_string(st.st_mode)})",
        ]

        if resolved_user:
            likely_access = _likely_user_can_access(dev_uinput, resolved_user)
            details.append(
                f"user={resolved_user}",
            )
            details.append(
                f"configured_access={'yes' if likely_access else 'no'}",
            )
        else:
            likely_access = False

        process_access = os.access(dev_uinput, os.R_OK | os.W_OK)
        details.append(f"process_access={'yes' if process_access else 'no'}")

        if process_access:
            items.append(
                DoctorItem(
                    name="/dev/uinput",
                    status="OK",
                    summary="Current process can read and write /dev/uinput",
                    details=tuple(details),
                )
            )
        elif resolved_user and likely_access:
            items.append(
                DoctorItem(
                    name="/dev/uinput",
                    status="WARN",
                    summary=(
                        f"{resolved_user} appears to be configured for /dev/uinput access, "
                        "but this session cannot use it yet"
                    ),
                    details=tuple(
                        [
                            *details,
                            "A logout/login or a fresh shell may be required after group changes.",
                        ]
                    ),
                    action="Log out and back in, then rerun `py-ydotool doctor`.",
                )
            )
        else:
            items.append(
                DoctorItem(
                    name="/dev/uinput",
                    status="ERROR",
                    summary=(
                        "Current user does not appear to have read/write access to /dev/uinput"
                    ),
                    details=tuple(details),
                    action=(
                        "Run `py-ydotool setup` once with administrator "
                        "privileges to grant a dedicated group read/write "
                        "access to /dev/uinput."
                    ),
                )
            )

    socket = Path(resolved_socket_path)
    parent = socket.parent
    parent_exists = parent.exists()
    parent_writable = os.access(parent, os.W_OK) if parent_exists else False
    socket_details = [f"socket_path={socket}", f"parent={parent}"]
    if parent_exists:
        socket_details.append(f"parent_writable={'yes' if parent_writable else 'no'}")
    else:
        socket_details.append("parent_exists=no")

    if not parent_exists:
        items.append(
            DoctorItem(
                name="socket-path",
                status="ERROR",
                summary=f"Socket directory does not exist: {parent}",
                details=tuple(socket_details),
                action=(
                    "Choose an existing writable socket directory with "
                    "`--socket-path`, or create the directory before running "
                    "py-ydotool."
                ),
            )
        )
    elif not parent_writable:
        items.append(
            DoctorItem(
                name="socket-path",
                status="ERROR",
                summary=f"Socket directory is not writable: {parent}",
                details=tuple(socket_details),
                action=(
                    "Choose a writable socket path with `--socket-path`, or "
                    "adjust the directory permissions."
                ),
            )
        )
    else:
        exists, state = _existing_socket_state(socket)
        if not exists:
            items.append(
                DoctorItem(
                    name="socket-path",
                    status="OK",
                    summary="Socket path looks usable; the daemon can create it on demand",
                    details=tuple(socket_details),
                )
            )
        elif state == "ready":
            items.append(
                DoctorItem(
                    name="socket-path",
                    status="OK",
                    summary="An existing ydotoold socket is already responding",
                    details=tuple(socket_details),
                )
            )
        elif state == "stale":
            items.append(
                DoctorItem(
                    name="socket-path",
                    status="WARN",
                    summary="A socket file exists but does not look ready",
                    details=tuple(
                        [
                            *socket_details,
                            "py-ydotool can remove stale socket files "
                            "automatically when "
                            "gui.daemon(clean_stale_socket=True) is used.",
                        ]
                    ),
                    action="Remove the stale socket or let `with gui.daemon():` recreate it.",
                )
            )
        else:
            items.append(
                DoctorItem(
                    name="socket-path",
                    status="ERROR",
                    summary="The configured socket path already exists but is not a socket",
                    details=tuple(socket_details),
                    action=(
                        "Remove or rename the existing file, or use a different `--socket-path`."
                    ),
                )
            )

    items.sort(key=lambda item: (-_STATUS_ORDER[item.status], item.name))
    return DoctorReport(items=tuple(items), socket_path=resolved_socket_path)


def _report_item_map(report: DoctorReport) -> dict[str, DoctorItem]:
    return {item.name: item for item in report.items}


def _doctor_readiness_summary(report: DoctorReport) -> dict[str, object]:
    item_map = _report_item_map(report)
    managed_statuses = [item_map[name].status for name in _MANAGED_ITEM_NAMES if name in item_map]
    core_statuses = {name: item_map[name].status for name in _CORE_ITEM_NAMES if name in item_map}

    usable_now = (
        core_statuses.get("ydotool") == "OK"
        and core_statuses.get("ydotoold") == "OK"
        and core_statuses.get("/dev/uinput") == "OK"
        and core_statuses.get("socket-path") in {"OK", "WARN"}
    )
    managed_setup_complete = bool(managed_statuses) and all(
        status == "OK" for status in managed_statuses
    )

    helper_item = item_map.get("setup-privileges")
    if helper_item is None:
        setup_apply_path = "unknown"
    elif helper_item.status != "OK":
        setup_apply_path = "manual-root-shell"
    elif "sudo" in helper_item.summary:
        setup_apply_path = "sudo"
    elif "pkexec" in helper_item.summary:
        setup_apply_path = "pkexec"
    else:
        setup_apply_path = "already-root"

    return {
        "usable_now": usable_now,
        "managed_setup_complete": managed_setup_complete,
        "setup_apply_path": setup_apply_path,
    }


def doctor_report_to_dict(report: DoctorReport) -> dict[str, object]:
    return {
        "socket_path": report.socket_path,
        "summary": {
            "overall_status": report.overall_status,
            "ok": report.ok_count,
            "warn": report.warn_count,
            "error": report.error_count,
        },
        "readiness": _doctor_readiness_summary(report),
        "items": [
            {
                "name": item.name,
                "status": item.status,
                "summary": item.summary,
                "details": list(item.details),
                "action": item.action,
            }
            for item in report.items
        ],
        "next_actions": list(report.next_actions),
    }


def render_doctor_report_json(report: DoctorReport, *, stream: TextIO | None = None) -> str:
    rendered = json.dumps(doctor_report_to_dict(report), indent=2, sort_keys=True) + "\n"
    if stream is not None:
        stream.write(rendered)
    return rendered


def render_doctor_report(report: DoctorReport, *, stream: TextIO | None = None) -> str:
    readiness = _doctor_readiness_summary(report)
    lines = [
        "py-ydotool doctor",
        (
            f"Summary: {report.overall_status} "
            f"({report.ok_count} OK, {report.warn_count} WARN, "
            f"{report.error_count} ERROR)"
        ),
        "",
        "Readiness:",
        f"- usable_now={'yes' if readiness['usable_now'] else 'no'}",
        (f"- managed_setup_complete={'yes' if readiness['managed_setup_complete'] else 'no'}"),
        f"- setup_apply_path={readiness['setup_apply_path']}",
        "",
    ]

    for item in report.items:
        lines.append(f"[{item.status}] {item.name}: {item.summary}")
        for detail in item.details:
            lines.append(f"  - {detail}")
        if item.action:
            lines.append(f"  - next: {item.action}")
        lines.append("")

    if report.next_actions:
        lines.append("Recommended next actions:")
        for index, action in enumerate(report.next_actions, start=1):
            lines.append(f"{index}. {action}")
    else:
        lines.append("Recommended next actions:")
        lines.append("1. You can proceed with `with gui.daemon():` or `@gui.daemon()` as-is.")

    rendered = "\n".join(lines).rstrip() + "\n"
    if stream is not None:
        stream.write(rendered)
    return rendered


def _read_text_if_exists(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _build_rule_text(group: str) -> str:
    return UDEV_RULE_TEMPLATE.format(group=group)


def build_setup_plan(
    options: SetupOptions,
    *,
    paths: SystemPaths = SystemPaths(),
) -> SetupPlan:
    rule_path = paths.udev_rules_dir / DEFAULT_UDEV_RULE_FILENAME
    modules_load_path = (
        paths.modules_load_dir / DEFAULT_MODULES_LOAD_FILENAME
        if options.ensure_module_loaded_on_boot
        else None
    )

    group_exists = True
    try:
        grp.getgrnam(options.group)
    except KeyError:
        group_exists = False

    user_in_group = False
    if options.target_user and options.add_user_to_group:
        try:
            user_in_group = options.group in _user_group_names(options.target_user)
        except KeyError:
            user_in_group = False

    will_write_rule = _read_text_if_exists(rule_path) != _build_rule_text(options.group)
    will_write_modules_load = False
    if modules_load_path is not None:
        will_write_modules_load = _read_text_if_exists(modules_load_path) != MODULES_LOAD_CONTENT

    dev_exists = paths.dev_uinput.exists()
    current_mode = None
    current_group = None
    if dev_exists:
        st = paths.dev_uinput.stat(follow_symlinks=False)
        current_mode = stat.S_IMODE(st.st_mode)
        current_group = _safe_group_name(st.st_gid)

    will_run_modprobe = not dev_exists
    will_reload_udev_rules = will_write_rule
    will_update_runtime_permissions = (
        not dev_exists or current_group != options.group or current_mode != 0o660
    )
    will_create_group = not group_exists
    will_add_user_to_group = bool(
        options.target_user and options.add_user_to_group and not user_in_group
    )
    needs_relogin = will_add_user_to_group

    steps: list[SetupStep] = []
    if will_create_group:
        steps.append(
            SetupStep(
                description=f"Create the `{options.group}` group",
                command_preview=f"groupadd --system {options.group}",
                details=(f"reason=group `{options.group}` does not exist",),
            )
        )
    if will_add_user_to_group and options.target_user:
        steps.append(
            SetupStep(
                description=f"Add `{options.target_user}` to the `{options.group}` group",
                command_preview=f"usermod -aG {options.group} {options.target_user}",
                details=(
                    f"reason=user `{options.target_user}` is not in `{options.group}`",
                    "session_note=logout/login is usually required afterward",
                ),
            )
        )
    if will_write_rule:
        steps.append(
            SetupStep(
                description=f"Write the udev rule to {rule_path}",
                command_preview=f"write {rule_path}",
                details=(
                    f"reason=missing or different managed rule for group `{options.group}`",
                    f"content={_build_rule_text(options.group).strip()}",
                ),
            )
        )
    if will_write_modules_load and modules_load_path is not None:
        steps.append(
            SetupStep(
                description=f"Ensure the uinput module loads on boot via {modules_load_path}",
                command_preview=f"write {modules_load_path}",
                details=(
                    "reason=missing or different managed modules-load entry",
                    f"content={MODULES_LOAD_CONTENT.strip()}",
                ),
            )
        )
    if will_run_modprobe:
        steps.append(
            SetupStep(
                description="Load the uinput kernel module now",
                command_preview="modprobe uinput",
                details=("reason=/dev/uinput is missing right now",),
            )
        )
    if will_reload_udev_rules:
        steps.append(
            SetupStep(
                description="Reload udev rules so the new rule is known immediately",
                command_preview="udevadm control --reload-rules",
                details=("reason=the managed udev rule changed",),
            )
        )
    if will_update_runtime_permissions:
        steps.append(
            SetupStep(
                description=(f"Apply group `{options.group}` and mode 0660 to {paths.dev_uinput}"),
                command_preview=(
                    f"chgrp {options.group} {paths.dev_uinput} && chmod 0660 {paths.dev_uinput}"
                ),
                details=(
                    f"desired_group={options.group}",
                    "desired_mode=0660",
                ),
            )
        )

    return SetupPlan(
        steps=tuple(steps),
        target_user=options.target_user,
        group=options.group,
        rule_path=rule_path,
        modules_load_path=modules_load_path,
        will_create_group=will_create_group,
        will_add_user_to_group=will_add_user_to_group,
        will_write_rule=will_write_rule,
        will_write_modules_load=will_write_modules_load,
        will_run_modprobe=will_run_modprobe,
        will_reload_udev_rules=will_reload_udev_rules,
        will_update_runtime_permissions=will_update_runtime_permissions,
        needs_relogin=needs_relogin,
    )


def render_setup_plan(plan: SetupPlan, *, dry_run: bool) -> str:
    lines = [
        "py-ydotool setup",
        "",
        (
            "This command is explicit and one-time: it prepares Linux so "
            "normal py-ydotool usage does not need administrator privileges."
        ),
        "",
        "Setup targets:",
        f"- target_user={plan.target_user or 'none'}",
        f"- target_group={plan.group}",
        f"- udev_rule_path={plan.rule_path}",
        (
            "- modules_load_path="
            f"{plan.modules_load_path if plan.modules_load_path is not None else 'skipped'}"
        ),
        "",
    ]
    helper = _available_privilege_helper()
    if not dry_run:
        if helper == "root":
            lines.append("This shell is already running as root, so setup can apply directly.")
        elif helper in {"sudo", "pkexec"}:
            lines.append(f"When applied, setup will request administrator privileges via {helper}.")
        else:
            lines.append(
                "No sudo/pkexec helper was detected here; re-run setup from a root shell if "
                "changes are needed."
            )
        lines.append("")
    if plan.steps:
        lines.append("Planned changes:")
        for index, step in enumerate(plan.steps, start=1):
            lines.append(f"{index}. {step.description}")
            if step.command_preview:
                lines.append(f"   preview: {step.command_preview}")
            for detail in step.details:
                lines.append(f"   detail: {detail}")
    else:
        lines.append("No setup changes are needed; the system already looks configured.")

    lines.append("")
    if plan.needs_relogin and plan.target_user:
        lines.append(
            "Note: "
            f"`{plan.target_user}` will likely need to log out and back in "
            "after the group change."
        )
        lines.append("")

    if dry_run:
        lines.append("Dry run only: no privileged changes were applied.")
        lines.append(
            "Review the targets, previews, and details above before re-running without --dry-run."
        )
    else:
        lines.append(
            "Changes will be applied explicitly; nothing here uses setuid "
            "or hidden privilege escalation."
        )

    return "\n".join(lines).rstrip() + "\n"


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_checked(command: list[str]) -> None:
    try:
        subprocess.run(command, text=True, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nstdout: {exc.stdout}\nstderr: {exc.stderr}"
        ) from exc


def apply_setup_plan(
    plan: SetupPlan,
    *,
    options: SetupOptions,
    paths: SystemPaths = SystemPaths(),
) -> None:
    if not options.privileged:
        raise PermissionError("setup apply requires administrator privileges")

    if plan.will_create_group:
        _run_checked(["groupadd", "--system", plan.group])

    if plan.will_add_user_to_group and plan.target_user:
        _run_checked(["usermod", "-aG", plan.group, plan.target_user])

    if plan.will_write_rule:
        _write_text_file(plan.rule_path, _build_rule_text(plan.group))

    if plan.will_write_modules_load and plan.modules_load_path is not None:
        _write_text_file(plan.modules_load_path, MODULES_LOAD_CONTENT)

    if plan.will_run_modprobe:
        _run_checked(["modprobe", "uinput"])

    if plan.will_reload_udev_rules:
        _run_checked(["udevadm", "control", "--reload-rules"])

    if plan.will_update_runtime_permissions and paths.dev_uinput.exists():
        group = grp.getgrnam(plan.group)
        st = paths.dev_uinput.stat(follow_symlinks=False)
        os.chown(paths.dev_uinput, st.st_uid, group.gr_gid, follow_symlinks=False)
        os.chmod(paths.dev_uinput, 0o660, follow_symlinks=False)


def _should_reexec_privileged(options: SetupOptions) -> bool:
    return not options.dry_run and os.geteuid() != 0


def rerun_setup_with_privileges(argv: list[str], *, stream: TextIO | None = None) -> int:
    if shutil.which("sudo"):
        command = ["sudo", sys.executable, "-m", "py_ydotool", *argv, "--as-root"]
    elif shutil.which("pkexec"):
        command = ["pkexec", sys.executable, "-m", "py_ydotool", *argv, "--as-root"]
    else:
        raise RuntimeError(
            "Neither sudo nor pkexec is available. Re-run "
            "`py-ydotool setup` as root or install sudo/pkexec."
        )

    if stream is not None:
        stream.write(
            f"Requesting administrator privileges via {command[0]} so "
            "setup can apply the planned changes.\n"
        )
    completed = subprocess.run(command)
    return completed.returncode
