"""
Aegis Flow - System & Auth API Routes
Health check, authentication, and system status endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.database.db import get_db
from backend.app.models.models import (
    User, EmergencyRequest, Ambulance, TrafficSignal,
    EmergencyStatus, AmbulanceStatus, SystemEvent
)
from backend.app.schemas.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    HealthResponse, SystemEventResponse
)
from backend.app.services.auth import (
    hash_password, verify_password, create_access_token, require_auth
)

router = APIRouter()


# ─── Authentication ────────────────────────────────────

@router.post("/auth/register", response_model=TokenResponse, tags=["Auth"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        phone=data.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserResponse, tags=["Auth"])
def get_me(user: User = Depends(require_auth)):
    """Get current authenticated user."""
    return UserResponse.model_validate(user)


# ─── System Health ─────────────────────────────────────

@router.get("/system/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """System health check endpoint."""
    try:
        active_emergencies = db.query(EmergencyRequest).filter(
            EmergencyRequest.status.notin_([
                EmergencyStatus.COMPLETED,
                EmergencyStatus.CANCELLED,
            ])
        ).count()

        online_signals = db.query(TrafficSignal).filter(
            TrafficSignal.is_online == True
        ).count()

        available_ambulances = db.query(Ambulance).filter(
            Ambulance.status == AmbulanceStatus.AVAILABLE,
            Ambulance.is_active == True,
        ).count()

        db_status = "connected"
    except Exception:
        active_emergencies = 0
        online_signals = 0
        available_ambulances = 0
        db_status = "error"

    return HealthResponse(
        status="operational",
        version="1.0.0-prototype",
        database=db_status,
        mqtt="simulation",  # Updated when MQTT connects
        ai_enabled=True,
        simulation_mode=True,
        active_emergencies=active_emergencies,
        online_signals=online_signals,
        available_ambulances=available_ambulances,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/system/events", response_model=list[SystemEventResponse], tags=["System"])
def get_events(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent system events for audit log."""
    events = db.query(SystemEvent).order_by(
        SystemEvent.created_at.desc()
    ).limit(limit).all()
    return [SystemEventResponse.model_validate(e) for e in events]
