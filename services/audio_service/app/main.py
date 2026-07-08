import random

from fastapi import FastAPI

from shared.schemas import (
    AudioResult,
    ServiceStatus,
)


app = FastAPI(
    title="EdgeSense-MA Audio Service",
    version="0.5.0",
)


def classify_audio(
    volume_db: float,
) -> tuple[str, float]:
    if volume_db >= 85:
        return "alarm_like_sound", 0.86

    if volume_db >= 70:
        return "loud_noise", 0.78

    return "normal_sound", 0.70


@app.get(
    "/audio/status",
    response_model=ServiceStatus,
)
def audio_status() -> ServiceStatus:
    return ServiceStatus(
        service="audio_service",
        details={
            "mode": "mock",
            "source_mode": "mock",
            "hardware_ready": False,
            "trusted_for_risk": False,
            "note": (
                "Synthetic audio metadata is excluded "
                "from risk scoring."
            ),
        },
    )


@app.get(
    "/audio/latest",
    response_model=AudioResult,
)
def latest_audio() -> AudioResult:
    volume = round(
        random.uniform(35.0, 92.0),
        1,
    )

    event, confidence = classify_audio(volume)

    return AudioResult(
        event=event,
        confidence=confidence,
        volume_db=volume,
        source_mode="mock",
        hardware_ready=False,
    )
