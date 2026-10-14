/**
 * Aegis Flow - Main Application Logic
 * Handles routing, page initialization, maps, and user interactions.
 */

// ═══════════════════════════════════════════════════════
// Global State
// ═══════════════════════════════════════════════════════

const state = {
    currentPage: 'landing',
    currentEmergencyId: null,
    selectedAmbulanceId: null,
    activeEmergency: null,
    maps: {},
    markers: {},
    gpsSimInterval: null,
    gpsSimRunning: false,
    refreshInterval: null,
    settings: {
        aiEnabled: true,
        simulationMode: true,
        hardwareMode: false,
        gpsInterval: 3,
        refreshInterval: 5,
    },
};

// ═══════════════════════════════════════════════════════
// Router
// ═══════════════════════════════════════════════════════

const routes = {
    '/': 'landing',
    '/emergency': 'emergency',
    '/emergency/status': 'status',
    '/driver': 'driver',
    '/hospital/dashboard': 'hospital',
    '/hospital/ai': 'ai',
    '/traffic/signals': 'signals',
    '/settings': 'settings',
};

function navigate(path) {
    window.location.hash = path;
}

function handleRoute() {
    const hash = window.location.hash.slice(1) || '/';
    // Handle tracking routes with ID
    let pageName = routes[hash];
    
    if (!pageName && hash.startsWith('/emergency/tracking/')) {
        pageName = 'status';
        state.currentEmergencyId = hash.split('/').pop();
    }
    if (!pageName && hash === '/emergency/status') {
        pageName = 'status';
    }

    if (!pageName) pageName = 'landing';

    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    
    // Show target page
    const page = document.getElementById(`page-${pageName}`);
    if (page) page.classList.add('active');

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('data-page') === pageName);
    });

    state.currentPage = pageName;
    initPage(pageName);
}

async function initPage(page) {
    switch (page) {
        case 'landing': await initLanding(); break;
        case 'emergency': initEmergencyForm(); break;
        case 'status': await initStatusPage(); break;
        case 'driver': await initDriverDashboard(); break;
        case 'hospital': await initHospitalDashboard(); break;
        case 'ai': await initAIDashboard(); break;
        case 'signals': await initSignalDashboard(); break;
        case 'settings': initSettings(); break;
    }
}

// ═══════════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// ═══════════════════════════════════════════════════════
// Login
// ═══════════════════════════════════════════════════════

function showLogin() {
    document.getElementById('login-modal').classList.add('visible');
}

function hideLogin() {
    document.getElementById('login-modal').classList.remove('visible');
}

async function doLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    try {
        const data = await api.login(username, password);
        hideLogin();
        showToast(`Welcome, ${data.user.full_name || data.user.username}!`, 'success');
        updateAuthUI();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function updateAuthUI() {
    const btn = document.getElementById('login-btn');
    if (api.user) {
        btn.textContent = `${api.user.full_name || api.user.username} (${api.user.role})`;
        btn.onclick = () => {
            api.clearAuth();
            updateAuthUI();
            showToast('Logged out', 'info');
        };
    } else {
        btn.textContent = 'Login';
        btn.onclick = showLogin;
    }
}

// ═══════════════════════════════════════════════════════
// Map Helpers
// ═══════════════════════════════════════════════════════

function initMap(containerId, center = [18.5204, 73.8567], zoom = 14) {
    if (state.maps[containerId]) {
        state.maps[containerId].invalidateSize();
        return state.maps[containerId];
    }

    const container = document.getElementById(containerId);
    if (!container || container.offsetWidth === 0) return null;

    const map = L.map(containerId).setView(center, zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
    }).addTo(map);

    state.maps[containerId] = map;
    return map;
}

function createIcon(emoji, color = '#ef4444', size = 32) {
    return L.divIcon({
        html: `<div style="background:${color};width:${size}px;height:${size}px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:${size*0.5}px;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);">${emoji}</div>`,
        className: '',
        iconSize: [size, size],
        iconAnchor: [size/2, size/2],
    });
}

// ═══════════════════════════════════════════════════════
// Landing Page
// ═══════════════════════════════════════════════════════

async function initLanding() {
    try {
        const health = await api.getHealth();
        document.getElementById('stat-emergencies').textContent = health.active_emergencies;
        document.getElementById('stat-ambulances').textContent = health.available_ambulances;
        document.getElementById('stat-signals').textContent = health.online_signals;
        document.getElementById('stat-status').textContent = '✓';
        document.getElementById('stat-mode').textContent = 
            health.simulation_mode ? 'Simulation Mode' : 'Hardware Mode';
    } catch (e) {
        document.getElementById('stat-status').textContent = '✗';
        document.getElementById('stat-mode').textContent = 'Backend offline';
        showToast('Backend is not running. Start it with: python -m uvicorn backend.app.main:app --reload', 'error');
    }
}

// ═══════════════════════════════════════════════════════
// Emergency Request
// ═══════════════════════════════════════════════════════

function initEmergencyForm() {
    setTimeout(() => {
        const map = initMap('emergency-map');
        if (map) {
            // Click to set location
            map.on('click', (e) => {
                document.getElementById('em-lat').value = e.latlng.lat.toFixed(6);
                document.getElementById('em-lng').value = e.latlng.lng.toFixed(6);
                document.getElementById('location-status').textContent = `📍 ${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`;
                
                // Add/update marker
                if (state.markers['emergency-pin']) {
                    state.markers['emergency-pin'].setLatLng(e.latlng);
                } else {
                    state.markers['emergency-pin'] = L.marker(e.latlng, {
                        icon: createIcon('🚨', '#ef4444', 40)
                    }).addTo(map);
                }
            });
        }
    }, 200);
}

function detectLocation() {
    if (!navigator.geolocation) {
        showToast('Geolocation not supported by browser', 'error');
        return;
    }

    document.getElementById('location-status').textContent = '⏳ Detecting...';
    
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            document.getElementById('em-lat').value = pos.coords.latitude.toFixed(6);
            document.getElementById('em-lng').value = pos.coords.longitude.toFixed(6);
            document.getElementById('location-status').textContent = 
                `📍 ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;

            const map = state.maps['emergency-map'];
            if (map) {
                const latlng = [pos.coords.latitude, pos.coords.longitude];
                map.setView(latlng, 16);
                if (state.markers['emergency-pin']) {
                    state.markers['emergency-pin'].setLatLng(latlng);
                } else {
                    state.markers['emergency-pin'] = L.marker(latlng, {
                        icon: createIcon('🚨', '#ef4444', 40)
                    }).addTo(map);
                }
            }
            showToast('Location detected!', 'success');
        },
        (err) => {
            // Fallback to Pune demo location
            document.getElementById('em-lat').value = '18.5172';
            document.getElementById('em-lng').value = '73.8483';
            document.getElementById('location-status').textContent = '📍 Using demo location (Pune)';
            showToast('Using demo location. Real GPS not available.', 'warning');
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

async function submitEmergency(e) {
    e.preventDefault();
    
    const lat = parseFloat(document.getElementById('em-lat').value);
    const lng = parseFloat(document.getElementById('em-lng').value);
    
    if (!lat || !lng) {
        showToast('Please set a location first', 'error');
        return;
    }

    const btn = document.getElementById('em-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Submitting...';

    try {
        const emergency = await api.createEmergency({
            emergency_type: document.getElementById('em-type').value,
            severity: document.getElementById('em-severity').value,
            patient_name: document.getElementById('em-name').value || null,
            patient_phone: document.getElementById('em-phone').value || null,
            description: document.getElementById('em-desc').value || null,
            latitude: lat,
            longitude: lng,
            address: document.getElementById('em-address').value || null,
        });

        showToast('Emergency request submitted!', 'success');
        state.currentEmergencyId = emergency.id;

        // Auto-assign ambulance
        try {
            await api.autoAssign(emergency.id);
            showToast('Ambulance assigned automatically!', 'success');
        } catch (assignErr) {
            showToast('No ambulance available: ' + assignErr.message, 'warning');
        }

        navigate('/emergency/status');
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🚨 Submit Emergency Request';
    }
}

// ═══════════════════════════════════════════════════════
// Emergency Status & Tracking
// ═══════════════════════════════════════════════════════

async function initStatusPage() {
    if (!state.currentEmergencyId) {
        // Try to get most recent emergency
        try {
            const emergencies = await api.listEmergencies();
            if (emergencies.length > 0) {
                state.currentEmergencyId = emergencies[0].id;
            } else {
                document.getElementById('status-details').innerHTML = 
                    '<p class="text-muted">No emergency requests found. <a href="#/emergency" style="color:var(--blue-400)">Create one</a></p>';
                return;
            }
        } catch (e) {
            document.getElementById('status-details').innerHTML = '<p class="text-muted">Backend offline</p>';
            return;
        }
    }

    await refreshStatus();

    // Set up WebSocket for live updates
    api.connectWS('emergencies', (data) => {
        if (state.currentPage === 'status') {
            refreshStatus();
        }
    });

    api.connectWS('tracking', (data) => {
        if (data.type === 'location_update' && state.currentPage === 'status') {
            updateTrackingMarker(data);
        }
    });
}

async function refreshStatus() {
    if (!state.currentEmergencyId) return;
    
    try {
        const em = await api.getEmergency(state.currentEmergencyId);
        state.activeEmergency = em;

        // Update badge
        const badge = document.getElementById('status-badge');
        const statusColors = {
            pending: 'badge-amber', assigned: 'badge-blue', accepted: 'badge-blue',
            en_route: 'badge-amber', picked_up: 'badge-green', transporting: 'badge-amber',
            completed: 'badge-green', cancelled: 'badge-neutral', no_ambulance: 'badge-red',
        };
        badge.className = `badge ${statusColors[em.status] || 'badge-neutral'}`;
        badge.textContent = em.status.replace('_', ' ').toUpperCase();

        // Update details
        document.getElementById('status-details').innerHTML = `
            <div class="grid-2 gap-sm">
                <div><span class="text-muted text-sm">Request ID</span><br><span class="mono text-sm">${em.id.slice(0,8)}...</span></div>
                <div><span class="text-muted text-sm">Type</span><br>${em.emergency_type}</div>
                <div><span class="text-muted text-sm">Severity</span><br><span class="badge ${em.severity === 'critical' ? 'badge-red' : 'badge-amber'}">${em.severity}</span></div>
                <div><span class="text-muted text-sm">ETA</span><br><strong>${em.estimated_arrival_minutes ? em.estimated_arrival_minutes.toFixed(1) + ' min' : 'Calculating...'}</strong></div>
                <div><span class="text-muted text-sm">Ambulance</span><br>${em.ambulance_id ? em.ambulance_id.slice(0,8) : 'Not assigned'}</div>
                <div><span class="text-muted text-sm">Hospital</span><br>${em.hospital_id ? em.hospital_id.slice(0,12) : 'Not assigned'}</div>
            </div>
            ${em.description ? `<div class="mt-md"><span class="text-muted text-sm">Description</span><br>${em.description}</div>` : ''}
        `;

        // Update timeline
        const timeline = document.getElementById('status-timeline');
        let items = [];
        items.push({ text: 'Emergency request created', time: em.created_at, active: true });
        if (em.assigned_at) items.push({ text: 'Ambulance assigned', time: em.assigned_at, active: true });
        if (em.accepted_at) items.push({ text: 'Driver accepted assignment', time: em.accepted_at, active: true });
        if (em.picked_up_at) items.push({ text: 'Patient picked up', time: em.picked_up_at, active: true });
        if (em.completed_at) items.push({ text: 'Arrived at hospital', time: em.completed_at, active: true });
        if (em.status === 'no_ambulance') items.push({ text: 'No ambulance available', time: null, emergency: true });

        timeline.innerHTML = items.map(item => `
            <div class="timeline-item ${item.active ? 'active' : ''} ${item.emergency ? 'emergency' : ''}">
                <div class="timeline-time">${item.time ? new Date(item.time).toLocaleTimeString() : '—'}</div>
                <div class="timeline-text">${item.text}</div>
            </div>
        `).join('');

        // Initialize tracking map
        setTimeout(() => {
            const map = initMap('tracking-map', [em.latitude, em.longitude], 15);
            if (map) {
                // Patient marker
                if (state.markers['patient']) {
                    state.markers['patient'].setLatLng([em.latitude, em.longitude]);
                } else {
                    state.markers['patient'] = L.marker([em.latitude, em.longitude], {
                        icon: createIcon('🚨', '#ef4444', 36)
                    }).addTo(map).bindPopup('Patient Location');
                }

                // Ambulance marker if assigned
                if (em.ambulance_id) {
                    loadAmbulanceOnMap(map, em.ambulance_id);
                }
            }
        }, 200);

    } catch (e) {
        document.getElementById('status-details').innerHTML = '<p class="text-muted">Error loading status</p>';
    }
}

async function loadAmbulanceOnMap(map, ambulanceId) {
    try {
        const amb = await api.getAmbulance(ambulanceId);
        if (amb.latitude && amb.longitude) {
            if (state.markers['ambulance-track']) {
                state.markers['ambulance-track'].setLatLng([amb.latitude, amb.longitude]);
            } else {
                state.markers['ambulance-track'] = L.marker([amb.latitude, amb.longitude], {
                    icon: createIcon('🚑', '#3b82f6', 36)
                }).addTo(map).bindPopup(`Ambulance ${amb.vehicle_number}`);
            }
        }
    } catch (e) {}
}

function updateTrackingMarker(data) {
    const map = state.maps['tracking-map'];
    if (!map) return;
    const latlng = [data.latitude, data.longitude];
    if (state.markers['ambulance-track']) {
        state.markers['ambulance-track'].setLatLng(latlng);
    } else {
        state.markers['ambulance-track'] = L.marker(latlng, {
            icon: createIcon('🚑', '#3b82f6', 36)
        }).addTo(map);
    }
}

// ═══════════════════════════════════════════════════════
// Driver Dashboard
// ═══════════════════════════════════════════════════════

async function initDriverDashboard() {
    try {
        const ambulances = await api.listAmbulances();
        const select = document.getElementById('driver-ambulance-select');
        select.innerHTML = '<option value="">Select ambulance...</option>' +
            ambulances.map(a => `<option value="${a.id}">${a.vehicle_number} — ${a.driver_name || 'No driver'} (${a.status})</option>`).join('');

        if (state.selectedAmbulanceId) {
            select.value = state.selectedAmbulanceId;
            selectAmbulance(state.selectedAmbulanceId);
        }

        await loadDriverRequests();
    } catch (e) {
        showToast('Error loading driver dashboard', 'error');
    }

    setTimeout(() => {
        initMap('driver-map');
    }, 200);

    // WebSocket for new requests
    api.connectWS('emergencies', (data) => {
        if (state.currentPage === 'driver') {
            loadDriverRequests();
        }
    });
}

async function selectAmbulance(id) {
    if (!id) return;
    state.selectedAmbulanceId = id;
    try {
        const amb = await api.getAmbulance(id);
        document.getElementById('driver-status').textContent = amb.status.replace('_', ' ');
        document.getElementById('driver-status').className = `stat-value ${amb.status === 'available' ? 'green' : 'amber'}`;
        document.getElementById('driver-vehicle').textContent = amb.vehicle_number;
        document.getElementById('driver-speed').innerHTML = `${amb.speed_kmh || 0} <small>km/h</small>`;

        // Show active assignment if assigned
        await loadDriverRequests();
        checkActiveAssignment(amb);
    } catch (e) {
        showToast('Error loading ambulance', 'error');
    }
}

async function loadDriverRequests() {
    try {
        const emergencies = await api.listEmergencies();
        const pending = emergencies.filter(e => e.status === 'pending');
        const assigned = emergencies.filter(e => 
            (e.status === 'assigned' || e.status === 'accepted') && 
            e.ambulance_id === state.selectedAmbulanceId
        );

        document.getElementById('pending-count').textContent = pending.length;

        const container = document.getElementById('driver-requests');
        if (pending.length === 0 && assigned.length === 0) {
            container.innerHTML = '<p class="text-sm text-muted">No pending requests</p>';
            return;
        }

        container.innerHTML = [...assigned, ...pending].map(em => `
            <div class="card ${em.ambulance_id === state.selectedAmbulanceId ? 'emergency' : ''}" style="margin-bottom:8px;padding:12px;">
                <div class="flex justify-between items-center">
                    <div>
                        <span class="badge ${em.severity === 'critical' ? 'badge-red' : 'badge-amber'}">${em.severity}</span>
                        <strong class="ml-sm">${em.emergency_type}</strong>
                        <span class="text-sm text-muted ml-sm">${new Date(em.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div class="flex gap-sm">
                        ${em.status === 'pending' ? `
                            <button class="btn btn-sm btn-success" onclick="acceptRequest('${em.id}')">Accept</button>
                        ` : ''}
                        ${em.status === 'assigned' && em.ambulance_id === state.selectedAmbulanceId ? `
                            <button class="btn btn-sm btn-success" onclick="driverAccept()">✅ Accept</button>
                            <button class="btn btn-sm btn-danger" onclick="driverReject()">✗ Reject</button>
                        ` : ''}
                    </div>
                </div>
                ${em.description ? `<div class="text-sm text-muted mt-sm">${em.description}</div>` : ''}
            </div>
        `).join('');

    } catch (e) {}
}

async function acceptRequest(emergencyId) {
    if (!state.selectedAmbulanceId) {
        showToast('Select an ambulance first', 'error');
        return;
    }
    try {
        await api.assignAmbulance(emergencyId, state.selectedAmbulanceId);
        showToast('Request assigned to you!', 'success');
        state.currentEmergencyId = emergencyId;
        await loadDriverRequests();
        selectAmbulance(state.selectedAmbulanceId);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function driverAccept() {
    if (!state.selectedAmbulanceId) return;
    try {
        await api.acceptAssignment(state.selectedAmbulanceId);
        showToast('Assignment accepted! En route.', 'success');
        selectAmbulance(state.selectedAmbulanceId);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function driverReject() {
    if (!state.selectedAmbulanceId) return;
    try {
        await api.rejectAssignment(state.selectedAmbulanceId);
        showToast('Assignment rejected.', 'warning');
        selectAmbulance(state.selectedAmbulanceId);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function checkActiveAssignment(amb) {
    const card = document.getElementById('active-assignment-card');
    if (['en_route', 'on_scene', 'transporting'].includes(amb.status)) {
        card.style.display = 'block';
    } else {
        card.style.display = 'none';
    }
}

async function markPickup() {
    if (!state.currentEmergencyId) {
        // Find active emergency for this ambulance
        const emergencies = await api.listEmergencies();
        const active = emergencies.find(e => e.ambulance_id === state.selectedAmbulanceId && 
            ['accepted', 'en_route'].includes(e.status));
        if (active) state.currentEmergencyId = active.id;
    }
    if (!state.currentEmergencyId) { showToast('No active emergency', 'error'); return; }
    try {
        await api.markPickup(state.currentEmergencyId);
        showToast('Patient picked up!', 'success');
        selectAmbulance(state.selectedAmbulanceId);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function markComplete() {
    if (!state.currentEmergencyId) {
        const emergencies = await api.listEmergencies();
        const active = emergencies.find(e => e.ambulance_id === state.selectedAmbulanceId);
        if (active) state.currentEmergencyId = active.id;
    }
    if (!state.currentEmergencyId) { showToast('No active emergency', 'error'); return; }
    try {
        await api.markComplete(state.currentEmergencyId);
        showToast('Emergency completed! Patient at hospital.', 'success');
        state.currentEmergencyId = null;
        selectAmbulance(state.selectedAmbulanceId);
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ─── GPS Simulation ──────────────────────────────

// Demo route points (Pune city route)
const demoRoute = [
    [18.5150, 73.8500], [18.5160, 73.8510], [18.5170, 73.8515],
    [18.5180, 73.8520], [18.5185, 73.8530], [18.5190, 73.8540],
    [18.5195, 73.8545], [18.5200, 73.8550], [18.5205, 73.8555],
    [18.5210, 73.8560], [18.5215, 73.8565], [18.5204, 73.8567],
];

let simIndex = 0;

function toggleGpsSimulation() {
    if (state.gpsSimRunning) {
        stopGpsSimulation();
    } else {
        startGpsSimulation();
    }
}

function startGpsSimulation() {
    if (!state.selectedAmbulanceId) {
        showToast('Select an ambulance first', 'error');
        return;
    }

    state.gpsSimRunning = true;
    simIndex = 0;
    document.getElementById('gps-sim-btn').textContent = '⏹ Stop Simulation';
    document.getElementById('gps-sim-btn').classList.add('btn-danger');
    showToast('GPS simulation started', 'info');

    state.gpsSimInterval = setInterval(async () => {
        if (simIndex >= demoRoute.length) {
            stopGpsSimulation();
            showToast('GPS simulation completed', 'success');
            return;
        }

        const [lat, lng] = demoRoute[simIndex];
        const speed = 30 + Math.random() * 30;

        try {
            await api.updateLocation(state.selectedAmbulanceId, lat, lng, speed);
            document.getElementById('driver-speed').innerHTML = `${speed.toFixed(0)} <small>km/h</small>`;

            // Update driver map
            const map = state.maps['driver-map'];
            if (map) {
                const latlng = [lat, lng];
                if (state.markers['driver-ambulance']) {
                    state.markers['driver-ambulance'].setLatLng(latlng);
                } else {
                    state.markers['driver-ambulance'] = L.marker(latlng, {
                        icon: createIcon('🚑', '#3b82f6', 36)
                    }).addTo(map);
                }
                map.panTo(latlng);
            }
        } catch (e) {}

        simIndex++;
    }, (state.settings.gpsInterval || 3) * 1000);
}

function stopGpsSimulation() {
    state.gpsSimRunning = false;
    clearInterval(state.gpsSimInterval);
    document.getElementById('gps-sim-btn').textContent = '▶ Start Simulation';
    document.getElementById('gps-sim-btn').classList.remove('btn-danger');
}

// ═══════════════════════════════════════════════════════
// Hospital Command Center
// ═══════════════════════════════════════════════════════

async function initHospitalDashboard() {
    await refreshDashboard();

    // Auto-refresh
    if (state.refreshInterval) clearInterval(state.refreshInterval);
    state.refreshInterval = setInterval(() => {
        if (state.currentPage === 'hospital') refreshDashboard();
    }, (state.settings.refreshInterval || 5) * 1000);

    // WebSocket
    api.connectWS('emergencies', (data) => {
        if (state.currentPage === 'hospital') refreshDashboard();
    });

    setTimeout(() => {
        const map = initMap('hospital-map');
        if (map) loadAllMarkersOnMap(map);
    }, 200);
}

async function refreshDashboard() {
    try {
        const [emergencies, ambulances, health, events] = await Promise.all([
            api.listEmergencies(),
            api.listAmbulances(),
            api.getHealth(),
            api.getEvents(20),
        ]);

        const active = emergencies.filter(e => !['completed', 'cancelled'].includes(e.status));
        const enRoute = emergencies.filter(e => ['en_route', 'accepted'].includes(e.status));
        const available = ambulances.filter(a => a.status === 'available');

        document.getElementById('h-active').textContent = active.length;
        document.getElementById('h-enroute').textContent = enRoute.length;
        document.getElementById('h-available').textContent = available.length;
        document.getElementById('h-signals').textContent = health.online_signals;

        // Emergency list
        const list = document.getElementById('emergency-list');
        if (active.length === 0) {
            list.innerHTML = '<p class="text-sm text-muted">No active emergencies</p>';
        } else {
            list.innerHTML = active.map(em => `
                <div class="card ${em.severity === 'critical' ? 'emergency' : ''}" style="margin-bottom:8px;padding:12px;">
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="badge ${em.severity === 'critical' ? 'badge-red' : 'badge-amber'}">${em.severity}</span>
                            <strong>${em.emergency_type}</strong>
                        </div>
                        <span class="badge badge-neutral">${em.status.replace('_',' ')}</span>
                    </div>
                    <div class="text-sm text-muted mt-sm">
                        ETA: ${em.estimated_arrival_minutes ? em.estimated_arrival_minutes.toFixed(1) + ' min' : '—'} |
                        Ambulance: ${em.ambulance_id ? em.ambulance_id.slice(0,8) : 'None'} |
                        ${new Date(em.created_at).toLocaleTimeString()}
                    </div>
                    ${em.status === 'pending' ? `
                        <button class="btn btn-sm btn-primary mt-sm" onclick="autoAssignFromDashboard('${em.id}')">Auto-Assign Ambulance</button>
                    ` : ''}
                </div>
            `).join('');
        }

        // Ambulance list
        const ambList = document.getElementById('ambulance-list');
        ambList.innerHTML = ambulances.map(a => `
            <div class="flex justify-between items-center" style="padding:8px 0;border-bottom:1px solid var(--border-subtle);">
                <div>
                    <span class="status-dot ${a.status === 'available' ? 'online' : a.status === 'off_duty' ? 'offline' : 'warning'}"></span>
                    <strong class="ml-sm">${a.vehicle_number}</strong>
                    <span class="text-sm text-muted ml-sm">${a.driver_name || '—'}</span>
                </div>
                <span class="badge ${a.status === 'available' ? 'badge-green' : 'badge-amber'}">${a.status.replace('_',' ')}</span>
            </div>
        `).join('');

        // Event log
        const eventLog = document.getElementById('event-log');
        eventLog.innerHTML = events.map(ev => `
            <div style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">
                <div class="flex justify-between">
                    <span class="text-sm"><span class="badge ${ev.severity === 'critical' ? 'badge-red' : ev.severity === 'warning' ? 'badge-amber' : 'badge-neutral'}" style="margin-right:4px">${ev.severity}</span>${ev.message}</span>
                    <span class="text-sm text-muted mono">${new Date(ev.created_at).toLocaleTimeString()}</span>
                </div>
            </div>
        `).join('') || '<p class="text-sm text-muted">No events</p>';

    } catch (e) {
        showToast('Error refreshing dashboard', 'error');
    }
}

async function autoAssignFromDashboard(emergencyId) {
    try {
        const result = await api.autoAssign(emergencyId);
        if (result.status === 'no_ambulance') {
            showToast('No ambulance available', 'warning');
        } else {
            showToast('Ambulance assigned!', 'success');
        }
        refreshDashboard();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function loadAllMarkersOnMap(map) {
    try {
        const [ambulances, hospitals, signals] = await Promise.all([
            api.listAmbulances(),
            api.listHospitals(),
            api.listSignals(),
        ]);

        hospitals.forEach(h => {
            L.marker([h.latitude, h.longitude], {
                icon: createIcon('🏥', '#22c55e', 32)
            }).addTo(map).bindPopup(`<b>${h.name}</b><br>Beds: ${h.available_beds}`);
        });

        ambulances.forEach(a => {
            if (a.latitude && a.longitude) {
                L.marker([a.latitude, a.longitude], {
                    icon: createIcon('🚑', a.status === 'available' ? '#3b82f6' : '#f59e0b', 30)
                }).addTo(map).bindPopup(`<b>${a.vehicle_number}</b><br>${a.status}`);
            }
        });

        signals.forEach(s => {
            const color = s.state === 'emergency_priority' ? '#ef4444' : s.state === 'normal' ? '#22c55e' : '#f59e0b';
            L.marker([s.latitude, s.longitude], {
                icon: createIcon('🚦', color, 28)
            }).addTo(map).bindPopup(`<b>${s.name}</b><br>State: ${s.state}`);
        });

    } catch (e) {}
}

// ═══════════════════════════════════════════════════════
// AI Decision Dashboard
// ═══════════════════════════════════════════════════════

async function initAIDashboard() {
    try {
        const emergencies = await api.listEmergencies();
        const active = emergencies.filter(e => !['completed', 'cancelled'].includes(e.status));
        const select = document.getElementById('ai-emergency-select');
        select.innerHTML = '<option value="">Select active emergency...</option>' +
            active.map(e => `<option value="${e.id}">${e.emergency_type} (${e.severity}) — ${e.status}</option>`).join('');
    } catch (e) {}

    setTimeout(() => initMap('ai-map'), 200);
}

async function runAIAnalysis() {
    const emergencyId = document.getElementById('ai-emergency-select').value;
    if (!emergencyId) {
        showToast('Select an emergency first', 'error');
        return;
    }

    try {
        const result = await api.runAnalysis(emergencyId);
        
        document.getElementById('ai-priority').textContent = result.priority_score?.toFixed(1) || '—';
        document.getElementById('ai-eta').textContent = result.eta_minutes ? result.eta_minutes.toFixed(1) + ' min' : '—';
        document.getElementById('ai-density').textContent = result.traffic_density ? (result.traffic_density * 100).toFixed(0) + '%' : '—';
        document.getElementById('ai-quality').textContent = result.data_quality_score ? (result.data_quality_score * 100).toFixed(0) + '%' : '—';

        document.getElementById('ai-explanation').textContent = result.explanation || 'No explanation available';

        // Factor breakdown
        if (result.factors) {
            try {
                const factors = JSON.parse(result.factors);
                document.getElementById('ai-factors').innerHTML = Object.entries(factors).map(([key, val]) => `
                    <div class="flex justify-between items-center" style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">
                        <span class="text-sm">${key.replace(/_/g, ' ')}</span>
                        <div class="flex items-center gap-sm">
                            <div style="width:100px;height:6px;background:var(--navy-700);border-radius:3px;overflow:hidden;">
                                <div style="width:${Math.min(val * 100, 100)}%;height:100%;background:${val > 0.7 ? 'var(--red-500)' : val > 0.4 ? 'var(--amber-500)' : 'var(--green-500)'};border-radius:3px;"></div>
                            </div>
                            <span class="mono text-sm">${(val * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('ai-factors').innerHTML = `<p class="text-sm">${result.factors}</p>`;
            }
        }

        showToast('AI analysis complete', 'success');
    } catch (e) {
        showToast('AI analysis failed: ' + e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════
// Traffic Signal Dashboard
// ═══════════════════════════════════════════════════════

async function initSignalDashboard() {
    await refreshSignals();

    api.connectWS('signals', (data) => {
        if (state.currentPage === 'signals') refreshSignals();
    });
}

async function refreshSignals() {
    try {
        const signals = await api.listSignals();

        // Stats
        document.getElementById('sig-normal').textContent = signals.filter(s => s.state === 'normal').length;
        document.getElementById('sig-emergency').textContent = signals.filter(s => s.state === 'emergency_priority').length;
        document.getElementById('sig-manual').textContent = signals.filter(s => s.manual_override).length;
        document.getElementById('sig-offline').textContent = signals.filter(s => !s.is_online).length;

        // Signal cards
        const grid = document.getElementById('signal-grid');
        grid.innerHTML = signals.map(s => `
            <div class="card ${s.state === 'emergency_priority' ? 'emergency' : s.state === 'manual' ? 'warning' : ''}">
                <div class="card-header">
                    <div class="card-title">
                        <span class="status-dot ${s.is_online ? 'online' : 'offline'}"></span>
                        ${s.name}
                    </div>
                    <span class="badge ${s.state === 'emergency_priority' ? 'badge-red' : s.state === 'normal' ? 'badge-green' : 'badge-amber'}">${s.state.replace('_',' ')}</span>
                </div>
                <div class="flex items-center gap-md mb-md">
                    <div class="traffic-light">
                        <div class="light red ${s.current_phase === 'red' || s.current_phase === 'all_red' ? 'active' : ''}"></div>
                        <div class="light yellow ${s.current_phase === 'yellow' ? 'active' : ''}"></div>
                        <div class="light green ${s.current_phase === 'green' ? 'active' : ''}"></div>
                    </div>
                    <div>
                        <div class="text-sm text-muted">${s.intersection_name || ''}</div>
                        <div class="text-sm">Phase: <strong>${s.current_phase || '—'}</strong></div>
                        <div class="text-sm">Override: ${s.manual_override ? '<span class="text-amber">YES</span>' : 'No'}</div>
                    </div>
                </div>
                <div class="flex gap-sm flex-wrap">
                    <button class="btn btn-sm btn-success" onclick="sendSignalCmd('${s.id}', 'normal', 'green', 'Operator set normal')">Normal</button>
                    <button class="btn btn-sm btn-warning" onclick="sendSignalCmd('${s.id}', 'prepare', 'yellow', 'Prepare for emergency')">Prepare</button>
                    <button class="btn btn-sm btn-primary" onclick="sendSignalCmd('${s.id}', 'emergency_priority', 'green', 'Emergency priority')">Emergency</button>
                    <button class="btn btn-sm btn-danger" onclick="overrideSignal('${s.id}', 'force_red')">Force Red</button>
                    <button class="btn btn-sm btn-secondary" onclick="overrideSignal('${s.id}', '${s.manual_override ? 'disable_manual' : 'enable_manual'}')">${s.manual_override ? 'Release' : 'Manual'}</button>
                </div>
            </div>
        `).join('');

    } catch (e) {
        showToast('Error loading signals', 'error');
    }
}

async function sendSignalCmd(signalId, requestedState, phase, reason) {
    try {
        await api.sendSignalCommand(signalId, {
            requested_state: requestedState,
            requested_phase: phase,
            reason: reason,
            expiry_seconds: parseInt(document.getElementById('setting-expiry')?.value || '60'),
        });
        showToast(`Signal command sent: ${requestedState}`, 'success');
        await refreshSignals();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function overrideSignal(signalId, action) {
    try {
        await api.overrideSignal(signalId, action, 'Manual operator action');
        showToast(`Override: ${action.replace('_', ' ')}`, 'warning');
        await refreshSignals();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════
// Settings
// ═══════════════════════════════════════════════════════

function initSettings() {
    document.getElementById('setting-ai-enabled').checked = state.settings.aiEnabled;
    document.getElementById('setting-sim-mode').checked = state.settings.simulationMode;
    document.getElementById('setting-hw-mode').checked = state.settings.hardwareMode;
    document.getElementById('setting-gps-interval').value = state.settings.gpsInterval;
    document.getElementById('setting-refresh-interval').value = state.settings.refreshInterval;
}

function saveSettings() {
    state.settings.aiEnabled = document.getElementById('setting-ai-enabled').checked;
    state.settings.simulationMode = document.getElementById('setting-sim-mode').checked;
    state.settings.hardwareMode = document.getElementById('setting-hw-mode').checked;
    state.settings.gpsInterval = parseInt(document.getElementById('setting-gps-interval').value);
    state.settings.refreshInterval = parseInt(document.getElementById('setting-refresh-interval').value);
    localStorage.setItem('aegis_settings', JSON.stringify(state.settings));
    showToast('Settings saved!', 'success');
}

// ═══════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════

window.addEventListener('hashchange', handleRoute);

window.addEventListener('load', () => {
    // Load saved settings
    const saved = localStorage.getItem('aegis_settings');
    if (saved) {
        try { Object.assign(state.settings, JSON.parse(saved)); } catch(e) {}
    }

    updateAuthUI();
    handleRoute();
});
