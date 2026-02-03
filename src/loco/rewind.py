"""REWIND feature - Roll back sessions to previous conversation turns.

This module provides the core data structures and RewindManager class for
tracking file changes across conversation turns and enabling rollback.
"""

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loco.git import is_git_repo, get_current_branch, run_git_command


class ChangeType(Enum):
    """Type of file change."""
    CREATED = "created"      # File didn't exist, now does
    MODIFIED = "modified"    # File existed, content changed
    DELETED = "deleted"      # File existed, now doesn't


@dataclass
class FileChange:
    """A single file modification within a turn."""
    path: str                        # Absolute path to file
    change_type: ChangeType
    content_before: str | None       # None if file was created
    content_after: str | None        # None if file was deleted

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "content_before": self.content_before,
            "content_after": self.content_after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileChange":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            change_type=ChangeType(data["change_type"]),
            content_before=data.get("content_before"),
            content_after=data.get("content_after"),
        )


@dataclass
class TurnCheckpoint:
    """Snapshot of state at end of a conversation turn."""
    turn_number: int
    message_index: int               # Index in conversation.messages where turn ends
    timestamp: datetime
    file_changes: list[FileChange] = field(default_factory=list)
    summary: str | None = None       # Auto-generated from assistant response

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "turn_number": self.turn_number,
            "message_index": self.message_index,
            "timestamp": self.timestamp.isoformat(),
            "file_changes": [fc.to_dict() for fc in self.file_changes],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TurnCheckpoint":
        """Create from dictionary."""
        return cls(
            turn_number=data["turn_number"],
            message_index=data["message_index"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            file_changes=[FileChange.from_dict(fc) for fc in data.get("file_changes", [])],
            summary=data.get("summary"),
        )


@dataclass
class RewindState:
    """Session-level rewind tracking."""
    session_id: str
    working_directory: str
    git_branch: str | None = None           # Branch at session start (if git repo)
    git_head: str | None = None             # Commit hash at session start
    current_turn: int = 0
    checkpoints: list[TurnCheckpoint] = field(default_factory=list)
    # Track original file states (first time loco touches each file)
    originals: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "working_directory": self.working_directory,
            "git_branch": self.git_branch,
            "git_head": self.git_head,
            "current_turn": self.current_turn,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "originals": self.originals,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RewindState":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            working_directory=data["working_directory"],
            git_branch=data.get("git_branch"),
            git_head=data.get("git_head"),
            current_turn=data.get("current_turn", 0),
            checkpoints=[TurnCheckpoint.from_dict(cp) for cp in data.get("checkpoints", [])],
            originals=data.get("originals", {}),
        )


@dataclass
class Conflict:
    """Represents a conflict when a file was modified outside loco."""
    path: str
    expected_content: str | None   # What loco thinks the file should be
    actual_content: str | None     # What the file actually contains


def hash_path(path: str) -> str:
    """Generate a short hash for a file path (for storage filenames)."""
    return hashlib.sha256(path.encode()).hexdigest()[:16]


def read_file_safe(path: str, max_size: int = 10 * 1024 * 1024) -> str | None:
    """Safely read a file, returning None if it doesn't exist or is too large.

    Args:
        path: Path to the file
        max_size: Maximum file size to read (default 10MB)

    Returns:
        File content as string, or None if file doesn't exist or exceeds size limit
    """
    try:
        p = Path(path)
        if not p.exists():
            return None
        if p.stat().st_size > max_size:
            return None  # Skip files that are too large
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def get_git_context() -> dict[str, str | None]:
    """Get git context for the current directory.

    Returns:
        Dict with 'branch' and 'head' keys (values may be None if not a git repo)
    """
    if not is_git_repo():
        return {"branch": None, "head": None}

    branch = get_current_branch()

    # Get HEAD commit hash
    success, stdout, _ = run_git_command(["rev-parse", "HEAD"], check=False)
    head = stdout.strip() if success else None

    return {"branch": branch, "head": head}


