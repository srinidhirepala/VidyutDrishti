# Feature 01 - Project Scaffolding & Docker Compose Skeleton

## Errors Log

### E01-001 - Host Python is 3.10, `tomllib` unavailable
- **When:** While designing the scaffolding test (`tests/test_scaffold.py`).
- **Symptom:** `ModuleNotFoundError: No module named 'tomllib'` when probing the host environment.
- **Root cause:** `tomllib` is a standard-library module only from Python 3.11 onwards. The target runtime (Docker image `python:3.11-slim`) has it, but the developer host does not.
- **Resolution:** Replaced TOML parsing in the prototype test with a regex assertion on the raw file contents. The regex checks that `requires-python = ">=3.11"` is present and that each core dependency name is listed. No production signal lost for prototype-grade verification.
- **Status:** Resolved. Test passes on Python 3.10 host.

### E01-002 - PowerShell treats stderr as error stream
- **When:** Running `git push` and `python -m unittest`.
- **Symptom:** Non-zero exit reported by the shell wrapper even though the underlying commands succeeded (git: "new branch main -> main"; unittest: "OK" with `Ran 9 tests`).
- **Root cause:** PowerShell surfaces any data on stderr as a `NativeCommandError`. Many Unix-friendly tools log non-error progress to stderr.
- **Resolution:** Ignored spurious exit codes after confirming the primary output string ("OK" for unittest, "new branch" for git push). Not a VidyutDrishti bug; a shell quirk. No code change required.
- **Status:** Resolved / documented.

No other errors encountered during Feature 01.

