"""Tests for snapshot storage functionality."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from loco.snapshots import SnapshotStorage, hash_path, get_sessions_dir
from loco.rewind import (
    ChangeType,
    FileChange,
    TurnCheckpoint,
    RewindState,
)


class TestHashPath:
    """Tests for path hashing."""

    def test_hash_path_consistency(self):
        """Test that hash_path produces consistent results."""
        path = "/home/user/project/src/main.py"
        hash1 = hash_path(path)
        hash2 = hash_path(path)
        assert hash1 == hash2

    def test_hash_path_different_paths(self):
        """Test that different paths produce different hashes."""
        path1 = "/home/user/file1.py"
        path2 = "/home/user/file2.py"
        hash1 = hash_path(path1)
        hash2 = hash_path(path2)
        assert hash1 != hash2

    def test_hash_path_length(self):
        """Test that hash is 16 characters."""
        hash_value = hash_path("/any/path/file.txt")
        assert len(hash_value) == 16

    def test_hash_path_special_characters(self):
        """Test hashing paths with special characters."""
        path = "/home/user/my project/file (1).py"
        hash_value = hash_path(path)
        assert len(hash_value) == 16
        assert hash_value.isalnum()


class TestSnapshotStorage:
    """Tests for SnapshotStorage class."""

    def test_storage_initialization(self):
        """Test SnapshotStorage initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                assert storage.session_id == "test_session"
                assert storage.session_dir == Path(tmpdir) / "test_session"

    def test_ensure_dirs(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                assert storage.session_dir.exists()
                assert storage.snapshots_dir.exists()
                assert storage.originals_dir.exists()
                assert storage.turns_dir.exists()

    def test_save_and_load_original_existing_file(self):
        """Test saving and loading original file state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save original
                test_path = "/path/to/test.py"
                original_content = "def hello(): pass"
                storage.save_original(test_path, original_content)

                # Load original
                existed, content = storage.load_original(test_path)

                assert existed is True
                assert content == original_content

    def test_save_and_load_original_nonexistent_file(self):
        """Test saving and loading state for file that didn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save original for non-existent file
                test_path = "/path/to/new.py"
                storage.save_original(test_path, None)

                # Load original
                existed, content = storage.load_original(test_path)

                assert existed is False
                assert content is None

    def test_save_and_load_turn(self):
        """Test saving and loading turn checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # First save an original for the file
                test_path = "/path/to/file.py"
                storage.save_original(test_path, "original content")

                # Create checkpoint with changes
                checkpoint = TurnCheckpoint(
                    turn_number=1,
                    message_index=5,
                    timestamp=datetime(2025, 1, 15, 10, 30, 0),
                    file_changes=[
                        FileChange(
                            path=test_path,
                            change_type=ChangeType.MODIFIED,
                            content_before="original content",
                            content_after="modified content",
                        )
                    ],
                    summary="Modified the file",
                )

                # Save turn
                storage.save_turn(checkpoint)

                # Load turn
                loaded = storage.load_turn(1)

                assert loaded is not None
                assert loaded.turn_number == 1
                assert loaded.message_index == 5
                assert loaded.summary == "Modified the file"
                assert len(loaded.file_changes) == 1
                assert loaded.file_changes[0].content_after == "modified content"

    def test_save_and_load_rewind_state(self):
        """Test saving and loading rewind state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save some originals first
                storage.save_original("/test1.py", "content1")
                storage.save_original("/test2.py", None)

                # Save a turn
                checkpoint = TurnCheckpoint(
                    turn_number=1,
                    message_index=3,
                    timestamp=datetime.now(),
                    file_changes=[],
                    summary="Test turn",
                )
                storage.save_turn(checkpoint)

                # Create and save state
                state = RewindState(
                    session_id="test_session",
                    working_directory="/test/dir",
                    git_branch="main",
                    git_head="abc123",
                    current_turn=1,
                    checkpoints=[checkpoint],
                    originals={"/test1.py": "content1", "/test2.py": None},
                )
                storage.save_rewind_state(state)

                # Load state
                loaded = storage.load_rewind_state()

                assert loaded is not None
                assert loaded.session_id == "test_session"
                assert loaded.working_directory == "/test/dir"
                assert loaded.git_branch == "main"
                assert loaded.current_turn == 1
                assert len(loaded.checkpoints) == 1

    def test_load_nonexistent_turn(self):
        """Test loading a turn that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                loaded = storage.load_turn(999)
                assert loaded is None

    def test_load_nonexistent_original(self):
        """Test loading an original that wasn't saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                existed, content = storage.load_original("/nonexistent/path.py")
                assert existed is False
                assert content is None

    def test_cleanup(self):
        """Test cleanup removes snapshots directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                # Save some data
                storage.save_original("/test.py", "content")

                assert storage.snapshots_dir.exists()

                # Cleanup
                storage.cleanup()

                assert not storage.snapshots_dir.exists()
                assert storage.session_dir.exists()  # Session dir should remain

    def test_cleanup_full(self):
        """Test full cleanup removes entire session directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                assert storage.session_dir.exists()

                # Full cleanup
                storage.cleanup_full()

                assert not storage.session_dir.exists()

    def test_get_storage_size(self):
        """Test getting storage size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")
                storage.ensure_dirs()

                # Initially empty
                size = storage.get_storage_size()
                assert size == 0

                # Add some data
                storage.save_original("/test.py", "x" * 100)

                # Should have some size now
                size = storage.get_storage_size()
                assert size > 0

    def test_list_originals(self):
        """Test listing saved originals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save some originals
                storage.save_original("/path/to/file1.py", "content1")
                storage.save_original("/path/to/file2.py", "content2")
                storage.save_original("/path/to/file3.py", None)

                # List originals
                paths = storage.list_originals()

                assert len(paths) == 3
                assert "/path/to/file1.py" in paths
                assert "/path/to/file2.py" in paths
                assert "/path/to/file3.py" in paths

    def test_list_turns(self):
        """Test listing saved turns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save some turns
                for i in [1, 3, 5]:
                    checkpoint = TurnCheckpoint(
                        turn_number=i,
                        message_index=i * 2,
                        timestamp=datetime.now(),
                    )
                    storage.save_turn(checkpoint)

                # List turns
                turns = storage.list_turns()

                assert turns == [1, 3, 5]

    def test_turn_with_deleted_file(self):
        """Test saving turn with a deleted file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save original first
                storage.save_original("/test.py", "original content")

                # Create checkpoint with deletion
                checkpoint = TurnCheckpoint(
                    turn_number=1,
                    message_index=2,
                    timestamp=datetime.now(),
                    file_changes=[
                        FileChange(
                            path="/test.py",
                            change_type=ChangeType.DELETED,
                            content_before="original content",
                            content_after=None,
                        )
                    ],
                )

                # Save turn
                storage.save_turn(checkpoint)

                # Load turn
                loaded = storage.load_turn(1)

                assert loaded is not None
                assert len(loaded.file_changes) == 1
                assert loaded.file_changes[0].change_type == ChangeType.DELETED
                assert loaded.file_changes[0].content_after is None


class TestMultipleTurns:
    """Tests for multiple turn scenarios."""

    def test_multiple_turns_same_file(self):
        """Test multiple modifications to the same file across turns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("loco.snapshots.get_sessions_dir") as mock_dir:
                mock_dir.return_value = Path(tmpdir)
                storage = SnapshotStorage("test_session")

                # Save original
                storage.save_original("/test.py", "original")

                # Turn 1
                checkpoint1 = TurnCheckpoint(
                    turn_number=1,
                    message_index=2,
                    timestamp=datetime.now(),
                    file_changes=[
                        FileChange(
                            path="/test.py",
                            change_type=ChangeType.MODIFIED,
                            content_before="original",
                            content_after="version1",
                        )
                    ],
                )
                storage.save_turn(checkpoint1)

                # Turn 2
                checkpoint2 = TurnCheckpoint(
                    turn_number=2,
                    message_index=4,
                    timestamp=datetime.now(),
                    file_changes=[
                        FileChange(
                            path="/test.py",
                            change_type=ChangeType.MODIFIED,
                            content_before="version1",
                            content_after="version2",
                        )
                    ],
                )
                storage.save_turn(checkpoint2)

                # Verify both turns load correctly
                loaded1 = storage.load_turn(1)
                loaded2 = storage.load_turn(2)

                assert loaded1.file_changes[0].content_after == "version1"
                assert loaded2.file_changes[0].content_after == "version2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
