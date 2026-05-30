#!/usr/bin/env python3
"""
Upload RTDB chunk files produced by firebase-rtdb-split.

Features:
  * Additive PATCH/merge uploads in ≤ 4 MB batches (never overwrites siblings).
  * Recursive splitting of oversized single entries (child-key by child-key).
  * Automatic retry with exponential backoff on transient write failures.
  * Resumable: completed chunks are recorded in a ``.upload-progress`` manifest
    and skipped on a subsequent (non-wipe) run.
  * ``--dry-run`` to preview the plan without writing anything.
"""

import argparse
import json
import os
import sys
import threading
import time

from firebase_rtdb_restore._common import (
    init_app,
    recursive_write,
    resolve_service_account,
    service_account_error,
    tty_progress,
    with_retry,
)

MAX_BATCH_BYTES = 4 * 1024 * 1024   # 4 MB per request (conservative)
MANIFEST_NAME = ".upload-progress"


def _upload_one_chunk(target_ref, path, fname, dry_run):
    """Upload a single chunk file. Returns ``(ok, entries_written)``."""
    with open(path, encoding="utf-8") as f:
        chunk = json.load(f)

    entries_written = 0
    batch = {}
    batch_sz = 2  # opening/closing braces
    req = 0
    ok = True

    def flush():
        nonlocal batch, batch_sz, req, entries_written, ok
        if not batch:
            return
        req += 1
        tty_progress(f"  {fname}  req#{req}  ({len(batch)} entries, {batch_sz // 1024} KB)   ")
        payload = batch
        batch, batch_sz = {}, 2
        if dry_run:
            entries_written += len(payload)
            return
        try:
            with_retry(lambda: target_ref.update(payload), label=f"{fname} req#{req}")
            entries_written += len(payload)
        except Exception as e:  # noqa: BLE001 — report and mark chunk failed
            print(f"\n  ERROR on {fname} req#{req}: {e}")
            ok = False

    for key, val in chunk.items():
        entry_sz = len(json.dumps({key: val}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        # Flush current batch if adding this entry would exceed the limit.
        if batch and batch_sz + entry_sz > MAX_BATCH_BYTES:
            flush()

        # Single entry too large even alone — write it recursively, key-by-key.
        if entry_sz > MAX_BATCH_BYTES:
            if dry_run:
                tty_progress(f"  {fname}  giant:{key} ({entry_sz // 1024} KB) — would split recursively")
                entries_written += 1
                continue
            try:
                recursive_write(target_ref.child(key), val, f"/{key}", MAX_BATCH_BYTES)
                entries_written += 1
            except Exception as e:  # noqa: BLE001
                print(f"\n  ERROR on {fname} giant:{key}: {e}")
                ok = False
            continue

        batch[key] = val
        batch_sz += entry_sz

    flush()
    return ok, entries_written


def upload_chunks(chunks_dir, sa_path, target_path, do_wipe=False, database_url=None,
                  do_wipe_root=False, dry_run=False, workers=1):
    try:
        import firebase_admin  # noqa: F401
        from firebase_admin import db
    except ImportError:
        print("ERROR: firebase-admin not installed. Run: pip3 install firebase-admin")
        sys.exit(1)

    if not os.path.isdir(chunks_dir):
        print(f"ERROR: Chunks directory not found: {chunks_dir}")
        sys.exit(1)

    if not os.path.exists(sa_path):
        print(f"ERROR: Service account file not found: {sa_path}")
        sys.exit(1)

    chunk_files = sorted(
        f for f in os.listdir(chunks_dir)
        if f.startswith("chunk_") and f.endswith(".json")
    )
    if not chunk_files:
        print(f"ERROR: No chunk_*.json files found in: {chunks_dir}")
        sys.exit(1)

    # ── Init Firebase ────────────────────────────────────────────────────────
    sa, db_url = init_app(sa_path, database_url)
    target_ref = db.reference(target_path)

    # ── Resume manifest ──────────────────────────────────────────────────────
    manifest_path = os.path.join(chunks_dir, MANIFEST_NAME)
    completed = set()
    wiping = do_wipe or do_wipe_root
    if wiping:
        # Fresh restore — discard any prior progress record.
        if os.path.exists(manifest_path) and not dry_run:
            os.remove(manifest_path)
    elif os.path.exists(manifest_path):
        with open(manifest_path) as f:
            completed = {line.strip() for line in f if line.strip()}

    pending = [f for f in chunk_files if f not in completed]

    wipe_desc = "no (resume/append mode)"
    if do_wipe_root:
        wipe_desc = "YES — entire database root (/) will be wiped"
    elif do_wipe:
        wipe_desc = f"YES — target path ({target_path}) will be wiped"

    print(f"\nProject:    {sa['project_id']}")
    print(f"Database:   {db_url}")
    print(f"Target Path: {target_path}")
    print(f"Chunks dir: {chunks_dir}")
    print(f"Chunks:     {len(chunk_files)} ({len(completed)} already done, {len(pending)} pending)")
    print(f"Wipe first: {wipe_desc}")
    print(f"Workers:    {workers}")
    if dry_run:
        print("Mode:       DRY RUN — no data will be written")
    print()

    # ── Step 1: Wipe ─────────────────────────────────────────────────────────
    if wiping:
        scope_path = "/" if do_wipe_root else target_path
        wipe_ref = db.reference("/") if do_wipe_root else target_ref
        print("WARNING: This will permanently delete data at:")
        print(f"         Path:     {scope_path}")
        print(f"         Project:  {sa['project_id']}")
        print(f"         Database: {db_url}")
        if dry_run:
            print(f"(dry-run) would wipe {scope_path} before uploading.\n")
        else:
            answer = input("         Type 'yes' to confirm: ").strip().lower()
            if answer != "yes":
                print("Aborted.")
                sys.exit(0)
            print(f"\nWiping {scope_path} ...", end=" ", flush=True)
            wipe_ref.delete()
            print("done\n")

    if not pending:
        print("Nothing to upload — all chunks already completed.")
        print("(delete the .upload-progress file to force a full re-upload.)")
        return

    # ── Step 2: Upload chunks ────────────────────────────────────────────────
    manifest_lock = threading.Lock()

    def record(fname):
        if dry_run:
            return
        with manifest_lock, open(manifest_path, "a") as mf:
            mf.write(fname + "\n")

    total_entries = 0
    failed = []
    t_start = time.time()

    def handle(fname):
        path = os.path.join(chunks_dir, fname)
        ok, n = _upload_one_chunk(target_ref, path, fname, dry_run)
        return fname, ok, n

    if workers > 1 and not dry_run:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(handle, fn) for fn in pending]
            for fut in as_completed(futures):
                fname, ok, n = fut.result()
                done += 1
                if ok:
                    total_entries += n
                    record(fname)
                else:
                    failed.append(fname)
                print(f"  [{done:4d}/{len(pending)}] {fname} — {'ok' if ok else 'FAILED'} ({n} entries)")
    else:
        for i, fname in enumerate(pending, 1):
            pct = i * 100 // len(pending)
            tty_progress(f"  [{i:4d}/{len(pending)}] {pct:3d}%  {fname}   ")
            fname, ok, n = handle(fname)
            if ok:
                total_entries += n
                record(fname)
            else:
                failed.append(fname)

    elapsed_total = time.time() - t_start
    print(f"\n\nDone in {int(elapsed_total // 60)}m{int(elapsed_total % 60)}s")
    print(f"  Uploaded: {total_entries} entries across {len(pending) - len(failed)} chunks")

    if failed:
        print(f"\n  FAILED chunks ({len(failed)}) — re-run (without --wipe) to retry only these:")
        for f in failed:
            print(f"    {f}")
        sys.exit(1)
    elif dry_run:
        print("\nDry run complete. No data was written.")
    else:
        print("\nRestore complete. Verify in Firebase Console → Realtime Database → Data.")


def main():
    parser = argparse.ArgumentParser(description="Upload RTDB chunk files produced by firebase-rtdb-split.")
    parser.add_argument("chunks_dir", help="Directory containing the chunk_*.json files.")
    parser.add_argument("-s", "--service-account", help="Path to the Firebase service account JSON key. Can also be set via the FIREBASE_SERVICE_ACCOUNT_KEY env var, or fall back to './serviceAccountKey.json' in the current directory.")
    parser.add_argument("-p", "--path", default="/users", help="The target RTDB path to merge the chunks into (default: '/users').")
    parser.add_argument("--wipe", action="store_true", help="Wipe the TARGET path (-p/--path) before uploading. Leaves sibling nodes untouched.")
    parser.add_argument("--wipe-root", action="store_true", help="Wipe the ENTIRE database root (/) before uploading. Destroys all data.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded/wiped without writing anything.")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Number of chunks to upload in parallel (default: 1).")
    parser.add_argument("-d", "--database-url", help="Override the default Firebase database URL (useful for custom domains or regional RTDB instances).")

    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be a positive integer")

    sa_path = resolve_service_account(args.service_account)
    if not sa_path:
        service_account_error()
        sys.exit(1)

    upload_chunks(
        chunks_dir=os.path.expanduser(args.chunks_dir),
        sa_path=sa_path,
        target_path=args.path,
        do_wipe=args.wipe,
        do_wipe_root=args.wipe_root,
        dry_run=args.dry_run,
        workers=args.workers,
        database_url=args.database_url,
    )


if __name__ == "__main__":
    main()
