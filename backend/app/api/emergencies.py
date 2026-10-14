"""
Aegis Flow - Emergency Request API Routes
Handles emergency creation, assignment, status updates, and lifecycle.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import math

from backend.app.database.db import get_db
from backend.app.models.models import (
    EmergencyRequest, Ambulance, Hospital, User, SystemEvent,
    EmergencyStatus, AmbulanceStatus, UserRole
)
from backend.app.schemas.schemas import (
    EmergencyCreate, EmergencyResponse, EmergencyAssign
)
from backend.app.services.auth import get_current_user
from backend.app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/emergencies", tags=["Emergencies"])


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@router.post("", response_model=EmergencyResponse, status_code=201)
async def create_emergency(data: EmergencyCreate, db: Session = Depends(get_db),
                           user: Optional[User] = Depends(get_current_user)):
    """Create a new emergency request."""
    emergency = EmergencyRequest(
        requester_id=user.id if user else None,
        emergency_type=data.emergency_type,
        severity=data.severity,
        description=data.description,
        patient_name=data.patient_name,
        patient_phone=data.patient_phone,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        status=EmergencyStatus.PENDING,
    )
    db.add(emergency)

    # Log system event
    event = SystemEvent(
        event_type="emergency_created",
        severity="critical",
        source="api",
        entity_type="emergency",
        entity_id=emergency.id,
        message=f"New {data.severity.value} emergency: {data.emergency_type.value}",
        details=f'{{"lat": {data.latitude}, "lng": {data.longitude}}}',
    )
    db.add(event)
    db.commit()
    db.refresh(emergency)

    # Broadcast to command center
    await ws_manager.send_to_channel("emergencies", {
        "type": "emergency_created",
        "data": EmergencyResponse.model_validate(emergency).model_dump(mode="json"),
    })

    return emergency


@router.get("", response_model=list[EmergencyResponse])
def list_emergencies(
    status_filter: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List emergency requests, optionally filtered by status."""
    query = db.query(EmergencyRequest)
    if status_filter:
        query = query.filter(EmergencyRequest.status == status_filter)
    emergencies = query.order_by(EmergencyRequest.created_at.desc()).limit(limit).all()
    return emergencies


@router.get("/{request_id}", response_model=EmergencyResponse)
def get_emergency(request_id: str, db: Session = Depends(get_db)):
    """Get a specific emergency request by ID."""
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == request_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return emergency


@router.post("/{request_id}/assign", response_model=EmergencyResponse)
async def assign_ambulance(
    request_id: str,
    data: EmergencyAssign,
    db: Session = Depends(get_db),
):
    """Assign an ambulance (and optionally hospital) to an emergency."""
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == request_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")
    if emergency.status not in [EmergencyStatus.PENDING, EmergencyStatus.NO_AMBULANCE]:
        raise HTTPException(status_code=400, detail=f"Cannot assign: status is {emergency.status.value}")

    ambulance = db.query(Ambulance).filter(Ambulance.id == data.ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")
    if ambulance.status != AmbulanceStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail=f"Ambulance not available: {ambulance.status.value}")

    # Calculate ETA estimate
    eta = None
    if ambulance.latitude and ambulance.longitude:
        distance = haversine_km(
            ambulance.latitude, ambulance.longitude,
            emergency.latitude, emergency.longitude
        )
        avg_speed_kmh = 40  # Conservative city speed
        eta = (distance / avg_speed_kmh) * 60  # minutes

    # Assign hospital if provided
    if data.hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == data.hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=404, detail="Hospital not found")
        emergency.hospital_id = data.hospital_id

    # If no hospital specified, find nearest
    if not emergency.hospital_id:
        hospitals = db.query(Hospital).filter(
            Hospital.is_active == True,
            Hospital.emergency_department == True,
        ).all()
        if hospitals:
            nearest = min(hospitals, key=lambda h: haversine_km(
                emergency.latitude, emergency.longitude,
                h.latitude, h.longitude
            ))
            emergency.hospital_id = nearest.id

    emergency.ambulance_id = data.ambulance_id
    emergency.status = EmergencyStatus.ASSIGNED
    emergency.assigned_at = datetime.now(timezone.utc)
    emergency.estimated_arrival_minutes = round(eta, 1) if eta else None

    ambulance.status = AmbulanceStatus.ASSIGNED

    event = SystemEvent(
        event_type="ambulance_assigned",
        severity="info",
        source="api",
        entity_type="emergency",
        entity_id=request_id,
        message=f"Ambulance {ambulance.vehicle_number} assigned. ETA: {eta:.1f} min" if eta else f"Ambulance {ambulance.vehicle_number} assigned",
    )
    db.add(event)
    db.commit()
    db.refresh(emergency)

    await ws_manager.send_to_channel("emergencies", {
        "type": "ambulance_assigned",
        "data": EmergencyResponse.model_validate(emergency).model_dump(mode="json"),
    })

    return emergency


