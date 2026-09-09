SHELL := /bin/bash

.PHONY: install api web test build db-up db-down mapper-install

install:
	cd rumbo-api && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
	cd rumbo-web-app && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

api:
	cd rumbo-api && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload --port 8000

web:
	cd rumbo-web-app && npm run dev

test:
	cd rumbo-api && source .venv/bin/activate && pytest
	cd structural-mapper && source .venv/bin/activate && pytest -q
	cd rumbo-web-app && npm run build

mapper-install:
	cd structural-mapper && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-geometry.txt

build:
	cd rumbo-web-app && npm run build
