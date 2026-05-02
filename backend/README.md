# backend

VidyutDrishti backend: ingestion, forecasting, detection engine, and FastAPI.

## Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI entrypoint (fleshed out in Feature 17)
│   ├── config.py             # Pydantic settings
│   ├── db/                   # SQLAlchemy models and session
│   ├── ingestion/            # Feature 04
│   ├── forecasting/          # Features 05-07
│   ├── detection/            # Features 08-16
│   ├── feedback/             # Feature 19
│   ├── audit/                # Feature 20
│   ├── eval/                 # Feature 21
│   └── schemas/              # Pydantic API schemas
├── tests/
└── pyproject.toml
```

## Local dev (once dependencies are installed)

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
pytest
```
