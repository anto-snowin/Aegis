"""
Aegis Flow - Traffic Signal API Routes
Signal state management, commands, and manual override.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.app.database.db import get_db
from backend.app.models.models import (
    TrafficSignal, SignalCommand, SystemEvent,
    SignalState, SignalPhase
)
from backend.app.schemas.schemas import (
    SignalResponse, SignalCommandCreate, SignalCommandResponse, SignalOverride
)
from backend.app.services.websocket_manager import ws_manager
from backend.app.services.mqtt_service import mqtt_service

router = APIRouter(prefix="/signals", tags=["Traffic Signals"])


@router.get("", response_model=list[SignalResponse])
def list_signals(db: Session = Depends(get_db)):
    """List all traffic signals."""
    return db.query(TrafficSignal).all()


@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: str, db: Session = Depends(get_db)):
    """Get specific signal details."""
    signal = db.query(TrafficSignal).filter(TrafficSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.post("/{signal_id}/command", response_model=SignalCommandResponse, status_code=201)
async def send_command(
    signal_id: str,
    data: SignalCommandCreate,
    db: Session = Depends(get_db),
):
    """Send a signal command (e.g., request emergency priority)."""
    signal = db.query(TrafficSignal).filter(TrafficSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Safety: check if manual override is active
    if signal.manual_override and data.requested_state == SignalState.EMERGENCY_PRIORITY:
        raise HTTPException(
            status_code=403,
            detail="Signal is under manual override. Cannot apply AI emergency priority."
        )

    # Safety: check for duplicate active commands
    active_cmd = db.query(SignalCommand).filter(
        SignalCommand.signal_id == signal_id,
        SignalCommand.expired == False,
        SignalCommand.acknowledged == False,
        SignalCommand.expires_at > datetime.now(timezone.utc),
    ).first()
    if active_cmd and data.requested_state == SignalState.EMERGENCY_PRIORITY:
        raise HTTPException(
            status_code=409,
            detail="Active command already pending for this signal"
        )

    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=data.expiry_seconds)

    command = SignalCommand(
        signal_id=signal_id,
        emergency_id=data.emergency_id,
        ambulance_id=data.ambulance_id,
        requested_state=data.requested_state,
        requested_phase=data.requested_phase,
        reason=data.reason,
        priority_score=data.priority_score,
        created_at=now,
        expires_at=expires,
    )
    db.add(command)

    # In simulation mode, auto-acknowledge and apply
    signal.state = data.requested_state
    if data.requested_phase:
        signal.current_phase = data.requested_phase
    command.acknowledged = True
    command.acknowledged_at = now
    command.actual_state = data.requested_state

    db.add(SystemEvent(
        event_type="signal_command_sent",
        severity="warning" if data.requested_state == SignalState.EMERGENCY_PRIORITY else "info",
        source="api",
        entity_type="signal",
        entity_id=signal_id,
        message=f"Signal {signal.name} → {data.requested_state.value}: {data.reason}",
    ))

    db.commit()
    db.refresh(command)

    # Broadcast signal change
    await ws_manager.send_to_channel("signals", {
        "type": "signal_changed",
        "signal_id": signal_id,
        "state": data.requested_state.value,
        "phase": data.requested_phase.value if data.requested_phase else None,
        "reason": data.reason,
        "command_id": command.id,
    })

    # Publish MQTT command to ESP32 / IoT controller
    mqtt_service.publish_signal_command(
        signal_id=signal_id,
        state=data.requested_state.value,
        phase=data.requested_phase.value if data.requested_phase else "GREEN",
        duration_sec=data.expiry_seconds,
    )

    return command


@router.post("/{signal_id}/override", response_model=SignalResponse)
async def override_signal(
    signal_id: str,
    data: SignalOverride,
    db: Session = Depends(get_db),
):
    """Manual override for traffic authority."""
    signal = db.query(TrafficSignal).filter(TrafficSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if data.action == "enable_manual":
        signal.manual_override = True
        signal.state = SignalState.MANUAL
        signal.override_by = "traffic_operator"
    elif data.action == "disable_manual":
        signal.manual_override = False
        signal.state = SignalState.NORMAL
        signal.override_by = None
    elif data.action == "force_normal":
        signal.state = SignalState.NORMAL
        signal.current_phase = SignalPhase.GREEN
        signal.manual_override = False
        signal.override_by = None
        # Expire active commands
        active_cmds = db.query(SignalCommand).filter(
            SignalCommand.signal_id == signal_id,
            SignalCommand.expired == False,
        ).all()
        for cmd in active_cmds:
            cmd.expired = True
    elif data.action == "force_red":
        signal.state = SignalState.MANUAL
        signal.current_phase = SignalPhase.ALL_RED
        signal.manual_override = True
        signal.override_by = "traffic_operator"

    db.add(SystemEvent(
        event_type="signal_override",
        severity="warning",
        source="traffic_operator",
        entity_type="signal",
        entity_id=signal_id,
        message=f"Manual override: {data.action} - {data.reason}",
    ))

    db.commit()
    db.refresh(signal)

    await ws_manager.send_to_channel("signals", {
        "type": "signal_override",
        "signal_id": signal_id,
        "state": signal.state.value,
        "manual_override": signal.manual_override,
        "action": data.action,
    })

    mqtt_service.publish(f"aegis/signals/{signal_id}/override", {
        "signal_id": signal_id,
        "state": signal.state.value,
        "manual_override": signal.manual_override,
        "action": data.action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return signal


@router.get("/{signal_id}/commands", response_model=list[SignalCommandResponse])
def get_signal_commands(signal_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Get command history for a signal."""
    commands = db.query(SignalCommand).filter(
        SignalCommand.signal_id == signal_id
    ).order_by(SignalCommand.created_at.desc()).limit(limit).all()
    return commands
