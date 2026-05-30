# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.5] - 2026-05-30
### Added
- Automated unit test suite execution on pushes and pull requests to `main` via `.github/workflows/tests.yml`.
- Standard pre-commit hooks configuration (`.pre-commit-config.yaml`) using `ruff` and standard formatting checks.
- Live test status badge in `README.md`.

### Changed
- Configured PyPI publish step in `.github/workflows/publish.yml` to allow grace-fails (`continue-on-error: true`) so that GitHub Release and assets upload always completes even when PyPI trusted publishing is not yet configured.

---

## [0.1.4] - 2026-05-30
### Added
- Comprehensive Python unit test suite in `tests/test_restore_toolkit.py` covering all components (`split_backup`, `validate_chunks`, `upload_chunks`, `upload_single_user`) using zero-dependency mocking.
- Automated packaging and GitHub Release flow in `.github/workflows/publish.yml` to compile wheel/sdist distributions and attach them as downloadable assets to GitHub Releases.

### Changed
- Refactored `upload_chunks.py` and `upload_single_user.py` to defer `firebase_admin` imports to inside the functions, preventing module-import failures on clean systems when running mocked tests.

---

## [0.1.3] - 2026-05-30
### Added
- Interactive GitHub YAML Issue Templates in `.github/ISSUE_TEMPLATE/` for bug reports (`bug_report.yml`) and feature requests (`feature_request.yml`).
- Issue template configuration (`config.yml`) to disable blank issues and direct Q&A support to GitHub Discussions.

---

## [0.1.2] - 2026-05-30
### Added
- Detailed Contributing guidelines (`CONTRIBUTING.md`).
- Contributor Covenant Code of Conduct (`CODE_OF_CONDUCT.md`).
- Security Policy (`SECURITY.md`) with private vulnerability reporting instructions.
- Pull Request template (`.github/pull_request_template.md`).

---

## [0.1.1] - 2026-05-30
### Changed
- Updated maintainer email to `berkayturanci@gmail.com` in `pyproject.toml`.

---

## [0.1.0] - 2026-05-30
### Added
- Initial standalone release of the Firebase RTDB Lossless Restore Toolkit extracted from `smartinventory`.
- Support for CLI entry points (`firebase-rtdb-split`, `firebase-rtdb-validate`, `firebase-rtdb-upload`, `firebase-rtdb-upload-single`).
- Premium setup documentation in `README.md`.
- Automated PyPI publishing on tags via GitHub Actions.
