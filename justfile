set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
  @just --list

sync:
  uv sync

fmt:
  uv run ruff format .

lint:
  uv run ruff check .

fix:
  uv run ruff check --fix .
  uv run ruff format .

test:
  uv run pytest

check: lint test

ci: lint test

version:
  uv run python scripts/check_version.py --print

version-check:
  uv run python scripts/check_version.py

set-version version:
  uv run python scripts/set_version.py {{version}}

tag-version:
  git tag "v$(uv run python scripts/check_version.py --print)"

release-check: version-check ci build

build:
  uv build

hooks-install:
  lefthook install

setup:
  uv sync
  lefthook install
