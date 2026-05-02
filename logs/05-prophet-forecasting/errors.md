# Feature 05 - Prophet Forecasting

## Errors Log

### E05-001 - Prophet not available on host
- **When:** First test run on development workstation.
- **Symptom:** `ModuleNotFoundError: No module named 'prophet'` when importing forecasting modules.
- **Root cause:** Prophet requires C++ build tools and is not pre-installed on the Windows host used for development.
- **Resolution:** Wrapped all Prophet imports in `try/except` blocks, setting `PROPHET_AVAILABLE = False` when unavailable. Tests use `@unittest.skipUnless(PROPHET_AVAILABLE, ...)` to gate Prophet-dependent cases. The non-Prophet tests (dataclass validation, persistence stubs) still run and pass.
- **Status:** Resolved / accepted. Prophet will be available in the Docker image (listed in `pyproject.toml`) for Feature 22 end-to-end testing.

No other errors encountered during Feature 05 development.

