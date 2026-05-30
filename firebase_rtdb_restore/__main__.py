"""Allow ``python -m firebase_rtdb_restore`` to list the available commands."""

import sys

COMMANDS = {
    "split": "firebase_rtdb_restore.split_backup",
    "validate": "firebase_rtdb_restore.validate_chunks",
    "upload": "firebase_rtdb_restore.upload_chunks",
    "upload-single": "firebase_rtdb_restore.upload_single_user",
}


def main():
    print("Firebase RTDB Lossless Restore Toolkit\n")
    print("Run one of the module entry points directly, e.g.:")
    for name, module in COMMANDS.items():
        print(f"  python -m {module}    # {name}")
    print("\nOr use the installed console scripts: firebase-rtdb-split, "
          "firebase-rtdb-validate, firebase-rtdb-upload, firebase-rtdb-upload-single.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
