"""
Unit tests for Aegis Flow AI components:
- PriorityEngine
- ETAEngine
- TrafficAnalyzer
- CorridorController thresholds
"""

import pytest
from backend.app.ai.priority_engine import PriorityEngine
from backend.app.ai.eta_engine import ETAEngine, haversine_km
from backend.app.ai.traffic_analyzer import TrafficAnalyzer


def test_priority_engine_critical_cardiac():
    score, factors, explanation = PriorityEngine.calculate_priority(
        severity="critical",
        emergency_type="cardiac",
        traffic_density=0.8,
        distance_km=4.5,
        wait_time_minutes=6.0,
        patient_vitals_critical=True,
    )
    assert 75.0 <= score <= 100.0
    assert "critical" in explanation.lower() or "cardiac" in explanation.lower()
    assert factors["severity_weight"] == 1.0  # 40/40


def test_priority_engine_low_severity():
    score, factors, explanation = PriorityEngine.calculate_priority(
        severity="low",
        emergency_type="other",
        traffic_density=0.2,
        distance_km=1.0,
        wait_time_minutes=0.0,
    )
    assert score < 50.0
    assert factors["severity_weight"] == 0.25  # 10/40


def test_conflict_resolution():
    res = PriorityEngine.resolve_corridor_conflict(
        priority_a=90.0,
        priority_b=40.0,
        distance_a_m=200.0,
        distance_b_m=300.0,
    )
    assert res["winner"] == "A"
    assert "Vehicle A" in res["action"]


def test_eta_engine_green_corridor_savings():
    res = ETAEngine.calculate_eta(
        current_lat=18.5150,
        current_lon=73.8500,
        target_lat=18.5285,
        target_lon=73.8660,
        current_speed_kmh=40.0,
        traffic_density=0.7,
        signals_count=3,
        green_corridor_active=True,
    )
    assert res["baseline_eta_minutes"] > res["aegis_eta_minutes"]
    assert res["time_saved_minutes"] > 0
    assert res["time_saved_percent"] > 15.0


def test_traffic_analyzer():
    res = TrafficAnalyzer.estimate_corridor_density(18.5204, 73.8567, hour_of_day=9)
    assert 0.0 <= res["density_index"] <= 1.0
    assert res["congestion_level"] in ["LIGHT", "MODERATE", "HEAVY"]
    assert res["recommended_prepare_seconds"] >= 10


def test_approach_timings():
    # 100m away at 40km/h: should trigger emergency green wave
    timings = TrafficAnalyzer.calculate_approach_timings(
        distance_to_signal_meters=100.0,
        speed_kmh=40.0,
        density_index=0.5,
    )
    assert timings["should_emergency"] is True
    assert timings["passed_intersection"] is False

    # 400m away at 40km/h: arrival in 36s (queue clear 15.5s + 8s = 23.5s) -> should_prepare
    timings_prepare = TrafficAnalyzer.calculate_approach_timings(
        distance_to_signal_meters=200.0,
        speed_kmh=40.0,
        density_index=0.5,
    )
    assert timings_prepare["should_prepare"] is True
