from __future__ import annotations

from shared.schemas import AgentDecision, AgentInput, Detection, RiskLevel, VisionResult


IMPORTANT_OBJECTS = {
    "person",
    "car",
    "motorcycle",
    "bus",
    "truck",
}

CONTEXT_OBJECTS = {
    "backpack",
    "handbag",
    "suitcase",
    "laptop",
    "cell phone",
    "bottle",
    "chair",
    "potted plant",
    "tv",
    "keyboard",
    "mouse",
}

POOR_FRAME_QUALITY = {
    "blurry",
}

POOR_LIGHTING = {
    "too_dark",
    "too_bright",
}


def normalize_label(label: str) -> str:
    return label.strip().lower()


def format_detected_objects(objects: list[Detection]) -> str:
    if not objects:
        return "none"

    parts = []
    for obj in objects[:5]:
        parts.append(f"{obj.label} ({obj.confidence:.2f})")

    if len(objects) > 5:
        parts.append(f"+{len(objects) - 5} more")

    return ", ".join(parts)


def score_vision(vision: VisionResult) -> tuple[int, str, dict]:
    objects = vision.objects
    frame_metadata = vision.frame_metadata or {}

    labels = [normalize_label(obj.label) for obj in objects]
    detected_labels = set(labels)

    frame_quality = frame_metadata.get("frame_quality", "unknown")
    lighting_status = frame_metadata.get("lighting_status", "unknown")
    detector_status = frame_metadata.get("detector_status", "unknown")
    detection_count = int(frame_metadata.get("detection_count", len(objects)))
    model_latency_ms = frame_metadata.get("model_latency_ms")
    blur_score = frame_metadata.get("blur_score")
    brightness = frame_metadata.get("brightness")

    poor_frame = frame_quality in POOR_FRAME_QUALITY
    poor_lighting = lighting_status in POOR_LIGHTING
    vision_uncertain = poor_frame or poor_lighting or detector_status == "mock_fallback"

    important_detected = sorted(detected_labels.intersection(IMPORTANT_OBJECTS))
    context_detected = sorted(detected_labels.intersection(CONTEXT_OBJECTS))

    summary = {
        "detector_status": detector_status,
        "detection_count": detection_count,
        "detected_objects": [
            {
                "label": obj.label,
                "confidence": obj.confidence,
                "bbox": obj.bbox,
            }
            for obj in objects
        ],
        "frame_quality": frame_quality,
        "lighting_status": lighting_status,
        "vision_uncertain": vision_uncertain,
        "model_latency_ms": model_latency_ms,
        "blur_score": blur_score,
        "brightness": brightness,
    }

    if "person" in detected_labels and (
        "backpack" in detected_labels
        or "handbag" in detected_labels
        or "suitcase" in detected_labels
    ):
        return (
            2,
            f"Person with carried object detected: {format_detected_objects(objects)}.",
            summary,
        )

    if "person" in detected_labels:
        return (
            1,
            f"Person detected by real vision model: {format_detected_objects(objects)}.",
            summary,
        )

    if important_detected:
        return (
            1,
            f"Important object detected by real vision model: {format_detected_objects(objects)}.",
            summary,
        )

    if context_detected:
        return (
            0,
            f"Context object detected, but no direct safety object found: {format_detected_objects(objects)}.",
            summary,
        )

    if objects:
        return (
            0,
            f"Objects detected, but none are currently risk-relevant: {format_detected_objects(objects)}.",
            summary,
        )

    if vision_uncertain:
        return (
            1,
            (
                "No object detected, but vision is uncertain because "
                f"frame_quality={frame_quality} and lighting_status={lighting_status}."
            ),
            summary,
        )

    return (
        0,
        "No relevant object detected and the frame quality is acceptable.",
        summary,
    )


def score_sensors(air_quality_level: str, temperature_c: float) -> tuple[int, str, dict]:
    summary = {
        "air_quality_level": air_quality_level,
        "temperature_c": temperature_c,
    }

    if air_quality_level == "critical" or temperature_c > 32:
        return 2, "Critical environmental condition detected.", summary

    if air_quality_level == "warning" or temperature_c > 28:
        return 1, "Environmental warning detected.", summary

    return 0, "Environmental readings are normal.", summary


