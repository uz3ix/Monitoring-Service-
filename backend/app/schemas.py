from datetime import datetime, timezone
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

AgentId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")]
ByteCount = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]
Rate = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ServiceName = Annotated[str, Field(min_length=1, max_length=256)]
ServiceStatus = Literal["running", "paused", "start_pending", "pause_pending", "continue_pending", "stop_pending", "stopped", "not_found", "access_denied", "unknown", "unsupported"]


class MetricCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: AgentId
    collected_at: AwareDatetime
    cpu_percent: float = Field(ge=0, le=100, allow_inf_nan=False, strict=True)
    memory_used_bytes: ByteCount
    memory_total_bytes: ByteCount = Field(gt=0)
    disk_used_bytes: ByteCount
    disk_total_bytes: ByteCount = Field(gt=0)
    cpu_max_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    sample_duration_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    uptime_seconds: ByteCount | None = None
    network_receive_bytes_per_second: Rate | None = None
    network_send_bytes_per_second: Rate | None = None
    disk_read_bytes_per_second: Rate | None = None
    disk_write_bytes_per_second: Rate | None = None
    services: dict[ServiceName, ServiceStatus] | None = Field(default=None, max_length=50)

    @field_validator("collected_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        if self.memory_used_bytes > self.memory_total_bytes:
            raise ValueError("Занятая память не может превышать общий объём")
        if self.disk_used_bytes > self.disk_total_bytes:
            raise ValueError("Занятое место не может превышать объём диска")
        return self


class MetricRead(MetricCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    received_at: AwareDatetime
