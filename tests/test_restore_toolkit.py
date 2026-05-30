import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Inject mock firebase_admin modules into sys.modules
# This allows running these unit tests on any clean system without having firebase-admin installed.
mock_firebase_admin = MagicMock()
mock_credentials = MagicMock()
mock_db = MagicMock()

# Link attributes explicitly so "from firebase_admin import credentials, db" matches correctly
mock_firebase_admin.credentials = mock_credentials
mock_firebase_admin.db = mock_db

sys.modules["firebase_admin"] = mock_firebase_admin
sys.modules["firebase_admin.credentials"] = mock_credentials
sys.modules["firebase_admin.db"] = mock_db

# Import the toolkit components (now safe to import because firebase_admin is mocked)
from firebase_rtdb_restore import _common
from firebase_rtdb_restore.split_backup import split_backup
from firebase_rtdb_restore.upload_chunks import upload_chunks
from firebase_rtdb_restore.upload_single_user import upload_single_user
from firebase_rtdb_restore.validate_chunks import load_chunks, stream_original


class TestRestoreToolkit(unittest.TestCase):
    def setUp(self):
        # Reset the mock calls and restore attribute links
        mock_firebase_admin.reset_mock()
        mock_credentials.reset_mock()
        mock_db.reset_mock()

        # Explicitly clear side_effects to prevent cross-test state leakage
        mock_db.reference.side_effect = None
        mock_db.reference.return_value = MagicMock()

        mock_firebase_admin.credentials = mock_credentials
        mock_firebase_admin.db = mock_db

        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.chunks_dir = os.path.join(self.test_dir, "chunks")

        # Synthetic backup data
        self.synthetic_data = {
            "metadata": {
                "created": "2026-05-30"
            },
            "users": {
                "user_0001": {"name": "Alice", "email": "alice@example.com", "role": "admin"},
                "user_0002": {"name": "Bob", "email": "bob@example.com", "role": "user"},
                "user_0003": {"name": "Charlie", "email": "charlie@example.com", "role": "user"},
                "user_0004": {"name": "David", "email": "david@example.com", "role": "manager"}
            }
        }

        # Write synthetic backup file
        self.backup_file = os.path.join(self.test_dir, "backup.json")
        with open(self.backup_file, "w", encoding="utf-8") as f:
            json.dump(self.synthetic_data, f, indent=2)

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)

    def _write_service_account(self):
        sa_file = os.path.join(self.test_dir, "service_account.json")
        with open(sa_file, "w") as f:
            json.dump({"project_id": "test-project-123"}, f)
        return sa_file

    def test_split_backup(self):
        """Test stream-splitting of backup JSON into chunks."""
        # Split with chunk size of 2 (should produce 2 chunks of 2 users each)
        chunk_num, total = split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        self.assertEqual(chunk_num, 2)
        self.assertEqual(total, 4)

        # Verify chunk 0000
        chunk_0_path = os.path.join(self.chunks_dir, "chunk_0000.json")
        self.assertTrue(os.path.exists(chunk_0_path))
        with open(chunk_0_path) as f:
            chunk_0 = json.load(f)
        self.assertEqual(len(chunk_0), 2)
        self.assertIn("user_0001", chunk_0)
        self.assertIn("user_0002", chunk_0)

        # Verify chunk 0001
        chunk_1_path = os.path.join(self.chunks_dir, "chunk_0001.json")
        self.assertTrue(os.path.exists(chunk_1_path))
        with open(chunk_1_path) as f:
            chunk_1 = json.load(f)
        self.assertEqual(len(chunk_1), 2)
        self.assertIn("user_0003", chunk_1)
        self.assertIn("user_0004", chunk_1)

    def test_split_backup_minified(self):
        """Splitting must work on minified (single-line) JSON too."""
        minified = os.path.join(self.test_dir, "minified.json")
        with open(minified, "w", encoding="utf-8") as f:
            json.dump(self.synthetic_data, f, separators=(",", ":"))

        chunk_num, total = split_backup(minified, self.chunks_dir, chunk_size=1000, node_key="users")
        self.assertEqual(total, 4)
        self.assertEqual(chunk_num, 1)

    def test_split_backup_node_after_large_header(self):
        """The target node may sit well beyond the first 10 KB of the file."""
        data = {
            "metadata": {"blob": "x" * 50_000},  # >> 10 KB before the users node
            "users": {f"user_{i:04d}": {"i": i} for i in range(5)},
        }
        big = os.path.join(self.test_dir, "big_header.json")
        with open(big, "w", encoding="utf-8") as f:
            json.dump(data, f)

        chunk_num, total = split_backup(big, self.chunks_dir, chunk_size=1000, node_key="users")
        self.assertEqual(total, 5)
        self.assertGreaterEqual(chunk_num, 1)

    def test_split_backup_missing_node(self):
        """A backup without the requested node returns (0, 0) rather than crashing."""
        chunk_num, total = split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="does_not_exist")
        self.assertEqual((chunk_num, total), (0, 0))

    def test_validate_chunks_passed(self):
        """Test validation succeeds on a lossless split."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        chunk_fps, duplicates = load_chunks(self.chunks_dir)
        self.assertEqual(len(chunk_fps), 4)
        self.assertEqual(len(duplicates), 0)

        orig_fps = dict(stream_original(self.backup_file, "users"))
        self.assertEqual(len(orig_fps), 4)

        # Compare fingerprints
        for key, (fp, _size) in chunk_fps.items():
            self.assertIn(key, orig_fps)
            self.assertEqual(fp, orig_fps[key][0])

    def test_validate_chunks_tampered(self):
        """Test validation catches missing, extra, and mismatching values."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        chunk_0_path = os.path.join(self.chunks_dir, "chunk_0000.json")
        with open(chunk_0_path) as f:
            chunk = json.load(f)

        del chunk["user_0001"]  # Missing user
        chunk["user_0002"]["name"] = "Tampered Bob"  # Value mismatch
        chunk["extra_user"] = {"name": "Malicious User"}  # Extra user

        with open(chunk_0_path, "w") as f:
            json.dump(chunk, f)

        chunk_fps, duplicates = load_chunks(self.chunks_dir)
        self.assertNotIn("user_0001", chunk_fps)
        self.assertIn("extra_user", chunk_fps)

        orig_fps = dict(stream_original(self.backup_file, "users"))

        self.assertIn("user_0001", orig_fps)
        self.assertNotIn("user_0001", chunk_fps)

        orig_fp = orig_fps["user_0002"][0]
        chunk_fp = chunk_fps["user_0002"][0]
        self.assertNotEqual(orig_fp, chunk_fp)

    def test_upload_chunks_wipe_target(self):
        """--wipe deletes the TARGET path (not the root) and uploads each chunk."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        mock_root_ref = MagicMock()
        mock_target_ref = MagicMock()

        def mock_ref_side_effect(path):
            return mock_root_ref if path == "/" else mock_target_ref

        mock_db.reference.side_effect = mock_ref_side_effect

        sa_file = self._write_service_account()

        with patch("builtins.input", return_value="yes"):
            upload_chunks(
                chunks_dir=self.chunks_dir,
                sa_path=sa_file,
                target_path="/users",
                do_wipe=True,
            )

        mock_firebase_admin.initialize_app.assert_called_once()
        # Target path wiped, root left untouched.
        mock_target_ref.delete.assert_called_once()
        mock_root_ref.delete.assert_not_called()
        # 2 chunks -> 2 batch updates.
        self.assertEqual(mock_target_ref.update.call_count, 2)

    def test_upload_chunks_wipe_root(self):
        """--wipe-root deletes the database root."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        mock_root_ref = MagicMock()
        mock_target_ref = MagicMock()

        def mock_ref_side_effect(path):
            return mock_root_ref if path == "/" else mock_target_ref

        mock_db.reference.side_effect = mock_ref_side_effect

        sa_file = self._write_service_account()

        with patch("builtins.input", return_value="yes"):
            upload_chunks(
                chunks_dir=self.chunks_dir,
                sa_path=sa_file,
                target_path="/users",
                do_wipe_root=True,
            )

        mock_root_ref.delete.assert_called_once()

    def test_upload_chunks_dry_run(self):
        """--dry-run writes nothing and creates no progress manifest."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        mock_target_ref = MagicMock()
        mock_db.reference.return_value = mock_target_ref

        sa_file = self._write_service_account()

        upload_chunks(
            chunks_dir=self.chunks_dir,
            sa_path=sa_file,
            target_path="/users",
            dry_run=True,
        )

        mock_target_ref.update.assert_not_called()
        mock_target_ref.delete.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.chunks_dir, ".upload-progress")))

    def test_upload_chunks_resume_skips_completed(self):
        """A chunk recorded in .upload-progress is skipped on a non-wipe re-run."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        # Pretend chunk_0000 already uploaded.
        with open(os.path.join(self.chunks_dir, ".upload-progress"), "w") as f:
            f.write("chunk_0000.json\n")

        mock_target_ref = MagicMock()
        mock_db.reference.return_value = mock_target_ref

        sa_file = self._write_service_account()

        upload_chunks(
            chunks_dir=self.chunks_dir,
            sa_path=sa_file,
            target_path="/users",
        )

        # Only the remaining chunk_0001 should be uploaded.
        self.assertEqual(mock_target_ref.update.call_count, 1)

    def test_upload_single_user(self):
        """Test uploading a single user recursively with mock Firebase."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        mock_user_ref = MagicMock()
        mock_db.reference.return_value = mock_user_ref

        sa_file = self._write_service_account()

        chunk_file = os.path.join(self.chunks_dir, "chunk_0000.json")
        upload_single_user(
            key="user_0001",
            chunk_path=chunk_file,
            sa_path=sa_file,
            parent_path="/users",
        )

        # Writes each top-level key of user_0001: name, email, role
        self.assertEqual(mock_user_ref.child.call_count, 3)
        self.assertEqual(mock_user_ref.child().set.call_count, 3)

    def test_upload_chunks_wipe_abort(self):
        """Declining the wipe confirmation aborts cleanly without deleting or writing."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        mock_target_ref = MagicMock()
        mock_db.reference.return_value = mock_target_ref

        sa_file = self._write_service_account()

        with patch("builtins.input", return_value="no"), self.assertRaises(SystemExit) as cm:
            upload_chunks(
                chunks_dir=self.chunks_dir,
                sa_path=sa_file,
                target_path="/users",
                do_wipe=True,
            )

        self.assertEqual(cm.exception.code, 0)
        mock_target_ref.delete.assert_not_called()
        mock_target_ref.update.assert_not_called()

    def test_upload_chunks_missing_service_account(self):
        """A non-existent service-account path fails fast with exit code 1."""
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")

        with self.assertRaises(SystemExit) as cm:
            upload_chunks(
                chunks_dir=self.chunks_dir,
                sa_path=os.path.join(self.test_dir, "does_not_exist.json"),
                target_path="/users",
            )

        self.assertEqual(cm.exception.code, 1)

    def test_init_app_uses_custom_database_url(self):
        """A custom --database-url is passed through to initialize_app verbatim."""
        sa_file = self._write_service_account()
        custom_url = "https://custom-db.europe-west1.firebasedatabase.app"

        _sa, db_url = _common.init_app(sa_file, database_url=custom_url)

        self.assertEqual(db_url, custom_url)
        # initialize_app(cred, {"databaseURL": <url>}) — verify the options dict.
        options = mock_firebase_admin.initialize_app.call_args[0][1]
        self.assertEqual(options["databaseURL"], custom_url)

    def test_init_app_defaults_database_url_from_project_id(self):
        """Without an override the database URL is derived from the project id."""
        sa_file = self._write_service_account()

        _sa, db_url = _common.init_app(sa_file)

        self.assertEqual(db_url, "https://test-project-123.firebaseio.com")


