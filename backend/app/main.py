import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="Monitoring Service",
    description="Приём и чтение метрик агентов мониторинга.",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(router)


class HealthResponse(BaseModel):
    status: str
    database: str


@app.get("/health", response_model=HealthResponse, tags=["Состояние"])
def health() -> HealthResponse:
    """Проверить, что API может выполнить запрос к PostgreSQL."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Не удалось проверить подключение к PostgreSQL")
        raise HTTPException(
            status_code=503,
            detail="База данных недоступна",
        ) from None

    return HealthResponse(status="ok", database="ok")
