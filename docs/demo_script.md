# 🎙️ Aegis Flow — Hackathon Presentation & Live Demo Script

**Total Demo Duration:** 5–7 Minutes  
**Target Audience:** Hackathon Judges, Technical Evaluators, Industry Mentors  

---

## 1. The Hook (0:00 - 1:00)

> *"Judges, in critical medical emergencies like cardiac arrests or severe trauma, the first 60 minutes are known as the **'Golden Hour'**. Yet in dense urban cities across India and the world, ambulances spend up to 45% of their total transit time stranded at red traffic lights, stuck behind congested intersection queues.*
>
> *Today, we present **Aegis Flow** — an AI-powered emergency response and dynamic traffic signal control system that eliminates intersection delays, creating an intelligent **Green Wave** that guides ambulances safely and rapidly to hospitals."*

---

## 2. Live Demonstration Flow (1:00 - 4:30)

### Phase 1: Citizen SOS & Incident Creation (1:00 - 1:45)
1. Open the web app on your laptop: `http://localhost:8000`
2. Click **"Request Emergency"** on the hero banner.
3. Select **"Cardiac Emergency"**, Severity **"Critical"**, and enter patient details.
4. Click **"Submit Emergency SOS"**.
5. **Show Judges:**
   - The emergency is immediately assigned a real-time tracking token.
   - The backend fires an asynchronous WebSocket event.

### Phase 2: AI Auto-Dispatch & Driver Dashboard (1:45 - 2:30)
1. Switch to the **Driver Dashboard** (`#/driver`).
2. Show the incoming dispatch card for Ambulance **`MH-12-AE-1001`**.
3. Click **"Accept Emergency"**.
4. Click **"▶ Start Simulation"** (or run `python simulation/traffic_sim.py` in terminal).
5. **Point out to Judges:**
   - Real-time GPS coordinates stream across the map at 50 km/h.
   - Live speed, heading, and distance to destination update continuously.

### Phase 3: The Green Wave & ESP32 Hardware Integration (2:30 - 3:30)
1. Switch to the **Traffic Signals** view (`#/traffic/signals`) side-by-side with your physical **ESP32 breadboard model**.
2. **As the ambulance approaches within 850 meters of Junction 1:**
   - The UI signal card shifts to **PREPARE** (Yellow).
   - On the ESP32 breadboard, the priority LED enters flashing caution mode to clear the queue ahead.
3. **As the ambulance enters within 400 meters:**
   - The UI turns solid **EMERGENCY PRIORITY** (Bright Green).
   - On the ESP32, the **North-South Green LED turns solid ON**, the **East-West Red LED locks ON**, and the piezo buzzer sounds.
   - Cross-traffic is safely held red.
4. **As the ambulance passes through the intersection (<30 meters):**
   - The signal enters **CLEARANCE** (Yellow buffer) for 4 seconds, then automatically reverts to **NORMAL** cyclic operation.

### Phase 4: AI Explainability & Authority Control (3:30 - 4:30)
1. Open the **AI Insights Dashboard** (`#/hospital/ai`).
2. Select the active emergency and click **"Run AI Analysis"**.
3. **Highlight the AI Metrics:**
   - **Priority Score: 88.5 / 100** with natural-language medical rationale.
   - **Dynamic ETA:** 7.2 minutes vs 12.5 minutes baseline (**42% time saved**).
   - **Explainable Factors breakdown:** Severity (100%), Medical urgency (92%), Congestion (68%).
4. Show the **Traffic Operator Manual Override:**
   - Click **"Force Red"** or **"Manual Override"** to demonstrate that human traffic authority operators always maintain absolute control.

---

## 3. Anticipated Judge Questions & Answers

### Q1: *"What happens if an ambulance gets stuck or the WiFi disconnects while the green light is active?"*
> **Answer:** *"Aegis Flow is built with a strict **Fail-Safe Watchdog**. The ESP32 firmware contains a local hardware countdown timer. If no MQTT heartbeat or GPS update arrives within 45 seconds, the ESP32 automatically triggers a 4-second Yellow clearance buffer and safely falls back to local cyclic timing without any server dependency."*

### Q2: *"Can this system be compromised by someone sending fake emergency signals?"*
> **Answer:** *"All commands require JWT authentication with cryptographic role-based verification. Furthermore, signal preemption commands cannot be triggered manually from the outside; they are only issued server-side by the Corridor Controller after validating that a registered emergency vehicle is physically inside the spatial geofence moving toward the intersection."*

### Q3: *"How does this scale to a whole city with hundreds of intersections?"*
> **Answer:** *"Aegis Flow uses MQTT pub/sub with isolated topic namespaces (`aegis/signals/{id}/command`). Controllers only listen to their own topic. Traffic analysis is computed locally per corridor corridor corridor segment, maintaining low latency even across thousands of nodes."*
