# Examples — practice the workflow safely

This folder contains a small, **synthetic** backup so you can run the full
split → validate flow locally before touching real Firebase data.

- [`sample-backup.json`](sample-backup.json) — a tiny RTDB-style export with a
  `users` node (three UIDs) plus sibling `metadata` and `config` nodes. It is
  completely fake and safe to commit.

> The `config` sibling is intentional: it shows why `--wipe` (target path only)
> is safer than `--wipe-root`. Wiping `/users` leaves `/config` untouched;
> wiping the root removes everything.

Generated chunks land in a `rtdb-chunks/` directory, which is git-ignored.

## 1. Split

Split the `users` node into chunks of 2 entries (so you get more than one file):

```bash
firebase-rtdb-split examples/sample-backup.json -o examples/rtdb-chunks -n users -c 2
# or, from a source checkout without installing:
# python3 -m firebase_rtdb_restore.split_backup examples/sample-backup.json -o examples/rtdb-chunks -n users -c 2
```

Expected result — 3 users split into two files:

```
  chunk_0000.json  (2 entries)
  chunk_0001.json  (1 entries)

Done: 3 entries → 2 chunk files in:
  examples/rtdb-chunks/
```

## 2. Validate (lossless check)

Confirm the chunks are a byte-exact, SHA-256-verified split of the original:

```bash
firebase-rtdb-validate examples/sample-backup.json examples/rtdb-chunks -n users
```

Expected tail — a clean pass:

```
  OK    No duplicate keys across chunks
  OK    All original entries present in chunks
  OK    No extra keys in chunks
  OK    All values match exactly (SHA-256 verified)
  ...
  RESULT: PASSED — chunks are a 100% lossless split of the original
```

### See validation catch tampering

Edit any value in `examples/rtdb-chunks/chunk_0000.json` (for example change
Alice's name), then re-run the validate command. It now fails with a
`Value mismatches (SHA-256 differs)` line — this is the guard that protects you
from a silently corrupted restore.

## 3. Upload — preview only (no Firebase needed)

Upload requires a real Firebase service account, but you can preview exactly
what *would* happen with `--dry-run`. These write nothing:

```bash
# Append/resume into /users (safe merge — no deletes)
firebase-rtdb-upload examples/rtdb-chunks -s serviceAccountKey.json -p /users --dry-run

# Clean restore of the target path only (wipes /users, keeps /config)
firebase-rtdb-upload examples/rtdb-chunks -s serviceAccountKey.json -p /users --wipe --dry-run

# Full reset (wipes the entire database root — destroys everything)
firebase-rtdb-upload examples/rtdb-chunks -s serviceAccountKey.json -p /users --wipe-root --dry-run
```

To restore one specific entry recursively — `uid_carol` lives in
`chunk_0001.json` and has a nested `items` map, so it exercises the
child-by-child writer:

```bash
firebase-rtdb-upload-single uid_carol examples/rtdb-chunks/chunk_0001.json -s serviceAccountKey.json -p /users
```

Only drop `--dry-run` once you have verified the project, database URL, target
path, and a validated chunk set against a backup you trust.
