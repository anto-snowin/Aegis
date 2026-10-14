"""
Aegis Flow - Main FastAPI Application
AI-Powered Emergency Response & Dynamic Traffic Signal Control System

This is a college hackathon prototype. It is NOT connected to any real
emergency services, traffic infrastructure, or medical systems.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from backend.app.database.db import init_db
from backend.app.database.seed import seed_database
from backend.app.api import system, emergencies, ambulances, signals, hospitals, ai
from backend.app.services.websocket_manager import ws_manager
from backend.app.services.mqtt_service import mqtt_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, seed data, and start MQTT service on startup."""
    print("=" * 60)
    print("  AEGIS FLOW - Emergency Response System")
    print("  [!] PROTOTYPE / DEMO - Not for real emergencies")
    print("=" * 60)
    init_db()
    seed_database()
    mqtt_service.start()
    print("[SERVER] Backend ready at http://localhost:8000")
    print("[SERVER] API docs at http://localhost:8000/docs")
    print("[SERVER] Frontend at http://localhost:8000")
    yield
    print("[SERVER] Shutting down Aegis Flow...")
    mqtt_service.stop()


app = FastAPI(
    title="Aegis Flow API",
    description=(
        "AI-Powered Emergency Response & Dynamic Traffic Signal Control System. "
        "⚠️ This is a college hackathon prototype."
    ),
    version="1.0.0-prototype",
    lifespan=lifespan,
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ────────────────────────────────────────
app.include_router(system.router, prefix="/api")
app.include_router(emergencies.router, prefix="/api")
app.include_router(ambulances.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(hospitals.router, prefix="/api")
app.include_router(ai.router, prefix="/api")


# ─── WebSocket Endpoints ──────────────────────────────

@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    """
    WebSocket endpoint for real-time updates.
    Channels: emergencies, tracking, signals, general
    """
    await ws_manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for heartbeat / client messages
            await ws_manager.send_personal(websocket, {
                "type": "ack",
                "channel": channel,
            })
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, channel)


# ─── Static Files (Frontend) ──────────────────────────

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")
    app.mount("/pages", StaticFiles(directory=os.path.join(frontend_dir, "pages")), name="pages")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(os.path.join(frontend_dir, "favicon.ico"),
                            media_type="image/x-icon") if os.path.exists(
            os.path.join(frontend_dir, "favicon.ico")) else ""
