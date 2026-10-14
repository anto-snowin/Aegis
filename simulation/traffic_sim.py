"""
Aegis Flow — Multi-Agent Traffic & Ambulance Simulation
Demonstrates dynamic green corridor activation, multi-signal staging, and ETA calculation.
"""

import time
import requests
import math
import random
import sys

API_BASE = "http://localhost:8000/api"

# ANSI Colors for Terminal
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_RED     = "\033[91m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_BLUE    = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN    = "\033[96m"

# Demonstration Corridor Route (Pune, India - FC Road to Sancheti Hospital)
WAYPOINTS = [
    {"name": "Fergusson College Gate",     "lat": 18.5150, "lon": 73.8500, "speed": 40.0},
    {"name": "Dnyaneshwar Paduka Chowk",   "lat": 18.5175, "lon": 73.8525, "speed": 45.0},
    {"name": "Approaching Good Luck Chowk", "lat": 18.5190, "lon": 73.8545, "speed": 50.0},
    {"name": "Good Luck Chowk (Signal 1)",  "lat": 18.5204, "lon": 73.8567, "speed": 55.0}, # Sig 1
    {"name": "Modern College Road",        "lat": 18.5220, "lon": 73.8585, "speed": 52.0},
    {"name": "JM Road Jn (Signal 2)",      "lat": 18.5240, "lon": 73.8610, "speed": 48.0}, # Sig 2
    {"name": "COEP Flyover Approach",      "lat": 18.5260, "lon": 73.8635, "speed": 42.0},
    {"name": "Sancheti Hospital Gate",     "lat": 18.5285, "lon": 73.8660, "speed": 20.0}, # Destination
]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def check_backend():
    print(f"{C_CYAN}[SIM]{C_RESET} Connecting to Aegis Flow backend at {API_BASE}...")
    try:
        r = requests.get(f"{API_BASE}/system/health", timeout=3)
        if r.status_code == 200:
            data = r.json()
            print(f"{C_GREEN}✓ Backend Connected!{C_RESET} Status: {data['status']}, Signals: {data['online_signals']}, Ambulances: {data['available_ambulances']}")
            return True
        else:
            print(f"{C_RED}✗ Backend returned HTTP {r.status_code}{C_RESET}")
            return False
    except Exception as e:
        print(f"{C_RED}✗ Could not connect to backend ({e}). Make sure backend server is running!{C_RESET}")
        return False


def get_available_ambulance():
    r = requests.get(f"{API_BASE}/ambulances")
    ambulances = r.json()
    if not ambulances:
        return None
    # Pick first ambulance
    return ambulances[0]["id"]


def create_demo_emergency():
    print(f"\n{C_MAGENTA}🚨 Triggering High-Priority Cardiac Emergency Call...{C_RESET}")
    payload = {
        "emergency_type": "cardiac",
        "severity": "critical",
        "patient_name": "Ramesh Kulkarni",
        "patient_phone": "+91-9822012345",
        "latitude": 18.5150,
        "longitude": 73.8500,
        "address": "Fergusson College Road, Shivajinagar, Pune",
        "description": "Severe acute chest pain, breathlessness, cardiac distress"
    }
    r = requests.post(f"{API_BASE}/emergencies", json=payload)
    if r.status_code == 201:
        em = r.json()
        print(f"{C_GREEN}✓ Emergency Created:{C_RESET} ID: {em['id']} | Severity: {em['severity']}")
        return em["id"]
    return None


def run_simulation(auto_create_emergency=True):
    print("=" * 65)
    print(f"{C_BOLD}{C_CYAN}  AEGIS FLOW — DYNAMIC GREEN CORRIDOR SIMULATION  {C_RESET}")
    print("=" * 65)

    if not check_backend():
        print("\nPlease run the backend first with:")
        print("  uvicorn backend.app.main:app --reload --port 8000")
        sys.exit(1)

    amb_id = get_available_ambulance()
    if not amb_id:
        print(f"{C_RED}No ambulances found in database.{C_RESET}")
        return

    emergency_id = None
    if auto_create_emergency:
        emergency_id = create_demo_emergency()
        if emergency_id:
            # Auto-assign ambulance
            print(f"{C_CYAN}🤖 Running AI Auto-Dispatch...{C_RESET}")
            assign_res = requests.post(f"{API_BASE}/emergencies/{emergency_id}/auto-assign")
            if assign_res.status_code == 200:
                print(f"{C_GREEN}✓ Ambulance Assigned successfully!{C_RESET}")
            
            # Driver accepts
            requests.post(f"{API_BASE}/ambulances/{amb_id}/accept")
            print(f"{C_GREEN}✓ Driver Accepted dispatch.{C_RESET}")

    print("\n" + "─" * 65)
    print(f"{C_BOLD}Starting Live Telemetry Stream along Pune Emergency Corridor...{C_RESET}")
    print("─" * 65)

    # Step through waypoints
    for i in range(len(WAYPOINTS) - 1):
        start = WAYPOINTS[i]
        end = WAYPOINTS[i + 1]

        # Interpolate 4 sub-steps between waypoints
        num_substeps = 4
        for step in range(num_substeps):
            fraction = step / float(num_substeps)
            cur_lat = start["lat"] + (end["lat"] - start["lat"]) * fraction
            cur_lon = start["lon"] + (end["lon"] - start["lon"]) * fraction
            cur_speed = start["speed"] + (end["speed"] - start["speed"]) * fraction

            # Calculate heading
            dlat = end["lat"] - start["lat"]
            dlon = end["lon"] - start["lon"]
            heading = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360

            # Send telemetry to backend
            telemetry = {
                "latitude": round(cur_lat, 6),
                "longitude": round(cur_lon, 6),
                "speed_kmh": round(cur_speed, 1),
                "heading": round(heading, 1)
            }

            try:
                r = requests.post(f"{API_BASE}/ambulances/{amb_id}/location", json=telemetry)
                # Fetch signals to see their live state
                sig_res = requests.get(f"{API_BASE}/signals")
                signals = sig_res.json() if sig_res.status_code == 200 else []
            except Exception as e:
                print(f"{C_RED}Error posting telemetry: {e}{C_RESET}")
                signals = []

            # Display status dashboard row
            sig_statuses = []
            for s in signals[:2]:
                color = C_GREEN if s["state"] == "emergency_priority" else (C_YELLOW if s["state"] == "prepare" else C_CYAN)
                sig_statuses.append(f"{s['name'][:12]}: {color}{s['state'].upper()}{C_RESET}")

            status_line = " | ".join(sig_statuses)
            print(f"[{time.strftime('%H:%M:%S')}] 🚑 At {start['name'][:22]:<22} | Speed: {cur_speed:4.1f} km/h | {status_line}")

            time.sleep(1.2)

    # Mark pickup and completed
    if emergency_id:
        print(f"\n{C_GREEN}✓ Arrived at Patient! Marking patient picked up...{C_RESET}")
        requests.post(f"{API_BASE}/emergencies/{emergency_id}/pickup")
        time.sleep(1.5)
        print(f"{C_GREEN}✓ Delivered to Sancheti Hospital. Emergency Completed!{C_RESET}")
        requests.post(f"{API_BASE}/emergencies/{emergency_id}/complete")

    print("\n" + "=" * 65)
    print(f"{C_BOLD}{C_GREEN}  CORRIDOR SIMULATION COMPLETE — ALL SIGNALS RESTORED  {C_RESET}")
    print("=" * 65)


if __name__ == "__main__":
    run_simulation()
