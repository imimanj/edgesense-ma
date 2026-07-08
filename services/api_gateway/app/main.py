from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from shared.event_store import (
    EVENT_IMAGES_DIR,
    get_latest_event,
    list_events,
    read_event,
)

app = FastAPI(title="EdgeSense-MA API Gateway", version="0.5.0")

REPORTS_DIR = Path("data/reports")
LATEST_REPORT_PATH = REPORTS_DIR / "latest_decision.json"
VISION_WORKER_STATUS_PATH = Path(
    os.getenv(
        "VISION_WORKER_STATUS_PATH",
        "data/runtime/motion_vision_worker_status.json",
    )
)

USE_BACKGROUND_VISION_CACHE = (
    os.getenv("USE_BACKGROUND_VISION_CACHE", "true").lower() == "true"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_worker_status() -> dict:
    if not VISION_WORKER_STATUS_PATH.exists():
        return {
            "worker": "vision-worker",
            "state": "unavailable",
            "error": "Worker status file does not exist.",
        }

    try:
        return json.loads(
            VISION_WORKER_STATUS_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        return {
            "worker": "vision-worker",
            "state": "error",
            "error": str(exc),
        }


def service_url(env_name: str, default_url: str) -> str:
    return os.getenv(env_name, default_url)


SERVICE_URLS = {
    "camera_status": service_url("CAMERA_SERVICE_URL", "http://127.0.0.1:8001/camera/status"),
    "camera_snapshot": service_url("CAMERA_SNAPSHOT_URL", "http://127.0.0.1:8001/camera/snapshot"),

    "sensor_status": service_url("SENSOR_SERVICE_URL", "http://127.0.0.1:8002/sensors/status"),
    "sensor_current": service_url("SENSOR_CURRENT_URL", "http://127.0.0.1:8002/sensors/current"),

    "audio_status": service_url("AUDIO_SERVICE_URL", "http://127.0.0.1:8003/audio/status"),
    "audio_latest": service_url("AUDIO_LATEST_URL", "http://127.0.0.1:8003/audio/latest"),

    "vision_status": service_url("VISION_SERVICE_URL", "http://127.0.0.1:8004/vision/status"),
    "vision_latest": service_url("VISION_LATEST_URL", "http://127.0.0.1:8004/vision/latest"),
    "vision_detect": service_url("VISION_DETECT_URL", "http://127.0.0.1:8004/vision/detect"),

    "agent_status": service_url("AGENT_SERVICE_URL", "http://127.0.0.1:8005/agents/status"),
    "agent_analyze": service_url("AGENT_ANALYZE_URL", "http://127.0.0.1:8005/agents/analyze"),
    "agent_demo": service_url("AGENT_DEMO_URL", "http://127.0.0.1:8005/agents/demo"),
}


async def get_json(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def post_json(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.post(url)
    response.raise_for_status()
    return response.json()


async def run_camera_to_vision(client: httpx.AsyncClient) -> dict:
    """
    Local MVP flow:
    1. Ask camera-service to save a mock snapshot.
    2. Send that saved image file to vision-inference-service.
    3. Return the vision detection result.
    """
    snapshot_result = await post_json(client, SERVICE_URLS["camera_snapshot"])
    image_path = snapshot_result.get("path")

    if not image_path:
        return await get_json(client, SERVICE_URLS["vision_latest"])

    path = Path(image_path)

    if not path.exists():
        return await get_json(client, SERVICE_URLS["vision_latest"])

    with path.open("rb") as image_file:
        files = {
            "file": (
                path.name,
                image_file,
                "image/jpeg",
            )
        }
        response = await client.post(SERVICE_URLS["vision_detect"], files=files)
        response.raise_for_status()
        vision_result = response.json()

    vision_result["snapshot_path"] = str(path)
    return vision_result


def save_decision_report(report: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    LATEST_REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    safe_timestamp = report["generated_at"].replace(":", "-").replace(".", "-")
    history_path = REPORTS_DIR / f"decision_{safe_timestamp}.json"
    history_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "system": "EdgeSense-MA",
        "gateway_version": "0.5.0",
    }


@app.get("/system/status")
async def system_status() -> dict:
    checks = {
        "camera": SERVICE_URLS["camera_status"],
        "sensor": SERVICE_URLS["sensor_status"],
        "audio": SERVICE_URLS["audio_status"],
        "vision": SERVICE_URLS["vision_status"],
        "agent": SERVICE_URLS["agent_status"],
    }

    results = {}

    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in checks.items():
            try:
                results[name] = await get_json(client, url)
            except Exception as exc:
                results[name] = {
                    "service": name,
                    "status": "offline",
                    "error": str(exc),
                }

    return {
        "system": "EdgeSense-MA",
        "services": results,
    }


@app.get("/system/snapshot")
async def system_snapshot() -> dict:
    if USE_BACKGROUND_VISION_CACHE:
        return await system_live()

    async with httpx.AsyncClient(timeout=30.0) as client:
        sensors = await get_json(client, SERVICE_URLS["sensor_current"])
        audio = await get_json(client, SERVICE_URLS["audio_latest"])
        vision = await run_camera_to_vision(client)

    return {
        "system": "EdgeSense-MA",
        "generated_at": utc_now_iso(),
        "sensors": sensors,
        "audio": audio,
        "vision": vision,
    }


@app.get("/system/live")
async def system_live() -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        sensors = await get_json(client, SERVICE_URLS["sensor_current"])
        audio = await get_json(client, SERVICE_URLS["audio_latest"])
        vision = await get_json(client, SERVICE_URLS["vision_latest"])

    return {
        "system": "EdgeSense-MA",
        "generated_at": utc_now_iso(),
        "source": "background_worker_cache",
        "worker": read_worker_status(),
        "sensors": sensors,
        "audio": audio,
        "vision": vision,
    }


@app.get("/system/worker-status")
def system_worker_status() -> dict:
    return {
        "system": "EdgeSense-MA",
        "generated_at": utc_now_iso(),
        "worker": read_worker_status(),
    }


@app.post("/system/analyze-live")
async def analyze_live_system() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        sensors = await get_json(client, SERVICE_URLS["sensor_current"])
        audio = await get_json(client, SERVICE_URLS["audio_latest"])
        vision = await get_json(client, SERVICE_URLS["vision_latest"])

        agent_payload = {
            "vision": vision,
            "sensors": sensors,
            "audio": audio,
        }

        response = await client.post(
            SERVICE_URLS["agent_analyze"],
            json=agent_payload,
        )
        response.raise_for_status()
        decision = response.json()

    report = {
        "system": "EdgeSense-MA",
        "generated_at": utc_now_iso(),
        "analysis_mode": "background_worker_cache",
        "worker": read_worker_status(),
        "input_snapshot": agent_payload,
        "decision": decision,
    }

    save_decision_report(report)
    return report


@app.post("/system/analyze")
async def analyze_current_system() -> dict:
    if USE_BACKGROUND_VISION_CACHE:
        return await analyze_live_system()

    async with httpx.AsyncClient(timeout=30.0) as client:
        sensors = await get_json(client, SERVICE_URLS["sensor_current"])
        audio = await get_json(client, SERVICE_URLS["audio_latest"])
        vision = await run_camera_to_vision(client)

        agent_payload = {
            "vision": vision,
            "sensors": sensors,
            "audio": audio,
        }

        response = await client.post(
            SERVICE_URLS["agent_analyze"],
            json=agent_payload,
        )
        response.raise_for_status()
        decision = response.json()

    report = {
        "system": "EdgeSense-MA",
        "generated_at": utc_now_iso(),
        "input_snapshot": agent_payload,
        "decision": decision,
    }

    save_decision_report(report)

    return report


@app.get("/agents/demo/{scenario}")
async def proxy_agent_demo(scenario: str) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as client:
        return await get_json(client, f"{SERVICE_URLS['agent_demo']}/{scenario}")


def load_event_or_raise(event_id: str) -> dict:
    try:
        return read_event(event_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@app.get("/events")
def event_history(
    limit: int = 50,
    risk: str | None = None,
    trigger: str | None = None,
    object_label: str | None = None,
    category: str | None = None,
) -> dict:
    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    events = list_events(
        limit=safe_limit,
        risk=risk,
        trigger=trigger,
        object_label=object_label,
        category=category,
    )

    return {
        "count": len(events),
        "limit": safe_limit,
        "filters": {
            "risk": risk,
            "trigger": trigger,
            "object_label": object_label,
            "category": category,
        },
        "events": events,
    }


@app.get("/events/latest")
def latest_persistent_event() -> dict:
    event = get_latest_event()

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="No persistent events are available.",
        )

    return event


@app.get("/events/{event_id}/image")
def persistent_event_image(event_id: str) -> FileResponse:
    event = load_event_or_raise(event_id)

    image_value = (
        event.get("evidence", {})
        .get("annotated_image_path")
    )

    if not isinstance(image_value, str):
        raise HTTPException(
            status_code=404,
            detail="This event has no annotated image.",
        )

    image_path = Path(image_value).resolve()
    allowed_directory = EVENT_IMAGES_DIR.resolve()

    if allowed_directory not in image_path.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid event image path.",
        )

    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="The event image was not found.",
        )

    media_type = "image/jpeg"

    if image_path.suffix.lower() == ".png":
        media_type = "image/png"
    elif image_path.suffix.lower() == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path=image_path,
        media_type=media_type,
        filename=image_path.name,
    )


@app.get("/events/{event_id}")
def persistent_event_details(event_id: str) -> dict:
    return load_event_or_raise(event_id)


@app.get("/reports/latest")
def latest_report() -> dict:
    if not LATEST_REPORT_PATH.exists():
        return {
            "title": "EdgeSense-MA MVP Report",
            "summary": "No persisted reports yet. Run POST /system/analyze first.",
        }

    return json.loads(LATEST_REPORT_PATH.read_text(encoding="utf-8"))


@app.get("/reports/history")
def report_history() -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    reports = sorted(
        [
            path.name
            for path in REPORTS_DIR.glob("decision_*.json")
        ],
        reverse=True,
    )

    return {
        "count": len(reports),
        "reports": reports[:20],
    }
