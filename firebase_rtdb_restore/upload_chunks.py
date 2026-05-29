#!/usr/bin/env python3
"""
Upload RTDB chunk files produced by firebase-rtdb-split.
"""

import argparse
import json
import os
import sys
import time

try:
    import firebase_admin
    from firebase_admin import credentials, db
except ImportError:
    print("firebase-admin not installed. Run:")
    print("  pip3 install firebase-admin")
    sys.exit(1)


def _send_batch(ref, batch, fname, req_num):
    try:
        ref.update(batch)
        return True
    except Exception as e:
        print(f"\n  ERROR on {fname} req#{req_num}: {e}")
        return False


def _send_giant_entry(ref, key, val, fname, req_num, max_batch_bytes):
    """Single entry whose data exceeds max_batch_bytes — write each top-level key separately."""
    print(f"\n  Giant entry {key} — writing {len(val)} top-level keys individually...")
    entry_ref = ref.child(key)
    for k, v in val.items():
        sz = len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode())
        print(f"\r    /{key}/{k}  ({sz // 1024} KB)   ", end="", flush=True)
        try:
            entry_ref.child(k).set(v)
        except Exception as e:
            print(f"\n  ERROR on {fname} req#{req_num} /{key}/{k}: {e}")
            return False
    print(f"\r    /{key} — all keys written{' ' * 30}")
    return True


def upload_chunks(chunks_dir, sa_path, target_path, do_wipe, database_url=None):
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
    with open(sa_path) as f:
        sa = json.load(f)

    cred = credentials.Certificate(sa_path)
    db_url = database_url or f"https://{sa['project_id']}.firebaseio.com"

    firebase_admin.initialize_app(cred, {
        "databaseURL": db_url
    })

    root_ref = db.reference("/")
    target_ref = db.reference(target_path)

    print(f"\nProject:    {sa['project_id']}")
    print(f"Database:   {db_url}")
    print(f"Target Path: {target_path}")
    print(f"Chunks dir: {chunks_dir}")
    print(f"Chunks:     {len(chunk_files)}")
    print(f"Wipe first: {'YES — entire database root (/) will be wiped' if do_wipe else 'no (resume/append mode)'}\n")

    # ── Step 1: Wipe entire root ─────────────────────────────────────────────
    if do_wipe:
        print("WARNING: This will permanently delete ALL data in the database.")
        print(f"         Project: {sa['project_id']}")
        print(f"         Database: {db_url}")
        answer = input("         Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)
        print("\nWiping entire database root ...", end=" ", flush=True)
        root_ref.delete()
        print("done\n")

    # ── Step 2: Upload chunks ────────────────────────────────────────────────
    MAX_BATCH_BYTES = 4 * 1024 * 1024   # 4 MB per request (conservative)

    total_entries = 0
    failed = []
    t_start = time.time()
    req_num = 0

    for i, fname in enumerate(chunk_files, 1):
        path = os.path.join(chunks_dir, fname)
        with open(path, encoding="utf-8") as f:
            chunk = json.load(f)

        items = list(chunk.items())
        batch = {}
        batch_sz = 2   # opening/closing braces
        chunk_ok = True

        for key, val in items:
            entry = json.dumps({key: val}, ensure_ascii=False, separators=(",", ":"))
            entry_sz = len(entry.encode("utf-8"))

            # Flush current batch if adding this entry would exceed the limit
            if batch and batch_sz + entry_sz > MAX_BATCH_BYTES:
                req_num += 1
                elapsed = time.time() - t_start
                pct = i * 100 // len(chunk_files)
                print(
                    f"\r  [{i:4d}/{len(chunk_files)}] {pct:3d}%  {fname}  "
                    f"req#{req_num}  ({len(batch)} entries, {batch_sz//1024} KB)   ",
                    end="", flush=True
                )
                if _send_batch(target_ref, batch, fname, req_num):
                    total_entries += len(batch)
                else:
                    failed.append(f"{fname}[req#{req_num}]")
                    chunk_ok = False
                batch = {}
                batch_sz = 2

            # Single entry is too large even alone — write key-by-key
            if entry_sz > MAX_BATCH_BYTES:
                req_num += 1
                if not _send_giant_entry(target_ref, key, val, fname, req_num, MAX_BATCH_BYTES):
                    failed.append(f"{fname}[req#{req_num} giant:{key}]")
                    chunk_ok = False
                else:
                    total_entries += 1
                continue

            batch[key] = val
            batch_sz += entry_sz

        # Flush remaining entries in this chunk
        if batch:
            req_num += 1
            pct = i * 100 // len(chunk_files)
            print(
                f"\r  [{i:4d}/{len(chunk_files)}] {pct:3d}%  {fname}  "
                f"req#{req_num}  ({len(batch)} entries, {batch_sz//1024} KB)   ",
                end="", flush=True
            )
            if _send_batch(target_ref, batch, fname, req_num):
                total_entries += len(batch)
            else:
                failed.append(f"{fname}[req#{req_num}]")
                chunk_ok = False

    elapsed_total = time.time() - t_start
    print(f"\n\nDone in {int(elapsed_total // 60)}m{int(elapsed_total % 60)}s")
    print(f"  Uploaded: {total_entries} entries across {len(chunk_files) - len(failed)} chunks")

    if failed:
        print(f"\n  FAILED chunks ({len(failed)}) — re-run without --wipe to retry:")
        for f in failed:
            print(f"    {f}")
        sys.exit(1)
    else:
        print("\nRestore complete. Verify in Firebase Console → Realtime Database → Data.")


def main():
    parser = argparse.ArgumentParser(description="Upload RTDB chunk files produced by firebase-rtdb-split.")
    parser.add_argument("chunks_dir", help="Directory containing the chunk_*.json files.")
    parser.add_argument("-s", "--service-account", help="Path to the Firebase service account JSON key. Can also be set via the FIREBASE_SERVICE_ACCOUNT_KEY env var, or fall back to './serviceAccountKey.json' in the current directory.")
    parser.add_argument("-p", "--path", default="/users", help="The target RTDB path to merge the chunks into (default: '/users').")
    parser.add_argument("--wipe", action="store_true", help="Wipe the ENTIRE database root (/) before starting the upload.")
    parser.add_argument("-d", "--database-url", help="Override the default Firebase database URL (useful for custom domains or regional RTDB instances).")

    args = parser.parse_args()

    # Determine service account path
    sa_path = None
    if args.service_account:
        sa_path = os.path.expanduser(args.service_account)
    elif os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY"):
        sa_path = os.path.expanduser(os.environ["FIREBASE_SERVICE_ACCOUNT_KEY"])
    elif os.path.exists("./serviceAccountKey.json"):
        sa_path = "./serviceAccountKey.json"

    if not sa_path:
        print("ERROR: Service account file must be provided via -s/--service-account,")
        print("or set via the FIREBASE_SERVICE_ACCOUNT_KEY environment variable,")
        print("or exist as './serviceAccountKey.json' in the current working directory.")
        sys.exit(1)

    upload_chunks(
        chunks_dir=os.path.expanduser(args.chunks_dir),
        sa_path=sa_path,
        target_path=args.path,
        do_wipe=args.wipe,
        database_url=args.database_url
    )


if __name__ == "__main__":
    main()
