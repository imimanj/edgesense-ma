from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class ServiceStatus(BaseModel):
    service: str
    status: str = "online"
    timestamp: datetime = Field(default_factory=utc_now)
    details: dict = Field(default_factory=dict)


class Detection(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: List[int] = Field(default_factory=list)


class VisionResult(BaseModel):
    objects: List[Detection] = Field(default_factory=list)
    latency_ms: float = 0.0
    fps: float = 0.0
    model: str = "mock-yolo-edge"
    mode: str = "mock"
    snapshot_path: Optional[str] = None
    frame_metadata: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class SensorReading(BaseModel):
    temperature_c: float
    humidity_percent: float
    pressure_hpa: float
    air_quality_raw: int
    air_quality_level: str
    timestamp: datetime = Field(default_factory=utc_now)


class AudioResult(BaseModel):
    event: str
    confidence: float = Field(ge=0, le=1)
    volume_db: float
    source_mode: str = "unknown"
    hardware_ready: bool = False
    timestamp: datetime = Field(default_factory=utc_now)


class AgentInput(BaseModel):
    vision: VisionResult
    sensors: SensorReading
    audio: AudioResult


class AgentDecision(BaseModel):
    final_risk: RiskLevel
    reason: str
    recommended_action: str
    modality_summary: dict
    timestamp: datetime = Field(default_factory=utc_now)
