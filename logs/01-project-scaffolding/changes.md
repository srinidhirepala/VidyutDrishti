# Feature 01 - Project Scaffolding & Docker Compose Skeleton

## Changes Log

### Implemented as specified in `features.md` section 01
- Monorepo layout created: `backend/`, `frontend/`, `simulator/`, `db/migrations/`, `db/seed/`, `infra/`, `logs/`.
- `docker-compose.yml` with baseline services (`timescaledb`, `backend`, `frontend`).
- `infra/.env.sample` with DB, simulator, API, and feature-flag variables.
- `backend/pyproject.toml` pinning Python 3.11 and the full dependency matrix listed in `README.md`.
- `frontend/package.json` scaffolded with React 18, Vite 5, TypeScript 5, Vitest, Recharts, Leaflet, react-leaflet, TanStack Query, axios.
- Root `Makefile` with `up`, `down`, `reset`, `seed`, `lint`, `test`, `logs` targets.

### Deviations from plan
- **Package manager choice deferred.** `features.md` left "Poetry/uv chosen at commit time" open. Chose **pip + pyproject.toml editable install** instead - keeps the Docker image simple and avoids adding a lock-file ecosystem before it's needed. Can swap to uv in a later feature if install times become painful.
- **pnpm not yet introduced.** Frontend is scaffolded with plain `npm` in `Dockerfile.frontend` since `package-lock.json` has not been generated (no Node runtime available in this host environment). Feature 18 will commit an actual lockfile and can switch to pnpm at that point.
- **Vite source tree not created.** `frontend/index.html` references `/src/main.tsx` which will be created in Feature 18. Feature 01 only commits the declarative surface (package.json, index.html, README); runtime React code lives with the dashboard feature.
- **Dockerfiles marked as skeletons.** Final multi-stage builds and healthchecks are deferred to Feature 22 per the plan.
- **Pre-commit hooks not wired.** `features.md` mentions ruff/black/mypy/eslint/prettier pre-commit; these are declared in `pyproject.toml` and `package.json` respectively, but a `.pre-commit-config.yaml` is deliberately deferred until there is real code to lint (Feature 02 onwards).

### New additions not explicitly in the plan
- `backend/app/config.py` with a `Settings` class using `pydantic-settings`. Chosen over a hand-rolled `os.getenv` approach so every later feature (ingestion, scheduler, API) can import `get_settings()` consistently from day one.
- `backend/app/main.py` with a `/health` stub. Not strictly required by Feature 01, but ensures the Docker image has something to serve on port 8000 and makes Feature 22's healthcheck trivial.
- `logs/README.md` added to explain the per-feature log folder discipline for anyone browsing the repo.

