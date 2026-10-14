"""
Aegis Flow - AI Traffic Analyzer
Analyzes traffic density, queue lengths, and optimal queue clearance timings.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone


class TrafficAnalyzer:
    """
    Evaluates traffic congestion levels and calculates the advance warning window
    needed to clear intersection queues before an emergency vehicle arrives.
    """

    @classmethod
    def estimate_corridor_density(
        cls,
        latitude: float,
        longitude: float,
        hour_of_day: int = None,
        manual_override: float = None,
    ) -> Dict[str, Any]:
        """
        Calculates traffic congestion index (0.0 to 1.0) for a given area/corridor.
        Uses time-of-day traffic modeling with peak rush hours.
        """
        if manual_override is not None:
            density = min(1.0, max(0.05, manual_override))
        else:
            if hour_of_day is None:
                hour_of_day = datetime.now(timezone.utc).hour

            # Rush hour modeling: 8-10 AM (heavy), 17-20 PM (heavy), late night (light)
            if 8 <= hour_of_day <= 10 or 17 <= hour_of_day <= 20:
                base_density = 0.75
            elif 11 <= hour_of_day <= 16:
                base_density = 0.45
            elif 21 <= hour_of_day <= 23:
                base_density = 0.30
            else:
                base_density = 0.15

            # Spatial pseudo-variance based on coordinates
            coord_variance = (math_hash(latitude, longitude) % 20) / 100.0 - 0.10
            density = min(0.95, max(0.10, base_density + coord_variance))

        # Categorize
        if density > 0.70:
            level = "HEAVY"
            color = "#ef4444"
        elif density > 0.40:
            level = "MODERATE"
            color = "#f59e0b"
        else:
            level = "LIGHT"
            color = "#22c55e"

        # Calculate queue length per lane in vehicles
        avg_queue_vehicles = round(density * 18)
        # Average time to discharge a queue of N cars: ~2 seconds startup + ~1.8s per vehicle
        queue_clearance_seconds = round(3.0 + avg_queue_vehicles * 1.8)

        return {
            "density_index": round(density, 2),
            "congestion_level": level,
            "color": color,
            "estimated_queue_vehicles": avg_queue_vehicles,
            "recommended_prepare_seconds": max(10, queue_clearance_seconds),
            "camera_verified": False,
        }

    @classmethod
    def calculate_approach_timings(
        cls,
        distance_to_signal_meters: float,
        speed_kmh: float,
        density_index: float,
    ) -> Dict[str, Any]:
        """
        Determines when the signal should switch from NORMAL to PREPARE,
        then to EMERGENCY_PRIORITY green wave.
        """
        speed_mps = max(5.0, (speed_kmh or 35.0) * (1000.0 / 3600.0))
        time_to_arrival_sec = distance_to_signal_meters / speed_mps

        # Required queue flush window
        queue_clear_sec = 8.0 + (density_index * 15.0)

        # Trigger prepare when arrival is within (queue_clear_sec + 8 seconds)
        trigger_prepare_sec = queue_clear_sec + 8.0

        should_prepare = time_to_arrival_sec <= trigger_prepare_sec and distance_to_signal_meters > 80.0
        should_emergency = time_to_arrival_sec <= (queue_clear_sec + 2.0) or distance_to_signal_meters <= 120.0
        passed_intersection = distance_to_signal_meters < 15.0

        return {
            "time_to_arrival_sec": round(time_to_arrival_sec, 1),
            "queue_clearance_needed_sec": round(queue_clear_sec, 1),
            "should_prepare": should_prepare,
            "should_emergency": should_emergency,
            "passed_intersection": passed_intersection,
        }


def math_hash(lat: float, lon: float) -> int:
    """Deterministic integer hash from coordinates for synthetic variance."""
    val = int(abs(lat * 10000 + lon * 100))
    return val % 100
