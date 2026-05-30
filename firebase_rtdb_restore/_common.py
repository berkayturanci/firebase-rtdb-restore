#!/usr/bin/env python3
"""
Shared helpers for the Firebase RTDB restore toolkit.

Keeps the streaming JSON parser, node location, service-account resolution,
idempotent app initialisation, retrying writes and TTY-aware progress in one
place so the four CLI entry points stay thin and behave consistently.
"""

import contextlib
import json
import os
import sys
import time

READ_CHUNK = 128 * 1024  # 128 KB read window

# Sentinel distinguishing "value not parsed yet" from a legitimate JSON ``null``
# value, so an entry whose value is literally ``null`` is not silently dropped.
_INCOMPLETE = object()


def is_tty():
    return sys.stdout.isatty()


def tty_progress(msg):
    """Emit a carriage-return progress line, but only on an interactive TTY.

    On non-interactive streams (CI logs, pipes, test runners) this is a no-op so
    the transient ``\\r`` updates do not flood the output. Final/summary lines
    should use ``print`` directly.
    """
    if is_tty():
        print(f"\r{msg}", end="", flush=True)


def locate_node(f, node_key):
    """Stream-search the open text file ``f`` for the top-level ``"<node_key>": {``.

    Reads the file in blocks until the node is found, so the target node may
    appear anywhere in the backup rather than only within a fixed-size header
    window. Returns the leftover buffer positioned just after the opening
    ``{`` of the node object, or ``None`` if the node is never found.
    """
    node_pattern = f'"{node_key}"'
    # Retain enough of a tail across reads that a pattern straddling a read
    # boundary still matches on the next iteration.
    overlap = len(node_pattern) + 1
    buf = ""
    while True:
        idx = buf.find(node_pattern)
        if idx != -1:
            after = buf[idx + len(node_pattern):]
            colon = after.find(":")
            if colon != -1:
                brace = after.find("{", colon)
                if brace != -1:
                    return after[brace + 1:]
            # Key found but ':' / '{' not fully buffered yet — keep from the key
            # onward and read more.
            more = f.read(READ_CHUNK)
            if not more:
                return None
            buf = buf[idx:] + more
            continue
        more = f.read(READ_CHUNK)
        if not more:
            return None
        buf = buf[-overlap:] + more


def iter_entries(f, buf, file_size=None, label=""):
    """Yield ``(key, value)`` pairs from the node object being streamed.

    ``buf`` must be positioned just after the node's opening ``{`` (see
    :func:`locate_node`). Works on both pretty-printed and minified JSON and
    never loads the whole file into memory. When ``file_size`` and ``label`` are
    given, a TTY-only progress line is emitted as the file is consumed.
    """
    decoder = json.JSONDecoder()
    total = 0

    def report():
        if file_size and label:
            pct = min(f.tell() * 100 // file_size, 100)
            tty_progress(f"  {label}: {total} entries | {pct}% read ")

    while True:
        if len(buf) < READ_CHUNK:
            more = f.read(READ_CHUNK)
            if more:
                buf += more
                report()

        s = buf.lstrip(" \t\n\r")
        if not s or s[0] == "}":
            break
        if s[0] == ",":
            buf = s[1:]
            continue
        if s[0] != '"':
            # Unexpected character outside of a key — skip one char and retry.
            buf = s[1:]
            continue

        # ── parse key ───────────────────────────────────────────────────────
        try:
            key, key_end = decoder.raw_decode(s)
        except json.JSONDecodeError:
            more = f.read(READ_CHUNK)
            if not more:
                break
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

        # ── parse value (read more if incomplete) ───────────────────────────
        val = _INCOMPLETE
        while True:
            try:
                val, val_end = decoder.raw_decode(val_str)
                break
            except json.JSONDecodeError:
                more = f.read(READ_CHUNK)
                if not more:
                    break  # EOF with incomplete value
                val_str += more

        if val is _INCOMPLETE:
            break  # incomplete entry at EOF — stop

        total += 1
        buf = val_str[val_end:]
        yield key, val

    report()


def resolve_service_account(arg):
    """Resolve the service-account path from CLI arg, env var, or local default.

    Order of precedence: explicit ``arg`` → ``FIREBASE_SERVICE_ACCOUNT_KEY`` env
    var → ``./serviceAccountKey.json``. Returns the expanded path or ``None``.
    """
    if arg:
        return os.path.expanduser(arg)
    env = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")
    if env:
        return os.path.expanduser(env)
    if os.path.exists("./serviceAccountKey.json"):
        return "./serviceAccountKey.json"
    return None


def service_account_error():
    print("ERROR: Service account file must be provided via -s/--service-account,")
    print("or set via the FIREBASE_SERVICE_ACCOUNT_KEY environment variable,")
    print("or exist as './serviceAccountKey.json' in the current working directory.")


def init_app(sa_path, database_url=None):
    """Initialise the default Firebase app idempotently.

    Returns ``(service_account_dict, database_url)``. Safe to call more than once
    in the same process: a pre-existing default app is reused instead of raising.
    """
    import firebase_admin
    from firebase_admin import credentials

    with open(sa_path) as f:
        sa = json.load(f)

    db_url = database_url or f"https://{sa['project_id']}.firebaseio.com"

    # A pre-existing default app raises ValueError — reuse it instead of failing.
    with contextlib.suppress(ValueError):
        firebase_admin.initialize_app(credentials.Certificate(sa_path), {"databaseURL": db_url})

    return sa, db_url


def with_retry(fn, *, attempts=4, base_delay=1.0, label=""):
    """Call ``fn`` with exponential backoff, retrying on any exception.

    ``attempts`` is the total number of tries (1 initial + ``attempts - 1``
    retries). Re-raises the last exception if every attempt fails.
    """
    last = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — surface any transient failure to retry
            last = e
            if i == attempts:
                break
            delay = base_delay * (2 ** (i - 1))
            print(f"\n  retry {i}/{attempts - 1} for {label or 'write'} after error: {e} (waiting {delay:.1f}s)")
            time.sleep(delay)
    raise last


def recursive_write(ref, value, path, max_bytes, depth=0):
    """Write ``value`` to ``ref``, splitting dicts child-by-child if too large.

    Any single write is retried with backoff. A non-dict value larger than
    ``max_bytes`` cannot be split, so it is written as one request with a warning.
    """
    sz = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
    indent = "  " * (depth + 1)
    tty_progress(f"{indent}{path}  ({sz // 1024} KB) ...")

    if sz <= max_bytes or not isinstance(value, dict):
        if sz > max_bytes:
            print(
                f"\n  WARNING: {path} is {sz // 1024} KB and is not a dict — "
                f"cannot split further, writing as a single request."
            )
        with_retry(lambda: ref.set(value), label=path)
        return

    # Too large — write each child key separately (recursing as needed).
    for k, v in value.items():
        recursive_write(ref.child(k), v, f"{path}/{k}", max_bytes, depth + 1)
