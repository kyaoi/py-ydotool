from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "src" / "py_ydotool" / "VERSION"
PYPROJECT_FILE = ROOT / "pyproject.toml"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True, slots=True)
class VersionCheckResult:
    ok: bool
    message: str


def read_version_file(path: Path = VERSION_FILE) -> str:
    return path.read_text(encoding="utf-8").strip()


def read_pyproject_version(path: Path = PYPROJECT_FILE) -> str:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def parse_version(text: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"Invalid version: {text!r}")
    return tuple(int(part) for part in match.groups())


def is_release_tag(tag: str) -> bool:
    return _VERSION_RE.fullmatch(tag.strip()) is not None


def tag_to_version(tag: str) -> str:
    major, minor, patch = parse_version(tag)
    return f"{major}.{minor}.{patch}"


def normalize_release_tag(version: str) -> str:
    major, minor, patch = parse_version(version)
    return f"v{major}.{minor}.{patch}"


def latest_release_tag(tags: Iterable[str]) -> str | None:
    release_tags = [tag for tag in tags if is_release_tag(tag)]
    if not release_tags:
        return None
    return max(release_tags, key=lambda tag: parse_version(tag_to_version(tag)))


def replace_pyproject_version_text(text: str, new_version: str) -> str:
    parse_version(new_version)
    pattern = r'(?m)^version = "[^"]+"$'
    if re.search(pattern, text) is None:
        raise ValueError("Could not find [project].version in pyproject.toml")
    return re.sub(
        pattern,
        f'version = "{new_version}"',
        text,
        count=1,
    )


def write_version(new_version: str) -> None:
    parse_version(new_version)
    VERSION_FILE.write_text(f"{new_version}\n", encoding="utf-8")
    pyproject_text = PYPROJECT_FILE.read_text(encoding="utf-8")
    PYPROJECT_FILE.write_text(
        replace_pyproject_version_text(pyproject_text, new_version),
        encoding="utf-8",
    )


def git_output(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_head_tags() -> list[str]:
    return git_output("tag", "--points-at", "HEAD")


def get_repo_tags() -> list[str]:
    return git_output("tag")


def evaluate_version_state(
    *,
    version_file_version: str,
    pyproject_version: str,
    head_tags: Iterable[str],
    repo_tags: Iterable[str],
) -> VersionCheckResult:
    if version_file_version != pyproject_version:
        return VersionCheckResult(
            ok=False,
            message=(
                "Version mismatch: "
                f"VERSION={version_file_version} pyproject={pyproject_version}. "
                "Run `just set-version <version>` to sync them."
            ),
        )

    normalized_version_tag = normalize_release_tag(version_file_version)
    normalized_head_release_tags = [
        normalize_release_tag(tag_to_version(tag)) for tag in head_tags if is_release_tag(tag)
    ]

    if normalized_head_release_tags:
        if normalized_version_tag not in normalized_head_release_tags:
            return VersionCheckResult(
                ok=False,
                message=(
                    "HEAD has a release tag, but it does not match the package version: "
                    f"expected {normalized_version_tag}, "
                    f"got {', '.join(normalized_head_release_tags)}"
                ),
            )
        return VersionCheckResult(
            ok=True,
            message=f"Version check passed: HEAD tag matches {normalized_version_tag}.",
        )

    latest_tag = latest_release_tag(repo_tags)
    if latest_tag is None:
        return VersionCheckResult(
            ok=True,
            message=(
                "Version check passed: no prior release tag found; "
                f"current version is {version_file_version}."
            ),
        )

    current_tuple = parse_version(version_file_version)
    latest_tuple = parse_version(tag_to_version(latest_tag))
    if current_tuple <= latest_tuple:
        return VersionCheckResult(
            ok=False,
            message=(
                "Version has not been bumped since the latest release tag. "
                f"Current version: {version_file_version}. Latest tag: {latest_tag}. "
                "Bump the version before pushing, or tag HEAD with the matching release version."
            ),
        )

    return VersionCheckResult(
        ok=True,
        message=(
            "Version check passed: current version "
            f"{version_file_version} is newer than latest release tag {latest_tag}."
        ),
    )


def check_repository_version() -> VersionCheckResult:
    return evaluate_version_state(
        version_file_version=read_version_file(),
        pyproject_version=read_pyproject_version(),
        head_tags=get_head_tags(),
        repo_tags=get_repo_tags(),
    )
