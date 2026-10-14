"""
Aegis Flow - SQLAlchemy Database Models
All entities required for emergency response coordination.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from backend.app.database.db import Base


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


# ─── Enums ─────────────────────────────────────────────

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DRIVER = "driver"
    HOSPITAL = "hospital"
    TRAFFIC = "traffic"
    ADMIN = "admin"


class EmergencyType(str, enum.Enum):
    CARDIAC = "cardiac"
    ACCIDENT = "accident"
    STROKE = "stroke"
    BREATHING = "breathing"
    BURN = "burn"
    PREGNANCY = "pregnancy"
    OTHER = "other"


class EmergencySeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmergencyStatus(str, enum.Enum):
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


class AmbulanceStatus(str, enum.Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    TRANSPORTING = "transporting"
    AT_HOSPITAL = "at_hospital"
    OFF_DUTY = "off_duty"


class SignalState(str, enum.Enum):
    NORMAL = "normal"
    PREPARE = "prepare"
    EMERGENCY_PRIORITY = "emergency_priority"
    CLEARANCE = "clearance"
    MANUAL = "manual"
    OFFLINE = "offline"


class SignalPhase(str, enum.Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    ALL_RED = "all_red"


# ─── Models ────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    role = Column(SQLEnum(UserRole), nullable=False)
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    emergency_requests = relationship("EmergencyRequest", back_populates="requester")


class EmergencyRequest(Base):
    __tablename__ = "emergency_requests"

    id = Column(String, primary_key=True, default=generate_uuid)
    requester_id = Column(String, ForeignKey("users.id"), nullable=True)
    emergency_type = Column(SQLEnum(EmergencyType), nullable=False)
    severity = Column(SQLEnum(EmergencySeverity), nullable=False, default=EmergencySeverity.HIGH)
    description = Column(Text)
    patient_name = Column(String(200))
    patient_phone = Column(String(20))

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))

    # Assignment
    status = Column(SQLEnum(EmergencyStatus), default=EmergencyStatus.PENDING, nullable=False)
    ambulance_id = Column(String, ForeignKey("ambulances.id"), nullable=True)
    hospital_id = Column(String, ForeignKey("hospitals.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    assigned_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    picked_up_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # ETA
    estimated_arrival_minutes = Column(Float, nullable=True)

    # Relationships
    requester = relationship("User", back_populates="emergency_requests")
    ambulance = relationship("Ambulance", back_populates="emergency_requests")
    hospital = relationship("Hospital", back_populates="emergency_requests")
    ai_decisions = relationship("AIDecision", back_populates="emergency_request")


class Ambulance(Base):
    __tablename__ = "ambulances"

    id = Column(String, primary_key=True, default=generate_uuid)
    vehicle_number = Column(String(50), unique=True, nullable=False)
    driver_id = Column(String, ForeignKey("users.id"), nullable=True)
    driver_name = Column(String(200))
    status = Column(SQLEnum(AmbulanceStatus), default=AmbulanceStatus.AVAILABLE, nullable=False)

    # Current location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed_kmh = Column(Float, default=0)
    heading = Column(Float, default=0)
    last_gps_update = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    emergency_requests = relationship("EmergencyRequest", back_populates="ambulance")
    location_history = relationship("AmbulanceLocation", back_populates="ambulance")


class AmbulanceLocation(Base):
    __tablename__ = "ambulance_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ambulance_id = Column(String, ForeignKey("ambulances.id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0)
    heading = Column(Float, default=0)
    timestamp = Column(DateTime, default=utcnow)

    # Relationships
    ambulance = relationship("Ambulance", back_populates="location_history")


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(300), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))
    phone = Column(String(20))
    emergency_department = Column(Boolean, default=True)
    available_beds = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    emergency_requests = relationship("EmergencyRequest", back_populates="hospital")


class TrafficSignal(Base):
    __tablename__ = "traffic_signals"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    intersection_name = Column(String(300))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Current state
    state = Column(SQLEnum(SignalState), default=SignalState.NORMAL, nullable=False)
    current_phase = Column(SQLEnum(SignalPhase), default=SignalPhase.RED)
    cycle_time_seconds = Column(Integer, default=90)

    # Controller
    controller_id = Column(String(100))
    mqtt_topic = Column(String(200))
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, nullable=True)

    # Override
    manual_override = Column(Boolean, default=False)
    override_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    # Relationships
    commands = relationship("SignalCommand", back_populates="signal")


class SignalCommand(Base):
    __tablename__ = "signal_commands"

    id = Column(String, primary_key=True, default=generate_uuid)
    signal_id = Column(String, ForeignKey("traffic_signals.id"), nullable=False)
    emergency_id = Column(String, ForeignKey("emergency_requests.id"), nullable=True)
    ambulance_id = Column(String, nullable=True)

    # Command details
    requested_state = Column(SQLEnum(SignalState), nullable=False)
    requested_phase = Column(SQLEnum(SignalPhase), nullable=True)
    reason = Column(Text)
    priority_score = Column(Float, nullable=True)

    # Status
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    actual_state = Column(SQLEnum(SignalState), nullable=True)
    expired = Column(Boolean, default=False)

    # Timing
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    signal = relationship("TrafficSignal", back_populates="commands")


class AIDecision(Base):
    __tablename__ = "ai_decisions"

    id = Column(String, primary_key=True, default=generate_uuid)
    emergency_id = Column(String, ForeignKey("emergency_requests.id"), nullable=False)
    ambulance_id = Column(String, nullable=True)
    signal_id = Column(String, nullable=True)

    # Decision details
    decision_type = Column(String(50), nullable=False)  # eta, priority, route, corridor
    priority_score = Column(Float, nullable=True)
    eta_minutes = Column(Float, nullable=True)
    traffic_density = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)

    # Explanation
    explanation = Column(Text)
    factors = Column(Text)  # JSON string of individual factor scores
    recommendation = Column(Text)

    # Data quality
    gps_fresh = Column(Boolean, default=True)
    camera_available = Column(Boolean, default=False)
    data_quality_score = Column(Float, default=0.5)

    created_at = Column(DateTime, default=utcnow)

    # Relationships
    emergency_request = relationship("EmergencyRequest", back_populates="ai_decisions")


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False)  # emergency_created, signal_changed, etc.
    severity = Column(String(20), default="info")  # info, warning, error, critical
    source = Column(String(100))  # api, ai, mqtt, signal, system
    entity_type = Column(String(50), nullable=True)  # emergency, ambulance, signal
    entity_id = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON string for extra data
    created_at = Column(DateTime, default=utcnow)
