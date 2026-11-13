"""The UI package must be type-checked without a mypy escape hatch."""

from __future__ import annotations

import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


class TestNoMypyEscapeHatch:
    def test_pyproject_has_no_ignore_errors_override(self):
        content = PYPROJECT.read_text(encoding="utf-8")
        assert "ignore_errors" not in content

    def test_pyproject_has_no_ui_module_override_block(self):
        content = PYPROJECT.read_text(encoding="utf-8")
        assert not re.search(r"\[\[tool\.mypy\.overrides\]\].*?youmudow\.ui", content, re.DOTALL)

    def test_mypy_passes_on_ui_package(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "mypy", "src/youmudow/ui"],
            capture_output=True,
            text=True,
            cwd=str(PYPROJECT.parent),
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
