"""
Aegis Flow - Dynamic Green Corridor Controller
Coordinates multi-intersection green waves ahead of active emergency vehicles.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import math

from backend.app.models.models import (
    TrafficSignal, SignalCommand, EmergencyRequest, Ambulance,
    SignalState, SignalPhase, SystemEvent, AIDecision
)
from backend.app.services.websocket_manager import ws_manager
from backend.app.ai.traffic_analyzer import TrafficAnalyzer
from backend.app.ai.priority_engine import PriorityEngine


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two GPS coordinates."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class CorridorController:
    """
    Evaluates ambulance GPS trajectory and manages preemption on upcoming signals.
    """

    PREPARE_RADIUS_METERS = 850.0       # Begin queue clearance
    PRIORITY_GREEN_RADIUS_METERS = 400.0  # Turn solid green for ambulance
    EXIT_THRESHOLD_METERS = 30.0        # Ambulance cleared intersection

    @classmethod
    async def process_ambulance_movement(
        cls,
        ambulance_id: str,
        current_lat: float,
        current_lon: float,
        speed_kmh: float,
        db: Session,
        mqtt_publisher=None,
    ) -> List[Dict[str, Any]]:
        """
        Main loop called whenever an ambulance updates its GPS coordinates.
        Checks nearby signals, activates or advances corridor states, and logs events.
        """
        ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
        if not ambulance:
            return []

        # Find active emergency associated with this ambulance
        emergency = db.query(EmergencyRequest).filter(
            EmergencyRequest.ambulance_id == ambulance_id,
            EmergencyRequest.status.in_(["assigned", "accepted", "en_route", "transporting"])
        ).first()

        # If no active emergency, do not preempt signals
        if not emergency:
            return []

        # Priority calculation
        priority_score, _, _ = PriorityEngine.calculate_priority(
            severity=emergency.severity.value,
            emergency_type=emergency.emergency_type.value,
        )

        # Get all online traffic signals
        signals = db.query(TrafficSignal).filter(TrafficSignal.is_online == True).all()
        actions_taken = []
        now = datetime.now(timezone.utc)

        for sig in signals:
            # Skip if signal is manually overridden
            if sig.manual_override:
                continue

            dist_m = haversine_meters(current_lat, current_lon, sig.latitude, sig.longitude)

            # Analyze approach timing
            timings = TrafficAnalyzer.calculate_approach_timings(
                distance_to_signal_meters=dist_m,
                speed_kmh=speed_kmh,
                density_index=0.5,
            )

            # 1. Check if ambulance has passed through an active emergency signal
            if dist_m <= cls.EXIT_THRESHOLD_METERS and sig.state == SignalState.EMERGENCY_PRIORITY:
                # Transition to CLEARANCE then back to NORMAL
                sig.state = SignalState.CLEARANCE
                sig.current_phase = SignalPhase.YELLOW
                db.commit()

                event_msg = f"Ambulance {ambulance.vehicle_number} cleared {sig.name}. Reverting corridor to clearance."
                db.add(SystemEvent(
                    event_type="signal_corridor_cleared",
                    severity="info",
                    source="corridor_controller",
                    entity_type="signal",
                    entity_id=sig.id,
                    message=event_msg,
                ))
                db.commit()

                # Broadcast
                await ws_manager.send_to_channel("signals", {
                    "type": "signal_changed",
                    "signal_id": sig.id,
                    "state": SignalState.CLEARANCE.value,
                    "phase": SignalPhase.YELLOW.value,
                    "reason": "Ambulance passed intersection - clearance active",
                })

                if mqtt_publisher:
                    mqtt_publisher(f"aegis/signals/{sig.id}/command", {
                        "state": "CLEARANCE",
                        "phase": "YELLOW",
                        "duration_sec": 4,
                    })

                actions_taken.append({"signal_id": sig.id, "action": "clearance", "distance_m": dist_m})

            # 2. Urgent Emergency Green Corridor (within 400m)
            elif dist_m <= cls.PRIORITY_GREEN_RADIUS_METERS and dist_m > cls.EXIT_THRESHOLD_METERS:
                if sig.state != SignalState.EMERGENCY_PRIORITY:
                    sig.state = SignalState.EMERGENCY_PRIORITY
                    sig.current_phase = SignalPhase.GREEN
                    
                    cmd = SignalCommand(
                        signal_id=sig.id,
                        emergency_id=emergency.id,
                        ambulance_id=ambulance.id,
                        requested_state=SignalState.EMERGENCY_PRIORITY,
                        requested_phase=SignalPhase.GREEN,
                        reason=f"Dynamic Green Wave for {emergency.emergency_type.value} emergency ({dist_m:.0f}m away)",
                        priority_score=priority_score,
                        acknowledged=True,
                        acknowledged_at=now,
                        actual_state=SignalState.EMERGENCY_PRIORITY,
                        created_at=now,
                        expires_at=now + timedelta(seconds=45),
                    )
                    db.add(cmd)
                    db.add(SystemEvent(
                        event_type="signal_corridor_activated",
                        severity="warning",
                        source="corridor_controller",
                        entity_type="signal",
                        entity_id=sig.id,
                        message=f"GREEN WAVE activated at {sig.name} for {ambulance.vehicle_number}",
                    ))
                    db.commit()

                    await ws_manager.send_to_channel("signals", {
                        "type": "signal_changed",
                        "signal_id": sig.id,
                        "state": SignalState.EMERGENCY_PRIORITY.value,
                        "phase": SignalPhase.GREEN.value,
                        "reason": cmd.reason,
                    })

                    if mqtt_publisher:
                        mqtt_publisher(f"aegis/signals/{sig.id}/command", {
                            "state": "EMERGENCY_PRIORITY",
                            "phase": "GREEN",
                            "priority_lane": "AMBULANCE_APPROACH",
                            "opposing_lane": "RED",
                            "duration_sec": 45,
                        })

                    actions_taken.append({"signal_id": sig.id, "action": "emergency_green", "distance_m": dist_m})

            # 3. Preparation & Queue Flush Warning (within 850m)
            elif dist_m <= cls.PREPARE_RADIUS_METERS and dist_m > cls.PRIORITY_GREEN_RADIUS_METERS:
                if sig.state == SignalState.NORMAL:
                    sig.state = SignalState.PREPARE
                    sig.current_phase = SignalPhase.YELLOW
                    
                    cmd = SignalCommand(
                        signal_id=sig.id,
                        emergency_id=emergency.id,
                        ambulance_id=ambulance.id,
                        requested_state=SignalState.PREPARE,
                        requested_phase=SignalPhase.YELLOW,
                        reason=f"Prepare queue clearance: ambulance approaching ({dist_m:.0f}m away)",
                        priority_score=priority_score,
                        acknowledged=True,
                        acknowledged_at=now,
                        actual_state=SignalState.PREPARE,
                        created_at=now,
                        expires_at=now + timedelta(seconds=30),
                    )
                    db.add(cmd)
                    db.add(SystemEvent(
                        event_type="signal_corridor_prepare",
                        severity="info",
                        source="corridor_controller",
                        entity_type="signal",
                        entity_id=sig.id,
                        message=f"PREPARE state activated at {sig.name}: clearing intersection queues",
                    ))
                    db.commit()

                    await ws_manager.send_to_channel("signals", {
                        "type": "signal_changed",
                        "signal_id": sig.id,
                        "state": SignalState.PREPARE.value,
                        "phase": SignalPhase.YELLOW.value,
                        "reason": cmd.reason,
                    })

                    if mqtt_publisher:
                        mqtt_publisher(f"aegis/signals/{sig.id}/command", {
                            "state": "PREPARE",
                            "phase": "YELLOW",
                            "duration_sec": 30,
                        })

                    actions_taken.append({"signal_id": sig.id, "action": "prepare", "distance_m": dist_m})

        return actions_taken
