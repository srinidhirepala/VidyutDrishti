# Feature 01 - Project Scaffolding & Docker Compose Skeleton

## Test Review

**Test file:** `tests/test_scaffold.py` (stdlib `unittest`, no third-party deps required).

**Run command:**
```powershell
python -m unittest logs/01-project-scaffolding/tests/test_scaffold.py -v
```

**Result:** `Ran 9 tests in 0.131s - OK` (9 passed, 0 failed, 0 errors).

### Coverage Map

| Test | Validates |
|------|-----------|
| `TestRepoLayout.test_required_paths_exist` | All 23 anchor files/folders promised in `features.md` section 01 exist on disk. |
| `TestRepoLayout.test_22_feature_log_folders` | Exactly 22 numbered feature folders are present under `logs/`. |
| `TestRepoLayout.test_each_feature_folder_has_log_files` | Every feature folder has `tests/`, `test_review.md`, `changes.md`, `errors.md`. |
| `TestFrontendPackageJson.test_valid_json` | `frontend/package.json` is parseable and identifies the correct project. |
| `TestFrontendPackageJson.test_core_libraries_declared` | `react`, `react-dom`, `leaflet`, `react-leaflet`, `recharts` declared in deps. |
| `TestFrontendPackageJson.test_dev_libraries_declared` | `vite`, `typescript`, `vitest` declared in devDependencies. |
| `TestDockerCompose.test_core_services_present` | `timescaledb`, `backend`, `frontend` services declared. |
| `TestPyProjectToml.test_requires_python_311` | Backend pins Python 3.11+. |
| `TestPyProjectToml.test_core_dependencies_declared` | FastAPI, SQLAlchemy, Alembic, Prophet, scikit-learn, APScheduler, holidays, Pandas all declared. |

### Observations

- Tests are deliberately **structural**, not behavioural. Feature 01 only promises scaffolding; there is no runtime logic to exercise yet. Behavioural tests begin with Feature 02 (simulator determinism).
- `tomllib` is Python 3.11+ only. The host here is 3.10, so the pyproject check uses regex rather than parsing. Once the Docker backend image is in use (Python 3.11), later features can switch to `tomllib` if desired.
- `yaml` is not relied upon at test time; `docker-compose.yml` is checked with substring assertions, which is sufficient for a "services exist" prototype check.

### Constraints Honoured

- Read-only posture: no test touches a DB or network.
- Prototype discipline: no production-grade assertions (e.g. exact dependency pinning, lockfile integrity).
- No functional gaps vs `features.md` section 01: every listed path exists and every promised service appears in the compose file.

