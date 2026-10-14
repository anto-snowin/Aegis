"""
Unit tests for Aegis Flow signal state machine & safety rules.
"""

from datetime import datetime, timezone, timedelta
from backend.app.models.models import SignalState, SignalPhase
from backend.app.services.signal_state_machine import SignalStateMachine, SignalDirection


def test_valid_transitions():
    # NORMAL -> PREPARE is allowed
    ok, msg = SignalStateMachine.can_transition(SignalState.NORMAL, SignalState.PREPARE)
    assert ok is True

    # PREPARE -> EMERGENCY_PRIORITY is allowed
    ok, msg = SignalStateMachine.can_transition(SignalState.PREPARE, SignalState.EMERGENCY_PRIORITY)
    assert ok is True

    # EMERGENCY_PRIORITY -> CLEARANCE is allowed
    ok, msg = SignalStateMachine.can_transition(SignalState.EMERGENCY_PRIORITY, SignalState.CLEARANCE)
    assert ok is True

    # CLEARANCE -> NORMAL is allowed
    ok, msg = SignalStateMachine.can_transition(SignalState.CLEARANCE, SignalState.NORMAL)
    assert ok is True


def test_invalid_safety_transitions():
    # EMERGENCY_PRIORITY cannot jump directly back to NORMAL without clearance buffer
    ok, msg = SignalStateMachine.can_transition(SignalState.EMERGENCY_PRIORITY, SignalState.NORMAL, is_manual=False)
    assert ok is False
    assert "Invalid safety transition" in msg


def test_dual_approach_conflict_safety():
    # Test all states to ensure NS and EW are NEVER both Green
    for state in [SignalState.NORMAL, SignalState.PREPARE, SignalState.EMERGENCY_PRIORITY, SignalState.CLEARANCE, SignalState.MANUAL]:
        phases = SignalStateMachine.compute_dual_approach_phases(state, SignalDirection.NORTH_SOUTH)
        ns_green = (phases["NS"] == SignalPhase.GREEN)
        ew_green = (phases["EW"] == SignalPhase.GREEN)
        # Safety invariant: Never both green
        assert not (ns_green and ew_green), f"Safety violation in state {state}: Both NS and EW are Green!"


def test_command_watchdog_expiry():
    # Recent command should not be expired
    now = datetime.now(timezone.utc)
    recent = now - timedelta(seconds=15)
    assert SignalStateMachine.check_command_expiry(recent, expiry_seconds=45) is False

    # Old command exceeding 45s should be expired
    stale = now - timedelta(seconds=50)
    assert SignalStateMachine.check_command_expiry(stale, expiry_seconds=45) is True
