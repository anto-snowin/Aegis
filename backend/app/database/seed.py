"""
Aegis Flow - Database Seed Script
Creates demo data for hackathon demonstration.
All data is clearly labelled as simulated/demo.
"""

from datetime import datetime, timezone
from backend.app.services.auth import hash_password
from backend.app.database.db import SessionLocal, init_db
from backend.app.models.models import (
    User, Ambulance, Hospital, TrafficSignal, UserRole,
    AmbulanceStatus, SignalState, SignalPhase
)


def seed_database():
    """Populate database with demo data for hackathon demonstration."""
    init_db()
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(User).count() > 0:
            print("[SEED] Database already contains data. Skipping seed.")
            return

        print("[SEED] Seeding database with demo data...")

        # ─── Users ─────────────────────────────────────
        users = [
            User(
                id="user-patient-001",
                username="patient1",
                hashed_password=hash_password("demo1234"),
                full_name="Rahul Sharma",
                role=UserRole.PATIENT,
                phone="+91-9876543210",
            ),
            User(
                id="user-driver-001",
                username="driver1",
                hashed_password=hash_password("demo1234"),
                full_name="Amit Kumar",
                role=UserRole.DRIVER,
                phone="+91-9876543211",
            ),
            User(
                id="user-driver-002",
                username="driver2",
                hashed_password=hash_password("demo1234"),
                full_name="Priya Singh",
                role=UserRole.DRIVER,
                phone="+91-9876543212",
            ),
            User(
                id="user-hospital-001",
                username="hospital1",
                hashed_password=hash_password("demo1234"),
                full_name="City Hospital Command",
                role=UserRole.HOSPITAL,
                phone="+91-9876543213",
            ),
            User(
                id="user-traffic-001",
                username="traffic1",
                hashed_password=hash_password("demo1234"),
                full_name="Traffic Control Operator",
                role=UserRole.TRAFFIC,
                phone="+91-9876543214",
            ),
            User(
                id="user-admin-001",
                username="admin",
                hashed_password=hash_password("admin1234"),
                full_name="System Administrator",
                role=UserRole.ADMIN,
            ),
        ]

        for user in users:
            db.add(user)
        db.flush()

        # ─── Hospitals (Demo locations in Pune, India) ─
        hospitals = [
            Hospital(
                id="hospital-001",
                name="City General Hospital",
                latitude=18.5204,
                longitude=73.8567,
                address="123 MG Road, Pune, Maharashtra",
                phone="+91-20-26161000",
                emergency_department=True,
                available_beds=15,
            ),
            Hospital(
                id="hospital-002",
                name="Sahyadri Super Specialty Hospital",
                latitude=18.5074,
                longitude=73.8278,
                address="456 Deccan Road, Pune, Maharashtra",
                phone="+91-20-67211000",
                emergency_department=True,
                available_beds=8,
            ),
            Hospital(
                id="hospital-003",
                name="Ruby Hall Clinic",
                latitude=18.5362,
                longitude=73.8810,
                address="789 Sassoon Road, Pune, Maharashtra",
                phone="+91-20-26163391",
                emergency_department=True,
                available_beds=12,
            ),
        ]

        for hospital in hospitals:
            db.add(hospital)
        db.flush()

        # ─── Ambulances ────────────────────────────────
        ambulances = [
            Ambulance(
                id="amb-001",
                vehicle_number="MH-12-AE-1001",
                driver_id="user-driver-001",
                driver_name="Amit Kumar",
                status=AmbulanceStatus.AVAILABLE,
                latitude=18.5150,
                longitude=73.8500,
                is_active=True,
            ),
            Ambulance(
                id="amb-002",
                vehicle_number="MH-12-AE-1002",
                driver_id="user-driver-002",
                driver_name="Priya Singh",
                status=AmbulanceStatus.AVAILABLE,
                latitude=18.5250,
                longitude=73.8700,
                is_active=True,
            ),
            Ambulance(
                id="amb-003",
                vehicle_number="MH-12-AE-1003",
                driver_name="Demo Driver 3",
                status=AmbulanceStatus.OFF_DUTY,
                latitude=18.5100,
                longitude=73.8400,
                is_active=True,
            ),
        ]

        for ambulance in ambulances:
            db.add(ambulance)
        db.flush()

        # ─── Traffic Signals (Demo intersections along a route) ─
        signals = [
            TrafficSignal(
                id="signal-001",
                name="Junction 1 - MG Road / FC Road",
                intersection_name="MG Road × FC Road",
                latitude=18.5180,
                longitude=73.8520,
                state=SignalState.NORMAL,
                current_phase=SignalPhase.GREEN,
                cycle_time_seconds=90,
                controller_id="esp32-001",
                mqtt_topic="aegis/signal/signal-001/command",
                is_online=True,
            ),
            TrafficSignal(
                id="signal-002",
                name="Junction 2 - FC Road / JM Road",
                intersection_name="FC Road × JM Road",
                latitude=18.5210,
                longitude=73.8550,
                state=SignalState.NORMAL,
                current_phase=SignalPhase.RED,
                cycle_time_seconds=90,
                controller_id="esp32-002",
                mqtt_topic="aegis/signal/signal-002/command",
                is_online=True,
            ),
            TrafficSignal(
                id="signal-003",
                name="Junction 3 - JM Road / University Road",
                intersection_name="JM Road × University Road",
                latitude=18.5230,
                longitude=73.8580,
                state=SignalState.NORMAL,
                current_phase=SignalPhase.GREEN,
                cycle_time_seconds=120,
                controller_id="esp32-003",
                mqtt_topic="aegis/signal/signal-003/command",
                is_online=True,
            ),
            TrafficSignal(
                id="signal-004",
                name="Junction 4 - Near City Hospital",
                intersection_name="University Road × Hospital Lane",
                latitude=18.5195,
                longitude=73.8560,
                state=SignalState.NORMAL,
                current_phase=SignalPhase.RED,
                cycle_time_seconds=90,
                controller_id="esp32-004",
                mqtt_topic="aegis/signal/signal-004/command",
                is_online=True,
            ),
        ]

        for signal in signals:
            db.add(signal)

        db.commit()
        print("[SEED] [OK] Database seeded successfully!")
        print(f"  - {len(users)} users (login: any username / demo1234)")
        print(f"  - {len(hospitals)} hospitals")
        print(f"  - {len(ambulances)} ambulances")
        print(f"  - {len(signals)} traffic signals")

    except Exception as e:
        db.rollback()
        print(f"[SEED] [ERROR] Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
