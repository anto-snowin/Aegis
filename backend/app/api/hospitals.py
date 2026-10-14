"""
Aegis Flow - Hospital API Routes
Hospital listing and status.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.models.models import Hospital
from backend.app.schemas.schemas import HospitalResponse

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])


@router.get("", response_model=list[HospitalResponse])
def list_hospitals(db: Session = Depends(get_db)):
    """List all active hospitals with emergency departments."""
    return db.query(Hospital).filter(Hospital.is_active == True).all()


@router.get("/{hospital_id}", response_model=HospitalResponse)
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    """Get specific hospital details."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital
