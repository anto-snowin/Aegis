/**
 * Aegis Flow - API Client
 * Handles all communication with the FastAPI backend.
 */

const API_BASE = window.location.origin + '/api';
const WS_BASE = `ws://${window.location.host}/ws`;

class AegisAPI {
    constructor() {
        this.token = localStorage.getItem('aegis_token');
        this.user = JSON.parse(localStorage.getItem('aegis_user') || 'null');
        this.ws = {};
    }

    headers() {
        const h = { 'Content-Type': 'application/json' };
        if (this.token) h['Authorization'] = `Bearer ${this.token}`;
        return h;
    }

    setAuth(token, user) {
        this.token = token;
        this.user = user;
        localStorage.setItem('aegis_token', token);
        localStorage.setItem('aegis_user', JSON.stringify(user));
    }

    clearAuth() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('aegis_token');
        localStorage.removeItem('aegis_user');
    }

    async request(method, path, body = null) {
        const opts = { method, headers: this.headers() };
        if (body) opts.body = JSON.stringify(body);
        try {
            const res = await fetch(`${API_BASE}${path}`, opts);
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || `API Error ${res.status}`);
            }
            return data;
        } catch (e) {
            console.error(`API ${method} ${path}:`, e);
            throw e;
        }
    }

    // ─── Auth ────────────────────────────
    async login(username, password) {
        const data = await this.request('POST', '/auth/login', { username, password });
        this.setAuth(data.access_token, data.user);
        return data;
    }

    async register(userData) {
        const data = await this.request('POST', '/auth/register', userData);
        this.setAuth(data.access_token, data.user);
        return data;
    }

    // ─── System ──────────────────────────
    async getHealth() {
        return this.request('GET', '/system/health');
    }

    async getEvents(limit = 50) {
        return this.request('GET', `/system/events?limit=${limit}`);
    }

    // ─── Emergencies ─────────────────────
    async createEmergency(data) {
        return this.request('POST', '/emergencies', data);
    }

    async getEmergency(id) {
        return this.request('GET', `/emergencies/${id}`);
    }

    async listEmergencies(statusFilter = null) {
        const q = statusFilter ? `?status_filter=${statusFilter}` : '';
        return this.request('GET', `/emergencies${q}`);
    }

    async assignAmbulance(emergencyId, ambulanceId, hospitalId = null) {
        return this.request('POST', `/emergencies/${emergencyId}/assign`, {
            ambulance_id: ambulanceId,
            hospital_id: hospitalId,
        });
    }

    async autoAssign(emergencyId) {
        return this.request('POST', `/emergencies/${emergencyId}/auto-assign`);
    }

    async markPickup(emergencyId) {
        return this.request('POST', `/emergencies/${emergencyId}/pickup`);
    }

    async markComplete(emergencyId) {
        return this.request('POST', `/emergencies/${emergencyId}/complete`);
    }

    // ─── Ambulances ─────────────────────
    async listAmbulances() {
        return this.request('GET', '/ambulances');
    }

    async getAmbulance(id) {
        return this.request('GET', `/ambulances/${id}`);
    }

    async acceptAssignment(ambulanceId) {
        return this.request('POST', `/ambulances/${ambulanceId}/accept`);
    }

    async rejectAssignment(ambulanceId) {
        return this.request('POST', `/ambulances/${ambulanceId}/reject`);
    }

    async updateLocation(ambulanceId, lat, lng, speed = 0, heading = 0) {
        return this.request('POST', `/ambulances/${ambulanceId}/location`, {
            latitude: lat,
            longitude: lng,
            speed_kmh: speed,
            heading: heading,
        });
    }

    async toggleDuty(ambulanceId) {
        return this.request('POST', `/ambulances/${ambulanceId}/toggle-duty`);
    }

    // ─── Hospitals ──────────────────────
    async listHospitals() {
        return this.request('GET', '/hospitals');
    }

    // ─── Signals ────────────────────────
    async listSignals() {
        return this.request('GET', '/signals');
    }

    async sendSignalCommand(signalId, data) {
        return this.request('POST', `/signals/${signalId}/command`, data);
    }

    async overrideSignal(signalId, action, reason) {
        return this.request('POST', `/signals/${signalId}/override`, { action, reason });
    }

    async getSignalCommands(signalId, limit = 20) {
        return this.request('GET', `/signals/${signalId}/commands?limit=${limit}`);
    }

    // ─── AI ─────────────────────────────
    async runAnalysis(emergencyId) {
        return this.request('POST', '/ai/analyze', { emergency_id: emergencyId });
    }

    async getAIDecisions() {
        return this.request('GET', '/ai/decisions');
    }

    // ─── WebSocket ──────────────────────
    connectWS(channel, onMessage) {
        if (this.ws[channel]) {
            try { this.ws[channel].close(); } catch(e) {}
        }

        const ws = new WebSocket(`${WS_BASE}/${channel}`);
        
        ws.onopen = () => {
            console.log(`[WS] Connected to ${channel}`);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type !== 'ack') {
                    onMessage(data);
                }
            } catch (e) {
                console.warn('[WS] Parse error:', e);
            }
        };

        ws.onclose = () => {
            console.log(`[WS] Disconnected from ${channel}`);
            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (this.ws[channel] === ws) {
                    this.connectWS(channel, onMessage);
                }
            }, 3000);
        };

        ws.onerror = (e) => {
            console.error(`[WS] Error on ${channel}:`, e);
        };

        this.ws[channel] = ws;
        return ws;
    }

    disconnectWS(channel) {
        if (this.ws[channel]) {
            this.ws[channel].close();
            delete this.ws[channel];
        }
    }

    disconnectAll() {
        Object.keys(this.ws).forEach(ch => this.disconnectWS(ch));
    }
}

// Global API instance
const api = new AegisAPI();
