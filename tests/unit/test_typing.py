"""The UI package must be type-checked without a mypy escape hatch."""

from __future__ import annotations

import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
TESTS_DIR = Path(__file__).resolve().parents[1]


class TestNoMypyEscapeHatch:
    def test_pyproject_has_no_ignore_errors_override(self):
        content = PYPROJECT.read_text(encoding="utf-8")
        assert "ignore_errors" not in content

    def test_pyproject_has_no_ui_module_override_block(self):
        content = PYPROJECT.read_text(encoding="utf-8")
        assert not re.search(r"\[\[tool\.mypy\.overrides\]\].*?youmudow\.ui", content, re.DOTALL)


class TestNoDuplicateTypecheck:
    """The test jobs must not re-run mypy; the ``typecheck`` job owns that."""

    def test_no_test_module_shells_out_to_mypy(self):
        offenders = []
        for path in TESTS_DIR.rglob("*.py"):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            if re.search(r'"-m",\s*"mypy"|-m mypy', text):
                offenders.append(str(path.relative_to(TESTS_DIR)))
        assert offenders == []