class RewindManager:
    """Manages rewind state for a loco session.

    This class handles:
    - Tracking file changes during each conversation turn
    - Storing snapshots of file states
    - Rewinding to previous turns by restoring file states
    - Persisting rewind state to disk
    """

    def __init__(self, state: RewindState, storage: "SnapshotStorage"):
        """Initialize with existing state and storage.

        Use RewindManager.initialize() to create a new manager.
        """
        self.state = state
        self.storage = storage
        self._current_turn_changes: dict[str, FileChange] = {}
        self._turn_in_progress = False

    @classmethod
    def initialize(
        cls,
        session_id: str,
        working_directory: str | None = None,
        git_context: dict[str, str | None] | None = None,
    ) -> "RewindManager":
        """Initialize a new RewindManager for a session.

        Args:
            session_id: Unique session identifier
            working_directory: Working directory (defaults to cwd)
            git_context: Git branch/head info (auto-detected if None)

        Returns:
            Initialized RewindManager
        """
        from loco.snapshots import SnapshotStorage

        if working_directory is None:
            working_directory = os.getcwd()

        if git_context is None:
            git_context = get_git_context()

        state = RewindState(
            session_id=session_id,
            working_directory=working_directory,
            git_branch=git_context.get("branch"),
            git_head=git_context.get("head"),
        )

        storage = SnapshotStorage(session_id)

        return cls(state, storage)

    @classmethod
    def load(cls, session_id: str) -> "RewindManager | None":
        """Load an existing RewindManager from disk.

        Args:
            session_id: Session ID to load

        Returns:
            RewindManager if found, None otherwise
        """
        from loco.snapshots import SnapshotStorage

        storage = SnapshotStorage(session_id)
        state = storage.load_rewind_state()

        if state is None:
            return None

        return cls(state, storage)

    def begin_turn(self) -> None:
        """Mark the beginning of a new conversation turn.

        Call this at the start of chat_turn() before any tools execute.
        """
        self._turn_in_progress = True
        self._current_turn_changes = {}

    def capture_before(self, path: str, max_size: int = 10 * 1024 * 1024) -> None:
        """Capture file state before a write/edit operation.

        Call this before any file modification.

        Args:
            path: Absolute path to the file
            max_size: Maximum file size to capture (default 10MB)
        """
        if not self._turn_in_progress:
            return

        # Normalize path
        path = str(Path(path).resolve())

        # Only capture if we haven't already captured this file this turn
        if path in self._current_turn_changes:
            return

        # Read current content (or None if file doesn't exist)
        content = read_file_safe(path, max_size)

        # Track original if this is the first time we're touching this file
        if path not in self.state.originals:
            self.state.originals[path] = content
            self.storage.save_original(path, content)

        # Initialize the change entry (will be completed in capture_after)
        self._current_turn_changes[path] = FileChange(
            path=path,
            change_type=ChangeType.CREATED if content is None else ChangeType.MODIFIED,
            content_before=content,
            content_after=None,  # Will be set in capture_after
        )

    def capture_after(
        self,
        path: str,
        content: str | None,
        change_type: ChangeType | None = None,
    ) -> None:
        """Capture file state after a write/edit operation.

        Call this after any file modification.

        Args:
            path: Absolute path to the file
            content: New file content (None if deleted)
            change_type: Type of change (auto-detected if None)
        """
        if not self._turn_in_progress:
            return

        # Normalize path
        path = str(Path(path).resolve())

        # Get or create the change entry
        if path not in self._current_turn_changes:
            # capture_before wasn't called, try to reconstruct
            self._current_turn_changes[path] = FileChange(
                path=path,
                change_type=ChangeType.MODIFIED,
                content_before=self.state.originals.get(path),
                content_after=None,
            )

        change = self._current_turn_changes[path]
        change.content_after = content

        # Auto-detect change type if not specified
        if change_type is not None:
            change.change_type = change_type
        elif content is None:
            change.change_type = ChangeType.DELETED
        elif change.content_before is None:
            change.change_type = ChangeType.CREATED
        else:
            change.change_type = ChangeType.MODIFIED

    def end_turn(self, message_index: int, summary: str | None = None) -> TurnCheckpoint:
        """Mark the end of a conversation turn.

        Call this after the assistant response is complete.

        Args:
            message_index: Index in conversation.messages where turn ends
            summary: Optional summary of what was done in this turn

        Returns:
            The created TurnCheckpoint
        """
        self.state.current_turn += 1

        # Create checkpoint with all changes from this turn
        checkpoint = TurnCheckpoint(
            turn_number=self.state.current_turn,
            message_index=message_index,
            timestamp=datetime.now(),
            file_changes=list(self._current_turn_changes.values()),
            summary=summary,
        )

        self.state.checkpoints.append(checkpoint)

        # Save turn snapshot
        self.storage.save_turn(checkpoint)

        # Reset turn state
        self._turn_in_progress = False
        self._current_turn_changes = {}

        return checkpoint

    def get_turn_summary(self, turn_number: int) -> str | None:
        """Get the summary for a specific turn.

        Args:
            turn_number: Turn number (1-indexed)

        Returns:
            Summary string or None
        """
        for checkpoint in self.state.checkpoints:
            if checkpoint.turn_number == turn_number:
                return checkpoint.summary
        return None

    def get_files_modified_after_turn(self, turn_number: int) -> list[FileChange]:
        """Get all file changes made after a specific turn.

        Args:
            turn_number: Turn number to get changes after

        Returns:
            List of FileChange objects for all changes after the turn
        """
        changes = []
        for checkpoint in self.state.checkpoints:
            if checkpoint.turn_number > turn_number:
                changes.extend(checkpoint.file_changes)
        return changes

    def validate_before_rewind(self, target_turn: int) -> list[Conflict]:
        """Check for conflicts before rewinding.

        This detects if files were modified outside of loco since the last
        known state.

        Args:
            target_turn: Turn number to rewind to

        Returns:
            List of Conflict objects for any detected conflicts
        """
        conflicts = []

        # Get all changes after target turn
        changes_to_revert = self.get_files_modified_after_turn(target_turn)

        # Check each file for unexpected changes
        for change in changes_to_revert:
            current = read_file_safe(change.path)
            expected = change.content_after

            if current != expected:
                conflicts.append(Conflict(
                    path=change.path,
                    expected_content=expected,
                    actual_content=current,
                ))

        return conflicts

    def rewind_to_turn(
        self,
        turn_number: int,
        force: bool = False,
    ) -> tuple[bool, list[str], list[Conflict]]:
        """Rewind to a specific turn, restoring all files to their state at that turn.

        Args:
            turn_number: Turn number to rewind to (0 means before any changes)
            force: If True, overwrite even if conflicts detected

        Returns:
            Tuple of (success, list of restored files, list of conflicts)
        """
        if turn_number < 0 or turn_number > self.state.current_turn:
            return False, [], []

        # Check for conflicts
        conflicts = self.validate_before_rewind(turn_number)
        if conflicts and not force:
            return False, [], conflicts

        restored_files: list[str] = []

        # Get all changes to revert (in reverse order - newest first)
        changes_to_revert = self.get_files_modified_after_turn(turn_number)

        # Build a map of what each file should be restored to
        # We need to restore each file to its state at the END of target_turn
        # or its original state if not modified by target_turn
        file_restore_map: dict[str, str | None] = {}

        for change in changes_to_revert:
            if change.path not in file_restore_map:
                # First time seeing this file - restore to state before first change
                file_restore_map[change.path] = change.content_before

        # Now apply the restorations
        for path, content in file_restore_map.items():
            try:
                p = Path(path)

                if content is None:
                    # File should not exist
                    if p.exists():
                        p.unlink()
                        restored_files.append(f"Deleted: {path}")
                else:
                    # File should exist with this content
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(content, encoding="utf-8")
                    restored_files.append(f"Restored: {path}")
            except OSError as e:
                # Log error but continue
                restored_files.append(f"Error restoring {path}: {e}")

        # Update state
        self.state.checkpoints = [
            cp for cp in self.state.checkpoints
            if cp.turn_number <= turn_number
        ]
        self.state.current_turn = turn_number

        # Persist updated state
        self.persist()

        return True, restored_files, conflicts

    def rewind_conversation_only(self, turn_number: int) -> bool:
        """Rewind state without restoring files.

        This only updates the rewind state to the target turn, keeping
        all file changes as they are. Useful when the user wants to
        restart the conversation from an earlier point but keep the
        current file state.

        Args:
            turn_number: Turn number to rewind to (0 means before any changes)

        Returns:
            True if successful, False otherwise
        """
        if turn_number < 0 or turn_number > self.state.current_turn:
            return False

        # Update state without touching files
        self.state.checkpoints = [
            cp for cp in self.state.checkpoints
            if cp.turn_number <= turn_number
        ]
        self.state.current_turn = turn_number

        # Persist updated state
        self.persist()

        return True

    def get_message_index_for_turn(self, turn_number: int) -> int | None:
        """Get the message index that corresponds to the end of a turn.

        Args:
            turn_number: Turn number to look up

        Returns:
            Message index or None if turn not found
        """
        for checkpoint in self.state.checkpoints:
            if checkpoint.turn_number == turn_number:
                return checkpoint.message_index
        return None

    def persist(self) -> None:
        """Save the current rewind state to disk."""
        self.storage.save_rewind_state(self.state)

    def cleanup(self) -> None:
        """Remove all stored snapshots for this session."""
        self.storage.cleanup()


# Global rewind manager instance (set during session initialization)
_rewind_manager: RewindManager | None = None


def get_rewind_manager() -> RewindManager | None:
    """Get the global rewind manager instance."""
    return _rewind_manager


def set_rewind_manager(manager: RewindManager | None) -> None:
    """Set the global rewind manager instance."""
    global _rewind_manager
    _rewind_manager = manager
