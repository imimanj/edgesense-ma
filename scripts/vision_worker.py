from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


CAMERA_SNAPSHOT_URL = os.getenv(
    "CAMERA_SNAPSHOT_URL",
    "http://127.0.0.1:8001/camera/snapshot",
)
VISION_DETECT_URL = os.getenv(
    "VISION_DETECT_URL",
    "http://127.0.0.1:8004/vision/detect",
)

WORKER_ENABLED = os.getenv(
    "VISION_WORKER_ENABLED",
    "true",
).lower() == "true"

INTERVAL_SECONDS = max(
    3.0,
    float(os.getenv("VISION_WORKER_INTERVAL_SECONDS", "10")),
)

START_DELAY_SECONDS = max(
    0.0,
    float(os.getenv("VISION_WORKER_START_DELAY_SECONDS", "3")),
)

RUNTIME_DIR = Path("data/runtime")
STATUS_PATH = RUNTIME_DIR / "vision_worker_status.json"
PID_PATH = RUNTIME_DIR / "vision_worker.pid"

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

running = True

status = {
    "worker": "vision-worker",
    "enabled": WORKER_ENABLED,
    "state": "starting",
    "pid": os.getpid(),
    "interval_seconds": INTERVAL_SECONDS,
    "camera_snapshot_url": CAMERA_SNAPSHOT_URL,
    "vision_detect_url": VISION_DETECT_URL,
    "cycles_completed": 0,
    "failures": 0,
    "last_started_at": None,
    "last_success_at": None,
    "last_error_at": None,
    "last_error": None,
    "last_cycle_duration_ms": None,
    "latest_snapshot_path": None,
    "latest_detection_count": None,
    "latest_objects": [],
    "latest_model_latency_ms": None,
    "latest_frame_quality": None,
    "latest_lighting_status": None,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status() -> None:
    temporary_path = STATUS_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(STATUS_PATH)


def stop_worker(signum: int, frame: object) -> None:
    global running
    running = False
    print(f"Stop signal received: {signum}", flush=True)


def sleep_interruptibly(seconds: float) -> None:
    deadline = time.monotonic() + seconds

    while running:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))


def run_cycle(session: requests.Session) -> None:
    cycle_started = time.perf_counter()

    status["state"] = "running"
    status["last_started_at"] = utc_now_iso()
    write_status()

    camera_response = session.post(
        CAMERA_SNAPSHOT_URL,
        timeout=20,
    )
    camera_response.raise_for_status()
    camera_result = camera_response.json()

    image_path_value = camera_result.get("path")
    if not image_path_value:
        raise RuntimeError("Camera service did not return an image path.")

    image_path = Path(image_path_value)
    if not image_path.exists():
        raise FileNotFoundError(f"Camera image does not exist: {image_path}")

    with image_path.open("rb") as image_file:
        files = {
            "file": (
                image_path.name,
                image_file,
                "image/jpeg",
            )
        }

        vision_response = session.post(
            VISION_DETECT_URL,
            files=files,
            timeout=45,
        )

    vision_response.raise_for_status()
    vision_result = vision_response.json()

    frame_metadata = vision_result.get("frame_metadata", {})
    objects = vision_result.get("objects", [])

    status["cycles_completed"] += 1
    status["state"] = "healthy"
    status["last_success_at"] = utc_now_iso()
    status["last_error"] = None
    status["latest_snapshot_path"] = str(image_path)
    status["latest_detection_count"] = len(objects)
    status["latest_objects"] = objects[:10]
    status["latest_model_latency_ms"] = frame_metadata.get(
        "model_latency_ms"
    )
    status["latest_frame_quality"] = frame_metadata.get(
        "frame_quality"
    )
    status["latest_lighting_status"] = frame_metadata.get(
        "lighting_status"
    )
    status["last_cycle_duration_ms"] = round(
        (time.perf_counter() - cycle_started) * 1000,
        2,
    )

    write_status()

    print(
        "Vision cycle complete | "
        f"cycle={status['cycles_completed']} | "
        f"detections={len(objects)} | "
        f"duration_ms={status['last_cycle_duration_ms']}",
        flush=True,
    )


def main() -> None:
    global running

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    write_status()

    if not WORKER_ENABLED:
        status["state"] = "disabled"
        write_status()
        print("Vision worker is disabled.", flush=True)
        return

    print(
        "Starting EdgeSense-MA vision worker | "
        f"interval={INTERVAL_SECONDS}s | "
        f"start_delay={START_DELAY_SECONDS}s",
        flush=True,
    )

    sleep_interruptibly(START_DELAY_SECONDS)

    try:
        with requests.Session() as session:
            while running:
                cycle_started = time.monotonic()

                try:
                    run_cycle(session)
                except Exception as exc:
                    status["state"] = "error"
                    status["failures"] += 1
                    status["last_error_at"] = utc_now_iso()
                    status["last_error"] = repr(exc)
                    write_status()

                    print(
                        f"Vision worker cycle failed: {exc!r}",
                        flush=True,
                    )

                elapsed = time.monotonic() - cycle_started
                remaining = max(
                    0.5,
                    INTERVAL_SECONDS - elapsed,
                )
                sleep_interruptibly(remaining)

    finally:
        status["state"] = "stopped"
        status["stopped_at"] = utc_now_iso()
        write_status()

        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass

        print("Vision worker stopped.", flush=True)


if __name__ == "__main__":
    main()
