from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EVENTS_DIR = Path(
    os.getenv(
        "EDGESENSE_EVENTS_DIR",
        "data/events",
    )
)

EVENT_IMAGES_DIR = EVENTS_DIR / "images"

MAX_EVENTS = max(
    1,
    int(os.getenv("EDGESENSE_MAX_EVENTS", "500")),
)

EVENT_RETENTION_DAYS = max(
    1,
    int(os.getenv("EDGESENSE_EVENT_RETENTION_DAYS", "30")),
)

EVENT_ID_PATTERN = re.compile(
    r"^[0-9]{8}T[0-9]{6}_[0-9]{6}Z_[a-f0-9]{8}$"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def create_event_id() -> str:
    timestamp = utc_now().strftime("%Y%m%dT%H%M%S_%fZ")
    random_suffix = secrets.token_hex(4)
    return f"{timestamp}_{random_suffix}"


def validate_event_id(event_id: str) -> str:
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        raise ValueError(f"Invalid event ID: {event_id}")

    return event_id


def ensure_event_directories() -> None:
    EVENTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    EVENT_IMAGES_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def copy_event_image(
    event_id: str,
    source_image_path: str | Path,
    image_label: str | None = None,
) -> str | None:
    source = Path(source_image_path)

    if not source.exists() or not source.is_file():
        return None

    suffix = source.suffix.lower()

    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"

    if image_label:
        safe_label = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            image_label.lower(),
        ).strip("_")

        if not safe_label:
            raise ValueError("Event image label is empty.")

        destination = (
            EVENT_IMAGES_DIR
            / f"{event_id}_{safe_label}{suffix}"
        )
    else:
        destination = (
            EVENT_IMAGES_DIR
            / f"{event_id}{suffix}"
        )

    shutil.copy2(
        source,
        destination,
    )

    return str(destination)


def parse_event_created_at(
    event_path: Path,
) -> datetime:
    try:
        payload = json.loads(
            event_path.read_text(
                encoding="utf-8",
            )
        )

        created_at = payload.get("created_at")

        if isinstance(created_at, str):
            parsed = datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00",
                )
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc,
                )

            return parsed.astimezone(
                timezone.utc,
            )

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        pass

    return datetime.fromtimestamp(
        event_path.stat().st_mtime,
        tz=timezone.utc,
    )


def delete_event_files(
    event_path: Path,
) -> dict[str, int]:
    deleted_events = 0
    deleted_images = 0

    event_id = event_path.stem

    if event_path.exists():
        event_path.unlink()
        deleted_events = 1

    for image_path in EVENT_IMAGES_DIR.glob(
        f"{event_id}*"
    ):
        if image_path.is_file():
            image_path.unlink()
            deleted_images += 1

    return {
        "deleted_events": deleted_events,
        "deleted_images": deleted_images,
    }


def cleanup_event_store() -> dict[str, Any]:
    ensure_event_directories()

    event_paths = sorted(
        EVENTS_DIR.glob("*.json"),
        key=lambda path: path.name,
        reverse=True,
    )

    scanned_events = len(event_paths)
    deleted_events = 0
    deleted_images = 0
    errors = []

    if not event_paths:
        return {
            "scanned_events": 0,
            "retained_events": 0,
            "deleted_events": 0,
            "deleted_images": 0,
            "max_events": MAX_EVENTS,
            "retention_days": EVENT_RETENTION_DAYS,
            "errors": [],
        }

    newest_event_path = event_paths[0]

    cutoff = utc_now() - timedelta(
        days=EVENT_RETENTION_DAYS,
    )

    for index, event_path in enumerate(
        event_paths
    ):
        if event_path == newest_event_path:
            continue

        exceeds_count_limit = index >= MAX_EVENTS

        try:
            event_created_at = parse_event_created_at(
                event_path
            )

            exceeds_age_limit = (
                event_created_at < cutoff
            )

        except OSError as exc:
            errors.append(
                {
                    "event_path": str(event_path),
                    "error": repr(exc),
                }
            )
            continue

        if not (
            exceeds_count_limit
            or exceeds_age_limit
        ):
            continue

        try:
            deletion_result = delete_event_files(
                event_path
            )

            deleted_events += deletion_result[
                "deleted_events"
            ]

            deleted_images += deletion_result[
                "deleted_images"
            ]

        except OSError as exc:
            errors.append(
                {
                    "event_path": str(event_path),
                    "error": repr(exc),
                }
            )

    retained_events = len(
        list(EVENTS_DIR.glob("*.json"))
    )

    return {
        "scanned_events": scanned_events,
        "retained_events": retained_events,
        "deleted_events": deleted_events,
        "deleted_images": deleted_images,
        "max_events": MAX_EVENTS,
        "retention_days": EVENT_RETENTION_DAYS,
        "errors": errors,
    }


