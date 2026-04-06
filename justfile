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
  PYTHONDONTWRITEBYTECODE=1 uv run python scripts/tag_version.py

build:
  uv build

release-check: version-check ci build

hooks-install:
  lefthook install

setup:
  uv sync
  lefthook install
