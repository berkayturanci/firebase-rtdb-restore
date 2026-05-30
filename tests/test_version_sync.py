import re
import unittest
from pathlib import Path

import firebase_rtdb_restore

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "version not found in pyproject.toml"
    return match.group(1)


class TestVersionSync(unittest.TestCase):
    """Guard against version drift across the package metadata.

    The documentation-site version (docs/index.html) is validated separately by
    scripts/check_docs_site.py in the docs-site CI job; this test covers the
    Python package version and the changelog so a release cannot ship with
    `__version__`, `pyproject.toml`, and `CHANGELOG.md` out of sync.
    """

    def test_init_matches_pyproject(self):
        self.assertEqual(
            firebase_rtdb_restore.__version__,
            _pyproject_version(),
            "firebase_rtdb_restore.__version__ must match pyproject.toml version",
        )

    def test_changelog_has_section_for_current_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        version = _pyproject_version()
        self.assertIn(
            f"## [{version}]",
            changelog,
            f"CHANGELOG.md must contain a section for version {version}",
        )


if __name__ == "__main__":
    unittest.main()
