"""
Aegis Flow - AI ETA Engine
Dynamic arrival estimation taking into account speed, congestion, and signal priority savings.
"""

from typing import Dict, Any, Tuple
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance in km between two GPS coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class ETAEngine:
    """
    Computes accurate dynamic ETAs and predicts emergency time savings
    delivered by the Aegis Flow dynamic green corridor.
    """

    # Average signal red wait time per intersection without preemption: 45 seconds
    AVERAGE_SIGNAL_DELAY_SECONDS = 45.0
    # Average signal wait time with Aegis green priority: 4 seconds
    AEGIS_SIGNAL_DELAY_SECONDS = 4.0

    @classmethod
    def calculate_eta(
        cls,
        current_lat: float,
        current_lon: float,
        target_lat: float,
        target_lon: float,
        current_speed_kmh: float = 0.0,
        traffic_density: float = 0.5,
        signals_count: int = 3,
        green_corridor_active: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculates baseline ETA vs Aegis-optimized ETA.
        """
        distance_km = haversine_km(current_lat, current_lon, target_lat, target_lon)
        # Urban routing factor (roads are ~1.25x haversine straight line)
        road_distance_km = max(0.2, distance_km * 1.25)

        # Baseline urban cruising speed (adjusted by congestion)
        # Low traffic: 48 km/h, Heavy traffic: 22 km/h
        baseline_speed_kmh = max(18.0, 50.0 - (traffic_density * 30.0))

        # If vehicle is actively moving fast, blend with actual measured speed
        if current_speed_kmh and current_speed_kmh > 15.0:
            effective_speed = 0.6 * baseline_speed_kmh + 0.4 * min(current_speed_kmh, 80.0)
        else:
            effective_speed = baseline_speed_kmh

        # Raw driving time in minutes
        raw_driving_minutes = (road_distance_km / effective_speed) * 60.0

        # Intersection wait times without priority
        baseline_signal_delay_min = (signals_count * cls.AVERAGE_SIGNAL_DELAY_SECONDS) / 60.0
        baseline_eta_min = raw_driving_minutes + baseline_signal_delay_min

        # Intersection wait times with Aegis green corridor
        if green_corridor_active:
            aegis_signal_delay_min = (signals_count * cls.AEGIS_SIGNAL_DELAY_SECONDS) / 60.0
            # Green wave also increases effective cruising speed by ~15% due to fewer stop-and-gos
            aegis_driving_minutes = raw_driving_minutes * 0.88
            aegis_eta_min = aegis_driving_minutes + aegis_signal_delay_min
        else:
            aegis_eta_min = baseline_eta_min

        time_saved_min = max(0.0, baseline_eta_min - aegis_eta_min)
        percent_saved = round((time_saved_min / baseline_eta_min) * 100, 1) if baseline_eta_min > 0 else 0.0

        return {
            "distance_km": round(road_distance_km, 2),
            "straight_line_km": round(distance_km, 2),
            "effective_speed_kmh": round(effective_speed, 1),
            "baseline_eta_minutes": round(baseline_eta_min, 1),
            "aegis_eta_minutes": round(aegis_eta_min, 1),
            "time_saved_minutes": round(time_saved_min, 1),
            "time_saved_percent": percent_saved,
            "signals_cleared": signals_count,
            "green_corridor_active": green_corridor_active,
        }
