from __future__ import annotations

import argparse
import sys

from ._system import (
    SetupOptions,
    apply_setup_plan,
    build_setup_plan,
    collect_doctor_report,
    default_socket_path,
    render_doctor_report,
    render_doctor_report_json,
    render_setup_plan,
    rerun_setup_with_privileges,
    resolve_target_user,
)

_ROOT_DESCRIPTION = (
    "Small CLI helpers for one-time py-ydotool setup and environment diagnosis.\n\n"
    "Normal Python usage should stay non-root. Use `setup` only when you need to\n"
    "prepare Linux for /dev/uinput access, then use `doctor` to confirm the result."
)

_DOCTOR_EPILOG = """Examples:
  py-ydotool doctor
  py-ydotool doctor --json
  py-ydotool doctor --strict
  py-ydotool doctor --group uinput-users
"""

_SETUP_EPILOG = """Examples:
  py-ydotool setup --dry-run
  py-ydotool setup
  py-ydotool setup --group uinput-users
  py-ydotool setup --user alice --group uinput-users
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py-ydotool",
        description=_ROOT_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor",
        help="Inspect the current ydotool/uinput setup",
        description=(
            "Inspect the current py-ydotool environment and explain what is missing for "
            "normal non-root usage."
        ),
        epilog=_DOCTOR_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument(
        "--socket-path",
        default=default_socket_path(),
        help="Socket path to inspect (default: %(default)s)",
    )
    doctor.add_argument(
        "--user",
        default=None,
        help="Evaluate /dev/uinput access for this user instead of the current user",
    )
    doctor.add_argument(
        "--group",
        default="input",
        help=(
            "Expected /dev/uinput group for managed setup checks. Use the same group that "
            "setup was configured with (default: %(default)s)"
        ),
    )
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print the doctor report as JSON for scripts and CI",
    )
    doctor.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit status for WARN items as well as ERROR items",
    )

    setup = subparsers.add_parser(
        "setup",
        help="Install the one-time Linux setup needed for normal non-root py-ydotool usage",
        description=(
            "Apply the explicit one-time Linux changes needed so regular py-ydotool usage "
            "does not require administrator privileges."
        ),
        epilog=_SETUP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup.add_argument(
        "--socket-path",
        default=default_socket_path(),
        help="Socket path to mention in post-setup guidance (default: %(default)s)",
    )
    setup.add_argument(
        "--user",
        default=None,
        help="User to add to the uinput-capable group (defaults to the invoking user)",
    )
    setup.add_argument(
        "--group",
        default="input",
        help=(
            "Group that should own /dev/uinput for managed setup. Pass the same value to "
            "`doctor --group` later if you customize it (default: %(default)s)"
        ),
    )
    setup.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change, but do not request privileges or modify the system",
    )
    setup.add_argument(
        "--skip-user-group",
        action="store_true",
        help="Do not add the target user to the chosen group",
    )
    setup.add_argument(
        "--skip-modules-load",
        action="store_true",
        help="Do not create /etc/modules-load.d entry for the uinput module",
    )
    setup.add_argument(
        "--as-root",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser


def _setup_followup_lines(report, options: SetupOptions) -> list[str]:
    if report.error_count == 0 and report.warn_count == 0:
        return [
            "Setup looks ready for normal non-root usage.",
            "Next: try `with gui.daemon():` or `@gui.daemon()` in your Python script.",
        ]

    relogin_related = {
        item.name
        for item in report.items
        if item.status == "WARN" and item.name in {"/dev/uinput", "user-group"}
    }
    if options.target_user and relogin_related:
        return [
            "The current login session may still be using the old group membership.",
            (
                f"Log out and back in as `{options.target_user}`, then re-run "
                f"`py-ydotool doctor --group {options.group}`."
            ),
        ]

    if report.next_actions:
        return [f"Next: {report.next_actions[0]}"]

    return ["Next: re-run `py-ydotool doctor` after addressing the remaining warnings."]


def _print_setup_postcheck(options: SetupOptions) -> None:
    report = collect_doctor_report(
        socket_path=options.socket_path,
        user=options.target_user,
        group=options.group,
    )
    print()
    print("Post-setup doctor summary:")
    print(render_doctor_report(report), end="")
    print()
    for line in _setup_followup_lines(report, options):
        print(line)


def _run_doctor(args: argparse.Namespace) -> int:
    report = collect_doctor_report(
        socket_path=args.socket_path,
        user=args.user,
        group=args.group,
    )
    rendered = render_doctor_report_json(report) if args.json else render_doctor_report(report)
    print(rendered, end="")
    if report.error_count:
        return 1
    if args.strict and report.warn_count:
        return 1
    return 0


def _run_setup(args: argparse.Namespace) -> int:
    options = SetupOptions(
        target_user=resolve_target_user(args.user, allow_root=False),
        group=args.group,
        ensure_module_loaded_on_boot=not args.skip_modules_load,
        add_user_to_group=not args.skip_user_group,
        dry_run=args.dry_run,
        privileged=args.as_root or args.dry_run,
        socket_path=args.socket_path,
    )

    plan = build_setup_plan(options)
    print(render_setup_plan(plan, dry_run=options.dry_run), end="")

    if not plan.has_work:
        _print_setup_postcheck(options)
        return 0

    if options.dry_run:
        return 0

    if not args.as_root:
        rerun_args = [
            "setup",
            "--socket-path",
            args.socket_path,
            "--group",
            args.group,
        ]
        if args.user is not None:
            rerun_args.extend(["--user", args.user])
        if args.skip_user_group:
            rerun_args.append("--skip-user-group")
        if args.skip_modules_load:
            rerun_args.append("--skip-modules-load")
        try:
            return rerun_setup_with_privileges(rerun_args, stream=sys.stdout)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    privileged_options = SetupOptions(
        target_user=resolve_target_user(args.user, allow_root=False),
        group=args.group,
        ensure_module_loaded_on_boot=not args.skip_modules_load,
        add_user_to_group=not args.skip_user_group,
        dry_run=False,
        privileged=True,
        socket_path=args.socket_path,
    )
    privileged_plan = build_setup_plan(privileged_options)
    try:
        apply_setup_plan(privileged_plan, options=privileged_options)
    except (PermissionError, RuntimeError) as exc:
        print(f"setup failed: {exc}", file=sys.stderr)
        return 1

    print()
    print("Setup changes applied.")
    _print_setup_postcheck(privileged_options)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "setup":
        return _run_setup(args)
    parser.error(f"unknown command: {args.command}")
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
