#!/usr/bin/env python3
"""Build script for YouMuDow using PyInstaller."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ENTRY = ROOT / "src" / "youmudow" / "main.py"
HOOKS = ROOT / "scripts" / "hooks"

# Extra imports that are only reached lazily at runtime (loaded on demand,
# never importable from main's static call graph).
LAZY_HIDDEN_IMPORTS = [
    "youmudow.ui.icon",
    "youmudow.services.notification_service",
]

# PIL.ImageTk needs the Tk bridge: ``_imagingtk`` (binary) and
# ``_tkinter_finder`` (imports tkinter and is filtered out of the graph by
# PyInstaller's hook-PIL.py). Without them the frozen app cannot render
# thumbnails through Tkinter.
PIL_TK_HIDDEN_IMPORTS = [
    "PIL._imagingtk",
    "PIL._tkinter_finder",
]

# Modules that PyInstaller's analysis picks up from the Python environment
# (keyring -> gi -> GTK, pkg_resources/setuptools, matplotlib, ...) but that a
# fresh YouMuDow never imports at runtime. Excluding them keeps the bundle lean
# without changing behaviour.
ENVIRONMENT_EXCLUDES = [
    "gi",
    "gi.repository",
    "gi.overrides",
    "gi.importer",
    "gi.module",
    "gi._gi",
    "gi._gtk",
    "gi.types",
    "gi.docstring",
    "keyring",
    "jack",
    "jwt",
    "apport",
    "apport_python_hook",
    "apt",
    "apt_pkg",
    "dbus",
    "pkg_resources",
    "setuptools",
    "pyparsing",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "IPython",
]


def clean() -> None:
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
    for spec in ROOT.glob("*.spec"):
        spec.unlink()
    print("Cleaned previous builds.")


def build() -> None:
    system = platform.system()

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "YouMuDow",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--additional-hooks-dir",
        str(HOOKS),
    ]

    # The whole youmudow package graph (styles, widgets, app, services,
    # adapters, domain) is already reached statically from main.py, so only the
    # genuinely lazy modules need explicit hidden imports. PIL.Image /
    # PIL.ImageTk are imported lazily by DetailPanel.
    for mod in LAZY_HIDDEN_IMPORTS + ["PIL.Image", "PIL.ImageTk"] + PIL_TK_HIDDEN_IMPORTS:
        args += ["--hidden-import", mod]

    if system != "Windows":
        args.append("--strip")
        for mod in ENVIRONMENT_EXCLUDES:
            args += ["--exclude-module", mod]

    args.append(str(ENTRY))

    print(f"Building for {system}...")
    result = subprocess.run(args, cwd=ROOT, check=False)
    if result.returncode == 0:
        output = DIST / ("YouMuDow.exe" if system == "Windows" else "YouMuDow")
        print(f"\nBuild successful: {output}")
        print("\nNOTE: ffmpeg and yt-dlp must be installed separately by the user.")
        print("Consider bundling them or pointing users to the README.")
    else:
        print("Build failed.")
        sys.exit(1)


if __name__ == "__main__":
    clean()
    build()
