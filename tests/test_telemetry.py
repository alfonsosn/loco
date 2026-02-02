"""Tests for cost profiling telemetry."""
import pytest
from datetime import datetime
from loco.telemetry import (
    OperationType,
    TrackedCall,
    CostProfile,
    CostTracker,
    track_operation,
    track_agent,
    get_tracker,
)


class TestTrackedCall:
    def test_serialization(self):
        call = TrackedCall(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            model="claude-3-sonnet",
            operation_type=OperationType.SEARCH_GREP,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.001,
        )

        data = call.to_dict()
        restored = TrackedCall.from_dict(data)

        assert restored.model == call.model
        assert restored.operation_type == call.operation_type
        assert restored.cost == call.cost


class TestCostProfile:
    def test_cost_aggregation(self):
        profile = CostProfile(
            session_id="test123",
            start_time=datetime.now(),
        )

        profile.add_call(TrackedCall(
            timestamp=datetime.now(),
            model="claude-3-sonnet",
            operation_type=OperationType.SEARCH_GREP,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.001,
        ))

        profile.add_call(TrackedCall(
            timestamp=datetime.now(),
            model="claude-3-sonnet",
            operation_type=OperationType.READ_FILE,
            input_tokens=200,
            output_tokens=100,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.002,
        ))

        assert profile.total_cost == 0.003
        assert profile.total_input_tokens == 300
        assert profile.total_output_tokens == 150

    def test_cost_by_operation(self):
        profile = CostProfile(
            session_id="test123",
            start_time=datetime.now(),
        )

        profile.add_call(TrackedCall(
            timestamp=datetime.now(),
            model="claude-3-sonnet",
            operation_type=OperationType.SEARCH_GREP,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.001,
        ))

        profile.add_call(TrackedCall(
            timestamp=datetime.now(),
            model="claude-3-sonnet",
            operation_type=OperationType.SEARCH_GREP,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cache_write_tokens=0,
            cost=0.001,
        ))

        by_op = profile.cost_by_operation()
        assert by_op["search:grep"] == 0.002

    def test_duplicate_file_detection(self):
        profile = CostProfile(
            session_id="test123",
            start_time=datetime.now(),
        )

        profile.record_file_read("src/main.py")
        profile.record_file_read("src/main.py")
        profile.record_file_read("src/other.py")

        duplicates = profile.duplicate_file_reads()
        assert len(duplicates) == 1
        assert duplicates[0] == ("src/main.py", 2)


class TestCostTracker:
    def test_singleton(self):
        t1 = CostTracker.get_instance()
        t2 = CostTracker.get_instance()
        assert t1 is t2

    def test_enable_disable(self):
        tracker = get_tracker()
        tracker.reset()

        assert not tracker.enabled
        tracker.enable()
        assert tracker.enabled
        tracker.disable()
        assert not tracker.enabled

    def test_track_call_when_enabled(self):
        tracker = get_tracker()
        tracker.reset()
        tracker.enable()

        tracker.track_call(
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
        )

        assert len(tracker.profile.calls) == 1

    def test_track_call_when_disabled(self):
        tracker = get_tracker()
        tracker.disable()  # Ensure disabled
        tracker.reset()

        tracker.track_call(
            model="claude-3-sonnet",
            input_tokens=100,
            output_tokens=50,
            cost=0.001,
        )

        # Should not track when disabled
        assert len(tracker.profile.calls) == 0


class TestContextManagers:
    def test_track_operation(self):
        from loco.telemetry import _current_operation

        assert _current_operation.get() == OperationType.UNKNOWN

        with track_operation(OperationType.SEARCH_GREP):
            assert _current_operation.get() == OperationType.SEARCH_GREP

        assert _current_operation.get() == OperationType.UNKNOWN

    def test_track_agent(self):
        from loco.telemetry import _current_agent

        assert _current_agent.get() is None

        with track_agent("explore"):
            assert _current_agent.get() == "explore"

        assert _current_agent.get() is None
