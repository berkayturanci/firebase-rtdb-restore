# Production Restore Runbook

A safety-first, step-by-step procedure for restoring production Firebase RTDB
data with `firebase-rtdb-tools`. Read this end-to-end **before** running any
upload against a real project.

> ⚠️ `--wipe` and `--wipe-root` permanently delete data. There is no undo.
> Always keep an untouched copy of your backup and rehearse with `--dry-run`.

- [1. Pre-flight checklist](#1-pre-flight-checklist)
- [2. Split](#2-split)
- [3. Validate (gate)](#3-validate-gate)
- [4. Dry run](#4-dry-run)
- [5. Execute the restore](#5-execute-the-restore)
- [6. Oversized entries](#6-oversized-entries)
- [7. Resuming after a failure](#7-resuming-after-a-failure)
- [8. Post-restore verification](#8-post-restore-verification)
- [9. Rollback & incident handling](#9-rollback--incident-handling)

For every flag and default, see the [CLI & API Reference](cli.md).

---

## 1. Pre-flight checklist

- [ ] **Keep the original backup immutable.** Work from a copy; never let the
      tool read the only copy you have.
- [ ] **Confirm the target project.** The database URL defaults to
      `https://<project_id>.firebaseio.com` derived from the service account.
      Double-check `project_id` in the service-account JSON is the project you
      intend to write to. Use `-d/--database-url` for regional/custom instances.
- [ ] **Scope the service account.** Use a key with only the access required to
      write the target path. Store it outside the repo; it is git-ignored here.
- [ ] **Pick the target path** (`-p`). Restoring `/users` should use `-p /users`.
- [ ] **Decide the write mode** up front: append/resume (default), target wipe
      (`--wipe`), or full reset (`--wipe-root`). See the
      [Choose Your Workflow](../README.md#choose-your-workflow) table.
- [ ] **Note the maintenance window.** Large restores issue many sequential
      requests; expect minutes for large datasets.

---

## 2. Split

```bash
firebase-rtdb-split backup.json -o ./chunks -n users -c 1000
```

Produces `chunk_0000.json`, `chunk_0001.json`, … under `./chunks`. Smaller
`-c` values yield more, smaller files (useful when individual entries are large).

---

## 3. Validate (gate)

**This step is a hard gate. Do not upload if it fails.**

```bash
firebase-rtdb-validate backup.json ./chunks -n users
```

It streams the original and compares a SHA-256 fingerprint of every entry
against the chunks, reporting duplicates, missing keys, extra keys, and value
mismatches, plus the largest entries (watch for entries over 1 MB / 10 MB). A
pass prints `RESULT: PASSED` and exits `0`.

---

## 4. Dry run

Preview exactly what would happen — no data is written:

```bash
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --dry-run
# preview a destructive variant the same way:
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --wipe --dry-run
```

Confirm the project, database URL, target path, chunk count, and wipe scope in
the printed header before continuing.

---

## 5. Execute the restore

Pick exactly one mode:

```bash
# Append / resume — additive PATCH merge, never deletes siblings (safest)
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users

# Target wipe — clears /users first, leaves other top-level nodes intact
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --wipe

# Full reset — clears the ENTIRE database root first (destroys everything)
firebase-rtdb-upload ./chunks -s serviceAccountKey.json -p /users --wipe-root
```

Notes:
- Both wipe flags require typing `yes` to confirm.
- Entries are sent in ≤ 4 MB batches via additive `PATCH`.
- Transient write errors are retried automatically with exponential backoff.
- `-w/--workers N` uploads N chunks in parallel; start at `1` and increase only
  if you understand your project's write throughput limits.

---

## 6. Oversized entries

If a single entry is too large for one request, the uploader splits it
recursively. To (re)restore one specific entry on its own:

```bash
firebase-rtdb-upload-single <uid> ./chunks/chunk_0007.json -s serviceAccountKey.json -p /users
```

This writes the entry child-by-child so each request stays within limits.

---

## 7. Resuming after a failure

Uploads are **resumable**. Each fully uploaded chunk is recorded in a
`.upload-progress` file inside the chunks directory.

- To retry only the unfinished chunks, **re-run the same command without any
  wipe flag**. Already-completed chunks are skipped, and a target/root wipe is
  not repeated.
- To force a full re-upload, delete `./chunks/.upload-progress` first.

Because uploads use additive `PATCH`, re-running is safe and idempotent for the
append path.

---

## 8. Post-restore verification

The validate step proves the **chunks** match the backup; it does not read back
what landed in RTDB. After uploading, verify the live database:

- **Spot-check sample keys** in the Firebase Console → Realtime Database → Data,
  including the largest entries flagged during validation.
- **Compare counts** where feasible (e.g. number of children under `/users`).
- **Check sibling nodes** survived if you used `--wipe` (target-only) — they
  should still be present; with `--wipe-root` they will not.
- **Confirm no failed chunks** were reported at the end of the upload. A
  non-zero exit means one or more chunks failed; resume per section 7.

---

## 9. Rollback & incident handling

- **Stop early.** If the upload reports failures, do not escalate to a wider
  wipe. Resume the failed chunks (section 7) or investigate first.
- **Re-restore from backup.** Because you kept the original backup immutable,
  recovery is: re-split (if needed) → validate → upload again into the target
  path.
- **Accidental `--wipe-root`.** Root wipe removes all nodes, including siblings
  not represented in your chunks. Recovery requires a backup of those nodes too;
  restore each affected node from its own backup.
- **Credential exposure.** If a service-account key may have leaked, revoke it
  in the Firebase Console and generate a new one before continuing.
