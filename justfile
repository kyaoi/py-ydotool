set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
  @just --list

sync:
  uv sync

fmt:
  uv run ruff format .

lint:
  uv run ruff check .
  uv run ruff format --check .

fix:
  uv run ruff check --fix .
  uv run ruff format .

test:
  uv run pytest -m "not integration"

test-integration:
  PY_YDOTOOL_RUN_INTEGRATION=1 uv run pytest -m integration

doctor:
  uv run python -m py_ydotool doctor

doctor-strict:
  uv run python -m py_ydotool doctor --strict

doctor-json:
  uv run python -m py_ydotool doctor --json

doctor-strict-json:
  uv run python -m py_ydotool doctor --json --strict

setup-dry-run:
  uv run python -m py_ydotool setup --dry-run

check:
  just fix
  just lint
  just test

ci:
  just lint
  just test

version:
  PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_version.py --print

version-check:
  PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_version.py

set-version version:
  PYTHONDONTWRITEBYTECODE=1 uv run python scripts/set_version.py {{version}}

release-version version:
  just set-version {{version}}
  git add pyproject.toml src/py_ydotool/VERSION uv.lock
  git commit -m "chore: bump version to {{version}}"
  just tag-version

tag-version:
  @version="$(PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_version.py --print)"; \
  dirty="$(git status --short -- pyproject.toml uv.lock src/py_ydotool/VERSION)"; \
  if [[ -n "$(git status --porcelain)" ]]; then \
    if [[ -n "$dirty" ]]; then \
      echo "Working tree is dirty. Commit version files before tagging v$version:" >&2; \
      echo "$dirty" >&2; \
    else \
      echo "Working tree is dirty. Commit or stash changes before tagging v$version." >&2; \
    fi; \
    exit 1; \
  fi; \
  if git rev-parse "v$version" >/dev/null 2>&1; then \
    echo "Tag already exists: v$version" >&2; \
    exit 1; \
  fi; \
  git tag "v$version"; \
  echo "Created tag v$version"

build:
  uv build

release-check: version-check ci build

hooks-install:
  lefthook install

setup:
  uv sync
  lefthook install
