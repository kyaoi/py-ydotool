import importlib.util
from pathlib import Path
from unittest.mock import Mock

from py_ydotool import __version__
from py_ydotool._version_tools import (
    evaluate_version_state,
    get_worktree_status,
    latest_release_tag,
    normalize_release_tag,
    parse_version,
    read_pyproject_version,
    read_version_file,
    refresh_lockfile,
    replace_pyproject_version_text,
    sync_release_tag,
    write_version,
)


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{script_name}_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_file_matches_runtime_version() -> None:
    assert read_version_file() == __version__


def test_pyproject_version_matches_version_file() -> None:
    assert read_pyproject_version() == read_version_file()


def test_parse_version_accepts_semver() -> None:
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v1.2.3") == (1, 2, 3)


def test_normalize_release_tag() -> None:
    assert normalize_release_tag("1.2.3") == "v1.2.3"


def test_latest_release_tag_picks_highest_semver() -> None:
    tags = ["v0.1.0", "not-a-release", "v0.2.0", "0.1.9"]
    assert latest_release_tag(tags) == "v0.2.0"


def test_replace_pyproject_version_text_rewrites_version() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    updated = replace_pyproject_version_text(pyproject_text, "9.9.9")
    assert 'version = "9.9.9"' in updated


def test_evaluate_version_state_accepts_matching_head_tag() -> None:
    result = evaluate_version_state(
        version_file_version="0.1.0",
        pyproject_version="0.1.0",
        head_tags=["v0.1.0"],
        repo_tags=["v0.1.0"],
    )
    assert result.ok is True


def test_evaluate_version_state_rejects_mismatch_between_files() -> None:
    result = evaluate_version_state(
        version_file_version="0.1.1",
        pyproject_version="0.1.0",
        head_tags=[],
        repo_tags=["v0.1.0"],
    )
    assert result.ok is False


def test_evaluate_version_state_requires_bump_after_latest_tag() -> None:
    result = evaluate_version_state(
        version_file_version="0.1.0",
        pyproject_version="0.1.0",
        head_tags=[],
        repo_tags=["v0.1.0"],
    )
    assert result.ok is False


def test_evaluate_version_state_accepts_newer_version_than_latest_tag() -> None:
    result = evaluate_version_state(
        version_file_version="0.1.1",
        pyproject_version="0.1.1",
        head_tags=[],
        repo_tags=["v0.1.0"],
    )
    assert result.ok is True


def test_replace_pyproject_version_text_allows_same_version() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    same = replace_pyproject_version_text(pyproject_text, read_version_file())
    assert same == pyproject_text


def test_normalize_release_tag_accepts_existing_v_prefix() -> None:
    assert normalize_release_tag("v1.2.3") == "v1.2.3"


def test_evaluate_version_state_accepts_matching_head_tag_without_dirty_bump() -> None:
    result = evaluate_version_state(
        version_file_version="0.2.0",
        pyproject_version="0.2.0",
        head_tags=["v0.2.0"],
        repo_tags=["v0.1.0", "v0.2.0"],
    )
    assert result.ok is True


def test_refresh_lockfile_runs_uv_lock(monkeypatch) -> None:
    run = Mock()
    monkeypatch.setattr("py_ydotool._version_tools.subprocess.run", run)

    refresh_lockfile()

    run.assert_called_once_with(["uv", "lock"], check=True, cwd=Path.cwd())


