# VidyutDrishti top-level Makefile.
# Cross-platform: works under GNU Make on Linux/macOS and under
# Git Bash / WSL on Windows. Native PowerShell users can call the
# underlying commands directly.

.PHONY: help up down reset seed lint test logs

help:
	@echo "VidyutDrishti - common tasks"
	@echo "  make up      - docker compose up --build -d"
	@echo "  make down    - docker compose down"
	@echo "  make reset   - docker compose down -v (wipes pgdata)"
	@echo "  make seed    - run simulator seeder (Feature 02)"
	@echo "  make lint    - ruff + black + mypy + eslint"
	@echo "  make test    - pytest + vitest"
	@echo "  make logs    - docker compose logs -f"

up:
	docker compose up --build -d

down:
	docker compose down

reset:
	docker compose down -v

seed:
	python -m simulator.generate --out data/

lint:
	cd backend && ruff check . && black --check . && mypy app
	cd frontend && npm run lint || true

test:
	cd backend && pytest
	cd frontend && npm test || true

logs:
	docker compose logs -f
