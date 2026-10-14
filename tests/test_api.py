"""
End-to-End API Integration Tests for Aegis Flow.
"""

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database.db import init_db
from backend.app.database.seed import seed_database

# Ensure database tables and seed data exist for test execution
init_db()
seed_database()

client = TestClient(app)


def test_system_health():
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["database"] == "connected"
    assert "active_emergencies" in data
    assert "online_signals" in data


def test_auth_and_login():
    import uuid
    uname = f"test_{uuid.uuid4().hex[:6]}"
    reg_res = client.post("/api/auth/register", json={
        "username": uname,
        "password": "Password123!",
        "full_name": "Test Operator",
        "role": "admin",
        "phone": "+91-9999999999"
    })
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert "access_token" in reg_data

    # Login
    login_res = client.post("/api/auth/login", json={
        "username": uname,
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


def test_emergency_lifecycle():
    # 1. Create emergency
    create_res = client.post("/api/emergencies", json={
        "emergency_type": "accident",
        "severity": "high",
        "description": "Two vehicle collision on FC road",
        "patient_name": "Anita Sharma",
        "patient_phone": "+91-9876543210",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "address": "Good Luck Chowk, Pune"
    })
    assert create_res.status_code == 201
    em_data = create_res.json()
    em_id = em_data["id"]
    assert em_data["status"] == "pending"

    # 2. List emergencies
    list_res = client.get("/api/emergencies")
    assert list_res.status_code == 200
    assert any(e["id"] == em_id for e in list_res.json())

    # 3. Auto-assign nearest ambulance
    assign_res = client.post(f"/api/emergencies/{em_id}/auto-assign")
    assert assign_res.status_code == 200
    assigned = assign_res.json()
    assert assigned["status"] in ["assigned", "no_ambulance"]

    # 4. Mark Pickup
    if assigned["status"] == "assigned":
        pickup_res = client.post(f"/api/emergencies/{em_id}/pickup")
        assert pickup_res.status_code == 200
        assert pickup_res.json()["status"] == "picked_up"

        # 5. Complete emergency
        comp_res = client.post(f"/api/emergencies/{em_id}/complete")
        assert comp_res.status_code == 200
        assert comp_res.json()["status"] == "completed"


def test_traffic_signals_and_override():
    # List signals
    sig_res = client.get("/api/signals")
    assert sig_res.status_code == 200
    signals = sig_res.json()
    assert len(signals) > 0
    sig_id = signals[0]["id"]

    # Manual override to force red
    override_res = client.post(f"/api/signals/{sig_id}/override", json={
        "action": "force_red",
        "reason": "Test safety manual hold"
    })
    assert override_res.status_code == 200
    assert override_res.json()["manual_override"] is True

    # Release manual override
    release_res = client.post(f"/api/signals/{sig_id}/override", json={
        "action": "force_normal",
        "reason": "Release back to autonomous scheduling"
    })
    assert release_res.status_code == 200
    assert release_res.json()["manual_override"] is False


def test_ai_analysis_endpoint():
    # Create emergency
    create_res = client.post("/api/emergencies", json={
        "emergency_type": "stroke",
        "severity": "critical",
        "patient_name": "Vijay Deshmukh",
        "latitude": 18.5204,
        "longitude": 73.8567,
    })
    em_id = create_res.json()["id"]

    # Run AI Analysis
    ai_res = client.post("/api/ai/analyze", json={
        "emergency_id": em_id,
        "ambulance_latitude": 18.5170,
        "ambulance_longitude": 73.8520,
        "ambulance_speed_kmh": 45.0,
    })
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert ai_data["priority_score"] is not None
    assert ai_data["eta_minutes"] is not None
    assert "explanation" in ai_data
    assert len(ai_data["explanation"]) > 10

    # Retrieve AI decisions
    dec_res = client.get("/api/ai/decisions")
    assert dec_res.status_code == 200
    assert len(dec_res.json()) > 0
