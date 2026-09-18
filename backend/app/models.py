from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        CheckConstraint("cpu_percent >= 0 AND cpu_percent <= 100", name="ck_metrics_cpu"),
        CheckConstraint("memory_used_bytes >= 0 AND memory_total_bytes > 0 AND memory_used_bytes <= memory_total_bytes", name="ck_metrics_memory"),
        CheckConstraint("disk_used_bytes >= 0 AND disk_total_bytes > 0 AND disk_used_bytes <= disk_total_bytes", name="ck_metrics_disk"),
        Index("ix_metrics_agent_collected_id", "agent_id", "collected_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(128))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_used_bytes: Mapped[int] = mapped_column(BigInteger)
    memory_total_bytes: Mapped[int] = mapped_column(BigInteger)
    disk_used_bytes: Mapped[int] = mapped_column(BigInteger)
    disk_total_bytes: Mapped[int] = mapped_column(BigInteger)
    cpu_max_percent: Mapped[float | None] = mapped_column(Float)
    sample_duration_seconds: Mapped[float | None] = mapped_column(Float)
    uptime_seconds: Mapped[int | None] = mapped_column(BigInteger)
    network_receive_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    network_send_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    disk_read_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    disk_write_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    services: Mapped[dict[str, str] | None] = mapped_column(JSONB)
