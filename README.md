# Firebase RTDB Lossless Restore Toolkit

A standalone, memory-efficient toolkit to restore large Firebase Realtime Database (RTDB) backups safely and losslessly.

[![PyPI version](https://img.shields.io/pypi/v/firebase-rtdb-tools.svg)](https://pypi.org/project/firebase-rtdb-tools/)
[![Run Tests](https://github.com/berkayturanci/firebase-rtdb-restore/actions/workflows/tests.yml/badge.svg)](https://github.com/berkayturanci/firebase-rtdb-restore/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Restoring a very large Firebase Realtime Database backup (e.g. 1 GB+) is surprisingly challenging:

1. **The Firebase Console "Import JSON" Trap**: The console import performs a `PUT` operation, which **fully overwrites** the target path. You cannot upload a large database in pieces via the UI because each successive upload wipes out the previous ones.
2. **The REST API / Admin SDK Request Limits**: Firebase enforces a strict size limit per write request (typically 16 MB to 256 MB depending on database load). Pushing a large JSON file in a single request will fail with timeouts or payload size errors.
3. **Memory Exhaustion**: Loading a multi-gigabyte JSON backup into memory in standard Python or Node.js scripts causes the process to crash with Out-Of-Memory (OOM) errors.

---

## The Solution

This toolkit provides 4 stream-based, memory-efficient scripts to split, validate, and upload database backups:

* **Stream Splitting**: Splits a giant JSON backup without loading the entire file into memory (uses 128 KB chunk reads + iterative decoding).
* **Fingerprint Validation**: Losslessly verifies the split by checking UID presence and canonical SHA-256 hash equality of all entry values.
* **Size-based PATCH Uploading**: Merges data additively via `PATCH` updates, automatically grouping entries into conservative ≤ 4 MB batches.
* **Oversized User Recovery**: Recursively drills down and splits individual massive user nodes (e.g. 40 MB+) child key by child key to fit within the API constraints.

---

## Installation

### Via PyPI (Recommended)

```bash
pip install firebase-rtdb-tools
```

This installs the four global command-line utilities:
* `firebase-rtdb-split`
* `firebase-rtdb-validate`
* `firebase-rtdb-upload`
* `firebase-rtdb-upload-single`

### Via Source

```bash
git clone https://github.com/berkayturanci/firebase-rtdb-restore.git
cd firebase-rtdb-restore
pip install -r requirements.txt
```

---

## Service Account Authentication

For uploading data to your Firebase database, you need a Google Service Account key.

1. Go to your **Firebase Console** -> **Project Settings** -> **Service accounts**.
2. Click **Generate new private key** and download the JSON file.
3. Use the JSON file with the `-s` / `--service-account` option, or set the environment variable:
   ```bash
   export FIREBASE_SERVICE_ACCOUNT_KEY="/path/to/serviceAccountKey.json"
   ```
   If neither is set, the tools look for a file named `serviceAccountKey.json` in your current working directory.

---

## Complete Step-by-Step Restore Workflow

### Step 1: Stream-split the giant backup file

Split the raw backup JSON into smaller, manageable chunks (default is 1,000 entries/keys per chunk). This works on pretty-printed as well as minified (single-line) JSON.

```bash
firebase-rtdb-split /path/to/backup.json -o ./chunks -n users -c 1000
```

* **`-o`, `--output-dir`**: Target directory for chunks (defaults to `<backup_file_dir>/rtdb-chunks`).
* **`-n`, `--node`**: The top-level key containing the entries to split (default: `users`).
* **`-c`, `--chunk-size`**: Number of entries per chunk file (default: 1000).

### Step 2: Losslessly verify the split

Before starting the upload, verify that the chunks are a 100% exact, lossless representation of the original backup file. This checks that no keys are missing, no extra keys were added, no duplicate keys exist, and every value is structurally identical (verified via SHA-256 hashes of canonical JSON representations).

```bash
firebase-rtdb-validate /path/to/backup.json ./chunks -n users
```

* **`-n`, `--node`**: The top-level key that was split (default: `users`).

If the result is **`PASSED`**, you are safe to proceed.

### Step 3: Upload chunks to Firebase

Upload all chunk files to Firebase via size-based batching. It uses `update()` (PATCH), which merges the entries additively and won't overwrite other sibling nodes.

```bash
# Full restore — wipe everything at the root first, then upload chunks under /users:
firebase-rtdb-upload ./chunks -p /users --wipe

# Append/Resume — merge chunks without wiping existing data:
firebase-rtdb-upload ./chunks -p /users
```

* **`-p`, `--path`**: The target database path to merge chunks into (default: `/users`).
* **`--wipe`**: Delete the *entire* database root (`/`) before starting the restore (requires interactive `yes` confirmation).
* **`-s`, `--service-account`**: Path to your service account JSON.
* **`-d`, `--database-url`**: Explicitly override or provide the Firebase Realtime Database URL (e.g. `https://my-app-default-rtdb.europe-west1.firebasedatabase.app`).

### Step 4: Handle giant individual nodes (if any)

If the upload script reports that a specific key (e.g., a single user with massive data > 10 MB) failed because it exceeds the request limit, use the single-node tool to restore it. This recursively splits the user's data by child key and writes each key individually.

```bash
firebase-rtdb-upload-single <UID_OR_KEY> ./chunks/chunk_0003.json -p /users
```

* **`-p`, `--path`**: The parent database path where the node resides (default: `/users`).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