@router.post("/{request_id}/auto-assign", response_model=EmergencyResponse)
async def auto_assign(request_id: str, db: Session = Depends(get_db)):
    """Automatically assign the nearest available ambulance."""
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == request_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")

    # Find available ambulances
    available = db.query(Ambulance).filter(
        Ambulance.status == AmbulanceStatus.AVAILABLE,
        Ambulance.is_active == True,
        Ambulance.latitude.isnot(None),
    ).all()

    if not available:
        emergency.status = EmergencyStatus.NO_AMBULANCE
        db.add(SystemEvent(
            event_type="no_ambulance_available",
            severity="warning",
            source="api",
            entity_type="emergency",
            entity_id=request_id,
            message="No ambulance available for assignment",
        ))
        db.commit()
        db.refresh(emergency)
        return emergency

    # Find nearest ambulance
    nearest = min(available, key=lambda a: haversine_km(
        emergency.latitude, emergency.longitude,
        a.latitude, a.longitude
    ))

    # Delegate to assign endpoint logic
    assign_data = EmergencyAssign(ambulance_id=nearest.id)
    return await assign_ambulance(request_id, assign_data, db)


@router.post("/{request_id}/pickup", response_model=EmergencyResponse)
async def mark_pickup(request_id: str, db: Session = Depends(get_db)):
    """Mark patient as picked up."""
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == request_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")

    emergency.status = EmergencyStatus.PICKED_UP
    emergency.picked_up_at = datetime.now(timezone.utc)

    if emergency.ambulance_id:
        ambulance = db.query(Ambulance).filter(Ambulance.id == emergency.ambulance_id).first()
        if ambulance:
            ambulance.status = AmbulanceStatus.TRANSPORTING

    db.add(SystemEvent(
        event_type="patient_picked_up",
        severity="info",
        source="api",
        entity_type="emergency",
        entity_id=request_id,
        message="Patient picked up, transporting to hospital",
    ))
    db.commit()
    db.refresh(emergency)

    await ws_manager.send_to_channel("emergencies", {
        "type": "patient_picked_up",
        "data": EmergencyResponse.model_validate(emergency).model_dump(mode="json"),
    })
    return emergency


@router.post("/{request_id}/complete", response_model=EmergencyResponse)
async def complete_emergency(request_id: str, db: Session = Depends(get_db)):
    """Mark emergency as completed (arrived at hospital)."""
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == request_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")

    emergency.status = EmergencyStatus.COMPLETED
    emergency.completed_at = datetime.now(timezone.utc)

    if emergency.ambulance_id:
        ambulance = db.query(Ambulance).filter(Ambulance.id == emergency.ambulance_id).first()
        if ambulance:
            ambulance.status = AmbulanceStatus.AVAILABLE

    db.add(SystemEvent(
        event_type="emergency_completed",
        severity="info",
        source="api",
        entity_type="emergency",
        entity_id=request_id,
        message="Emergency completed. Patient delivered to hospital.",
    ))
    db.commit()
    db.refresh(emergency)

    await ws_manager.send_to_channel("emergencies", {
        "type": "emergency_completed",
        "data": EmergencyResponse.model_validate(emergency).model_dump(mode="json"),
    })
    return emergency
