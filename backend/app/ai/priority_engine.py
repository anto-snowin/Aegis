"""
Aegis Flow - AI Priority Engine
Calculates dynamic priority scores (0-100) for emergency requests and signal preemption.
"""

from typing import Dict, Any, Tuple
import math


class PriorityEngine:
    """
    Computes explainable emergency priority scores based on:
    - Emergency severity and type
    - Patient condition / clinical indicators
    - Traffic density and congestion severity
    - Distance to hospital and patient
    - Temporal urgency (delay accumulated since call)
    """

    SEVERITY_WEIGHTS = {
        "critical": 40.0,
        "high": 30.0,
        "medium": 20.0,
        "low": 10.0,
    }

    EMERGENCY_TYPE_WEIGHTS = {
        "cardiac": 25.0,
        "stroke": 23.0,
        "breathing": 22.0,
        "accident": 20.0,
        "burn": 16.0,
        "pregnancy": 18.0,
        "other": 12.0,
    }

    @classmethod
    def calculate_priority(
        cls,
        severity: str,
        emergency_type: str,
        traffic_density: float = 0.5,
        distance_km: float = 3.0,
        wait_time_minutes: float = 0.0,
        patient_vitals_critical: bool = False,
    ) -> Tuple[float, Dict[str, float], str]:
        """
        Calculate total priority score between 0 and 100, factor breakdowns, and explanation.
        """
        # 1. Base severity score (0 to 40)
        sev_score = cls.SEVERITY_WEIGHTS.get(severity.lower(), 25.0)

        # 2. Emergency medical condition score (0 to 25)
        type_score = cls.EMERGENCY_TYPE_WEIGHTS.get(emergency_type.lower(), 15.0)
        if patient_vitals_critical:
            type_score = min(25.0, type_score + 5.0)

        # 3. Traffic congestion urgency bonus (0 to 15)
        # In heavy traffic, clearing signals is even more critical
        traffic_urgency = min(15.0, traffic_density * 15.0)

        # 4. Accumulated waiting delay penalty / urgency (0 to 12)
        # Adds urgency if waiting too long (e.g. +1 pt per 2 mins waiting, max 12)
        wait_urgency = min(12.0, wait_time_minutes * 0.5)

        # 5. Distance factor (0 to 8)
        # Closer distances need immediate swift clearing; longer distances need corridor setup
        dist_factor = min(8.0, max(2.0, distance_km * 0.8))

        # Total raw score
        raw_score = sev_score + type_score + traffic_urgency + wait_urgency + dist_factor
        score = min(100.0, max(0.0, round(raw_score, 1)))

        # Normalized factor contributions (0.0 to 1.0)
        factors = {
            "severity_weight": round(sev_score / 40.0, 2),
            "medical_urgency": round(type_score / 25.0, 2),
            "traffic_congestion_factor": round(traffic_density, 2),
            "delay_urgency": round(wait_urgency / 12.0, 2),
            "corridor_criticality": round(dist_factor / 8.0, 2),
        }

        # Generate human-readable explanation
        reasons = []
        if sev_score >= 35:
            reasons.append(f"Severity classified as {severity.upper()}")
        reasons.append(f"Medical category: {emergency_type.title()}")
        if traffic_density > 0.65:
            reasons.append(f"High traffic congestion along corridor ({int(traffic_density * 100)}%)")
        if wait_time_minutes >= 5.0:
            reasons.append(f"Accumulated response delay of {wait_time_minutes:.1f} min")
        if score >= 80:
            reasons.append("Eligible for maximum green corridor priority preempting all cross-traffic")
        elif score >= 60:
            reasons.append("Eligible for staged signal priority clearing queues in advance")
        else:
            reasons.append("Standard emergency transit with advisory signal timing")

        explanation = ". ".join(reasons) + "."

        return score, factors, explanation

    @classmethod
    def resolve_corridor_conflict(
        cls,
        priority_a: float,
        priority_b: float,
        distance_a_m: float,
        distance_b_m: float,
    ) -> Dict[str, Any]:
        """
        Resolves conflict if two emergency vehicles approach the same intersection.
        Returns winning ambulance decision and timing recommendations.
        """
        # Distance-weighted priority index
        weight_a = priority_a / max(10.0, distance_a_m)
        weight_b = priority_b / max(10.0, distance_b_m)

        winner = "A" if weight_a >= weight_b else "B"
        return {
            "winner": winner,
            "weight_a": round(weight_a, 4),
            "weight_b": round(weight_b, 4),
            "action": f"Grant green wave to Vehicle {winner} first; hold Vehicle {'B' if winner == 'A' else 'A'} at safe buffer distance.",
        }
