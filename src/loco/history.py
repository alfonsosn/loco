"""Conversation history persistence for loco."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loco.chat import Conversation, Message
from loco.config import get_config_dir
from loco.rewind import get_rewind_manager


def get_history_dir() -> Path:
    """Get the history directory path."""
    return get_config_dir() / "history"


def ensure_history_dir() -> Path:
    """Ensure history directory exists and return its path."""
    history_dir = get_history_dir()
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def generate_session_id() -> str:
    """Generate a unique session ID based on timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_conversation(
    conversation: Conversation,
    session_id: str | None = None,
    name: str | None = None,
) -> str:
    """Save a conversation to disk.

    Args:
        conversation: The conversation to save
        session_id: Optional session ID (generated if not provided)
        name: Optional human-readable name for the session

    Returns:
        The session ID of the saved conversation
    """
    history_dir = ensure_history_dir()

    if session_id is None:
        session_id = generate_session_id()

    # Build session data
    session_data = {
        "session_id": session_id,
        "name": name,
        "model": conversation.model,
        "created_at": datetime.now().isoformat(),
        "messages": [msg.to_dict() for msg in conversation.messages],
    }

    # Add usage data if available
    if conversation.usage:
        session_data["usage"] = conversation.usage.to_dict()

    # Save to file
    session_file = history_dir / f"{session_id}.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)

    # Also persist rewind state if available
    rewind_manager = get_rewind_manager()
    if rewind_manager:
        rewind_manager.persist()

    return session_id


def load_conversation(session_id: str) -> Conversation | None:
    """Load a conversation from disk.

    Args:
        session_id: The session ID to load

    Returns:
        The loaded conversation, or None if not found
    """
    history_dir = get_history_dir()
    session_file = history_dir / f"{session_id}.json"

    if not session_file.exists():
        return None

    try:
        with open(session_file) as f:
            data = json.load(f)

        conversation = Conversation(model=data.get("model", ""))

        for msg_data in data.get("messages", []):
            msg = Message(
                role=msg_data["role"],
                content=msg_data.get("content"),
                tool_calls=msg_data.get("tool_calls"),
                tool_call_id=msg_data.get("tool_call_id"),
                name=msg_data.get("name"),
            )
            conversation.messages.append(msg)
        
        # Load usage data if available
        if "usage" in data:
            from loco.usage import SessionUsage
            conversation.usage = SessionUsage.from_dict(data["usage"])

        return conversation

    except Exception:
        return None


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """List recent saved sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session metadata dicts
    """
    history_dir = get_history_dir()

    if not history_dir.exists():
        return []

    sessions = []

    for session_file in sorted(history_dir.glob("*.json"), reverse=True):
        if len(sessions) >= limit:
            break

        try:
            with open(session_file) as f:
                data = json.load(f)

            sessions.append({
                "session_id": data.get("session_id", session_file.stem),
                "name": data.get("name"),
                "model": data.get("model"),
                "created_at": data.get("created_at"),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue

    return sessions


def delete_session(session_id: str) -> bool:
    """Delete a saved session.

    Args:
        session_id: The session ID to delete

    Returns:
        True if deleted, False if not found
    """
    history_dir = get_history_dir()
    session_file = history_dir / f"{session_id}.json"

    deleted = False
    if session_file.exists():
        session_file.unlink()
        deleted = True

    # Also clean up rewind state if it exists
    from loco.snapshots import SnapshotStorage
    storage = SnapshotStorage(session_id)
    if storage.session_dir.exists():
        storage.cleanup_full()
        deleted = True

    return deleted
