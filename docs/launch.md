# Launch Kit

Use this page when introducing Firebase RTDB Restore Toolkit to developers, open-source communities, or teams that operate Firebase Realtime Database projects.

## Positioning

Firebase RTDB Restore Toolkit is an open-source Python CLI for safely restoring large Firebase Realtime Database backups. It stream-splits huge JSON exports, validates chunks with SHA-256 fingerprints, uploads in safe batches, supports dry runs and resumable progress, and documents destructive restore workflows before users touch production data.

The project should be promoted as a reliability and disaster-recovery tool, not as a generic Firebase helper script.

## Short Description

Safely split, validate, and restore large Firebase Realtime Database backups without console overwrite traps, request-size failures, or out-of-memory crashes.

## Social Post

I open-sourced Firebase RTDB Restore Toolkit: a Python CLI for safely restoring large Firebase Realtime Database backups.

It supports stream splitting, SHA-256 validation, dry-run uploads, resumable chunk restores, oversized-node recovery, PyPI releases, checksums, SBOM assets, and a production restore runbook.

Repo: https://github.com/berkayturanci/firebase-rtdb-restore

## Hacker News / Show HN Draft

Title:

```text
Show HN: Firebase RTDB Restore Toolkit - safer restores for large backups
```

Body:

```text
I built an open-source CLI for restoring large Firebase Realtime Database backups more safely.

The main problem is that Firebase Console imports use overwrite-style behavior, so uploading a large backup in pieces can erase previous data at the same path. Large RTDB exports can also hit request-size limits or out-of-memory failures when scripts load the full JSON file.

This tool uses a split -> validate -> dry-run -> upload workflow:

- stream-splits large JSON backups without loading the whole file into memory
- validates chunks with SHA-256 fingerprints
- uploads in size-bounded PATCH batches
- supports resumable progress after partial failures
- handles oversized individual entries recursively
- documents destructive flags and production restore checks

It is available on PyPI as `firebase-rtdb-tools`, and GitHub releases include checksums and an SBOM.

Repo: https://github.com/berkayturanci/firebase-rtdb-restore
```

## Reddit / Community Draft

```text
I open-sourced a small Python CLI for safer Firebase Realtime Database restores:

https://github.com/berkayturanci/firebase-rtdb-restore

It is meant for large RTDB JSON exports where console import or one-shot scripts are risky. The workflow is:

1. split a large backup into chunks without loading the full file into memory
2. validate the chunks against the original backup with SHA-256 fingerprints
3. dry-run the upload
4. upload chunks in safe PATCH batches with resumable progress

It also includes docs for destructive restore modes (`--wipe`, `--wipe-root`), a production runbook, PyPI packaging, CI across Python versions, checksums, and SBOM release assets.

Feedback is welcome, especially from people who have had to restore or migrate large RTDB projects.
```

## Dev.to / Blog Outline

Title options:

- Restoring Large Firebase Realtime Database Backups Safely
- Why Firebase RTDB Restores Fail, and How to Make Them Safer
- Open-Sourcing Firebase RTDB Restore Toolkit

Suggested outline:

1. The restore problem: console overwrites, request-size limits, and memory pressure.
2. The safer workflow: split, validate, dry-run, upload, verify.
3. How the CLI avoids loading giant JSON files into memory.
4. Why `PATCH` uploads and explicit destructive flags matter.
5. Running the synthetic example locally.
6. Release and trust signals: PyPI, CI matrix, checksums, SBOM, CodeQL, Dependabot, Scorecard.
7. Call for feedback and real-world restore scenarios.

## Maintainer Checklist Before Posting

- Confirm the latest GitHub release matches the PyPI version.
- Confirm the documentation site reports the current package version.
- Confirm release assets include the wheel, source distribution, `SHA256SUMS`, and `sbom.cdx.json`.
- Confirm open issues are triaged.
- Prefer linking to the repository and production runbook rather than pasting destructive commands directly into posts.

## Suggested GitHub Topics

```text
firebase
firebase-realtime-database
realtime-database
backup
restore
disaster-recovery
python
cli
database-tools
open-source
```
