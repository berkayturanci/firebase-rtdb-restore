#!/usr/bin/env python3
"""Validate release-sensitive documentation site metadata."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SITE_INDEX = ROOT / "docs" / "index.html"
SITE_APP = ROOT / "docs" / "app.js"


def main() -> int:
    package = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    version = package["version"]
    html = SITE_INDEX.read_text(encoding="utf-8")
    app_js = SITE_APP.read_text(encoding="utf-8")

    errors: list[str] = []

    body_match = re.search(r'<body[^>]*data-package-version="([^"]+)"', html)
    if not body_match:
        errors.append("docs/index.html must expose data-package-version on the body element.")
    elif body_match.group(1) != version:
        errors.append(
            f"docs/index.html data-package-version is {body_match.group(1)!r}, "
            f"but pyproject.toml version is {version!r}."
        )

    if "https://img.shields.io/pypi/v/firebase-rtdb-tools" not in html:
        errors.append("docs/index.html must use the live PyPI version badge.")

    if "https://github.com/berkayturanci/firebase-rtdb-restore/releases/latest" not in html:
        errors.append("docs/index.html must link to the latest GitHub release.")

    if re.search(r"(?<!DB)PATH=/", html) or re.search(r"(?<!DB)PATH=/", app_js):
        errors.append("docs must use DBPATH in generated make upload commands, not PATH.")

    if "pypi-v0." in html:
        errors.append("docs/index.html must not use hard-coded PyPI version badges.")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Documentation site release metadata matches package version {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
