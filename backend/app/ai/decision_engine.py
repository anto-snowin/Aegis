"""
Aegis Flow - Unified AI Decision Engine
Master decision orchestrator for emergency routing, priority scoring, and green corridor control.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json
from sqlalchemy.orm import Session

from backend.app.models.models import (
    EmergencyRequest, Ambulance, Hospital, TrafficSignal, AIDecision, SystemEvent
)
from backend.app.ai.priority_engine import PriorityEngine
from backend.app.ai.eta_engine import ETAEngine, haversine_km
from backend.app.ai.traffic_analyzer import TrafficAnalyzer
from backend.app.services.websocket_manager import ws_manager


class DecisionEngine:
    """
    Coordinates AI analysis across all subsystems and saves explainable decisions.
    """

    @classmethod
    async def analyze_emergency(
        cls,
        emergency_id: str,
        db: Session,
        ambulance_lat: Optional[float] = None,
        ambulance_lon: Optional[float] = None,
        ambulance_speed: Optional[float] = None,
    ) -> AIDecision:
        """
        Runs comprehensive AI evaluation for a given emergency:
        - Priority scoring & breakdown
        - ETA with green wave savings
        - Traffic density assessment
        - Explainable recommendations
        """
        emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == emergency_id).first()
        if not emergency:
            raise ValueError(f"Emergency {emergency_id} not found")

        # Determine ambulance position
        amb = None
        if emergency.ambulance_id:
            amb = db.query(Ambulance).filter(Ambulance.id == emergency.ambulance_id).first()

        current_lat = ambulance_lat or (amb.latitude if amb else emergency.latitude)
        current_lon = ambulance_lon or (amb.longitude if amb else emergency.longitude)
        speed = ambulance_speed or (amb.speed_kmh if amb else 35.0)

        # 1. Traffic density analysis
        traffic = TrafficAnalyzer.estimate_corridor_density(current_lat, current_lon)
        traffic_density = traffic["density_index"]

        # 2. Priority calculation
        wait_mins = 0.0
        if emergency.created_at:
            # Calculate elapsed wait minutes
            created = emergency.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            wait_mins = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 60.0)

        dist_to_patient = haversine_km(current_lat, current_lon, emergency.latitude, emergency.longitude)
        priority_score, factors_dict, explanation = PriorityEngine.calculate_priority(
            severity=emergency.severity.value,
            emergency_type=emergency.emergency_type.value,
            traffic_density=traffic_density,
            distance_km=dist_to_patient,
            wait_time_minutes=wait_mins,
        )

        # 3. Signals count along the corridor
        signals = db.query(TrafficSignal).filter(TrafficSignal.is_online == True).all()
        signals_count = len(signals) if signals else 4

        # 4. Target destination (Patient if en route to pickup, Hospital if transporting)
        target_lat = emergency.latitude
        target_lon = emergency.longitude
        if emergency.status in ["picked_up", "transporting"] and emergency.hospital_id:
            hosp = db.query(Hospital).filter(Hospital.id == emergency.hospital_id).first()
            if hosp:
                target_lat = hosp.latitude
                target_lon = hosp.longitude

        # 5. ETA Calculation
        eta_result = ETAEngine.calculate_eta(
            current_lat=current_lat,
            current_lon=current_lon,
            target_lat=target_lat,
            target_lon=target_lon,
            current_speed_kmh=speed,
            traffic_density=traffic_density,
            signals_count=signals_count,
            green_corridor_active=True,
        )

        # Update emergency estimated arrival time
        emergency.estimated_arrival_minutes = eta_result["aegis_eta_minutes"]

        # 6. Data Quality calculation
        gps_fresh = True
        data_quality = 0.95
        if amb and amb.last_gps_update:
            last_gps = amb.last_gps_update
            if last_gps.tzinfo is None:
                last_gps = last_gps.replace(tzinfo=timezone.utc)
            age_sec = (datetime.now(timezone.utc) - last_gps).total_seconds()
            if age_sec > 30:
                gps_fresh = False
                data_quality -= 0.35

        # 7. Recommendation
        recommendation = (
            f"Activate Dynamic Green Corridor for {signals_count} signals. "
            f"Expected time savings: {eta_result['time_saved_minutes']} min "
            f"({eta_result['time_saved_percent']}% faster arrival). "
            f"Priority class: {'HIGH' if priority_score >= 70 else 'STANDARD'}."
        )

        decision = AIDecision(
            emergency_id=emergency.id,
            ambulance_id=amb.id if amb else None,
            decision_type="corridor_and_priority",
            priority_score=priority_score,
            eta_minutes=eta_result["aegis_eta_minutes"],
            traffic_density=traffic_density,
            confidence=round(data_quality * 0.92, 2),
            explanation=explanation,
            factors=json.dumps(factors_dict),
            recommendation=recommendation,
            gps_fresh=gps_fresh,
            camera_available=False,
            data_quality_score=round(data_quality, 2),
            created_at=datetime.now(timezone.utc),
        )
        db.add(decision)

        # Log system event
        db.add(SystemEvent(
            event_type="ai_decision_generated",
            severity="info",
            source="ai_engine",
            entity_type="emergency",
            entity_id=emergency.id,
            message=f"AI Decision: Priority {priority_score}, ETA {eta_result['aegis_eta_minutes']} min (Saved {eta_result['time_saved_minutes']} min)",
        ))

        db.commit()
        db.refresh(decision)

        # Broadcast update
        await ws_manager.send_to_channel("general", {
            "type": "ai_decision",
            "emergency_id": emergency.id,
            "priority_score": priority_score,
            "eta_minutes": eta_result["aegis_eta_minutes"],
            "recommendation": recommendation,
        })

        return decision