def save_event(
    payload: dict[str, Any],
    annotated_image_path: str | Path | None = None,
    additional_image_paths: dict[
        str,
        str | Path,
    ] | None = None,
) -> dict[str, Any]:
    ensure_event_directories()

    event = dict(payload)

    event_id = str(
        event.get("event_id")
        or create_event_id()
    )

    validate_event_id(event_id)

    event["event_id"] = event_id
    event.setdefault(
        "created_at",
        utc_now_iso(),
    )

    if annotated_image_path:
        copied_image_path = copy_event_image(
            event_id=event_id,
            source_image_path=annotated_image_path,
        )

        if copied_image_path:
            evidence = dict(
                event.get("evidence")
                or {}
            )

            evidence["annotated_image_path"] = copied_image_path
            event["evidence"] = evidence

    if additional_image_paths:
        evidence = dict(
            event.get("evidence")
            or {}
        )

        for image_label, source_image_path in (
            additional_image_paths.items()
        ):
            copied_image_path = copy_event_image(
                event_id=event_id,
                source_image_path=source_image_path,
                image_label=image_label,
            )

            if copied_image_path:
                evidence[
                    f"{image_label}_image_path"
                ] = copied_image_path

        event["evidence"] = evidence

    event_path = EVENTS_DIR / f"{event_id}.json"
    temporary_path = EVENTS_DIR / f".{event_id}.tmp"

    temporary_path.write_text(
        json.dumps(
            event,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(event_path)

    event["event_path"] = str(event_path)
    event["retention_cleanup"] = cleanup_event_store()

    return event


def read_event(event_id: str) -> dict[str, Any]:
    validate_event_id(event_id)

    event_path = EVENTS_DIR / f"{event_id}.json"

    if not event_path.exists():
        raise FileNotFoundError(
            f"Event was not found: {event_id}"
        )

    return json.loads(
        event_path.read_text(
            encoding="utf-8",
        )
    )


def summarize_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    trigger = event.get("trigger") or {}
    vision = event.get("vision") or {}
    decision = event.get("decision") or {}
    classification = (
        event.get("classification")
        or {}
    )

    objects = vision.get("objects") or []

    return {
        "event_id": event.get("event_id"),
        "created_at": event.get("created_at"),
        "trigger_reason": trigger.get("reason"),
        "motion_percent": trigger.get("motion_percent"),
        "detection_count": len(objects),
        "detected_objects": [
            obj.get("label")
            for obj in objects
            if isinstance(obj, dict)
        ],
        "classification_status": classification.get(
            "status"
        ),
        "primary_category": classification.get(
            "primary_category"
        ),
        "categories": classification.get(
            "categories"
        ) or [],
        "final_risk": decision.get("final_risk"),
        "event_path": event.get("event_path"),
    }


def normalize_event_filter(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()

    if not normalized or normalized == "all":
        return None

    return normalized


def event_matches_filters(
    event_summary: dict[str, Any],
    risk: str | None = None,
    trigger: str | None = None,
    object_label: str | None = None,
    category: str | None = None,
) -> bool:
    normalized_risk = normalize_event_filter(risk)
    normalized_trigger = normalize_event_filter(trigger)
    normalized_object = normalize_event_filter(object_label)
    normalized_category = normalize_event_filter(category)

    event_risk = str(
        event_summary.get("final_risk")
        or ""
    ).strip().lower()

    event_trigger = str(
        event_summary.get("trigger_reason")
        or ""
    ).strip().lower()

    event_objects = {
        str(label).strip().lower()
        for label in (
            event_summary.get("detected_objects")
            or []
        )
        if label is not None
    }

    event_categories = {
        str(value).strip().lower()
        for value in (
            event_summary.get("categories")
            or []
        )
        if value is not None
    }

    primary_category = str(
        event_summary.get("primary_category")
        or ""
    ).strip().lower()

    if primary_category:
        event_categories.add(primary_category)

    if (
        normalized_risk is not None
        and event_risk != normalized_risk
    ):
        return False

    if (
        normalized_trigger is not None
        and event_trigger != normalized_trigger
    ):
        return False

    if (
        normalized_object is not None
        and normalized_object not in event_objects
    ):
        return False

    if (
        normalized_category is not None
        and normalized_category not in event_categories
    ):
        return False

    return True


def list_events(
    limit: int = 50,
    risk: str | None = None,
    trigger: str | None = None,
    object_label: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    ensure_event_directories()

    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    event_paths = sorted(
        EVENTS_DIR.glob("*.json"),
        key=lambda path: path.name,
        reverse=True,
    )

    events = []

    for event_path in event_paths:
        try:
            event = json.loads(
                event_path.read_text(
                    encoding="utf-8",
                )
            )

            event["event_path"] = str(event_path)
            event_summary = summarize_event(event)

            if not event_matches_filters(
                event_summary=event_summary,
                risk=risk,
                trigger=trigger,
                object_label=object_label,
                category=category,
            ):
                continue

            events.append(event_summary)

            if len(events) >= safe_limit:
                break

        except (OSError, json.JSONDecodeError):
            continue

    return events



def get_latest_event() -> dict[str, Any] | None:
    events = list_events(limit=1)

    if not events:
        return None

    event_id = events[0].get("event_id")

    if not isinstance(event_id, str):
        return None

    return read_event(event_id)
