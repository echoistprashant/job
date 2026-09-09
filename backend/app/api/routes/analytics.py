from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.services.analytics_service import SystemMetricsOverview, analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=SystemMetricsOverview, status_code=status.HTTP_200_OK)
def get_metrics_overview(db: Session = Depends(get_db)):
    """
    Phase 50: Retrieve production telemetry, funnel conversions, success rates, and active daemon statuses.
    """
    return analytics_service.get_overview_metrics(db)
