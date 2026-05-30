# Contributing to Firebase RTDB Lossless Restore Toolkit

Thank you for your interest in contributing to the **Firebase RTDB Lossless Restore Toolkit**! Contributions from the community help make this tool more robust, fast, and feature-rich for everyone.

Here is a guide to help you get started with contributing.

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to [berkayturanci@gmail.com](mailto:berkayturanci@gmail.com).

---

## How Can I Contribute?

### Reporting Bugs

If you find a bug, please open an issue on GitHub. Before submitting, please:
1. Check if the issue has already been reported in the [Issues](https://github.com/berkayturanci/firebase-rtdb-restore/issues) section.
2. Provide a clear description of the bug, including steps to reproduce.
3. Include relevant system details (Python version, operating system, etc.).

### Suggesting Enhancements

We welcome feature requests and enhancements! Please open an issue describing:
1. The problem you are trying to solve or the need that is currently unmet.
2. A description of the proposed solution or feature.
3. Any alternatives you have considered.

### Submitting Pull Requests

If you would like to contribute code changes:
1. Fork the repository and create a new branch from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Set up a local development environment (see below).
3. Implement your changes. Make sure your code is clean and follows standard Python formatting guidelines.
4. Run the full local validation gate before pushing (see [Validating your changes](#validating-your-changes)).
5. Commit your changes with clear, descriptive commit messages.
6. Push your branch to your fork and submit a Pull Request to our `main` branch.
7. Update documentation alongside behavior changes — README, `examples/`, the
   docs site under `docs/`, and `CHANGELOG.md` where relevant.

The `main` branch requires every pull request to pass CI before it can merge:
Ruff lint, the unit-test matrix (Python 3.8–3.13), the package build/metadata
check, and the documentation-site check. Running `make check` locally reproduces
the code gates so you don't have to wait on CI to catch a lint or test failure.

---

## Local Development Setup

To set up a local development environment for testing and editing:

1. Clone your fork of the repository:
   ```bash
   git clone https://github.com/YOUR-USERNAME/firebase-rtdb-restore.git
   cd firebase-rtdb-restore
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the package in editable mode **with the development tools**:
   ```bash
   pip install -e ".[dev]"
   ```
   This pulls in Ruff, `build`, `twine`, and `pre-commit` in addition to the
   runtime dependencies.
4. (Optional) install the git hooks:
   ```bash
   pre-commit install
   ```
5. Verify the entry points work locally:
   ```bash
   firebase-rtdb-split --help
   ```

---

## Validating your changes

Run the same gates CI enforces. The quickest path is the bundled target:

```bash
make check        # ruff check + unit tests + build + twine check
```

Or run them individually:

```bash
make lint                                         # ruff check .
make test                                         # unit tests
python3 -m build --sdist --wheel --outdir dist/   # packaging
python3 -m twine check dist/*                     # package metadata
```

To try the toolkit end-to-end against safe, synthetic data, follow the
walkthrough in [`examples/README.md`](examples/README.md).

---

## Reference documentation

- [CLI & API Reference](docs/cli.md) — every command, flag, default, and exit code.
- [Production Restore Runbook](docs/runbook.md) — safety checklist for real restores.
- [Release Process & Versioning Policy](docs/release-process.md) — how versions are bumped and released.

---

## Questions?

If you have any questions about the contribution process, feel free to open a discussion or contact [berkayturanci@gmail.com](mailto:berkayturanci@gmail.com).
