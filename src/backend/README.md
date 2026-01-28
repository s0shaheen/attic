# Attic Backend

FastAPI backend for Attic - Personal analytics platform for TikTok data.

## Requirements

- Python 3.12+
- pip

## Setup

1. Create a virtual environment:
   ```bash
   cd src/backend
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development

### Running the server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Running tests

```bash
pytest tests/ -v
```

### Linting and formatting

```bash
# Check for lint errors
ruff check .

# Format code
ruff format .

# Check formatting without changes
ruff format --check .
```

## Project Structure

```
src/backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── models/           # Pydantic models
│   ├── routers/          # API route handlers
│   ├── services/         # Business logic
│   └── repositories/     # Data access layer
├── tests/
│   ├── __init__.py
│   ├── conftest.py       # Pytest fixtures
│   └── test_health.py    # Health endpoint tests
├── pyproject.toml        # Project configuration
├── ruff.toml             # Ruff linter configuration
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check endpoint |
