from __future__ import annotations

from typing import Any


PERSON_LABELS = {
    "person",
}

ANIMAL_LABELS = {
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
}

VEHICLE_LABELS = {
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
}

CARRIED_OBJECT_LABELS = {
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
}

CATEGORY_PRIORITY = (
    "person",
    "animal",
    "vehicle",
    "carried_object",
    "general_object",
)


def normalize_label(value: Any) -> str:
    return str(value or "").strip().lower()


def extract_labels(
    objects: list[Any] | None,
) -> list[str]:
    labels: list[str] = []

    for detected_object in objects or []:
        if isinstance(detected_object, dict):
            label = normalize_label(
                detected_object.get("label")
            )
        else:
            label = normalize_label(
                getattr(
                    detected_object,
                    "label",
                    None,
                )
            )

        if label and label not in labels:
            labels.append(label)

    return labels


def category_for_label(label: str) -> str:
    if label in PERSON_LABELS:
        return "person"

    if label in ANIMAL_LABELS:
        return "animal"

    if label in VEHICLE_LABELS:
        return "vehicle"

    if label in CARRIED_OBJECT_LABELS:
        return "carried_object"

    return "general_object"


def classify_event_objects(
    objects: list[Any] | None,
    trigger_reason: str | None,
) -> dict[str, Any]:
    labels = extract_labels(objects)

    motion_confirmed = normalize_label(
        trigger_reason
    ) in {
        "motion",
        "pir_motion",
    }

    if not labels:
        primary_category = (
            "unknown_motion"
            if motion_confirmed
            else "no_detection"
        )

        return {
            "status": "unclassified",
            "primary_category": primary_category,
            "categories": [primary_category],
            "labels": [],
            "motion_confirmed": motion_confirmed,
            "detection_count": 0,
        }

    detected_categories = {
        category_for_label(label)
        for label in labels
    }

    categories = [
        category
        for category in CATEGORY_PRIORITY
        if category in detected_categories
    ]

    return {
        "status": "classified",
        "primary_category": categories[0],
        "categories": categories,
        "labels": labels,
        "motion_confirmed": motion_confirmed,
        "detection_count": len(labels),
    }
