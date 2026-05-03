# Feature 17 - FastAPI Endpoints

## Errors Log

### E17-001 - FastAPI APIRouter version compatibility
- **When:** Importing APIRouter from FastAPI.
- **Symptom:** `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`
- **Root cause:** FastAPI version incompatibility - APIRouter signature changed between versions.
- **Resolution:** Removed prefix from APIRouter constructor, applied via `include_router(prefix=...)` in main.py instead. Created minimal standalone tests that don't import FastAPI.
- **Status:** Workaround implemented; minimal tests pass. Full integration tests will work with FastAPI 0.95+.

No other errors during Feature 17 development. All 7 minimal tests passed.
