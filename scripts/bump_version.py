#!/usr/bin/env python3
"""Bump version across all files and create git tag.

Usage:
    python scripts/bump_version.py 1.1.0
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def bump(new_version: str) -> None:
    # pyproject.toml
    p = ROOT / "pyproject.toml"
    content = p.read_text()
    content = re.sub(r'(?<=^version = ")[\d.]+', new_version, content, flags=re.M)
    p.write_text(content)
    print(f"  pyproject.toml -> {new_version}")

    # __init__.py
    p = ROOT / "src" / "youmudow" / "__init__.py"
    content = p.read_text()
    content = re.sub(r'(?<=^__version__ = ")[\d.]+', new_version, content, flags=re.M)
    p.write_text(content)
    print(f"  __init__.py -> {new_version}")

    # README.md badge
    p = ROOT / "README.md"
    content = p.read_text()
    content = re.sub(r'version-[\d.]+-green', f'version-{new_version}-green', content)
    p.write_text(content)
    print(f"  README.md badge -> {new_version}")

    print(f"\nDone. To release:\n"
          f"  git add -A\n"
          f"  git commit -m 'chore: bump version to {new_version}'\n"
          f"  git tag v{new_version}\n"
          f"  git push origin main --tags")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py <version>")
        sys.exit(1)
    bump(sys.argv[1])
