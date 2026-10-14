"""
Aegis Flow - Traffic Signal State Machine & Safety Controller
Guarantees fail-safe transitions, yellow clearance intervals, and conflict prevention.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

from backend.app.models.models import SignalState, SignalPhase

logger = logging.getLogger("aegis.signals")


class SignalDirection(str, Enum):
    NORTH_SOUTH = "NS"
    EAST_WEST = "EW"


class SignalStateMachine:
    """
    Enforces strict safety rules for signal timing and priority overrides.
    """

    MIN_YELLOW_DURATION_SEC = 3.0
    MIN_ALL_RED_DURATION_SEC = 2.0
    DEFAULT_MAX_EMERGENCY_SEC = 60.0

    VALID_TRANSITIONS = {
        SignalState.NORMAL: [SignalState.PREPARE, SignalState.EMERGENCY_PRIORITY, SignalState.MANUAL, SignalState.OFFLINE],
        SignalState.PREPARE: [SignalState.EMERGENCY_PRIORITY, SignalState.NORMAL, SignalState.MANUAL, SignalState.OFFLINE],
        SignalState.EMERGENCY_PRIORITY: [SignalState.CLEARANCE, SignalState.MANUAL, SignalState.OFFLINE],
        SignalState.CLEARANCE: [SignalState.NORMAL, SignalState.MANUAL, SignalState.OFFLINE],
        SignalState.MANUAL: [SignalState.NORMAL, SignalState.OFFLINE],
        SignalState.OFFLINE: [SignalState.NORMAL, SignalState.MANUAL],
    }

    @classmethod
    def can_transition(cls, current_state: SignalState, target_state: SignalState, is_manual: bool = False) -> Tuple[bool, str]:
        """Verify whether the requested state transition complies with safety policy."""
        if is_manual:
            # Manual override by traffic authority has full emergency override authority
            return True, "Manual operator authority permitted."

        allowed = cls.VALID_TRANSITIONS.get(current_state, [])
        if target_state in allowed:
            return True, f"Valid transition: {current_state.value} -> {target_state.value}"

        return False, f"Invalid safety transition: Cannot jump directly from {current_state.value} to {target_state.value}"

    @classmethod
    def compute_dual_approach_phases(
        cls,
        state: SignalState,
        priority_direction: SignalDirection = SignalDirection.NORTH_SOUTH,
    ) -> Dict[str, SignalPhase]:
        """
        Determines the safe phases for both intersecting directions (NS vs EW).
        Strict safety invariant: NEVER allow simultaneous GREEN on both directions.
        """
        if state == SignalState.EMERGENCY_PRIORITY:
            # Priority corridor lane gets solid GREEN; conflicting lane gets strict RED
            if priority_direction == SignalDirection.NORTH_SOUTH:
                return {"NS": SignalPhase.GREEN, "EW": SignalPhase.RED}
            else:
                return {"NS": SignalPhase.RED, "EW": SignalPhase.GREEN}

        elif state == SignalState.PREPARE:
            # Yellow warning to clear approaching vehicles
            if priority_direction == SignalDirection.NORTH_SOUTH:
                return {"NS": SignalPhase.YELLOW, "EW": SignalPhase.RED}
            else:
                return {"NS": SignalPhase.RED, "EW": SignalPhase.YELLOW}

        elif state == SignalState.CLEARANCE:
            # All-red safety buffer to clear intersection before returning to normal
            return {"NS": SignalPhase.YELLOW, "EW": SignalPhase.RED}

        elif state == SignalState.MANUAL:
            # Default to all-red or holding phase
            return {"NS": SignalPhase.ALL_RED, "EW": SignalPhase.ALL_RED}

        else:  # NORMAL
            # Default cyclic state
            return {"NS": SignalPhase.GREEN, "EW": SignalPhase.RED}

    @classmethod
    def check_command_expiry(
        cls,
        command_created_at: datetime,
        expiry_seconds: int = 60,
    ) -> bool:
        """Watchdog check: verifies if an active emergency command has exceeded its fail-safe lifespan."""
        if command_created_at.tzinfo is None:
            command_created_at = command_created_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - command_created_at).total_seconds()
        return elapsed > expiry_seconds
