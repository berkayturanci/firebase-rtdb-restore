#!/usr/bin/env python3
"""
Stream-split a Firebase RTDB backup into N-entry chunk files.

Works on both pretty-printed AND minified (single-line) JSON.
Reads in 128 KB blocks — never loads the full file into memory.
"""

import argparse
import json
import os

from firebase_rtdb_restore._common import iter_entries, locate_node


def split_backup(input_path, output_dir, chunk_size, node_key):
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found: {input_path}")
        return 0, 0
    file_size = os.path.getsize(input_path)
    os.makedirs(output_dir, exist_ok=True)

    chunk_num = 0
    total = 0
    chunk = {}

    with open(input_path, encoding="utf-8") as f:
        buf = locate_node(f, node_key)
        if buf is None:
            print(f'ERROR: "{node_key}" key not found. Is this a Firebase RTDB backup?')
            return 0, 0

        for key, val in iter_entries(f, buf, file_size=file_size, label="parsing"):
            chunk[key] = val
            total += 1
            if len(chunk) >= chunk_size:
                _write_chunk(output_dir, chunk_num, chunk)
                chunk_num += 1
                chunk = {}

    # Final partial chunk
    if chunk:
        _write_chunk(output_dir, chunk_num, chunk)
        chunk_num += 1

    print(f"\n\nDone: {total} entries → {chunk_num} chunk files in:\n  {output_dir}/")
    _print_upload_instructions(output_dir, node_key)
    return chunk_num, total


def _write_chunk(output_dir, chunk_num, chunk):
    path = os.path.join(output_dir, f"chunk_{chunk_num:04d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunk, f)
    print(f"\r  chunk_{chunk_num:04d}.json  ({len(chunk)} entries){' ' * 30}")


def _print_upload_instructions(output_dir, node_key):
    print(f"\nUpload each chunk (merges into /{node_key} — does NOT overwrite others):")
    print(f"  for f in {output_dir}/chunk_*.json; do")
    print( "    echo \"Uploading $f ...\"")
    print(f"    firebase database:update /{node_key} \"$f\"")
    print( "  done")


def main():
    parser = argparse.ArgumentParser(description="Stream-split a Firebase RTDB backup into N-entry chunk files.")
    parser.add_argument("backup_file", help="Path to the RTDB backup JSON file.")
    parser.add_argument("-o", "--output-dir", help="Directory to save chunk files. Defaults to '<backup_file_dir>/rtdb-chunks'.")
    parser.add_argument("-c", "--chunk-size", type=int, default=1000, help="Number of entries per chunk file (default: 1000).")
    parser.add_argument("-n", "--node", default="users", help="The top-level JSON key to split (default: 'users').")

    args = parser.parse_args()

    if args.chunk_size < 1:
        parser.error("--chunk-size must be a positive integer")

    input_path = os.path.expanduser(args.backup_file)
    output_dir = os.path.expanduser(args.output_dir) if args.output_dir \
        else os.path.join(os.path.dirname(input_path), "rtdb-chunks")

    print(f"Input:      {input_path}")
    print(f"Output dir: {output_dir}")
    print(f"Chunk size: {args.chunk_size} entries")
    print(f"Split node: {args.node}\n")

    split_backup(input_path, output_dir, args.chunk_size, args.node)


if __name__ == "__main__":
    main()