def score_audio(
    event: str,
    confidence: float,
    volume_db: float,
    source_mode: str = "unknown",
    hardware_ready: bool = False,
) -> tuple[int, str, dict]:
    summary = {
        "event": event,
        "confidence": confidence,
        "volume_db": volume_db,
        "source_mode": source_mode,
        "hardware_ready": hardware_ready,
        "trusted_for_risk": hardware_ready,
    }

    if not hardware_ready:
        return (
            0,
            (
                "Audio hardware is not connected. "
                "Mock audio was stored as metadata only "
                "and excluded from risk scoring."
            ),
            summary,
        )

    if event == "alarm_like_sound":
        return 2, "Alarm-like sound detected.", summary

    if event == "loud_noise":
        return 1, "Loud noise detected.", summary

    return 0, "Audio level is normal.", summary


def combine_risk(
    total_score: int,
    vision_score: int,
    sensor_score: int,
    audio_score: int,
    vision_uncertain: bool,
) -> RiskLevel:
    if sensor_score == 2 or audio_score == 2:
        return RiskLevel.HIGH

    if vision_score >= 2 and (sensor_score >= 1 or audio_score >= 1):
        return RiskLevel.HIGH

    if total_score >= 4:
        return RiskLevel.HIGH

    if sensor_score == 1:
        return RiskLevel.MEDIUM

    if vision_uncertain and (sensor_score >= 1 or audio_score >= 1):
        return RiskLevel.MEDIUM

    if total_score >= 2:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def recommended_action(risk: RiskLevel, vision_uncertain: bool) -> str:
    if risk == RiskLevel.HIGH:
        return "Manual inspection recommended immediately. Check ventilation and investigate the detected event."

    if risk == RiskLevel.MEDIUM:
        if vision_uncertain:
            return "Check the environment and improve camera visibility before trusting the vision result."
        return "Check the environment and verify ventilation or safety conditions."

    if vision_uncertain:
        return "No immediate danger detected, but improve lighting or camera focus and continue monitoring."

    return "No immediate action required. Continue monitoring."


def analyze(input_data: AgentInput) -> AgentDecision:
    vision_score, vision_reason, vision_summary = score_vision(input_data.vision)

    sensor_score, sensor_reason, sensor_summary = score_sensors(
        input_data.sensors.air_quality_level,
        input_data.sensors.temperature_c,
    )

    audio_score, audio_reason, audio_summary = score_audio(
        input_data.audio.event,
        input_data.audio.confidence,
        input_data.audio.volume_db,
        input_data.audio.source_mode,
        input_data.audio.hardware_ready,
    )

    vision_uncertain = bool(
        vision_summary.get("vision_uncertain")
    )

    if (
        not input_data.vision.objects
        and vision_uncertain
    ):
        vision_score = 0
        vision_reason = (
            "No relevant object detected. "
            "Frame-quality uncertainty was recorded as "
            "metadata and did not add risk."
        )

    total = vision_score + sensor_score + audio_score

    risk = combine_risk(
        total_score=total,
        vision_score=vision_score,
        sensor_score=sensor_score,
        audio_score=audio_score,
        vision_uncertain=vision_uncertain,
    )

    reason = (
        f"{vision_reason} "
        f"{sensor_reason} "
        f"{audio_reason} "
        f"Total risk score: {total}."
    )

    return AgentDecision(
        final_risk=risk,
        reason=reason,
        recommended_action=recommended_action(risk, vision_uncertain),
        modality_summary={
            "vision_score": vision_score,
            "sensor_score": sensor_score,
            "audio_score": audio_score,
            "total_score": total,
            "vision_reason": vision_reason,
            "sensor_reason": sensor_reason,
            "audio_reason": audio_reason,
            "vision": vision_summary,
            "sensors": sensor_summary,
            "audio": audio_summary,
        },
    )
