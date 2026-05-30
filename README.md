<p align="center">
  <img src="docs/hero-banner.svg" alt="Firebase RTDB Restore Toolkit — stream-split, verify, and losslessly restore large Firebase Realtime Database backups" width="100%">
</p>

# Firebase RTDB Lossless Restore Toolkit

A simple, memory-efficient toolkit to restore large Firebase Realtime Database (RTDB) backups safely and without data loss.

[![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/berkayturanci/firebase-rtdb-restore)](https://github.com/berkayturanci/firebase-rtdb-restore/releases)
[![PyPI](https://img.shields.io/pypi/v/firebase-rtdb-tools.svg?label=PyPI&logo=pypi&color=3775A9)](https://pypi.org/project/firebase-rtdb-tools/)
[![Run Tests](https://github.com/berkayturanci/firebase-rtdb-restore/actions/workflows/tests.yml/badge.svg)](https://github.com/berkayturanci/firebase-rtdb-restore/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Restoring a large Firebase database backup (e.g., 1 GB+) using default tools is difficult for three reasons:

1. **The Overwrite Trap**: Importing a JSON file in the Firebase Console completely erases all existing data at that path first. You cannot upload a large backup in pieces because each new piece wipes out the previous ones.
2. **Request Size Limits**: Firebase limits the size of a single write request. Large backup files will timeout or fail with payload size errors.
3. **Out-Of-Memory Crashes**: Loading a giant JSON backup file into memory will crash standard scripts.

---

## The Solution

This toolkit solves these problems using four simple steps:

* **Stream Splitting**: Splits a giant JSON file into smaller chunks without loading the whole file into memory. It reads the file in tiny 128 KB blocks.
* **Lossless Verification**: Automatically checks that no data was lost during splitting by comparing SHA-256 fingerprints of every single entry.
* **Batch Uploading**: Groups entries into safe ≤ 4 MB batches and uploads them using additive `PATCH` updates, merging data without erasing anything else.
* **Oversized Entry Recovery**: Recursively splits individual massive entries (like a single user with huge data) child-key by child-key so they fit under request limits.

---

## Installation

### Via PyPI

```bash
pip install firebase-rtdb-tools
```

This installs four simple command-line tools:
* `firebase-rtdb-split`
* `firebase-rtdb-validate`
* `firebase-rtdb-upload`
* `firebase-rtdb-upload-single`

If PyPI does not show the package yet, install from source until the next release workflow publishes successfully.

### From Source

```bash
git clone https://github.com/berkayturanci/firebase-rtdb-restore.git
cd firebase-rtdb-restore
pip install -r requirements.txt
```

For local development, install the editable package with development tools:

```bash
pip install -e ".[dev]"
```

---

## How to Get Your Firebase Service Account Key

To upload data to your Firebase database:

1. Go to your **Firebase Console** -> **Project Settings** -> **Service accounts**.
2. Click **Generate new private key** and download the JSON file.
3. Pass the path to this JSON file using the `-s` / `--service-account` option, or set the environment variable:
   ```bash
   export FIREBASE_SERVICE_ACCOUNT_KEY="/path/to/serviceAccountKey.json"
   ```

---

## Before You Restore Production Data

⚠️ **WARNING**: Destructive operations like `--wipe` and `--wipe-root` can cause irreversible data loss if misused.

If you are restoring production data, please **stop and read the [Production Restore Runbook](docs/runbook.md)** before proceeding. The runbook covers:
* Safe dry-run previews
* Resuming from partial uploads
* Handling exponential backoff and rate limits
* Validating post-restore state

For a full list of all parameters, see the [CLI/API Reference](docs/cli.md). Other resources: [Contributing Guide](CONTRIBUTING.md) | [Security Policy](SECURITY.md) | [Release Notes](CHANGELOG.md).

### Choose Your Workflow

| Goal | Command Flag | Behavior |
|------|-------------|----------|
| **Evaluate/Preview** | `--dry-run` | Reads chunks and simulates the upload without writing any data. |
| **Append/Resume** | *(default)* | Uses additive `PATCH` to merge data. Does not erase existing siblings. |
| **Target Wipe** | `--wipe` | Wipes ONLY the specific target node (`-p /users`) before uploading chunks. |
| **Root Wipe** | `--wipe-root` | 🚨 Wipes the ENTIRE database root (`/`) before uploading. |
| **Oversized Recovery**| `upload-single` | Recursively splits and uploads a single giant node key-by-key. |

---

## Quick Examples

The commands below are quick examples. For production-safe procedures, refer to the [Production Restore Runbook](docs/runbook.md).

> **New here?** Try the whole split → validate flow on safe, synthetic data
> first — no Firebase project needed. See [`examples/README.md`](examples/README.md).

### Step 1: Split the giant backup file
Split the backup JSON into smaller files (default is 1,000 entries per file):
```bash
make split BACKUP=backup.json CHUNKS=./chunks NODE=users
```
*(Or use `firebase-rtdb-split backup.json -o ./chunks -n users -c 1000`)*

### Step 2: Verify the split
Check that the split was 100% exact and no data was lost:
```bash
make validate BACKUP=backup.json CHUNKS=./chunks NODE=users
```
*(Or use `firebase-rtdb-validate backup.json ./chunks -n users`)*

**Do not proceed if this step fails.**

### Step 3: Upload chunks to Firebase
Upload all chunks to your database. This merges data additively and will not overwrite other sibling nodes:
```bash
# Option A: Append/Resume (merges chunks into /users without wiping anything else)
make upload CHUNKS=./chunks SA=serviceAccountKey.json DBPATH=/users

# Option B: Clean restore of the TARGET path (wipes /users first, leaves siblings intact)
make upload-wipe CHUNKS=./chunks SA=serviceAccountKey.json DBPATH=/users

# Option C: Full reset (wipes the ENTIRE database root first — destroys all data)
make upload-wipe-root CHUNKS=./chunks SA=serviceAccountKey.json DBPATH=/users
```
*(Or use `firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --wipe`)*

**Upload options:**
* `--wipe` wipes only the target path (`-p`); `--wipe-root` wipes the entire database root.
* `--dry-run` previews exactly what would be wiped/uploaded without writing anything.
* `-w/--workers N` uploads N chunks in parallel (default 1).
* Uploads are **resumable**: completed chunks are recorded in a `.upload-progress` file inside the chunks directory and skipped automatically when you re-run after a failure. Transient write errors are retried with exponential backoff.

### Step 4: Handle giant entries (if any)
If the upload script reports that a specific entry failed because it is too large to fit in a single request:
```bash
make upload-single UID=some_uid CHUNKS=./chunks/chunk_0000.json SA=serviceAccountKey.json DBPATH=/users
```
*(Or use `firebase-rtdb-upload-single some_uid ./chunks/chunk_0000.json -s serviceAccountKey.json -p /users`)*

---

## License

MIT License. See [LICENSE](LICENSE) for details.
