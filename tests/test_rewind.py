"""Tests for the REWIND feature core functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from loco.rewind import (
    ChangeType,
    FileChange,
    TurnCheckpoint,
    RewindState,
    RewindManager,
    Conflict,
    hash_path,
    read_file_safe,
    get_rewind_manager,
    set_rewind_manager,
)


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_change_type_values(self):
        """Test ChangeType enum values."""
        assert ChangeType.CREATED.value == "created"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.DELETED.value == "deleted"


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_file_change_creation(self):
        """Test creating a FileChange object."""
        change = FileChange(
            path="/path/to/file.py",
            change_type=ChangeType.CREATED,
            content_before=None,
            content_after="new content",
        )
        assert change.path == "/path/to/file.py"
        assert change.change_type == ChangeType.CREATED
        assert change.content_before is None
        assert change.content_after == "new content"

    def test_file_change_to_dict(self):
        """Test FileChange serialization."""
        change = FileChange(
            path="/path/to/file.py",
            change_type=ChangeType.MODIFIED,
            content_before="old",
            content_after="new",
        )
        data = change.to_dict()
        assert data["path"] == "/path/to/file.py"
        assert data["change_type"] == "modified"
        assert data["content_before"] == "old"
        assert data["content_after"] == "new"

    def test_file_change_from_dict(self):
        """Test FileChange deserialization."""
        data = {
            "path": "/path/to/file.py",
            "change_type": "deleted",
            "content_before": "was here",
            "content_after": None,
        }
        change = FileChange.from_dict(data)
        assert change.path == "/path/to/file.py"
        assert change.change_type == ChangeType.DELETED
        assert change.content_before == "was here"
        assert change.content_after is None


class TestTurnCheckpoint:
    """Tests for TurnCheckpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test creating a TurnCheckpoint object."""
        now = datetime.now()
        checkpoint = TurnCheckpoint(
            turn_number=1,
            message_index=5,
            timestamp=now,
            file_changes=[],
            summary="Made some changes",
        )
        assert checkpoint.turn_number == 1
        assert checkpoint.message_index == 5
        assert checkpoint.timestamp == now
        assert checkpoint.file_changes == []
        assert checkpoint.summary == "Made some changes"

    def test_checkpoint_to_dict(self):
        """Test TurnCheckpoint serialization."""
        change = FileChange(
            path="/test.py",
            change_type=ChangeType.CREATED,
            content_before=None,
            content_after="content",
        )
        checkpoint = TurnCheckpoint(
            turn_number=1,
            message_index=3,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            file_changes=[change],
            summary="Test",
        )
        data = checkpoint.to_dict()
        assert data["turn_number"] == 1
        assert data["message_index"] == 3
        assert "2025-01-01" in data["timestamp"]
        assert len(data["file_changes"]) == 1
        assert data["summary"] == "Test"

    def test_checkpoint_from_dict(self):
        """Test TurnCheckpoint deserialization."""
        data = {
            "turn_number": 2,
            "message_index": 10,
            "timestamp": "2025-01-15T10:30:00",
            "file_changes": [
                {
                    "path": "/test.py",
                    "change_type": "modified",
                    "content_before": "old",
                    "content_after": "new",
                }
            ],
            "summary": "Refactored code",
        }
        checkpoint = TurnCheckpoint.from_dict(data)
        assert checkpoint.turn_number == 2
        assert checkpoint.message_index == 10
        assert checkpoint.timestamp.year == 2025
        assert len(checkpoint.file_changes) == 1
        assert checkpoint.file_changes[0].change_type == ChangeType.MODIFIED


class TestRewindState:
    """Tests for RewindState dataclass."""

    def test_state_creation(self):
        """Test creating a RewindState object."""
        state = RewindState(
            session_id="20250101_120000",
            working_directory="/home/user/project",
            git_branch="main",
            git_head="abc123",
        )
        assert state.session_id == "20250101_120000"
        assert state.working_directory == "/home/user/project"
        assert state.git_branch == "main"
        assert state.git_head == "abc123"
        assert state.current_turn == 0
        assert state.checkpoints == []
        assert state.originals == {}

    def test_state_to_dict(self):
        """Test RewindState serialization."""
        state = RewindState(
            session_id="test123",
            working_directory="/test",
            git_branch="feature",
            current_turn=3,
            originals={"/test.py": "original content"},
        )
        data = state.to_dict()
        assert data["session_id"] == "test123"
        assert data["working_directory"] == "/test"
        assert data["git_branch"] == "feature"
        assert data["current_turn"] == 3
        assert "/test.py" in data["originals"]

    def test_state_from_dict(self):
        """Test RewindState deserialization."""
        data = {
            "session_id": "test456",
            "working_directory": "/project",
            "git_branch": None,
            "git_head": None,
            "current_turn": 5,
            "checkpoints": [],
            "originals": {},
        }
        state = RewindState.from_dict(data)
        assert state.session_id == "test456"
        assert state.working_directory == "/project"
        assert state.git_branch is None
        assert state.current_turn == 5


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_hash_path(self):
        """Test path hashing produces consistent results."""
        path1 = "/home/user/file.py"
        path2 = "/home/user/other.py"

        hash1a = hash_path(path1)
        hash1b = hash_path(path1)
        hash2 = hash_path(path2)

        assert hash1a == hash1b  # Same path produces same hash
        assert hash1a != hash2  # Different paths produce different hashes
        assert len(hash1a) == 16  # Hash is 16 characters

    def test_read_file_safe_nonexistent(self):
        """Test reading non-existent file returns None."""
        result = read_file_safe("/nonexistent/path/file.txt")
        assert result is None

    def test_read_file_safe_exists(self):
        """Test reading existing file returns content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = read_file_safe(temp_path)
            assert result == "test content"
        finally:
            Path(temp_path).unlink()

    def test_read_file_safe_size_limit(self):
        """Test reading file over size limit returns None."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x" * 1000)  # 1KB of content
            temp_path = f.name

        try:
            # Should return None if max_size is smaller than file
            result = read_file_safe(temp_path, max_size=100)
            assert result is None

            # Should return content if max_size is larger
            result = read_file_safe(temp_path, max_size=2000)
            assert result == "x" * 1000
        finally:
            Path(temp_path).unlink()


class TestRewindManager:
    """Tests for RewindManager class."""

    def test_initialize(self):
        """Test RewindManager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )
            assert manager.state.session_id == "test_session"
            assert manager.state.working_directory == tmpdir
            assert manager.state.current_turn == 0

    def test_begin_and_end_turn(self):
        """Test turn tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )

            # Begin turn
            manager.begin_turn()

            # End turn
            checkpoint = manager.end_turn(message_index=5, summary="Did something")

            assert checkpoint.turn_number == 1
            assert checkpoint.message_index == 5
            assert checkpoint.summary == "Did something"
            assert manager.state.current_turn == 1

    def test_capture_file_changes(self):
        """Test capturing file changes during a turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file (resolve to handle macOS /var -> /private/var symlink)
            test_file = (Path(tmpdir) / "test.py").resolve()
            test_file.write_text("original content")

            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=str(Path(tmpdir).resolve()),
            )

            # Begin turn and capture changes
            manager.begin_turn()
            manager.capture_before(str(test_file))

            # Modify file
            test_file.write_text("modified content")
            manager.capture_after(str(test_file), "modified content", ChangeType.MODIFIED)

            # End turn
            checkpoint = manager.end_turn(message_index=3, summary="Modified file")

            # Verify changes were captured
            assert len(checkpoint.file_changes) == 1
            change = checkpoint.file_changes[0]
            assert change.path == str(test_file)
            assert change.change_type == ChangeType.MODIFIED
            assert change.content_before == "original content"
            assert change.content_after == "modified content"

    def test_capture_file_creation(self):
        """Test capturing file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "new.py"

            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )

            manager.begin_turn()
            manager.capture_before(str(test_file))  # File doesn't exist

            # Create file
            test_file.write_text("new content")
            manager.capture_after(str(test_file), "new content", ChangeType.CREATED)

            checkpoint = manager.end_turn(message_index=2)

            assert len(checkpoint.file_changes) == 1
            change = checkpoint.file_changes[0]
            assert change.change_type == ChangeType.CREATED
            assert change.content_before is None
            assert change.content_after == "new content"

    def test_rewind_to_turn(self):
        """Test rewinding to a previous turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("original")

            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )

            # Turn 1: Modify file
            manager.begin_turn()
            manager.capture_before(str(test_file))
            test_file.write_text("turn1")
            manager.capture_after(str(test_file), "turn1", ChangeType.MODIFIED)
            manager.end_turn(message_index=2)

            # Turn 2: Modify again
            manager.begin_turn()
            manager.capture_before(str(test_file))
            test_file.write_text("turn2")
            manager.capture_after(str(test_file), "turn2", ChangeType.MODIFIED)
            manager.end_turn(message_index=4)

            # Verify current state
            assert test_file.read_text() == "turn2"
            assert manager.state.current_turn == 2

            # Rewind to turn 1
            success, restored, conflicts = manager.rewind_to_turn(1)

            assert success
            assert len(conflicts) == 0
            assert test_file.read_text() == "turn1"
            assert manager.state.current_turn == 1

    def test_rewind_to_turn_zero(self):
        """Test rewinding to turn 0 (before any changes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "new.py"

            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )

            # Turn 1: Create file
            manager.begin_turn()
            manager.capture_before(str(test_file))
            test_file.write_text("created")
            manager.capture_after(str(test_file), "created", ChangeType.CREATED)
            manager.end_turn(message_index=2)

            assert test_file.exists()

            # Rewind to turn 0 (before creation)
            success, restored, conflicts = manager.rewind_to_turn(0)

            assert success
            assert not test_file.exists()  # File should be deleted
            assert manager.state.current_turn == 0

    def test_conflict_detection(self):
        """Test detection of external file modifications."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Resolve to handle macOS /var -> /private/var symlink
            test_file = (Path(tmpdir) / "test.py").resolve()
            test_file.write_text("original")

            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=str(Path(tmpdir).resolve()),
            )

            # Turn 1: Modify through manager
            manager.begin_turn()
            manager.capture_before(str(test_file))
            test_file.write_text("turn1")
            manager.capture_after(str(test_file), "turn1", ChangeType.MODIFIED)
            manager.end_turn(message_index=2)

            # External modification (simulating user edit)
            test_file.write_text("external change")

            # Validate before rewind
            conflicts = manager.validate_before_rewind(0)

            assert len(conflicts) == 1
            assert conflicts[0].path == str(test_file)
            assert conflicts[0].expected_content == "turn1"
            assert conflicts[0].actual_content == "external change"

    def test_get_message_index_for_turn(self):
        """Test getting message index for a specific turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RewindManager.initialize(
                session_id="test_session",
                working_directory=tmpdir,
            )

            manager.begin_turn()
            manager.end_turn(message_index=3)

            manager.begin_turn()
            manager.end_turn(message_index=7)

            assert manager.get_message_index_for_turn(1) == 3
            assert manager.get_message_index_for_turn(2) == 7
            assert manager.get_message_index_for_turn(3) is None


class TestGlobalRewindManager:
    """Tests for global rewind manager functions."""

    def test_get_set_rewind_manager(self):
        """Test getting and setting the global rewind manager."""
        # Initially should be None (or whatever was set before)
        original = get_rewind_manager()

        # Set a new manager
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = RewindManager.initialize(
                session_id="test",
                working_directory=tmpdir,
            )
            set_rewind_manager(manager)

            assert get_rewind_manager() is manager

        # Clean up - restore original
        set_rewind_manager(original)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
