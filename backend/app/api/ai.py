"""
Aegis Flow - AI API Routes
Endpoints for AI emergency analysis, decision logs, and predictive corridor stats.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.database.db import get_db
from backend.app.models.models import AIDecision, EmergencyRequest
from backend.app.schemas.schemas import AIAnalyzeRequest, AIDecisionResponse
from backend.app.ai.decision_engine import DecisionEngine
from backend.app.ai.traffic_analyzer import TrafficAnalyzer

router = APIRouter(prefix="/ai", tags=["AI Decision Engine"])


@router.post("/analyze", response_model=AIDecisionResponse)
async def analyze_emergency(
    data: AIAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    Run comprehensive AI evaluation for an emergency request:
    computes priority score, green corridor ETA savings, traffic density,
    and decision factors with natural language explanation.
    """
    emergency = db.query(EmergencyRequest).filter(EmergencyRequest.id == data.emergency_id).first()
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    try:
        decision = await DecisionEngine.analyze_emergency(
            emergency_id=data.emergency_id,
            db=db,
            ambulance_lat=data.ambulance_latitude,
            ambulance_lon=data.ambulance_longitude,
            ambulance_speed=data.ambulance_speed_kmh,
        )
        return decision
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.get("/decisions", response_model=List[AIDecisionResponse])
def get_decisions(
    limit: int = Query(20, ge=1, le=100),
    emergency_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retrieve recent AI decisions with explainability factors and ratings."""
    query = db.query(AIDecision)
    if emergency_id:
        query = query.filter(AIDecision.emergency_id == emergency_id)
    return query.order_by(AIDecision.created_at.desc()).limit(limit).all()


@router.get("/traffic/density")
def get_traffic_density(
    lat: float = Query(18.5204, ge=-90, le=90),
    lon: float = Query(73.8567, ge=-180, le=180),
):
    """Get real-time traffic density estimation and recommended approach timings."""
    return TrafficAnalyzer.estimate_corridor_density(lat, lon)
