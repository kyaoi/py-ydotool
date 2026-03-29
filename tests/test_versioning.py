from pathlib import Path

from py_ydotool import __version__
from scripts.version_tools import (
    evaluate_version_state,
    latest_release_tag,
    normalize_release_tag,
    parse_version,
    read_pyproject_version,
    read_version_file,
    replace_pyproject_version_text,
)


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
