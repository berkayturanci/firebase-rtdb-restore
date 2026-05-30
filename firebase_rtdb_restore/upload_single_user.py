#!/usr/bin/env python3
"""
Upload a single entry from a chunk file to RTDB, key-by-key.
Safe for entries with very large data (splits into one request per top-level child key recursively).
"""

import argparse
import json
import os
import sys


def write_ref(ref, value, path, max_bytes, depth=0):
    """Recursively write value to ref, splitting by sub-keys if too large."""
    sz = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
    indent = "  " * (depth + 1)
    print(f"\r{indent}{path}  ({sz // 1024} KB) ...", end=" ", flush=True)

    if sz <= max_bytes or not isinstance(value, dict):
        ref.set(value)
        print("done")
        return

    # Too large — write each child key separately
    print(f"splitting ({len(value)} sub-keys)")
    for k, v in value.items():
        write_ref(ref.child(k), v, f"{path}/{k}", max_bytes, depth + 1)


def upload_single_user(key, chunk_path, sa_path, parent_path, database_url=None):
    try:
        import firebase_admin
        from firebase_admin import credentials, db
    except ImportError:
        print("ERROR: firebase-admin not installed. Run: pip3 install firebase-admin")
        sys.exit(1)

    if not os.path.exists(chunk_path):
        print(f"ERROR: Chunk file not found: {chunk_path}")
        sys.exit(1)

    if not os.path.exists(sa_path):
        print(f"ERROR: Service account not found: {sa_path}")
        sys.exit(1)

    with open(sa_path) as f:
        sa = json.load(f)

    db_url = database_url or f"https://{sa['project_id']}.firebaseio.com"

    firebase_admin.initialize_app(credentials.Certificate(sa_path), {
        "databaseURL": db_url
    })

    with open(chunk_path) as f:
        chunk = json.load(f)

    if key not in chunk:
        print(f"ERROR: Key '{key}' not found in {chunk_path}")
        sys.exit(1)

    val = chunk[key]
    total_sz = len(json.dumps(val, ensure_ascii=False, separators=(",", ":")).encode())
    print(f"\nProject : {sa['project_id']}")
    print(f"Database: {db_url}")
    print(f"Key     : {key}")
    print(f"Size    : {total_sz / 1024 / 1024:.1f} MB")
    print(f"Sub-keys: {len(val) if isinstance(val, dict) else 0}\n")

    MAX_BYTES = 4 * 1024 * 1024  # 4 MB per request

    # Target path e.g. /users/uid
    target_path = f"{parent_path.rstrip('/')}/{key}"
    target_ref = db.reference(target_path)

    if isinstance(val, dict):
        for k, v in val.items():
            write_ref(target_ref.child(k), v, f"/{k}", MAX_BYTES)
    else:
        write_ref(target_ref, val, "", MAX_BYTES)

    print(f"\nEntry '{key}' fully restored under {target_path}.")


def main():
    parser = argparse.ArgumentParser(description="Upload a single entry from a chunk file to RTDB, splitting by sub-keys recursively if too large.")
    parser.add_argument("key", help="The specific key (e.g. UID) to restore.")
    parser.add_argument("chunk_file", help="Path to the chunk file containing the key.")
    parser.add_argument("-s", "--service-account", help="Path to the Firebase service account JSON key. Can also be set via the FIREBASE_SERVICE_ACCOUNT_KEY env var, or fall back to './serviceAccountKey.json' in the current directory.")
    parser.add_argument("-p", "--path", default="/users", help="The parent RTDB path where the entry resides (default: '/users').")
    parser.add_argument("-d", "--database-url", help="Override the default Firebase database URL.")

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

    upload_single_user(
        key=args.key,
        chunk_path=os.path.expanduser(args.chunk_file),
        sa_path=sa_path,
        parent_path=args.path,
        database_url=args.database_url
    )


if __name__ == "__main__":
    main()
