"""
Aegis Flow - Ambulance API Routes
Handles ambulance status, GPS location updates, and driver actions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from backend.app.database.db import get_db
from backend.app.models.models import (
    Ambulance, AmbulanceLocation, EmergencyRequest, SystemEvent,
    AmbulanceStatus, EmergencyStatus
)
from backend.app.schemas.schemas import AmbulanceResponse, LocationUpdate
from backend.app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/ambulances", tags=["Ambulances"])


@router.get("", response_model=list[AmbulanceResponse])
def list_ambulances(db: Session = Depends(get_db)):
    """List all ambulances."""
    return db.query(Ambulance).filter(Ambulance.is_active == True).all()


@router.get("/{ambulance_id}", response_model=AmbulanceResponse)
def get_ambulance(ambulance_id: str, db: Session = Depends(get_db)):
    """Get specific ambulance details."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")
    return ambulance


@router.post("/{ambulance_id}/accept", response_model=AmbulanceResponse)
async def accept_assignment(ambulance_id: str, db: Session = Depends(get_db)):
    """Driver accepts the emergency assignment."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")
    if ambulance.status != AmbulanceStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="No pending assignment to accept")

    ambulance.status = AmbulanceStatus.EN_ROUTE

    # Update emergency status
    emergency = db.query(EmergencyRequest).filter(
        EmergencyRequest.ambulance_id == ambulance_id,
        EmergencyRequest.status == EmergencyStatus.ASSIGNED,
    ).first()
    if emergency:
        emergency.status = EmergencyStatus.ACCEPTED
        emergency.accepted_at = datetime.now(timezone.utc)

    db.add(SystemEvent(
        event_type="assignment_accepted",
        severity="info",
        source="driver",
        entity_type="ambulance",
        entity_id=ambulance_id,
        message=f"Driver {ambulance.driver_name} accepted assignment",
    ))
    db.commit()
    db.refresh(ambulance)

    await ws_manager.send_to_channel("emergencies", {
        "type": "assignment_accepted",
        "ambulance_id": ambulance_id,
        "data": AmbulanceResponse.model_validate(ambulance).model_dump(mode="json"),
    })
    return ambulance


@router.post("/{ambulance_id}/reject")
async def reject_assignment(ambulance_id: str, db: Session = Depends(get_db)):
    """Driver rejects the emergency assignment."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    ambulance.status = AmbulanceStatus.AVAILABLE

    emergency = db.query(EmergencyRequest).filter(
        EmergencyRequest.ambulance_id == ambulance_id,
        EmergencyRequest.status == EmergencyStatus.ASSIGNED,
    ).first()
    if emergency:
        emergency.status = EmergencyStatus.PENDING
        emergency.ambulance_id = None
        emergency.assigned_at = None

    db.add(SystemEvent(
        event_type="assignment_rejected",
        severity="warning",
        source="driver",
        entity_type="ambulance",
        entity_id=ambulance_id,
        message=f"Driver {ambulance.driver_name} rejected assignment",
    ))
    db.commit()
    return {"status": "rejected", "message": "Assignment rejected. Emergency returned to pending."}


@router.post("/{ambulance_id}/location", response_model=AmbulanceResponse)
async def update_location(
    ambulance_id: str,
    data: LocationUpdate,
    db: Session = Depends(get_db),
):
    """Update ambulance GPS location."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    now = datetime.now(timezone.utc)

    # Update current position
    ambulance.latitude = data.latitude
    ambulance.longitude = data.longitude
    ambulance.speed_kmh = data.speed_kmh
    ambulance.heading = data.heading
    ambulance.last_gps_update = now

    # Store in location history
    location = AmbulanceLocation(
        ambulance_id=ambulance_id,
        latitude=data.latitude,
        longitude=data.longitude,
        speed_kmh=data.speed_kmh,
        heading=data.heading,
        timestamp=now,
    )
    db.add(location)
    db.commit()
    db.refresh(ambulance)

    # Broadcast location update
    await ws_manager.send_to_channel("tracking", {
        "type": "location_update",
        "ambulance_id": ambulance_id,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "speed_kmh": data.speed_kmh,
        "heading": data.heading,
        "timestamp": now.isoformat(),
    })

    return ambulance


@router.post("/{ambulance_id}/toggle-duty")
async def toggle_duty(ambulance_id: str, db: Session = Depends(get_db)):
    """Toggle ambulance between available and off-duty."""
    ambulance = db.query(Ambulance).filter(Ambulance.id == ambulance_id).first()
    if not ambulance:
        raise HTTPException(status_code=404, detail="Ambulance not found")

    if ambulance.status == AmbulanceStatus.OFF_DUTY:
        ambulance.status = AmbulanceStatus.AVAILABLE
        msg = "Ambulance now on duty"
    elif ambulance.status == AmbulanceStatus.AVAILABLE:
        ambulance.status = AmbulanceStatus.OFF_DUTY
        msg = "Ambulance now off duty"
    else:
        raise HTTPException(status_code=400, detail=f"Cannot toggle: ambulance is {ambulance.status.value}")

    db.commit()
    return {"status": ambulance.status.value, "message": msg}