class TestCommonHelpers(unittest.TestCase):
    def test_recursive_write_splits_oversized_dict(self):
        """A dict above max_bytes is split child-by-child; small values are set directly."""
        ref = MagicMock()
        big_value = {"a": "x" * 100, "b": "y" * 100, "c": "z" * 100}
        _common.recursive_write(ref, big_value, "/u", max_bytes=50)
        # One .set per child key (each small enough on its own).
        self.assertEqual(ref.child.call_count, 3)
        self.assertEqual(ref.child().set.call_count, 3)

    def test_recursive_write_small_value_single_set(self):
        ref = MagicMock()
        _common.recursive_write(ref, {"a": 1}, "/u", max_bytes=4 * 1024 * 1024)
        ref.set.assert_called_once()

    def test_with_retry_succeeds_after_transient_failure(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return "ok"

        with patch("time.sleep"):
            result = _common.with_retry(flaky, attempts=4, base_delay=0, label="test")
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)

    def test_with_retry_reraises_after_exhausting_attempts(self):
        def always_fail():
            raise ValueError("boom")

        with patch("time.sleep"), self.assertRaises(ValueError):
            _common.with_retry(always_fail, attempts=2, base_delay=0)

    def test_resolve_service_account_precedence(self):
        # Explicit arg wins.
        self.assertEqual(_common.resolve_service_account("/tmp/explicit.json"), "/tmp/explicit.json")
        # Falls back to env var.
        with patch.dict(os.environ, {"FIREBASE_SERVICE_ACCOUNT_KEY": "/tmp/env.json"}, clear=False):
            self.assertEqual(_common.resolve_service_account(None), "/tmp/env.json")


if __name__ == "__main__":
    unittest.main()
