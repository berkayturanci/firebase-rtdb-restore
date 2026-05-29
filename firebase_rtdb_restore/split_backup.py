#!/usr/bin/env python3
"""
Stream-split a Firebase RTDB backup into N-entry chunk files.

Works on both pretty-printed AND minified (single-line) JSON.
Reads in 128 KB blocks — never loads the full file into memory.
"""

import argparse
import json
import os
import sys

READ_CHUNK = 128 * 1024  # 128 KB read window


def split_backup(input_path, output_dir, chunk_size, node_key):
    decoder = json.JSONDecoder()
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found: {input_path}")
        return 0, 0
    file_size = os.path.getsize(input_path)
    os.makedirs(output_dir, exist_ok=True)

    chunk_num = 0
    total = 0
    chunk = {}
    bytes_read = 0

    with open(input_path, "r", encoding="utf-8") as f:
        # ── Step 1: locate node section and skip to first entry ──────────
        header = f.read(10 * 1024)
        bytes_read += len(header)

        node_pattern = f'"{node_key}"'
        node_idx = header.find(node_pattern)
        if node_idx == -1:
            print(f'ERROR: "{node_key}" key not found in first 10 KB. Is this a Firebase RTDB backup?')
            return 0, 0

        after = header[node_idx + len(node_pattern):]
        colon = after.find(":")
        brace = after.find("{", colon)
        if brace == -1:
            print(f"ERROR: could not find opening {{ of {node_key} object")
            return 0, 0

        # buf = everything after the opening { of the target object
        buf = after[brace + 1:]

        # ── Step 2: stream entries ──────────────────────────────────────
        while True:
            # Top up buffer to at least READ_CHUNK characters
            if len(buf) < READ_CHUNK:
                more = f.read(READ_CHUNK)
                if more:
                    bytes_read += len(more)
                    buf += more
                    pct = min(bytes_read * 100 // file_size, 100)
                    print(f"\r  {total} entries parsed | {pct}% read", end="", flush=True)

            s = buf.lstrip(" \t\n\r")

            if not s:
                break

            # End of object
            if s[0] == "}":
                break

            # Skip commas between entries
            if s[0] == ",":
                buf = s[1:]
                continue

            # Unexpected character — skip
            if s[0] != '"':
                buf = s[1:]
                continue

            # ── parse key ────────────────────────────────────────────────────
            try:
                key, key_end = decoder.raw_decode(s)
            except json.JSONDecodeError:
                # Need more data
                more = f.read(READ_CHUNK)
                if not more:
                    break
                bytes_read += len(more)
                buf = s + more
                continue

            if not isinstance(key, str):
                buf = s[key_end:]
                continue

            rest = s[key_end:].lstrip()
            if not rest or rest[0] != ":":
                buf = rest
                continue

            val_str = rest[1:].lstrip()

            # ── parse value (read more if incomplete) ────────────────────────
            val = None
            while True:
                try:
                    val, val_end = decoder.raw_decode(val_str)
                    break
                except json.JSONDecodeError:
                    more = f.read(READ_CHUNK)
                    if not more:
                        break  # EOF with incomplete value
                    bytes_read += len(more)
                    val_str += more

            if val is None:
                break  # incomplete entry at EOF — stop

            # ── store entry ──────────────────────────────────────────────────
            chunk[key] = val
            total += 1
            buf = val_str[val_end:]

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
