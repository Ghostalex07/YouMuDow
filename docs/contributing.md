# Contributing

## Setup Development Environment

```bash
git clone <repo>
cd YouMuDow
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

- Follow PEP 8 and the [Ruff](https://docs.astral.sh/ruff/) defaults
  (`line-length = 100`).
- Use type hints; the core layers are type-checked with mypy.
- Write concise docstrings on public modules, classes and functions.

## Quality Gates

Run all checks before submitting a change:

```bash
PYTHONPATH=src python3 -m pytest            # tests
ruff check src/ tests/                      # lint
ruff format --check src/ tests/             # formatting
PYTHONPATH=src mypy                         # type checking
```

Or use `make check`, which runs all four.

## Pre-commit Hooks

Hooks are configured in `.pre-commit-config.yaml` (ruff lint + format, trailing
whitespace, end-of-file fixes, YAML checks):

```bash
pip install pre-commit
pre-commit install       # runs hooks on every commit
pre-commit run --all-files   # run once against the whole repo
```

## Testing

```bash
PYTHONPATH=src python3 -m pytest            # all tests
PYTHONPATH=src python3 -m pytest tests/unit/test_validators.py -v   # one file
PYTHONPATH=src python3 -m pytest --cov=youmudow   # coverage report
```

## Architecture Notes

- Keep the dependency direction `ui → app → services → domain`; `adapters`
  provides external integrations.
- Browser detection lives in `adapters/browser_profiles.py`, not `domain`.
- yt-dlp error parsing lives in `adapters/ytdlp_adapter.py`.
- Never swallow exceptions silently — use `logging.debug/exception`.

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes and pass the quality gates above
4. Submit a pull request
