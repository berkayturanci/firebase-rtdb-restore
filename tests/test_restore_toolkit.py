import unittest
import json
import os
import sys
import shutil
import tempfile
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
from firebase_rtdb_restore.split_backup import split_backup
from firebase_rtdb_restore.validate_chunks import stream_original, load_chunks
from firebase_rtdb_restore.upload_chunks import upload_chunks
from firebase_rtdb_restore.upload_single_user import upload_single_user


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

    def test_validate_chunks_passed(self):
        """Test validation succeeds on a lossless split."""
        # 1. Split backup
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")
        
        # 2. Load chunks and stream original
        chunk_fps, duplicates = load_chunks(self.chunks_dir)
        self.assertEqual(len(chunk_fps), 4)
        self.assertEqual(len(duplicates), 0)
        
        orig_fps = dict(stream_original(self.backup_file, "users"))
        self.assertEqual(len(orig_fps), 4)
        
        # 3. Compare fingerprints
        for key, (fp, size) in chunk_fps.items():
            self.assertIn(key, orig_fps)
            self.assertEqual(fp, orig_fps[key][0])

    def test_validate_chunks_tampered(self):
        """Test validation catches missing, extra, and mismatching values."""
        # 1. Split backup
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")
        
        # 2. Tamper with a chunk file (remove one user, modify another, add an extra one)
        chunk_0_path = os.path.join(self.chunks_dir, "chunk_0000.json")
        with open(chunk_0_path, "r") as f:
            chunk = json.load(f)
            
        del chunk["user_0001"]  # Missing user
        chunk["user_0002"]["name"] = "Tampered Bob"  # Value mismatch
        chunk["extra_user"] = {"name": "Malicious User"}  # Extra user
        
        with open(chunk_0_path, "w") as f:
            json.dump(chunk, f)
            
        # 3. Verify validation flags these errors
        chunk_fps, duplicates = load_chunks(self.chunks_dir)
        self.assertNotIn("user_0001", chunk_fps)
        self.assertIn("extra_user", chunk_fps)
        
        orig_fps = dict(stream_original(self.backup_file, "users"))
        
        # user_0001 in original but missing from chunk
        self.assertIn("user_0001", orig_fps)
        self.assertNotIn("user_0001", chunk_fps)
        
        # user_0002 has mismatched fingerprints
        orig_fp = orig_fps["user_0002"][0]
        chunk_fp = chunk_fps["user_0002"][0]
        self.assertNotEqual(orig_fp, chunk_fp)

    def test_upload_chunks(self):
        """Test batch uploading chunks to mock Firebase RTDB."""
        # 1. Split backup
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")
        
        # 2. Setup mock DB reference
        mock_root_ref = MagicMock()
        mock_target_ref = MagicMock()
        
        def mock_ref_side_effect(path):
            if path == "/":
                return mock_root_ref
            return mock_target_ref
            
        mock_db.reference.side_effect = mock_ref_side_effect
        
        # 3. Create a fake service account file
        sa_file = os.path.join(self.test_dir, "service_account.json")
        with open(sa_file, "w") as f:
            json.dump({"project_id": "test-project-123"}, f)
            
        # 4. Upload (wipe=True, path="/users")
        with patch("builtins.input", return_value="yes"):  # Confirm wipe
            upload_chunks(
                chunks_dir=self.chunks_dir,
                sa_path=sa_file,
                target_path="/users",
                do_wipe=True
            )
            
        # Verify initialize_app was called
        mock_firebase_admin.initialize_app.assert_called_once()
        
        # Verify root reference delete (wipe) was called
        mock_root_ref.delete.assert_called_once()
        
        # Verify batch updates were called (2 updates since we have 2 chunks)
        self.assertEqual(mock_target_ref.update.call_count, 2)

    def test_upload_single_user(self):
        """Test uploading a single user recursively with mock Firebase."""
        # 1. Split backup
        split_backup(self.backup_file, self.chunks_dir, chunk_size=2, node_key="users")
        
        # 2. Setup mock DB reference
        mock_user_ref = MagicMock()
        mock_db.reference.return_value = mock_user_ref
        
        # 3. Create a fake service account file
        sa_file = os.path.join(self.test_dir, "service_account.json")
        with open(sa_file, "w") as f:
            json.dump({"project_id": "test-project-123"}, f)
            
        # 4. Upload single user
        chunk_file = os.path.join(self.chunks_dir, "chunk_0000.json")
        upload_single_user(
            key="user_0001",
            chunk_path=chunk_file,
            sa_path=sa_file,
            parent_path="/users"
        )
        
        # Verify child and set were called (writes each top-level key of user_0001: name, email, role)
        self.assertEqual(mock_user_ref.child.call_count, 3)
        self.assertEqual(mock_user_ref.child().set.call_count, 3)


if __name__ == "__main__":
    unittest.main()
