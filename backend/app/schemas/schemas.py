"""
Aegis Flow - Pydantic Schemas for API validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ─── Enums (mirroring SQLAlchemy enums for API) ────────

class UserRoleEnum(str, Enum):
    PATIENT = "patient"
    DRIVER = "driver"
    HOSPITAL = "hospital"
    TRAFFIC = "traffic"
    ADMIN = "admin"


class EmergencyTypeEnum(str, Enum):
    CARDIAC = "cardiac"
    ACCIDENT = "accident"
    STROKE = "stroke"
    BREATHING = "breathing"
    BURN = "burn"
    PREGNANCY = "pregnancy"
    OTHER = "other"


class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmergencyStatusEnum(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    EN_ROUTE = "en_route"
    PICKED_UP = "picked_up"
    TRANSPORTING = "transporting"
    ARRIVED = "arrived"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_AMBULANCE = "no_ambulance"


class AmbulanceStatusEnum(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    TRANSPORTING = "transporting"
    AT_HOSPITAL = "at_hospital"
    OFF_DUTY = "off_duty"


class SignalStateEnum(str, Enum):
    NORMAL = "normal"
    PREPARE = "prepare"
    EMERGENCY_PRIORITY = "emergency_priority"
    CLEARANCE = "clearance"
    MANUAL = "manual"
    OFFLINE = "offline"


class SignalPhaseEnum(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    ALL_RED = "all_red"


# ─── User Schemas ──────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4)
    full_name: Optional[str] = None
    role: UserRoleEnum
    phone: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    full_name: Optional[str]
    role: UserRoleEnum
    phone: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Emergency Schemas ─────────────────────────────────

class EmergencyCreate(BaseModel):
    emergency_type: EmergencyTypeEnum
    severity: SeverityEnum = SeverityEnum.HIGH
    description: Optional[str] = None
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class EmergencyResponse(BaseModel):
    id: str
    emergency_type: EmergencyTypeEnum
    severity: SeverityEnum
    description: Optional[str]
    patient_name: Optional[str]
    latitude: float
    longitude: float
    address: Optional[str]
    status: EmergencyStatusEnum
    ambulance_id: Optional[str]
    hospital_id: Optional[str]
    estimated_arrival_minutes: Optional[float]
    created_at: datetime
    assigned_at: Optional[datetime]
    accepted_at: Optional[datetime]
    picked_up_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmergencyAssign(BaseModel):
    ambulance_id: str
    hospital_id: Optional[str] = None


# ─── Ambulance Schemas ─────────────────────────────────

class AmbulanceResponse(BaseModel):
    id: str
    vehicle_number: str
    driver_name: Optional[str]
    status: AmbulanceStatusEnum
    latitude: Optional[float]
    longitude: Optional[float]
    speed_kmh: Optional[float]
    heading: Optional[float]
    last_gps_update: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: Optional[float] = Field(0, ge=0, le=200)
    heading: Optional[float] = Field(0, ge=0, le=360)


# ─── Hospital Schemas ──────────────────────────────────

class HospitalResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    address: Optional[str]
    phone: Optional[str]
    emergency_department: bool
    available_beds: int
    is_active: bool

    class Config:
        from_attributes = True


# ─── Traffic Signal Schemas ────────────────────────────

class SignalResponse(BaseModel):
    id: str
    name: str
    intersection_name: Optional[str]
    latitude: float
    longitude: float
    state: SignalStateEnum
    current_phase: Optional[SignalPhaseEnum]
    is_online: bool
    manual_override: bool
    last_heartbeat: Optional[datetime]

    class Config:
        from_attributes = True


class SignalCommandCreate(BaseModel):
    requested_state: SignalStateEnum
    requested_phase: Optional[SignalPhaseEnum] = None
    reason: str
    emergency_id: Optional[str] = None
    ambulance_id: Optional[str] = None
    priority_score: Optional[float] = None
    expiry_seconds: int = Field(default=60, ge=10, le=300)


class SignalCommandResponse(BaseModel):
    id: str
    signal_id: str
    requested_state: SignalStateEnum
    reason: str
    priority_score: Optional[float]
    acknowledged: bool
    expired: bool
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class SignalOverride(BaseModel):
    action: str = Field(..., pattern="^(enable_manual|disable_manual|force_normal|force_red)$")
    reason: str


# ─── AI Decision Schemas ──────────────────────────────

class AIAnalyzeRequest(BaseModel):
    emergency_id: str
    ambulance_latitude: Optional[float] = None
    ambulance_longitude: Optional[float] = None
    ambulance_speed_kmh: Optional[float] = None


class AIDecisionResponse(BaseModel):
    id: str
    emergency_id: str
    decision_type: str
    priority_score: Optional[float]
    eta_minutes: Optional[float]
    traffic_density: Optional[float]
    confidence: Optional[float]
    explanation: Optional[str]
    factors: Optional[str]
    recommendation: Optional[str]
    gps_fresh: bool
    data_quality_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── System Schemas ────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    mqtt: str
    ai_enabled: bool
    simulation_mode: bool
    active_emergencies: int
    online_signals: int
    available_ambulances: int
    timestamp: datetime


class SystemEventResponse(BaseModel):
    id: int
    event_type: str
    severity: str
    source: Optional[str]
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
