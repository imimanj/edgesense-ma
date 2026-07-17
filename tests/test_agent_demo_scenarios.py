import pytest
from fastapi import HTTPException

from services.agent_service.app.main import demo_scenario
from shared.schemas import RiskLevel


def test_normal_demo_is_low_risk():
    decision = demo_scenario("normal")

    assert decision.final_risk == RiskLevel.LOW
    assert decision.modality_summary["total_score"] == 1


def test_environmental_warning_aliases_are_medium_risk():
    for scenario in ("environmental-warning", "environment_warning"):
        decision = demo_scenario(scenario)

        assert decision.final_risk == RiskLevel.MEDIUM
        assert decision.modality_summary["vision_score"] == 1
        assert decision.modality_summary["sensor_score"] == 1
        assert decision.modality_summary["audio_score"] == 0
        assert decision.modality_summary["total_score"] == 2


def test_multimodal_warning_aliases_are_high_risk():
    for scenario in ("multimodal-warning", "multimodal_warning"):
        decision = demo_scenario(scenario)
        labels = {
            item["label"]
            for item in decision.modality_summary["vision"]["detected_objects"]
        }

        assert decision.final_risk == RiskLevel.HIGH
        assert decision.modality_summary["vision_score"] == 2
        assert decision.modality_summary["sensor_score"] == 2
        assert decision.modality_summary["audio_score"] == 1
        assert decision.modality_summary["total_score"] == 5
        assert "backpack" in labels


def test_unknown_demo_scenario_returns_not_found():
    with pytest.raises(HTTPException) as error:
        demo_scenario("unknown-scenario")

    assert error.value.status_code == 404
