from shared.decision_logic import analyze
from shared.schemas import AgentInput, AudioResult, Detection, SensorReading, VisionResult, RiskLevel


def test_normal_environment_is_low_risk():
    decision = analyze(AgentInput(
        vision=VisionResult(objects=[]),
        sensors=SensorReading(temperature_c=24, humidity_percent=45, pressure_hpa=1012, air_quality_raw=420, air_quality_level="normal"),
        audio=AudioResult(event="normal_sound", confidence=0.7, volume_db=48),
    ))
    assert decision.final_risk == RiskLevel.LOW


def test_multimodal_warning_is_high_risk():
    decision = analyze(AgentInput(
        vision=VisionResult(objects=[Detection(label="person", confidence=0.9, bbox=[]), Detection(label="bag", confidence=0.8, bbox=[])]),
        sensors=SensorReading(temperature_c=33, humidity_percent=60, pressure_hpa=1008, air_quality_raw=810, air_quality_level="critical"),
        audio=AudioResult(event="loud_noise", confidence=0.8, volume_db=78),
    ))
    assert decision.final_risk == RiskLevel.HIGH


def test_environmental_warning_alone_is_medium_risk():
    decision = analyze(AgentInput(
        vision=VisionResult(objects=[]),
        sensors=SensorReading(
            temperature_c=24,
            humidity_percent=45,
            pressure_hpa=1012,
            air_quality_raw=620,
            air_quality_level="warning",
        ),
        audio=AudioResult(event="normal_sound", confidence=0.7, volume_db=48),
    ))

    assert decision.final_risk == RiskLevel.MEDIUM