def test_write_version_can_skip_lock_refresh(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    pyproject_file = tmp_path / "pyproject.toml"
    version_file.write_text("0.1.0\n", encoding="utf-8")
    pyproject_file.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    write_version(
        "0.1.1",
        version_file=version_file,
        pyproject_file=pyproject_file,
        refresh_lock=False,
    )

    assert version_file.read_text(encoding="utf-8") == "0.1.1\n"
    assert 'version = "0.1.1"' in pyproject_file.read_text(encoding="utf-8")


def test_write_version_refreshes_lock_when_requested(tmp_path: Path, monkeypatch) -> None:
    version_file = tmp_path / "VERSION"
    pyproject_file = tmp_path / "pyproject.toml"
    version_file.write_text("0.1.0\n", encoding="utf-8")
    pyproject_file.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    refresh = Mock()
    monkeypatch.setattr("py_ydotool._version_tools.refresh_lockfile", refresh)

    write_version(
        "0.1.1",
        version_file=version_file,
        pyproject_file=pyproject_file,
        refresh_lock=True,
    )

    refresh.assert_called_once_with()


def test_get_worktree_status_checks_requested_paths(monkeypatch) -> None:
    run = Mock(
        return_value=Mock(
            stdout=" M pyproject.toml\n?? scratch.txt\n",
            returncode=0,
        )
    )
    monkeypatch.setattr("py_ydotool._version_tools.subprocess.run", run)

    result = get_worktree_status("pyproject.toml", "src/py_ydotool/VERSION")

    assert result == ["M pyproject.toml", "?? scratch.txt"]
    run.assert_called_once_with(
        [
            "git",
            "status",
            "--short",
            "--",
            "pyproject.toml",
            "src/py_ydotool/VERSION",
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def test_sync_release_tag_creates_missing_tag(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool._version_tools.get_head_commit", lambda: "abcdef1234567890")
    monkeypatch.setattr("py_ydotool._version_tools.get_tag_commit", lambda tag: None)
    run = Mock()
    monkeypatch.setattr("py_ydotool._version_tools.subprocess.run", run)

    result = sync_release_tag("1.2.3")

    assert result.action == "created"
    assert result.tag == "v1.2.3"
    assert result.message == "Created tag v1.2.3"
    run.assert_called_once_with(["git", "tag", "v1.2.3"], check=True)


def test_sync_release_tag_moves_existing_tag_to_head(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool._version_tools.get_head_commit", lambda: "abcdef1234567890")
    monkeypatch.setattr(
        "py_ydotool._version_tools.get_tag_commit",
        lambda tag: "1234567890abcdef",
    )
    run = Mock()
    monkeypatch.setattr("py_ydotool._version_tools.subprocess.run", run)

    result = sync_release_tag("1.2.3")

    assert result.action == "moved"
    assert result.tag == "v1.2.3"
    assert result.message == "Moved tag v1.2.3 to HEAD from 1234567"
    run.assert_called_once_with(["git", "tag", "-f", "v1.2.3"], check=True)


def test_sync_release_tag_keeps_tag_already_pointing_at_head(monkeypatch) -> None:
    monkeypatch.setattr("py_ydotool._version_tools.get_head_commit", lambda: "abcdef1234567890")
    monkeypatch.setattr(
        "py_ydotool._version_tools.get_tag_commit",
        lambda tag: "abcdef1234567890",
    )
    run = Mock()
    monkeypatch.setattr("py_ydotool._version_tools.subprocess.run", run)

    result = sync_release_tag("1.2.3")

    assert result.action == "unchanged"
    assert result.tag == "v1.2.3"
    assert result.message == "Tag already points at HEAD: v1.2.3"
    run.assert_not_called()


def test_check_version_script_prints_current_version(capsys, monkeypatch) -> None:
    check_version = _load_script_module("check_version")
    monkeypatch.setattr("sys.argv", ["check_version.py", "--print"])

    exit_code = check_version.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == read_version_file()
    assert captured.err == ""


def test_check_version_script_reports_failure_to_stderr(capsys, monkeypatch) -> None:
    check_version = _load_script_module("check_version")
    monkeypatch.setattr(
        check_version,
        "check_repository_version",
        lambda: evaluate_version_state(
            version_file_version="0.1.0",
            pyproject_version="0.1.1",
            head_tags=[],
            repo_tags=[],
        ),
    )
    monkeypatch.setattr("sys.argv", ["check_version.py"])

    exit_code = check_version.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Version mismatch" in captured.err
    assert captured.out == ""


def test_set_version_script_writes_version_and_prints_next_tag(capsys, monkeypatch) -> None:
    set_version = _load_script_module("set_version")
    write = Mock()
    monkeypatch.setattr(set_version, "write_version", write)
    monkeypatch.setattr("sys.argv", ["set_version.py", "1.2.3"])

    exit_code = set_version.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    write.assert_called_once_with("1.2.3", refresh_lock=True)
    assert "Updated version to 1.2.3." in captured.out
    assert "Next release tag: v1.2.3" in captured.out
    assert captured.err == ""


def test_tag_version_script_rejects_dirty_version_files(capsys, monkeypatch) -> None:
    tag_version = _load_script_module("tag_version")
    monkeypatch.setattr(tag_version, "read_version_file", lambda: "1.2.3")
    statuses = iter([["M pyproject.toml"], ["M pyproject.toml"]])
    monkeypatch.setattr(tag_version, "get_worktree_status", lambda *paths: next(statuses))

    exit_code = tag_version.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Commit version files before tagging v1.2.3" in captured.err
    assert "M pyproject.toml" in captured.err


def test_tag_version_script_prints_sync_message(capsys, monkeypatch) -> None:
    tag_version = _load_script_module("tag_version")
    monkeypatch.setattr(tag_version, "read_version_file", lambda: "1.2.3")
    monkeypatch.setattr(tag_version, "get_worktree_status", lambda *paths: [])
    monkeypatch.setattr(
        tag_version,
        "sync_release_tag",
        lambda version: Mock(message=f"Moved tag v{version} to HEAD from 1234567"),
    )

    exit_code = tag_version.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Moved tag v1.2.3 to HEAD from 1234567"
    assert captured.err == ""
