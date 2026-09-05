# FinFlow Backend

FastAPI backend for the FinFlow personal treasury management system.

## Development

Environment is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # create the venv and install all dependencies
uv run uvicorn app.main:app --reload --port 8000
uv run pytest           # run the test suite
uv run ruff check .     # lint
uv run black --check .  # format check
uv run mypy app         # type check
```

The health endpoint is exposed at `GET /api/v1/health`.
