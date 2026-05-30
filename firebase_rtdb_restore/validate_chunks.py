#!/usr/bin/env python3
"""
Verify that chunk files are a lossless, exact split of the original backup.

Streams the original JSON (never loads it fully into memory), computes a
SHA-256 fingerprint per entry, then compares against every chunk file. Only the
compact per-entry fingerprints (16-byte digest + size) are held resident, not
the entry data itself.
"""

import argparse
import hashlib
import json
import os
import sys

from firebase_rtdb_restore._common import iter_entries, locate_node


def _fingerprint(value):
    """SHA-256 of canonical (sorted-keys) JSON — order-independent deep equality.

    Returns ``(digest_bytes, byte_size)``. The raw 16-byte-truncated digest is
    kept instead of the 64-char hex string to roughly quarter resident memory
    when validating very large backups.
    """
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).digest()[:16], len(encoded)


def stream_original(input_path, node_key):
    """Stream-parse the target node object, yielding ``(key, fingerprint)`` pairs."""
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    file_size = os.path.getsize(input_path)

    with open(input_path, encoding="utf-8") as f:
        buf = locate_node(f, node_key)
        if buf is None:
            print(f'ERROR: "{node_key}" key not found.')
            sys.exit(1)

        for key, val in iter_entries(f, buf, file_size=file_size, label="Streaming original"):
            yield key, _fingerprint(val)

    print()  # newline after the progress line


def load_chunks(chunks_dir):
    """
    Load all chunk files, return {key: fingerprint} and a list of duplicate keys.
    """
    chunk_files = sorted(
        f for f in os.listdir(chunks_dir)
        if f.startswith("chunk_") and f.endswith(".json")
    )
    if not chunk_files:
        print(f"ERROR: No chunk_*.json files in {chunks_dir}")
        sys.exit(1)

    combined = {}
    duplicates = []

    for i, fname in enumerate(chunk_files, 1):
        print(f"\r  Loading chunks: {i}/{len(chunk_files)} ({fname})  ", end="", flush=True)
        path = os.path.join(chunks_dir, fname)
        with open(path, encoding="utf-8") as f:
            chunk = json.load(f)
        for key, val in chunk.items():
            fp, size = _fingerprint(val)
            if key in combined:
                duplicates.append((key, fname))
            combined[key] = (fp, size)

    print(f"\r  Loading chunks: {len(chunk_files)}/{len(chunk_files)} — {len(combined)} entries loaded  ")
    return combined, duplicates


def main():
    parser = argparse.ArgumentParser(description="Verify that chunk files are a lossless, exact split of the original backup.")
    parser.add_argument("backup_file", help="Path to the original RTDB backup JSON file.")
    parser.add_argument("chunks_dir", help="Directory containing the chunk_*.json files.")
    parser.add_argument("-n", "--node", default="users", help="The top-level JSON key that was split (default: 'users').")

    args = parser.parse_args()

    input_path = os.path.expanduser(args.backup_file)
    chunks_dir = os.path.expanduser(args.chunks_dir)

    if not os.path.exists(input_path):
        print(f"Backup file not found: {input_path}")
        sys.exit(1)
    if not os.path.isdir(chunks_dir):
        print(f"Chunks directory not found: {chunks_dir}")
        sys.exit(1)

    print(f"\nOriginal : {input_path}  ({os.path.getsize(input_path) / 1024 / 1024:.1f} MB)")
    print(f"Chunks   : {chunks_dir}")
    print(f"Split node: {args.node}\n")

    # Step 1: load chunks
    chunk_fps, duplicates = load_chunks(chunks_dir)

    # Step 2: stream original and compare
    missing_from_chunks = []   # in original, not in chunks
    value_mismatches = []   # key present but fingerprint differs
    seen_in_original = set()
    original_count = 0

    for key, (orig_fp, _) in stream_original(input_path, args.node):
        original_count += 1
        seen_in_original.add(key)
        if key not in chunk_fps:
            missing_from_chunks.append(key)
        elif chunk_fps[key][0] != orig_fp:
            value_mismatches.append(key)

    extra_in_chunks = [key for key in chunk_fps if key not in seen_in_original]

    # ── Report ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 55}")
    print(f"  Original entries : {original_count:,}")
    print(f"  Chunk entries    : {len(chunk_fps):,}")
    print(f"{'─' * 55}")

    ok = True

    if duplicates:
        ok = False
        print(f"  FAIL  Duplicate keys in chunks: {len(duplicates)}")
        for key, fname in duplicates[:10]:
            print(f"          {key}  (duplicate in {fname})")
        if len(duplicates) > 10:
            print(f"          ... and {len(duplicates) - 10} more")
    else:
        print("  OK    No duplicate keys across chunks")

    if missing_from_chunks:
        ok = False
        print(f"  FAIL  Entries missing from chunks: {len(missing_from_chunks)}")
        for key in missing_from_chunks[:10]:
            print(f"          {key}")
        if len(missing_from_chunks) > 10:
            print(f"          ... and {len(missing_from_chunks) - 10} more")
    else:
        print("  OK    All original entries present in chunks")

    if extra_in_chunks:
        ok = False
        print(f"  FAIL  Extra keys in chunks (not in original): {len(extra_in_chunks)}")
        for key in extra_in_chunks[:10]:
            print(f"          {key}")
    else:
        print("  OK    No extra keys in chunks")

    if value_mismatches:
        ok = False
        print(f"  FAIL  Value mismatches (SHA-256 differs): {len(value_mismatches)}")
        for key in value_mismatches[:10]:
            print(f"          {key}")
    else:
        print("  OK    All values match exactly (SHA-256 verified)")

    print(f"{'─' * 55}")

    # ── Top-10 largest entries ───────────────────────────────────────────────
    top10 = sorted(chunk_fps.items(), key=lambda x: x[1][1], reverse=True)[:10]
    total_bytes = sum(size for _, (_, size) in chunk_fps.items())
    print("\n  Top 10 largest entries (by JSON size):")
    for key, (_, size) in top10:
        bar = "!" if size > 10 * 1024 * 1024 else ("~" if size > 1 * 1024 * 1024 else " ")
        print(f"  {bar} {size / 1024:8.1f} KB   {key}")
    print(f"\n  Total data size : {total_bytes / 1024 / 1024:.1f} MB")
    print(f"  Avg per entry   : {total_bytes / max(len(chunk_fps), 1) / 1024:.1f} KB")
    print(f"  {'! = over 10 MB  ~ = over 1 MB  (RTDB node limit is 256 MB per write)'}")
    print(f"{'─' * 55}")

    if ok:
        print("  RESULT: PASSED — chunks are a 100% lossless split of the original\n")
        sys.exit(0)
    else:
        print("  RESULT: FAILED — see issues above\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
