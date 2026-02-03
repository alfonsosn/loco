"""Snapshot storage for REWIND feature.

This module handles file I/O for storing and retrieving file snapshots,
including original file states and per-turn changes.

Directory structure:
    ~/.config/loco/sessions/{session_id}/
    ├── session.json              # Existing: conversation, usage
    ├── rewind.json               # RewindState metadata
    └── snapshots/
        ├── originals/
        │   ├── {path_hash}.snapshot    # Original file content
        │   └── {path_hash}.meta        # {"path": "/abs/path", "existed": true}
        └── turns/
            └── turn-{NNN}/
                ├── {path_hash}.snapshot  # Content after this turn
                └── manifest.json         # List of FileChanges for this turn
"""

import json
import shutil
from pathlib import Path
from typing import Any

from loco.config import get_config_dir


def get_sessions_dir() -> Path:
    """Get the sessions directory path."""
    return get_config_dir() / "sessions"


def hash_path(path: str) -> str:
    """Generate a short hash for a file path (for storage filenames)."""
    import hashlib
    return hashlib.sha256(path.encode()).hexdigest()[:16]


class SnapshotStorage:
    """Handles file I/O for storing and retrieving file snapshots."""

    def __init__(self, session_id: str):
        """Initialize storage for a session.

        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id
        self.session_dir = get_sessions_dir() / session_id
        self.snapshots_dir = self.session_dir / "snapshots"
        self.originals_dir = self.snapshots_dir / "originals"
        self.turns_dir = self.snapshots_dir / "turns"

    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
        self.originals_dir.mkdir(exist_ok=True)
        self.turns_dir.mkdir(exist_ok=True)

    def save_original(self, path: str, content: str | None) -> None:
        """Save the original state of a file (first time it's touched).

        Args:
            path: Absolute path to the file
            content: File content (None if file didn't exist)
        """
        self.ensure_dirs()
        path_hash = hash_path(path)

        # Save metadata
        meta_file = self.originals_dir / f"{path_hash}.meta"
        meta_data = {
            "path": path,
            "existed": content is not None,
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        # Save content if file existed
        if content is not None:
            snapshot_file = self.originals_dir / f"{path_hash}.snapshot"
            with open(snapshot_file, "w", encoding="utf-8") as f:
                f.write(content)

    def load_original(self, path: str) -> tuple[bool, str | None]:
        """Load the original state of a file.

        Args:
            path: Absolute path to the file

        Returns:
            Tuple of (file_existed, content)
            - If file_existed is False, content is None
            - If file_existed is True, content is the original content
        """
        path_hash = hash_path(path)

        # Load metadata
        meta_file = self.originals_dir / f"{path_hash}.meta"
        if not meta_file.exists():
            return False, None

        try:
            with open(meta_file, encoding="utf-8") as f:
                meta_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False, None

        existed = meta_data.get("existed", False)
        if not existed:
            return False, None

        # Load content
        snapshot_file = self.originals_dir / f"{path_hash}.snapshot"
        if not snapshot_file.exists():
            return True, None

        try:
            with open(snapshot_file, encoding="utf-8") as f:
                return True, f.read()
        except (OSError, UnicodeDecodeError):
            return True, None

    def save_turn(self, checkpoint: "TurnCheckpoint") -> None:
        """Save a turn checkpoint with all its file changes.

        Args:
            checkpoint: TurnCheckpoint to save
        """
        from loco.rewind import TurnCheckpoint

        self.ensure_dirs()
        turn_dir = self.turns_dir / f"turn-{checkpoint.turn_number:03d}"
        turn_dir.mkdir(exist_ok=True)

        # Save manifest with change metadata
        manifest_data = {
            "turn_number": checkpoint.turn_number,
            "message_index": checkpoint.message_index,
            "timestamp": checkpoint.timestamp.isoformat(),
            "summary": checkpoint.summary,
            "changes": [],
        }

        # Save each file's after-state
        for change in checkpoint.file_changes:
            path_hash = hash_path(change.path)

            change_entry = {
                "path": change.path,
                "path_hash": path_hash,
                "change_type": change.change_type.value,
            }
            manifest_data["changes"].append(change_entry)

            # Save content_after if not None (deleted files have None)
            if change.content_after is not None:
                snapshot_file = turn_dir / f"{path_hash}.snapshot"
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    f.write(change.content_after)

        # Save manifest
        manifest_file = turn_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

    def load_turn(self, turn_number: int) -> "TurnCheckpoint | None":
        """Load a turn checkpoint.

        Args:
            turn_number: Turn number to load

        Returns:
            TurnCheckpoint if found, None otherwise
        """
        from loco.rewind import TurnCheckpoint, FileChange, ChangeType
        from datetime import datetime

        turn_dir = self.turns_dir / f"turn-{turn_number:03d}"
        manifest_file = turn_dir / "manifest.json"

        if not manifest_file.exists():
            return None

        try:
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        # Reconstruct file changes
        file_changes = []
        for change_entry in manifest_data.get("changes", []):
            path = change_entry["path"]
            path_hash = change_entry["path_hash"]
            change_type = ChangeType(change_entry["change_type"])

            # Load content_after from snapshot file
            snapshot_file = turn_dir / f"{path_hash}.snapshot"
            content_after = None
            if snapshot_file.exists():
                try:
                    with open(snapshot_file, encoding="utf-8") as f:
                        content_after = f.read()
                except (OSError, UnicodeDecodeError):
                    pass

            # Load content_before from original or previous turn
            existed, content_before = self.load_original(path)
            if not existed:
                content_before = None

            file_changes.append(FileChange(
                path=path,
                change_type=change_type,
                content_before=content_before,
                content_after=content_after,
            ))

        return TurnCheckpoint(
            turn_number=manifest_data["turn_number"],
            message_index=manifest_data["message_index"],
            timestamp=datetime.fromisoformat(manifest_data["timestamp"]),
            file_changes=file_changes,
            summary=manifest_data.get("summary"),
        )

    def save_rewind_state(self, state: "RewindState") -> None:
        """Save the rewind state to disk.

        Args:
            state: RewindState to save
        """
        self.ensure_dirs()
        rewind_file = self.session_dir / "rewind.json"

        # Convert state to dict (without full file contents in checkpoints)
        state_data = {
            "session_id": state.session_id,
            "working_directory": state.working_directory,
            "git_branch": state.git_branch,
            "git_head": state.git_head,
            "current_turn": state.current_turn,
            "originals": state.originals,
            "checkpoint_turns": [cp.turn_number for cp in state.checkpoints],
        }

        with open(rewind_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)

    def load_rewind_state(self) -> "RewindState | None":
        """Load the rewind state from disk.

        Returns:
            RewindState if found, None otherwise
        """
        from loco.rewind import RewindState

        rewind_file = self.session_dir / "rewind.json"

        if not rewind_file.exists():
            return None

        try:
            with open(rewind_file, encoding="utf-8") as f:
                state_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        # Load checkpoints from turn files
        checkpoints = []
        for turn_number in state_data.get("checkpoint_turns", []):
            checkpoint = self.load_turn(turn_number)
            if checkpoint:
                checkpoints.append(checkpoint)

        return RewindState(
            session_id=state_data["session_id"],
            working_directory=state_data["working_directory"],
            git_branch=state_data.get("git_branch"),
            git_head=state_data.get("git_head"),
            current_turn=state_data.get("current_turn", 0),
            checkpoints=checkpoints,
            originals=state_data.get("originals", {}),
        )

    def cleanup(self) -> None:
        """Remove all stored snapshots for this session."""
        if self.snapshots_dir.exists():
            shutil.rmtree(self.snapshots_dir)

    def cleanup_full(self) -> None:
        """Remove the entire session directory including snapshots and rewind state."""
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)

    def get_storage_size(self) -> int:
        """Get the total size of stored snapshots in bytes.

        Returns:
            Total size in bytes
        """
        total = 0
        if self.snapshots_dir.exists():
            for path in self.snapshots_dir.rglob("*"):
                if path.is_file():
                    total += path.stat().st_size
        return total

    def list_originals(self) -> list[str]:
        """List all original file paths that have been captured.

        Returns:
            List of absolute file paths
        """
        paths = []
        if not self.originals_dir.exists():
            return paths

        for meta_file in self.originals_dir.glob("*.meta"):
            try:
                with open(meta_file, encoding="utf-8") as f:
                    meta_data = json.load(f)
                    paths.append(meta_data["path"])
            except (OSError, json.JSONDecodeError, KeyError):
                continue

        return paths

    def list_turns(self) -> list[int]:
        """List all turn numbers that have been saved.

        Returns:
            List of turn numbers in ascending order
        """
        turns = []
        if not self.turns_dir.exists():
            return turns

        for turn_dir in self.turns_dir.iterdir():
            if turn_dir.is_dir() and turn_dir.name.startswith("turn-"):
                try:
                    turn_num = int(turn_dir.name[5:])
                    turns.append(turn_num)
                except ValueError:
                    continue

        return sorted(turns)
