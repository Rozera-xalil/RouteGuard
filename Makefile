.PHONY: setup data validate train test lint api up down demo

setup:
	uv sync --all-groups

data:
	uv run python -m routeguard.build_data

validate:
	uv run python -m routeguard.validate

train:
	uv run python -m routeguard.train

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

api:
	uv run uvicorn app.main:app --reload --port 8000

up:
	docker compose up --build -d

down:
	docker compose down

# No Kaggle download? Build everything from a toy dataset.
demo:
	uv run python -m routeguard.synthetic --out data/raw --n 9000
	uv run python -m routeguard.build_data
	uv run python -m routeguard.validate
	uv run python -m routeguard.train --n-trials 8
