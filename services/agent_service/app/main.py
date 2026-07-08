from __future__ import annotations

from fastapi import FastAPI, HTTPException

from shared.decision_logic import analyze
from shared.schemas import AgentDecision, AgentInput, AudioResult, Detection, SensorReading, ServiceStatus, VisionResult

app = FastAPI(title="EdgeSense-MA Agent Service", version="0.1.0")


@app.get("/agents/status", response_model=ServiceStatus)
def status() -> ServiceStatus:
    return ServiceStatus(service="agent_service", details={"mode": "rule-based", "langgraph_ready": False})


@app.post("/agents/analyze", response_model=AgentDecision)
def analyze_modalities(input_data: AgentInput) -> AgentDecision:
    return analyze(input_data)


@app.get("/agents/demo/{scenario}", response_model=AgentDecision)
def demo_scenario(scenario: str) -> AgentDecision:
    if scenario == "normal":
        input_data = AgentInput(
            vision=VisionResult(objects=[Detection(label="person", confidence=0.88, bbox=[10, 20, 100, 200])]),
            sensors=SensorReading(temperature_c=24.0, humidity_percent=45.0, pressure_hpa=1012.0, air_quality_raw=420, air_quality_level="normal"),
            audio=AudioResult(source_mode="demo", hardware_ready=True, event="normal_sound", confidence=0.72, volume_db=48),
        )
    elif scenario in {"environmental-warning", "environment_warning"}:
        input_data = AgentInput(
            vision=VisionResult(objects=[Detection(label="person", confidence=0.91, bbox=[10, 20, 100, 200])]),
            sensors=SensorReading(temperature_c=30.5, humidity_percent=55.0, pressure_hpa=1011.0, air_quality_raw=620, air_quality_level="warning"),
            audio=AudioResult(source_mode="demo", hardware_ready=True, event="normal_sound", confidence=0.71, volume_db=50),
        )
    elif scenario in {"multimodal-warning", "multimodal_warning"}:
        input_data = AgentInput(
            vision=VisionResult(objects=[Detection(label="person", confidence=0.91, bbox=[10, 20, 100, 200]), Detection(label="backpack", confidence=0.76, bbox=[120, 180, 220, 300])]),
            sensors=SensorReading(temperature_c=33.2, humidity_percent=65.0, pressure_hpa=1008.0, air_quality_raw=810, air_quality_level="critical"),
            audio=AudioResult(source_mode="demo", hardware_ready=True, event="loud_noise", confidence=0.82, volume_db=78),
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo scenario: {scenario}",
        )

    return analyze(input_data)
