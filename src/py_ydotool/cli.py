from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from contextlib import nullcontext

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
from .client import MouseButton, PyYDoTool
from .clipboard import supported_clipboard_backend_names
from .keys import Key

_ROOT_DESCRIPTION = (
    "Small CLI helpers for py-ydotool setup, environment diagnosis, and "
    "simple one-shot input commands.\n\n"
    "Normal Python usage should stay non-root. Use `setup` only when you need to\n"
    "prepare Linux for /dev/uinput access, then use `doctor` to confirm the result.\n"
    "For quick shell-driven automation, use `type`, `press`, `click`, `move`, or `drag`."
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

_TYPE_EPILOG = """Examples:
  py-ydotool type "hello"
  py-ydotool type "hello" --type-delay-ms 15
  py-ydotool type "hello" --no-daemon
"""

_PRESS_EPILOG = """Examples:
  py-ydotool press ENTER
  py-ydotool press CTRL V --hotkey
  py-ydotool press J L T ENTER --interval 0.2
"""

_CLICK_EPILOG = """Examples:
  py-ydotool click
  py-ydotool click --button right
  py-ydotool click --button 0xC0 --repeat 2 --next-delay-ms 50
"""

_MOVE_EPILOG = """Examples:
  py-ydotool move 400 220
  py-ydotool move 25 -10 --relative
"""

_CLICK_AT_EPILOG = """Examples:
  py-ydotool click-at 400 220
  py-ydotool click-at 400 220 --button right
"""

_DOUBLE_CLICK_EPILOG = """Examples:
  py-ydotool double-click
  py-ydotool double-click --button right --interval 0.2
"""

_MOUSE_DOWN_EPILOG = """Examples:
  py-ydotool mouse-down
  py-ydotool mouse-down --button middle
"""

_MOUSE_UP_EPILOG = """Examples:
  py-ydotool mouse-up
  py-ydotool mouse-up --button middle
"""

_DRAG_EPILOG = """Examples:
  py-ydotool drag 100 100 400 200
  py-ydotool drag 100 100 400 200 --button right
"""

_COPY_EPILOG = """Examples:
  py-ydotool copy "hello"
  py-ydotool copy "hello" --backend xclip
"""

_GET_CLIPBOARD_EPILOG = """Examples:
  py-ydotool get-clipboard
  py-ydotool get-clipboard --backend wl-clipboard
"""

_PASTE_EPILOG = """Examples:
  py-ydotool paste
  py-ydotool paste --no-daemon
"""

_PASTE_TEXT_EPILOG = """Examples:
  py-ydotool paste-text "hello"
  py-ydotool paste-text "hello" --backend xsel
"""

_BUTTON_ALIASES = {
    "left": MouseButton.LEFT,
    "right": MouseButton.RIGHT,
    "middle": MouseButton.MIDDLE,
    "side": MouseButton.SIDE,
    "extra": MouseButton.EXTRA,
    "forward": MouseButton.FORWARD,
    "back": MouseButton.BACK,
    "task": MouseButton.TASK,
}


_SUPPORTED_CLIPBOARD_BACKEND_NAMES = supported_clipboard_backend_names()
_SUPPORTED_CLIPBOARD_BACKENDS_TEXT = ", ".join(_SUPPORTED_CLIPBOARD_BACKEND_NAMES)


def _non_empty_cli_text(name: str) -> Callable[[str], str]:
    def _parser(value: str) -> str:
        if not value:
            raise argparse.ArgumentTypeError(f"{name} must not be empty")
        return value

    return _parser


def _integer_cli_value(name: str) -> Callable[[str], int]:
    def _parser(value: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc

    return _parser


def _real_number_cli_value(name: str) -> Callable[[str], float]:
    def _parser(value: str) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be a real number") from exc

    return _parser


def _non_negative_int_cli_value(name: str) -> Callable[[str], int]:
    def _parser(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
        if parsed < 0:
            raise argparse.ArgumentTypeError(f"{name} must be >= 0")
        return parsed

    return _parser


def _positive_int_cli_value(name: str) -> Callable[[str], int]:
    def _parser(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
        if parsed <= 0:
            raise argparse.ArgumentTypeError(f"{name} must be > 0")
        return parsed

    return _parser


def _add_socket_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--socket-path",
        default=default_socket_path(),
        type=_non_empty_cli_text("socket_path"),
        help="Socket path to use (default: %(default)s)",
    )


def _add_command_timeout_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--command-timeout",
        default=5.0,
        type=_real_number_cli_value("command_timeout"),
        help="Per-command timeout in seconds (default: %(default)s)",
    )


def _add_type_delay_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--type-delay-ms",
        default=0,
        type=_non_negative_int_cli_value("type_delay_ms"),
        help="Delay between typed characters in milliseconds (default: %(default)s)",
    )


def _clipboard_backend_cli_value(value: str) -> str:
    backend = _non_empty_cli_text("backend")(value).strip().lower()
    if backend in _SUPPORTED_CLIPBOARD_BACKEND_NAMES:
        return backend
    raise argparse.ArgumentTypeError(
        "unknown clipboard backend: "
        f"{value!r}. Supported backends: {_SUPPORTED_CLIPBOARD_BACKENDS_TEXT}"
    )


def _add_clipboard_backend_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        default=None,
        type=_clipboard_backend_cli_value,
        help=(
            "Clipboard backend name to force instead of auto-detection. "
            f"Supported backends: {_SUPPORTED_CLIPBOARD_BACKENDS_TEXT}."
        ),
    )


