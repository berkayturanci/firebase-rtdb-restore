# Release Process & Versioning Policy

How `firebase-rtdb-tools` is versioned and released, so every release updates
package metadata, changelog, and the published artifacts consistently.

- [Versioning policy](#versioning-policy)
- [Where the version lives](#where-the-version-lives)
- [Release checklist](#release-checklist)
- [How publishing works](#how-publishing-works)
- [Verifying a release](#verifying-a-release)
- [Rollback & recovery](#rollback--recovery)

---

## Versioning policy

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
Because this is an operational data-restore tool, version increments are judged
by **observable CLI behavior**, not just internal code:

- **MAJOR** — backward-incompatible changes to user-visible behavior: renaming
  or removing a CLI/flag, changing a default that affects what gets written,
  or changing the meaning of a destructive flag (e.g. the `--wipe` scope).
- **MINOR** — backward-compatible additions: new CLI, new optional flag, new
  output, or performance improvements that don't change results.
- **PATCH** — backward-compatible bug fixes and documentation/CI changes.

Destructive-flag semantics (`--wipe`, `--wipe-root`) are treated as part of the
public contract: any change to what they delete is at least a MINOR change and,
if it widens deletion scope, a MAJOR change with a prominent changelog note.

---

## Where the version lives

| Location | Field |
|----------|-------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `firebase_rtdb_restore/__init__.py` | `__version__ = "X.Y.Z"` |
| `CHANGELOG.md` | a dated `## [X.Y.Z]` section |

Keep all three in sync. The documentation-site release guard cross-checks the
site's version signal against `pyproject.toml`, so update the site metadata if
your change touches it.

---

## Release checklist

1. [ ] Decide the new version per the [versioning policy](#versioning-policy).
2. [ ] Bump `version` in `pyproject.toml` and `__version__` in
       `firebase_rtdb_restore/__init__.py`.
3. [ ] Move `CHANGELOG.md` `[Unreleased]` notes into a dated `## [X.Y.Z]`
       section; add anything missing.
4. [ ] Update docs if behavior changed: `README.md`, `docs/cli.md`,
       `docs/runbook.md`, and `examples/` as applicable.
5. [ ] Run the full local gate: `make check` (lint, tests, build, `twine check`).
6. [ ] Open a PR, get CI green (lint, Python 3.8–3.13, build/metadata, docs-site),
       and merge to `main`.
7. [ ] Tag the merged commit and push the tag:
       ```bash
       git tag vX.Y.Z
       git push origin vX.Y.Z
       ```
8. [ ] Watch the **Publish to PyPI & GitHub Release** workflow complete.
9. [ ] [Verify the release](#verifying-a-release).

---

## How publishing works

Pushing a `v*` tag triggers `.github/workflows/publish.yml`, which:

1. Builds the sdist and wheel.
2. Runs `twine check` on the artifacts.
3. Publishes to PyPI (`skip-existing` so re-runs are safe).
4. Generates `SHA256SUMS` and a CycloneDX SBOM into `artifacts/`.
5. Creates a GitHub Release with the wheel, sdist, checksums, and SBOM attached
   and auto-generated notes.

The workflow runs only on tags, so day-to-day PRs never publish.

### Release authentication (Trusted Publishing)

Publishing uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
over OIDC — there is **no long-lived PyPI API token** stored in the repository.
The workflow's `id-token: write` permission lets it mint a short-lived
credential, and the publisher is configured on PyPI as:

| Field | Value |
|-------|-------|
| Owner | `berkayturanci` |
| Repository | `firebase-rtdb-restore` |
| Workflow | `publish.yml` |
| Environment | *(none)* |

Because no explicit password is passed, the publish action also produces
[PEP 740](https://peps.python.org/pep-0740/) attestations for the artifacts.

---

## Verifying a release

- [ ] PyPI shows the new version: <https://pypi.org/project/firebase-rtdb-tools/>.
- [ ] `pip install firebase-rtdb-tools==X.Y.Z` works in a clean environment and
      the console scripts run (`firebase-rtdb-split --help`).
- [ ] The GitHub Release exists with the wheel and sdist attached.
- [ ] The documentation site reflects the new version.

---

## Rollback & recovery

- **Failed tag / bad release.** Do not delete a published PyPI version (PyPI
  disallows re-uploading the same version). Instead, fix forward: bump to the
  next PATCH, repeat the checklist, and yank the broken version on PyPI if it is
  harmful.
- **Failed publish step.** The workflow no longer masks publish failures, so a
  red run means the package did **not** publish. Fix the cause (credentials/
  metadata) and re-run by re-pushing the tag or cutting a new patch tag.
- **Wrong artifacts attached.** Edit the GitHub Release to remove incorrect
  assets and re-upload the correct `dist/*` built locally with `make build`.
