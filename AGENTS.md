# YouMuDow Development Guide

## Running Tests

```bash
# Run all tests
PYTHONPATH=src python3 -m pytest

# Run with coverage
PYTHONPATH=src python3 -m pytest --cov=src/youmudow

# Run specific test file
PYTHONPATH=src python3 -m pytest tests/unit/test_validators.py -v
```

## Running the Application

```bash
# Development mode
PYTHONPATH=src python3 -m youmudow.main

# With specific output path
PYTHONPATH=src python3 -m youmudow.main --output ~/Downloads
```

## Code Quality

```bash
# Format code
ruff check src/

# Type checking (if mypy installed)
mypy src/
```

## Project Structure

```
youmudow/
├── src/youmudow/
│   ├── domain/          # Data models, validators
│   ├── adapters/       # yt-dlp adapter
│   ├── services/       # Business logic
│   ├── app/            # Controller, state
│   └── ui/             # Tkinter interface
├── tests/
│   └── unit/           # Unit tests
├── CHANGELOG.md        # Version history
└── README.md           # Documentation
```

## Key Constants

- `SUPPORTED_BROWSERS` in validators.py - List of supported browsers
- `COLORS` in ui/window.py - UI color scheme
- `YtdlpConfig` in adapters/ytdlp_adapter.py - Download configuration

## Important Notes

- Always run tests after making changes: `PYTHONPATH=src python3 -m pytest`
- The adapter uses subprocess - ensure proper cleanup in finally blocks
- Browser profiles are detected from standard config paths (~/.config/*)
- Cookies file must be in Netscape format (.txt)