def _add_tool_options(
    parser: argparse.ArgumentParser,
    *,
    include_socket_path: bool = True,
    include_type_delay: bool = False,
    include_clipboard_backend: bool = False,
) -> None:
    if include_socket_path:
        _add_socket_option(parser)
    _add_command_timeout_option(parser)
    if include_type_delay:
        _add_type_delay_option(parser)
    if include_clipboard_backend:
        _add_clipboard_backend_option(parser)


def _add_daemon_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-daemon",
        action="store_true",
        help="Do not start/stop ydotoold automatically for this one-shot command",
    )
    parser.add_argument(
        "--ready-timeout",
        default=5.0,
        type=_real_number_cli_value("ready_timeout"),
        help=("How long to wait for ydotoold readiness when auto-starting (default: %(default)s)"),
    )
    parser.add_argument(
        "--stop-timeout",
        default=1.0,
        type=_real_number_cli_value("stop_timeout"),
        help=("How long to wait for ydotoold to stop when auto-starting (default: %(default)s)"),
    )
    parser.add_argument(
        "--settle-delay",
        default=0.2,
        type=_real_number_cli_value("settle_delay"),
        help=(
            "Quiet period to keep after the last input before stopping an "
            "owned daemon (default: %(default)s)"
        ),
    )


def _add_runtime_options(
    parser: argparse.ArgumentParser,
    *,
    include_type_delay: bool = False,
    include_clipboard_backend: bool = False,
) -> None:
    _add_tool_options(
        parser,
        include_type_delay=include_type_delay,
        include_clipboard_backend=include_clipboard_backend,
    )
    _add_daemon_options(parser)


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
        type=_non_empty_cli_text("socket_path"),
        help="Socket path to inspect (default: %(default)s)",
    )
    doctor.add_argument(
        "--user",
        default=None,
        type=_non_empty_cli_text("user"),
        help="Evaluate /dev/uinput access for this user instead of the current user",
    )
    doctor.add_argument(
        "--group",
        default="input",
        type=_non_empty_cli_text("group"),
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
        type=_non_empty_cli_text("socket_path"),
        help="Socket path to mention in post-setup guidance (default: %(default)s)",
    )
    setup.add_argument(
        "--user",
        default=None,
        type=_non_empty_cli_text("user"),
        help="User to add to the uinput-capable group (defaults to the invoking user)",
    )
    setup.add_argument(
        "--group",
        default="input",
        type=_non_empty_cli_text("group"),
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

    type_parser = subparsers.add_parser(
        "type",
        help="Type a text string with py-ydotool",
        description=(
            "Type text through ydotool, optionally auto-starting ydotoold for "
            "this one-shot command."
        ),
        epilog=_TYPE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    type_parser.add_argument("text", type=str, help="Text to type")
    _add_runtime_options(type_parser, include_type_delay=True)

    press = subparsers.add_parser(
        "press",
        help="Press one or more keys by name or keycode",
        description=(
            "Press one or more keys through ydotool. Use `--hotkey` to hold "
            "all keys together "
            "before releasing them in reverse order."
        ),
        epilog=_PRESS_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    press.add_argument(
        "keys",
        nargs="+",
        help="Key names like ENTER or CTRL, or numeric keycodes",
    )
    press.add_argument(
        "--interval",
        default=0.0,
        type=_real_number_cli_value("interval"),
        help="Delay between sequential key presses in seconds (default: %(default)s)",
    )
    press.add_argument(
        "--hotkey",
        action="store_true",
        help="Press all given keys as a single hotkey chord instead of sequentially",
    )
    _add_runtime_options(press)

    click = subparsers.add_parser(
        "click",
        help="Click a mouse button",
        description=(
            "Click a mouse button through ydotool, optionally auto-starting "
            "ydotoold for this one-shot command."
        ),
        epilog=_CLICK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    click.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    click.add_argument(
        "--repeat",
        default=None,
        type=_positive_int_cli_value("repeat"),
        help="How many clicks to send",
    )
    click.add_argument(
        "--next-delay-ms",
        default=None,
        type=_non_negative_int_cli_value("next_delay_ms"),
        help="Delay between repeated clicks in milliseconds",
    )
    _add_runtime_options(click)

    move = subparsers.add_parser(
        "move",
        help="Move the mouse pointer",
        description=(
            "Move the mouse pointer through ydotool, optionally auto-starting "
            "ydotoold for this one-shot command."
        ),
        epilog=_MOVE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    move.add_argument("x", type=_integer_cli_value("x"), help="Target X coordinate")
    move.add_argument("y", type=_integer_cli_value("y"), help="Target Y coordinate")
    move.add_argument(
        "--relative",
        action="store_true",
        help="Treat X and Y as relative deltas instead of an absolute position",
    )
    _add_runtime_options(move)

    click_at = subparsers.add_parser(
        "click-at",
        help="Move to a point and click there",
        description=(
            "Move to an absolute point, then click a mouse button through ydotool, "
            "optionally auto-starting ydotoold for this one-shot command."
        ),
        epilog=_CLICK_AT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    click_at.add_argument("x", type=_integer_cli_value("x"), help="Target X coordinate")
    click_at.add_argument("y", type=_integer_cli_value("y"), help="Target Y coordinate")
    click_at.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    click_at.add_argument(
        "--repeat",
        default=None,
        type=_positive_int_cli_value("repeat"),
        help="How many clicks to send",
    )
    click_at.add_argument(
        "--next-delay-ms",
        default=None,
        type=_non_negative_int_cli_value("next_delay_ms"),
        help="Delay between repeated clicks in milliseconds",
    )
    _add_runtime_options(click_at)

    double_click = subparsers.add_parser(
        "double-click",
        help="Double-click a mouse button",
        description=(
            "Double-click a mouse button through ydotool, optionally auto-starting "
            "ydotoold for this one-shot command."
        ),
        epilog=_DOUBLE_CLICK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    double_click.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    double_click.add_argument(
        "--interval",
        default=0.1,
        type=_real_number_cli_value("interval"),
        help="Delay between the two clicks in seconds (default: %(default)s)",
    )
    _add_runtime_options(double_click)

    mouse_down = subparsers.add_parser(
        "mouse-down",
        help="Press and hold a mouse button",
        description=(
            "Press and hold a mouse button through ydotool. For multi-command shell "
            "sequences, reuse the same socket with --no-daemon so the held button stays "
            "active until a later mouse-up."
        ),
        epilog=_MOUSE_DOWN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mouse_down.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    _add_runtime_options(mouse_down)

    mouse_up = subparsers.add_parser(
        "mouse-up",
        help="Release a mouse button",
        description=(
            "Release a mouse button through ydotool. Pair this with an earlier "
            "mouse-down on the same long-lived daemon/socket when scripting shell-side "
            "drag sequences."
        ),
        epilog=_MOUSE_UP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mouse_up.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    _add_runtime_options(mouse_up)

    drag = subparsers.add_parser(
        "drag",
        help="Drag the pointer between two absolute points",
        description=(
            "Move to a start point, hold a mouse button, then drag to an end point through "
            "ydotool, optionally auto-starting ydotoold for this one-shot command."
        ),
        epilog=_DRAG_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    drag.add_argument("start_x", type=_integer_cli_value("start_x"), help="Start X coordinate")
    drag.add_argument("start_y", type=_integer_cli_value("start_y"), help="Start Y coordinate")
    drag.add_argument("end_x", type=_integer_cli_value("end_x"), help="End X coordinate")
    drag.add_argument("end_y", type=_integer_cli_value("end_y"), help="End Y coordinate")
    drag.add_argument(
        "--button",
        default="left",
        help=("Mouse button name (left/right/middle/side/extra/forward/back/task) or hex code"),
    )
    _add_runtime_options(drag)

    copy = subparsers.add_parser(
        "copy",
        help="Copy text to the clipboard",
        description=(
            "Copy text to the system clipboard with the selected backend without touching ydotoold."
        ),
        epilog=_COPY_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    copy.add_argument("text", type=str, help="Text to copy")
    _add_tool_options(copy, include_socket_path=False, include_clipboard_backend=True)

    get_clipboard = subparsers.add_parser(
        "get-clipboard",
        help="Print the current clipboard text",
        description=(
            "Print the current system clipboard text with the selected backend "
            "without touching ydotoold."
        ),
        epilog=_GET_CLIPBOARD_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_tool_options(
        get_clipboard,
        include_socket_path=False,
        include_clipboard_backend=True,
    )

    paste = subparsers.add_parser(
        "paste",
        help="Send the paste hotkey",
        description=(
            "Send the usual Ctrl+V paste hotkey through ydotool, optionally "
            "auto-starting ydotoold for this one-shot command. This does not "
            "modify clipboard contents first; use paste-text when you want copy "
            "+ paste in one step."
        ),
        epilog=_PASTE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_runtime_options(paste)

    paste_text = subparsers.add_parser(
        "paste-text",
        help="Copy text, then send the paste hotkey",
        description=(
            "Copy text to the system clipboard with the selected backend, then "
            "send the usual Ctrl+V paste hotkey through ydotool, optionally "
            "auto-starting ydotoold for this one-shot command."
        ),
        epilog=_PASTE_TEXT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    paste_text.add_argument("text", type=str, help="Text to copy and paste")
    _add_runtime_options(paste_text, include_clipboard_backend=True)

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


def _key_name_map() -> dict[str, int]:
    result: dict[str, int] = {}
    for name, value in vars(Key).items():
        if name.startswith("_") or not isinstance(value, int):
            continue
        result[name.upper()] = value
    return result


def _parse_keycode_token(token: str) -> int:
    normalized = token.strip().upper().replace("-", "_")
    if not normalized:
        raise ValueError("key name must not be empty")

    key_map = _key_name_map()
    if normalized in key_map:
        return key_map[normalized]

    try:
        return int(token, 0)
    except ValueError as exc:
        raise ValueError(
            f"unknown key: {token!r}. Use names like ENTER or CTRL, or pass a numeric keycode."
        ) from exc


def _parse_keycode_tokens(tokens: Sequence[str]) -> list[int]:
    return [_parse_keycode_token(token) for token in tokens]


def _parse_button_token(token: str) -> str:
    normalized = token.strip().lower()
    if not normalized:
        raise ValueError("button must not be empty")
    if normalized in _BUTTON_ALIASES:
        return _BUTTON_ALIASES[normalized]
    if normalized.startswith("0x"):
        return normalized
    raise ValueError(
        "unknown button: "
        f"{token!r}. Use left/right/middle/side/extra/forward/back/task "
        "or a hex code like 0xC0."
    )


def _tool_from_args(args: argparse.Namespace) -> PyYDoTool:
    kwargs = {"command_timeout": args.command_timeout}
    if hasattr(args, "socket_path"):
        kwargs["socket_path"] = args.socket_path
    if hasattr(args, "type_delay_ms"):
        kwargs["type_delay_ms"] = args.type_delay_ms
    if hasattr(args, "backend"):
        kwargs["clipboard_backend"] = args.backend
    return PyYDoTool(**kwargs)


def _run_with_optional_daemon(args: argparse.Namespace, action: Callable[[PyYDoTool], None]) -> int:
    tool = _tool_from_args(args)
    context = (
        nullcontext()
        if args.no_daemon
        else tool.daemon(
            ready_timeout=args.ready_timeout,
            stop_timeout=args.stop_timeout,
            settle_delay=args.settle_delay,
        )
    )
    with context:
        action(tool)
    return 0


def _run_type(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.text:
        parser.error("text must not be empty")
    return _run_with_optional_daemon(args, lambda tool: tool.type(args.text))


def _run_press(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        keycodes = _parse_keycode_tokens(args.keys)
    except ValueError as exc:
        parser.error(str(exc))

    if args.hotkey and args.interval != 0.0:
        parser.error("--interval cannot be used together with --hotkey")

    def _action(tool: PyYDoTool) -> None:
        if args.hotkey:
            tool.hotkey(*keycodes)
            return
        tool.press_many(keycodes, interval=args.interval)

    return _run_with_optional_daemon(args, _action)


def _run_click(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    def _action(tool: PyYDoTool) -> None:
        tool.click(button=button, repeat=args.repeat, next_delay_ms=args.next_delay_ms)

    return _run_with_optional_daemon(args, _action)


def _run_move(args: argparse.Namespace) -> int:
    def _action(tool: PyYDoTool) -> None:
        if args.relative:
            tool.move_rel(args.x, args.y)
            return
        tool.move_to(args.x, args.y)

    return _run_with_optional_daemon(args, _action)


def _run_click_at(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    def _action(tool: PyYDoTool) -> None:
        tool.click_at(
            args.x,
            args.y,
            button=button,
            repeat=args.repeat,
            next_delay_ms=args.next_delay_ms,
        )

    return _run_with_optional_daemon(args, _action)


def _run_double_click(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    def _action(tool: PyYDoTool) -> None:
        tool.double_click(button=button, interval=args.interval)

    return _run_with_optional_daemon(args, _action)


def _run_mouse_down(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    return _run_with_optional_daemon(args, lambda tool: tool.mouse_down(button=button))


def _run_mouse_up(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    return _run_with_optional_daemon(args, lambda tool: tool.mouse_up(button=button))


def _run_drag(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        button = _parse_button_token(args.button)
    except ValueError as exc:
        parser.error(str(exc))

    def _action(tool: PyYDoTool) -> None:
        tool.drag_between(args.start_x, args.start_y, args.end_x, args.end_y, button=button)

    return _run_with_optional_daemon(args, _action)


def _run_copy(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.text:
        parser.error("text must not be empty")
    tool = _tool_from_args(args)
    tool.copy(args.text)
    return 0


def _run_get_clipboard(args: argparse.Namespace) -> int:
    tool = _tool_from_args(args)
    print(tool.get_clipboard(), end="")
    return 0


def _run_paste(args: argparse.Namespace) -> int:
    return _run_with_optional_daemon(args, lambda tool: tool.paste())


def _run_paste_text(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.text:
        parser.error("text must not be empty")
    return _run_with_optional_daemon(args, lambda tool: tool.paste_text(args.text))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "setup":
        return _run_setup(args)
    if args.command == "type":
        return _run_type(args, parser)
    if args.command == "press":
        return _run_press(args, parser)
    if args.command == "click":
        return _run_click(args, parser)
    if args.command == "move":
        return _run_move(args)
    if args.command == "click-at":
        return _run_click_at(args, parser)
    if args.command == "double-click":
        return _run_double_click(args, parser)
    if args.command == "mouse-down":
        return _run_mouse_down(args, parser)
    if args.command == "mouse-up":
        return _run_mouse_up(args, parser)
    if args.command == "drag":
        return _run_drag(args, parser)
    if args.command == "copy":
        return _run_copy(args, parser)
    if args.command == "get-clipboard":
        return _run_get_clipboard(args)
    if args.command == "paste":
        return _run_paste(args)
    if args.command == "paste-text":
        return _run_paste_text(args, parser)
    parser.error(f"unknown command: {args.command}")
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
