"""
Aegis Flow — Computer Vision Traffic Density Simulator
Simulates intersection camera feeds and vehicle detection for AI traffic analysis.
"""

import time
import random
import requests
import json

API_BASE = "http://localhost:8000/api"

class CameraTrafficDetector:
    """
    Simulates intersection camera vehicle detection (YOLO/OpenCV compatible).
    Calculates vehicle counts, queue lengths, and reports congestion density.
    """

    def __init__(self, intersection_name="Good Luck Chowk (North Approach)", camera_id="CAM-01"):
        self.intersection_name = intersection_name
        self.camera_id = camera_id
        self.lane_capacity = 25 # Max vehicles in visible approach zone

    def generate_synthetic_detection(self):
        """
        Generates simulated vehicle classification counts:
        cars, buses, trucks, motorcycles, ambulances.
        """
        base_cars = random.randint(6, 18)
        buses = random.randint(0, 2)
        trucks = random.randint(0, 1)
        two_wheelers = random.randint(4, 12)

        # Weighted vehicle equivalence units (PCU - Passenger Car Units)
        # Car = 1.0, Bus = 2.5, Truck = 2.0, Two Wheeler = 0.5
        total_pcu = (base_cars * 1.0) + (buses * 2.5) + (trucks * 2.0) + (two_wheelers * 0.5)
        density_ratio = min(1.0, total_pcu / self.lane_capacity)

        return {
            "camera_id": self.camera_id,
            "intersection": self.intersection_name,
            "counts": {
                "cars": base_cars,
                "buses": buses,
                "trucks": trucks,
                "motorcycles": two_wheelers,
                "total_vehicles": base_cars + buses + trucks + two_wheelers,
            },
            "pcu_units": round(total_pcu, 1),
            "density_index": round(density_ratio, 2),
            "congestion_level": "HEAVY" if density_ratio > 0.7 else ("MODERATE" if density_ratio > 0.4 else "LIGHT"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def run_detection_loop(self, iterations=10, interval_sec=2):
        print("=" * 60)
        print(f"  AEGIS FLOW — CAMERA VEHICLE DETECTOR ({self.camera_id})")
        print(f"  Monitoring: {self.intersection_name}")
        print("=" * 60)

        for i in range(iterations):
            detection = self.generate_synthetic_detection()
            counts = detection["counts"]
            print(f"[{time.strftime('%H:%M:%S')}] Detected: {counts['total_vehicles']:2d} vehicles "
                  f"({counts['cars']} cars, {counts['buses']} buses, {counts['motorcycles']} bikes) "
                  f"| Density: {int(detection['density_index']*100)}% [{detection['congestion_level']}]")
            time.sleep(interval_sec)

        print("\n✓ Camera detection stream completed.")


if __name__ == "__main__":
    detector = CameraTrafficDetector()
    detector.run_detection_loop()
