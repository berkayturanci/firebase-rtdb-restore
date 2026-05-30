# CLI & API Reference

Complete reference for the `firebase-rtdb-tools` command-line tools and the
importable Python functions that are safe for external use.

- [Conventions](#conventions)
- [`firebase-rtdb-split`](#firebase-rtdb-split)
- [`firebase-rtdb-validate`](#firebase-rtdb-validate)
- [`firebase-rtdb-upload`](#firebase-rtdb-upload)
- [`firebase-rtdb-upload-single`](#firebase-rtdb-upload-single)
- [Exit codes](#exit-codes)
- [Environment variables](#environment-variables)
- [Python API](#python-api)

---

## Conventions

- Each CLI is installed as a console script and is also runnable as a module,
  e.g. `firebase-rtdb-split ...` ≡ `python -m firebase_rtdb_restore.split_backup ...`.
- Paths accept `~` and are expanded.
- Destructive flags are called out explicitly. When in doubt, add `--dry-run`
  (upload only) and read the [Production Restore Runbook](runbook.md).

---

## `firebase-rtdb-split`

Stream-split a backup JSON into N-entry chunk files. Reads in 128 KB blocks and
never loads the whole file into memory; works on pretty-printed and minified JSON.

```
firebase-rtdb-split <backup_file> [-o OUTPUT_DIR] [-c CHUNK_SIZE] [-n NODE]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `backup_file` | *(required)* | Path to the RTDB backup JSON file. |
| `-o`, `--output-dir` | `<backup_dir>/rtdb-chunks` | Directory to write `chunk_NNNN.json` files. |
| `-c`, `--chunk-size` | `1000` | Entries per chunk file. Must be a positive integer. |
| `-n`, `--node` | `users` | Top-level JSON key to split. |

**Example**

```bash
firebase-rtdb-split backup.json -o ./chunks -n users -c 1000
```

---

## `firebase-rtdb-validate`

Verify that chunk files are a lossless, exact split of the original backup by
comparing per-entry SHA-256 fingerprints. Streams the original (never loads it
fully). Reports duplicates, missing/extra keys, value mismatches, and the
largest entries.

```
firebase-rtdb-validate <backup_file> <chunks_dir> [-n NODE]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `backup_file` | *(required)* | Path to the original backup JSON. |
| `chunks_dir` | *(required)* | Directory containing `chunk_*.json`. |
| `-n`, `--node` | `users` | Top-level JSON key that was split. |

Exits `0` only when the split is 100% lossless; otherwise exits `1`. **Do not
upload if validation fails.**

**Example**

```bash
firebase-rtdb-validate backup.json ./chunks -n users
```

---

## `firebase-rtdb-upload`

Upload chunk files to RTDB using additive `PATCH`/merge in ≤ 4 MB batches.
Oversized single entries are split recursively. Transient write failures are
retried with exponential backoff. Completed chunks are recorded in a
`.upload-progress` manifest and skipped on a non-wipe re-run.

```
firebase-rtdb-upload <chunks_dir> [-s SERVICE_ACCOUNT] [-p PATH]
                     [--wipe] [--wipe-root] [--dry-run]
                     [-w WORKERS] [-d DATABASE_URL]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `chunks_dir` | *(required)* | Directory containing `chunk_*.json`. |
| `-s`, `--service-account` | see [env vars](#environment-variables) | Path to the Firebase service-account JSON key. |
| `-p`, `--path` | `/users` | Target RTDB path to merge chunks into. |
| `--wipe` | off | **Destructive.** Wipe the **target path** (`-p`) before uploading. Siblings untouched. |
| `--wipe-root` | off | **Destructive.** Wipe the **entire database root** (`/`) before uploading. |
| `--dry-run` | off | Show what would be wiped/uploaded without writing anything. |
| `-w`, `--workers` | `1` | Number of chunks to upload in parallel. Must be a positive integer. |
| `-d`, `--database-url` | `https://<project_id>.firebaseio.com` | Override the database URL (custom domains / regional instances). |

Both wipe flags prompt for a typed `yes` confirmation (skipped under
`--dry-run`). On any failure the failed chunks are listed and the command exits
`1`; re-run **without** a wipe flag to retry only the unfinished chunks.

**Examples**

```bash
# Append/resume (safe merge)
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users

# Preview a target wipe without writing
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --wipe --dry-run

# Parallel upload, custom regional database
firebase-rtdb-upload ./chunks -s sa.json -w 4 -d https://my-db.europe-west1.firebasedatabase.app
```

---

## `firebase-rtdb-upload-single`

Upload one entry from a chunk file, writing recursively child-by-child so a
single very large node fits under request limits.

```
firebase-rtdb-upload-single <key> <chunk_file> [-s SERVICE_ACCOUNT] [-p PATH] [-d DATABASE_URL]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `key` | *(required)* | The specific key (e.g. a UID) to restore. |
| `chunk_file` | *(required)* | Path to the chunk file containing the key. |
| `-s`, `--service-account` | see [env vars](#environment-variables) | Path to the service-account JSON key. |
| `-p`, `--path` | `/users` | Parent RTDB path where the entry resides (target is `<path>/<key>`). |
| `-d`, `--database-url` | `https://<project_id>.firebaseio.com` | Override the database URL. |

**Example**

```bash
firebase-rtdb-upload-single some_uid ./chunks/chunk_0000.json -s serviceAccountKey.json -p /users
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — or a wipe confirmation was declined (clean abort). |
| `1` | Error: input/file not found, node not found, validation failed, or one or more chunk uploads failed. |

---

## Environment variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `FIREBASE_SERVICE_ACCOUNT_KEY` | `upload`, `upload-single` | Path to the service-account JSON. Used when `-s` is not given. |

Service-account resolution order: `-s/--service-account` → `FIREBASE_SERVICE_ACCOUNT_KEY`
→ `./serviceAccountKey.json` in the current directory.

---

## Python API

The CLIs are thin wrappers; the underlying functions are importable for
scripting. Stable, externally usable entry points:

```python
from firebase_rtdb_restore.split_backup import split_backup
from firebase_rtdb_restore.validate_chunks import stream_original, load_chunks
from firebase_rtdb_restore.upload_chunks import upload_chunks
from firebase_rtdb_restore.upload_single_user import upload_single_user
```

- `split_backup(input_path, output_dir, chunk_size, node_key) -> (chunk_count, total_entries)`
- `stream_original(input_path, node_key) -> Iterator[(key, (digest, size))]`
- `load_chunks(chunks_dir) -> (dict[key -> (digest, size)], duplicates)`
- `upload_chunks(chunks_dir, sa_path, target_path, do_wipe=False, database_url=None, do_wipe_root=False, dry_run=False, workers=1)`
- `upload_single_user(key, chunk_path, sa_path, parent_path, database_url=None)`

> **Internal:** `firebase_rtdb_restore._common` and any name prefixed with `_`
> are implementation details and may change without notice. Do not depend on them.
