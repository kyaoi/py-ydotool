set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
  @just --list

sync:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv sync

fmt:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run ruff format .

lint:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run ruff check .
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run ruff format --check .

fix:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run ruff check --fix .
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run ruff format .

test:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run pytest -m "not integration"

test-integration:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" PY_YDOTOOL_RUN_INTEGRATION=1 uv run pytest -m integration

doctor:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run python -m py_ydotool doctor

doctor-strict:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run python -m py_ydotool doctor --strict

doctor-json:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run python -m py_ydotool doctor --json

doctor-strict-json:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run python -m py_ydotool doctor --json --strict

setup-dry-run:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv run python -m py_ydotool setup --dry-run

check:
  just fix
  just lint
  just test

ci:
  just lint
  just test

version:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_version.py --print

version-check:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_version.py

set-version version:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" PYTHONDONTWRITEBYTECODE=1 uv run python scripts/set_version.py {{version}}

release-version version:
  just set-version {{version}}
  git add pyproject.toml src/py_ydotool/VERSION uv.lock
  git commit -m "chore: bump version to {{version}}"
  just tag-version

tag-version:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" PYTHONDONTWRITEBYTECODE=1 uv run python scripts/tag_version.py

build:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv build

release-check: version-check ci build

hooks-install:
  lefthook install

setup:
  MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" uv sync
  lefthook install
