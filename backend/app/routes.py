from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Metric
from app.schemas import AgentId, MetricCreate, MetricRead
from app.security import require_agent_token

router = APIRouter(prefix="/api/v1", tags=["Метрики"], dependencies=[Depends(require_agent_token)])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("/metrics", response_model=MetricRead, status_code=201)
def create_metric(payload: MetricCreate, session: DatabaseSession):
    """Сохранить одно измерение одного агента."""
    metric = Metric(**payload.model_dump())
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric


@router.get("/agents/{agent_id}/metrics/latest", response_model=MetricRead)
def latest_metric(agent_id: AgentId, session: DatabaseSession):
    """Последнее по времени измерения; при равном времени — по ID записи."""
    metric = session.scalar(
        select(Metric)
        .where(Metric.agent_id == agent_id)
        .order_by(Metric.collected_at.desc(), Metric.id.desc())
        .limit(1)
    )
    if metric is None:
        raise HTTPException(status_code=404, detail="Измерения агента не найдены")
    return metric
