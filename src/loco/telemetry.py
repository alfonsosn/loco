"""Cost profiling and telemetry for LOCO."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json
from pathlib import Path


class OperationType(Enum):
    """Categories of LLM operations for cost attribution."""
    # Core operations
    SEARCH_GREP = "search:grep"
    SEARCH_GLOB = "search:glob"
    READ_FILE = "read:file"
    READ_CONTEXT = "read:context"
    GENERATION_CODE = "generation:code"
    GENERATION_EDIT = "generation:edit"
    EXPLANATION = "explanation"
    PLANNING = "planning"

    # Agent operations
    AGENT_RESEARCH = "agent:research"
    AGENT_EXPLORATION = "agent:exploration"
    AGENT_RAILS = "agent:rails"
    AGENT_OVERHEAD = "agent:overhead"

    # System operations
    SYSTEM_ROUTING = "system:routing"
    SYSTEM_SYNTHESIS = "system:synthesis"
    SYSTEM_ERROR_RECOVERY = "system:error_recovery"

    # Default
    UNKNOWN = "unknown"


@dataclass
class TrackedCall:
    """A single tracked LLM call with full metadata."""
    timestamp: datetime
    model: str
    operation_type: OperationType
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost: float
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "operation_type": self.operation_type.value,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost": self.cost,
            "agent_name": self.agent_name,
            "tool_name": self.tool_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrackedCall":
        """Deserialize from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            model=data["model"],
            operation_type=OperationType(data["operation_type"]),
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cache_read_tokens=data.get("cache_read_tokens", 0),
            cache_write_tokens=data.get("cache_write_tokens", 0),
            cost=data["cost"],
            agent_name=data.get("agent_name"),
            tool_name=data.get("tool_name"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CostProfile:
    """Aggregated cost profile for a session."""
    session_id: str
    start_time: datetime
    calls: list[TrackedCall] = field(default_factory=list)
    files_read: dict[str, int] = field(default_factory=dict)  # path -> read count

    def add_call(self, call: TrackedCall) -> None:
        """Add a tracked call to the profile."""
        self.calls.append(call)

    def record_file_read(self, path: str) -> None:
        """Record a file read for duplicate detection."""
        self.files_read[path] = self.files_read.get(path, 0) + 1

    @property
    def total_cost(self) -> float:
        """Total cost of all calls."""
        return sum(c.cost for c in self.calls)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens."""
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens."""
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_cache_read(self) -> int:
        """Total cache read tokens."""
        return sum(c.cache_read_tokens for c in self.calls)

    @property
    def total_cache_write(self) -> int:
        """Total cache write tokens."""
        return sum(c.cache_write_tokens for c in self.calls)

    def cost_by_operation(self) -> dict[str, float]:
        """Get cost breakdown by operation type."""
        breakdown: dict[str, float] = {}
        for call in self.calls:
            key = call.operation_type.value
            breakdown[key] = breakdown.get(key, 0) + call.cost
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    def cost_by_model(self) -> dict[str, float]:
        """Get cost breakdown by model."""
        breakdown: dict[str, float] = {}
        for call in self.calls:
            breakdown[call.model] = breakdown.get(call.model, 0) + call.cost
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    def cost_by_agent(self) -> dict[str, float]:
        """Get cost breakdown by agent (None = main conversation)."""
        breakdown: dict[str, float] = {}
        for call in self.calls:
            key = call.agent_name or "main"
            breakdown[key] = breakdown.get(key, 0) + call.cost
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    def duplicate_file_reads(self) -> list[tuple[str, int]]:
        """Get files read more than once, sorted by count."""
        duplicates = [(path, count) for path, count in self.files_read.items() if count > 1]
        return sorted(duplicates, key=lambda x: x[1], reverse=True)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "calls": [c.to_dict() for c in self.calls],
            "files_read": self.files_read,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CostProfile":
        """Deserialize from dictionary."""
        profile = cls(
            session_id=data["session_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
        )
        profile.calls = [TrackedCall.from_dict(c) for c in data.get("calls", [])]
        profile.files_read = data.get("files_read", {})
        return profile

    def save(self, path: Path) -> None:
        """Save profile to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "CostProfile":
        """Load profile from JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))


import uuid
from contextvars import ContextVar

# Context variable to track current operation type
_current_operation: ContextVar[OperationType] = ContextVar(
    "current_operation", default=OperationType.UNKNOWN
)
_current_agent: ContextVar[Optional[str]] = ContextVar(
    "current_agent", default=None
)
_current_tool: ContextVar[Optional[str]] = ContextVar(
    "current_tool", default=None
)


class CostTracker:
    """Global cost tracker singleton."""

    _instance: Optional["CostTracker"] = None

    def __init__(self) -> None:
        self._enabled = False
        self._profile: Optional[CostProfile] = None

    @classmethod
    def get_instance(cls) -> "CostTracker":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def enable(self) -> None:
        """Enable cost tracking for this session."""
        self._enabled = True
        if self._profile is None:
            self._profile = CostProfile(
                session_id=str(uuid.uuid4())[:8],
                start_time=datetime.now(),
            )

    def disable(self) -> None:
        """Disable cost tracking."""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if tracking is enabled."""
        return self._enabled

    @property
    def profile(self) -> Optional[CostProfile]:
        """Get the current profile."""
        return self._profile

    def track_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        metadata: Optional[dict] = None,
    ) -> None:
        """Track an LLM call."""
        if not self._enabled or self._profile is None:
            return

        call = TrackedCall(
            timestamp=datetime.now(),
            model=model,
            operation_type=_current_operation.get(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cost=cost,
            agent_name=_current_agent.get(),
            tool_name=_current_tool.get(),
            metadata=metadata or {},
        )
        self._profile.add_call(call)

    def track_file_read(self, path: str) -> None:
        """Track a file read for duplicate detection."""
        if not self._enabled or self._profile is None:
            return
        self._profile.record_file_read(path)

    def reset(self) -> None:
        """Reset the tracker for a new session."""
        self._profile = CostProfile(
            session_id=str(uuid.uuid4())[:8],
            start_time=datetime.now(),
        )

    def save_profile(self, directory: Path) -> Optional[Path]:
        """Save current profile to directory. Returns path or None."""
        if self._profile is None:
            return None
        path = directory / f"profile_{self._profile.session_id}.json"
        self._profile.save(path)
        return path


# Context manager for setting operation type
from contextlib import contextmanager

@contextmanager
def track_operation(operation: OperationType):
    """Context manager to set the current operation type."""
    token = _current_operation.set(operation)
    try:
        yield
    finally:
        _current_operation.reset(token)


@contextmanager
def track_agent(agent_name: str):
    """Context manager to set the current agent."""
    token = _current_agent.set(agent_name)
    try:
        yield
    finally:
        _current_agent.reset(token)


@contextmanager
def track_tool(tool_name: str):
    """Context manager to set the current tool."""
    token = _current_tool.set(tool_name)
    try:
        yield
    finally:
        _current_tool.reset(token)


# Convenience function
def get_tracker() -> CostTracker:
    """Get the global cost tracker."""
    return CostTracker.get_instance()


def generate_report(profile: CostProfile) -> str:
    """Generate a markdown report from a cost profile."""

    duration = datetime.now() - profile.start_time
    duration_str = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"

    lines = [
        "# LOCO Cost Profile Report",
        "",
        f"**Session ID:** {profile.session_id}",
        f"**Duration:** {duration_str}",
        f"**Total Cost:** ${profile.total_cost:.4f}",
        "",
        "## Token Usage",
        "",
        f"- Input tokens: {profile.total_input_tokens:,}",
        f"- Output tokens: {profile.total_output_tokens:,}",
        f"- Cache read: {profile.total_cache_read:,}",
        f"- Cache write: {profile.total_cache_write:,}",
        "",
        "## Cost by Operation Type",
        "",
        "| Operation | Cost | Percentage |",
        "|-----------|------|------------|",
    ]

    total = profile.total_cost or 1
    for op, cost in profile.cost_by_operation().items():
        pct = (cost / total) * 100
        lines.append(f"| {op} | ${cost:.4f} | {pct:.1f}% |")

    lines.extend([
        "",
        "## Cost by Agent",
        "",
        "| Agent | Cost | Percentage |",
        "|-------|------|------------|",
    ])

    for agent, cost in profile.cost_by_agent().items():
        pct = (cost / total) * 100
        lines.append(f"| {agent} | ${cost:.4f} | {pct:.1f}% |")

    # Optimization opportunities
    duplicates = profile.duplicate_file_reads()
    if duplicates:
        lines.extend([
            "",
            "## Optimization Opportunities",
            "",
            "### Duplicate File Reads",
            "",
        ])
        for path, count in duplicates[:10]:
            lines.append(f"- `{path}`: read {count}x ({count - 1} duplicates)")

    lines.extend([
        "",
        "---",
        f"*Generated at {datetime.now().isoformat()}*",
    ])

    return "\n".join(lines)
