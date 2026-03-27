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

build:
  uv build

hooks-install:
  lefthook install

setup:
  uv sync
  lefthook install
