from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def safe_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def percentile(
    values: list[float],
    percentile_value: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return round(ordered[0], 4)

    position = (
        percentile_value / 100
    ) * (len(ordered) - 1)

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return round(
            ordered[lower_index],
            4,
        )

    fraction = position - lower_index

    result = (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )

    return round(result, 4)


def numeric_summary(
    values: list[float],
) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "p95": None,
        }

    ordered = sorted(values)
    count = len(ordered)
    mean = sum(ordered) / count

    if count % 2 == 1:
        median = ordered[count // 2]
    else:
        median = (
            ordered[(count // 2) - 1]
            + ordered[count // 2]
        ) / 2

    return {
        "count": count,
        "minimum": round(min(ordered), 4),
        "maximum": round(max(ordered), 4),
        "mean": round(mean, 4),
        "median": round(median, 4),
        "p25": percentile(ordered, 25),
        "p75": percentile(ordered, 75),
        "p90": percentile(ordered, 90),
        "p95": percentile(ordered, 95),
    }


def load_events(
    events_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    events = []
    errors = []

    event_paths = sorted(
        events_dir.glob("*.json"),
        key=lambda path: path.name,
    )

    for event_path in event_paths:
        try:
            payload = json.loads(
                event_path.read_text(
                    encoding="utf-8",
                )
            )

            if not isinstance(payload, dict):
                raise ValueError(
                    "Event payload is not a JSON object."
                )

            payload["_source_path"] = str(
                event_path
            )

            events.append(payload)

        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(
                {
                    "event_path": str(event_path),
                    "error": repr(exc),
                }
            )

    return events, errors


def build_event_row(
    event: dict[str, Any],
) -> dict[str, Any]:
    trigger = event.get("trigger") or {}
    vision = event.get("vision") or {}
    frame_metadata = (
        vision.get("frame_metadata")
        or {}
    )
    sensors = event.get("sensors") or {}
    audio = event.get("audio") or {}
    decision = event.get("decision") or {}
    modality_summary = (
        decision.get("modality_summary")
        or {}
    )
    enrichment = event.get("enrichment") or {}

    objects = [
        item
        for item in (
            vision.get("objects")
            or []
        )
        if isinstance(item, dict)
    ]

    object_labels = [
        str(item.get("label") or "unknown")
        for item in objects
    ]

    final_risk = str(
        decision.get("final_risk")
        or "UNKNOWN"
    ).upper()

    trigger_reason = str(
        trigger.get("reason")
        or "unknown"
    )

    audio_event = str(
        audio.get("event")
        or "unknown"
    )

    air_quality_level = str(
        sensors.get("air_quality_level")
        or "unknown"
    )

    frame_quality = str(
        frame_metadata.get("frame_quality")
        or "unknown"
    )

    motion_percent = safe_float(
        trigger.get("motion_percent")
    )

    blur_score = safe_float(
        frame_metadata.get("blur_score")
    )

    brightness = safe_float(
        frame_metadata.get("brightness")
    )

    model_latency_ms = safe_float(
        frame_metadata.get(
            "model_latency_ms"
        )
    )

    volume_db = safe_float(
        audio.get("volume_db")
    )

    total_score = safe_float(
        modality_summary.get("total_score")
    )

    detection_count = len(objects)

    high_without_objects = (
        final_risk == "HIGH"
        and detection_count == 0
    )

    motion_without_objects = (
        trigger_reason == "motion"
        and detection_count == 0
    )

    periodic_detection = (
        trigger_reason
        == "periodic_safety_scan"
        and detection_count > 0
    )

    blurry_detection = (
        detection_count > 0
        and frame_quality == "blurry"
    )

    normal_audio_high_risk = (
        final_risk == "HIGH"
        and audio_event == "normal_sound"
    )

    return {
        "event_id": event.get("event_id"),
        "created_at": event.get("created_at"),
        "trigger_reason": trigger_reason,
        "motion_percent": motion_percent,
        "final_risk": final_risk,
        "detection_count": detection_count,
        "detected_objects": ",".join(
            object_labels
        ),
        "frame_quality": frame_quality,
        "blur_score": blur_score,
        "brightness": brightness,
        "model_latency_ms": model_latency_ms,
        "air_quality_level": air_quality_level,
        "air_quality_raw": sensors.get(
            "air_quality_raw"
        ),
        "temperature_c": sensors.get(
            "temperature_c"
        ),
        "audio_event": audio_event,
        "volume_db": volume_db,
        "audio_confidence": audio.get(
            "confidence"
        ),
        "total_score": total_score,
        "enrichment_status": enrichment.get(
            "status"
        ),
        "decision_reason": decision.get(
            "reason"
        ),
        "recommended_action": decision.get(
            "recommended_action"
        ),
        "high_without_objects": high_without_objects,
        "motion_without_objects": motion_without_objects,
        "periodic_detection": periodic_detection,
        "blurry_detection": blurry_detection,
        "normal_audio_high_risk": normal_audio_high_risk,
        "source_path": event.get(
            "_source_path"
        ),
    }


def build_report(
    rows: list[dict[str, Any]],
    errors: list[dict[str, str]],
    events_dir: Path,
) -> dict[str, Any]:
    risk_counts = Counter(
        row["final_risk"]
        for row in rows
    )

    trigger_counts = Counter(
        row["trigger_reason"]
        for row in rows
    )

    object_counts = Counter()

    for row in rows:
        object_text = (
            row["detected_objects"]
            or ""
        )

        for label in object_text.split(","):
            normalized = label.strip()

            if normalized:
                object_counts[normalized] += 1

    frame_quality_counts = Counter(
        row["frame_quality"]
        for row in rows
    )

    air_quality_counts = Counter(
        row["air_quality_level"]
        for row in rows
    )

    audio_event_counts = Counter(
        row["audio_event"]
        for row in rows
    )

    enrichment_counts = Counter(
        str(
            row["enrichment_status"]
            or "unknown"
        )
        for row in rows
    )

    motion_values = [
        value
        for value in (
            row["motion_percent"]
            for row in rows
        )
        if value is not None
    ]

    blur_values = [
        value
        for value in (
            row["blur_score"]
            for row in rows
        )
        if value is not None
    ]

    brightness_values = [
        value
        for value in (
            row["brightness"]
            for row in rows
        )
        if value is not None
    ]

    latency_values = [
        value
        for value in (
            row["model_latency_ms"]
            for row in rows
        )
        if value is not None
    ]

    volume_values = [
        value
        for value in (
            row["volume_db"]
            for row in rows
        )
        if value is not None
    ]

    candidate_keys = [
        "high_without_objects",
        "motion_without_objects",
        "periodic_detection",
        "blurry_detection",
        "normal_audio_high_risk",
    ]

    candidate_review = {}

    for key in candidate_keys:
        matching_rows = [
            row
            for row in rows
            if row[key]
        ]

        candidate_review[key] = {
            "count": len(matching_rows),
            "event_ids": [
                row["event_id"]
                for row in matching_rows[:100]
            ],
        }

    events_with_objects = sum(
        1
        for row in rows
        if row["detection_count"] > 0
    )

    events_without_objects = (
        len(rows) - events_with_objects
    )

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "events_directory": str(events_dir),
        "total_events": len(rows),
        "load_errors": errors,
        "event_content": {
            "events_with_objects": events_with_objects,
            "events_without_objects": events_without_objects,
        },
        "distributions": {
            "risk": dict(
                sorted(risk_counts.items())
            ),
            "trigger": dict(
                sorted(trigger_counts.items())
            ),
            "objects": dict(
                sorted(object_counts.items())
            ),
            "frame_quality": dict(
                sorted(
                    frame_quality_counts.items()
                )
            ),
            "air_quality": dict(
                sorted(
                    air_quality_counts.items()
                )
            ),
            "audio_event": dict(
                sorted(
                    audio_event_counts.items()
                )
            ),
            "enrichment_status": dict(
                sorted(
                    enrichment_counts.items()
                )
            ),
        },
        "numeric_summary": {
            "motion_percent": numeric_summary(
                motion_values
            ),
            "blur_score": numeric_summary(
                blur_values
            ),
            "brightness": numeric_summary(
                brightness_values
            ),
            "model_latency_ms": numeric_summary(
                latency_values
            ),
            "audio_volume_db": numeric_summary(
                volume_values
            ),
        },
        "candidate_review": candidate_review,
        "interpretation_note": (
            "Candidate review groups are not confirmed false positives. "
            "They are event subsets that require manual evidence review "
            "before changing thresholds or agent rules."
        ),
    }


def write_csv(
    rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    if not rows:
        output_path.write_text(
            "",
            encoding="utf-8",
        )
        return

    fieldnames = list(rows[0].keys())

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--events-dir",
        default="data/events",
    )

    parser.add_argument(
        "--output-dir",
        default="data/calibration",
    )

    args = parser.parse_args()

    events_dir = Path(args.events_dir)
    output_dir = Path(args.output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    events, errors = load_events(
        events_dir
    )

    rows = [
        build_event_row(event)
        for event in events
    ]

    report = build_report(
        rows=rows,
        errors=errors,
        events_dir=events_dir,
    )

    report_path = (
        output_dir
        / "event_calibration_summary.json"
    )

    csv_path = (
        output_dir
        / "event_calibration_events.csv"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    write_csv(
        rows=rows,
        output_path=csv_path,
    )

    print(
        "Calibration analysis completed."
    )
    print(
        "Events analyzed:",
        report["total_events"],
    )
    print(
        "Risk distribution:",
        report["distributions"]["risk"],
    )
    print(
        "Trigger distribution:",
        report["distributions"]["trigger"],
    )
    print(
        "Events with objects:",
        report["event_content"][
            "events_with_objects"
        ],
    )
    print(
        "Events without objects:",
        report["event_content"][
            "events_without_objects"
        ],
    )

    for name, result in report[
        "candidate_review"
    ].items():
        print(
            f"{name}:",
            result["count"],
        )

    print(
        "JSON report:",
        report_path,
    )
    print(
        "CSV report:",
        csv_path,
    )


if __name__ == "__main__":
    main()
