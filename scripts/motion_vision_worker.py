from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import requests
from gpiozero import DigitalInputDevice
from picamera2 import Picamera2

from shared.event_store import (
    EVENT_RETENTION_DAYS,
    MAX_EVENTS,
    save_event,
)
from shared.event_classification import (
    classify_event_objects,
)


VISION_DETECT_URL = os.getenv(
    "VISION_DETECT_URL",
    "http://127.0.0.1:8004/vision/detect",
)

SENSOR_CURRENT_URL = os.getenv(
    "MOTION_SENSOR_CURRENT_URL",
    "http://127.0.0.1:8002/sensors/current",
)

AUDIO_LATEST_URL = os.getenv(
    "MOTION_AUDIO_LATEST_URL",
    "http://127.0.0.1:8003/audio/latest",
)

AGENT_ANALYZE_URL = os.getenv(
    "MOTION_AGENT_ANALYZE_URL",
    "http://127.0.0.1:8005/agents/analyze",
)

MULTIMODAL_ENRICHMENT_ENABLED = (
    os.getenv(
        "MOTION_MULTIMODAL_ENRICHMENT_ENABLED",
        "true",
    ).lower()
    == "true"
)

MULTIMODAL_TIMEOUT_SECONDS = float(
    os.getenv(
        "MOTION_MULTIMODAL_TIMEOUT_SECONDS",
        "10",
    )
)

FRAME_WIDTH = int(os.getenv("MOTION_CAMERA_FRAME_WIDTH", "1280"))
FRAME_HEIGHT = int(os.getenv("MOTION_CAMERA_FRAME_HEIGHT", "720"))
TARGET_FPS = float(os.getenv("MOTION_CAMERA_FPS", "10"))

MOTION_WIDTH = int(os.getenv("MOTION_ANALYSIS_WIDTH", "320"))
MOTION_HEIGHT = int(os.getenv("MOTION_ANALYSIS_HEIGHT", "180"))

PIXEL_DIFFERENCE_THRESHOLD = int(
    os.getenv("MOTION_PIXEL_DIFFERENCE_THRESHOLD", "25")
)

MOTION_PERCENT_THRESHOLD = float(
    os.getenv("MOTION_PERCENT_THRESHOLD", "1.0")
)

MOTION_CONSECUTIVE_FRAMES = int(
    os.getenv("MOTION_CONSECUTIVE_FRAMES", "2")
)

MOTION_COOLDOWN_SECONDS = float(
    os.getenv("MOTION_COOLDOWN_SECONDS", "5")
)

PERIODIC_SCAN_SECONDS = float(
    os.getenv("MOTION_PERIODIC_SCAN_SECONDS", "30")
)

PIR_ENABLED = (
    os.getenv("MOTION_PIR_ENABLED", "true").lower()
    == "true"
)

PIR_GPIO = int(
    os.getenv("MOTION_PIR_GPIO", "23")
)

PRIMARY_CAMERA_INDEX = int(
    os.getenv("MOTION_PRIMARY_CAMERA_INDEX", "0")
)

SECONDARY_CAMERA_INDEX = int(
    os.getenv("MOTION_SECONDARY_CAMERA_INDEX", "1")
)

CAMERA_WARMUP_SECONDS = float(
    os.getenv("MOTION_CAMERA_WARMUP_SECONDS", "1.0")
)

CAPTURE_FRAME_COUNT = max(
    1,
    int(
        os.getenv(
            "MOTION_CAPTURE_FRAME_COUNT",
            "3",
        )
    ),
)

CAPTURE_INTERFRAME_SECONDS = float(
    os.getenv(
        "MOTION_CAPTURE_INTERFRAME_SECONDS",
        "0.08",
    )
)

PIR_POLL_SECONDS = float(
    os.getenv("MOTION_PIR_POLL_SECONDS", "0.05")
)

PIR_CAPTURE_COOLDOWN_SECONDS = float(
    os.getenv(
        "MOTION_PIR_CAPTURE_COOLDOWN_SECONDS",
        "10",
    )
)

MAX_RUNTIME_SECONDS = float(
    os.getenv("MOTION_WORKER_MAX_RUNTIME_SECONDS", "0")
)

EVENT_STORE_ENABLED = (
    os.getenv("MOTION_EVENT_STORE_ENABLED", "true").lower()
    == "true"
)

SAVE_PERIODIC_EVENTS = (
    os.getenv("MOTION_SAVE_PERIODIC_EVENTS", "false").lower()
    == "true"
)

SAMPLES_DIR = Path("data/samples")
RUNTIME_DIR = Path("data/runtime")

LATEST_IMAGE_PATH = SAMPLES_DIR / "real_camera_latest.jpg"
IR_LATEST_IMAGE_PATH = SAMPLES_DIR / "ir_camera_latest.jpg"
STATUS_PATH = RUNTIME_DIR / "motion_vision_worker_status.json"
PID_PATH = RUNTIME_DIR / "motion_vision_worker.pid"

SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

running = True

status = {
    "worker": "motion-vision-worker",
    "state": "starting",
    "pid": os.getpid(),
    "camera_mode": "pir_triggered_dual_camera_capture",
    "camera_power_strategy": "open_on_pir_trigger",
    "camera_capture_state": "standby",
    "primary_camera_index": PRIMARY_CAMERA_INDEX,
    "secondary_camera_index": SECONDARY_CAMERA_INDEX,
    "primary_camera_model": "imx708_wide",
    "secondary_camera_model": "ov5647",
    "camera_warmup_seconds": CAMERA_WARMUP_SECONDS,
    "capture_frame_count": CAPTURE_FRAME_COUNT,
    "capture_cooldown_seconds": (
        PIR_CAPTURE_COOLDOWN_SECONDS
    ),
    "captures_started": 0,
    "captures_completed": 0,
    "capture_failures": 0,
    "last_capture_started_at": None,
    "last_capture_completed_at": None,
    "last_capture_duration_ms": None,
    "latest_primary_image_path": None,
    "latest_ir_image_path": None,
    "latest_primary_annotated_image_path": None,
    "primary_camera_last_error": None,
    "secondary_camera_last_error": None,
    "frame_size": {
        "width": FRAME_WIDTH,
        "height": FRAME_HEIGHT,
    },
    "motion_analysis_size": {
        "width": MOTION_WIDTH,
        "height": MOTION_HEIGHT,
    },
    "target_fps": TARGET_FPS,
    "motion_percent_threshold": MOTION_PERCENT_THRESHOLD,
    "motion_consecutive_frames": MOTION_CONSECUTIVE_FRAMES,
    "motion_cooldown_seconds": MOTION_COOLDOWN_SECONDS,
    "periodic_scan_seconds": PERIODIC_SCAN_SECONDS,
    "pir_enabled": PIR_ENABLED,
    "pir_gpio": PIR_GPIO,
    "pir_available": False,
    "pir_state": "disabled" if not PIR_ENABLED else "initializing",
    "pir_motion_detected": False,
    "pir_trigger_count": 0,
    "pir_last_motion_at": None,
    "pir_last_clear_at": None,
    "pir_last_change_at": None,
    "pir_error": None,
    "frames_processed": 0,
    "motion_frames": 0,
    "motion_events": 0,
    "periodic_scans": 0,
    "inference_requests": 0,
    "successful_inferences": 0,
    "failures": 0,
    "last_motion_percent": 0.0,
    "last_trigger_reason": None,
    "last_trigger_at": None,
    "last_success_at": None,
    "last_error_at": None,
    "last_error": None,
    "latest_detection_count": None,
    "latest_objects": [],
    "latest_classification": None,
    "latest_model_latency_ms": None,
    "latest_frame_quality": None,
    "latest_lighting_status": None,
    "measured_fps": 0.0,
    "event_store_enabled": EVENT_STORE_ENABLED,
    "event_max_count": MAX_EVENTS,
    "event_retention_days": EVENT_RETENTION_DAYS,
    "save_periodic_events": SAVE_PERIODIC_EVENTS,
    "events_saved": 0,
    "event_save_failures": 0,
    "last_event_id": None,
    "last_event_path": None,
    "last_event_error": None,
    "multimodal_enrichment_enabled": (
        MULTIMODAL_ENRICHMENT_ENABLED
    ),
    "multimodal_enrichment_attempts": 0,
    "multimodal_enrichment_successes": 0,
    "multimodal_enrichment_failures": 0,
    "last_decision_risk": None,
    "last_enrichment_error": None,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status() -> None:
    status["updated_at"] = utc_now_iso()
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


def save_frame(
    frame_rgb,
    path: Path = LATEST_IMAGE_PATH,
) -> None:
    frame_bgr = cv2.cvtColor(
        frame_rgb,
        cv2.COLOR_RGB2BGR,
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved = cv2.imwrite(
        str(path),
        frame_bgr,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save camera frame: {path}"
        )


def calculate_sharpness(frame_rgb) -> float:
    gray = cv2.cvtColor(
        frame_rgb,
        cv2.COLOR_RGB2GRAY,
    )

    return float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()
    )


def capture_best_camera_frame(
    camera_index: int,
    camera_label: str,
) -> tuple[object, dict]:
    camera = None
    started_at = time.perf_counter()

    try:
        camera = Picamera2(
            camera_num=camera_index,
        )

        configuration = (
            camera.create_still_configuration(
                main={
                    "size": (
                        FRAME_WIDTH,
                        FRAME_HEIGHT,
                    ),
                    "format": "RGB888",
                },
                buffer_count=4,
            )
        )

        camera.configure(configuration)
        camera.start()

        time.sleep(CAMERA_WARMUP_SECONDS)

        best_frame = None
        best_sharpness = -1.0

        for frame_index in range(
            CAPTURE_FRAME_COUNT
        ):
            candidate = camera.capture_array()
            sharpness = calculate_sharpness(
                candidate
            )

            if sharpness > best_sharpness:
                best_frame = candidate.copy()
                best_sharpness = sharpness

            if (
                frame_index
                < CAPTURE_FRAME_COUNT - 1
            ):
                time.sleep(
                    CAPTURE_INTERFRAME_SECONDS
                )

        if best_frame is None:
            raise RuntimeError(
                f"No frame was captured from "
                f"camera {camera_index}."
            )

        duration_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        metadata = {
            "camera_index": camera_index,
            "camera_label": camera_label,
            "resolution": {
                "width": FRAME_WIDTH,
                "height": FRAME_HEIGHT,
            },
            "frames_sampled": CAPTURE_FRAME_COUNT,
            "selected_sharpness": round(
                best_sharpness,
                3,
            ),
            "capture_duration_ms": duration_ms,
        }

        return best_frame, metadata

    finally:
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass

            try:
                camera.close()
            except Exception:
                pass


def collect_multimodal_context(
    session: requests.Session,
    vision_result: dict,
) -> dict:
    if not MULTIMODAL_ENRICHMENT_ENABLED:
        return {
            "status": "disabled",
            "sensors": None,
            "audio": None,
            "decision": None,
            "error": None,
        }

    try:
        sensor_response = session.get(
            SENSOR_CURRENT_URL,
            timeout=MULTIMODAL_TIMEOUT_SECONDS,
        )
        sensor_response.raise_for_status()
        sensors = sensor_response.json()

        audio_response = session.get(
            AUDIO_LATEST_URL,
            timeout=MULTIMODAL_TIMEOUT_SECONDS,
        )
        audio_response.raise_for_status()
        audio = audio_response.json()

        agent_payload = {
            "vision": vision_result,
            "sensors": sensors,
            "audio": audio,
        }

        agent_response = session.post(
            AGENT_ANALYZE_URL,
            json=agent_payload,
            timeout=MULTIMODAL_TIMEOUT_SECONDS,
        )
        agent_response.raise_for_status()
        decision = agent_response.json()

        return {
            "status": "complete",
            "sensors": sensors,
            "audio": audio,
            "decision": decision,
            "error": None,
        }

    except Exception as exc:
        return {
            "status": "failed",
            "sensors": None,
            "audio": None,
            "decision": None,
            "error": repr(exc),
        }


def run_yolo(
    session: requests.Session,
    frame_rgb,
    trigger_reason: str,
    motion_percent: float,
    ir_image_path: Path | None = None,
    capture_metadata: dict | None = None,
) -> None:
    save_frame(frame_rgb)

    status["inference_requests"] += 1
    status["last_trigger_reason"] = trigger_reason
    status["last_trigger_at"] = utc_now_iso()
    write_status()

    with LATEST_IMAGE_PATH.open("rb") as image_file:
        files = {
            "file": (
                LATEST_IMAGE_PATH.name,
                image_file,
                "image/jpeg",
            )
        }

        response = session.post(
            VISION_DETECT_URL,
            files=files,
            timeout=45,
        )

    response.raise_for_status()
    result = response.json()

    frame_metadata = result.get("frame_metadata", {})
    objects = result.get("objects", [])

    classification = classify_event_objects(
        objects=objects,
        trigger_reason=trigger_reason,
    )

    status["successful_inferences"] += 1
    status["last_success_at"] = utc_now_iso()
    status["latest_detection_count"] = len(objects)
    status["latest_objects"] = objects[:10]
    status["latest_classification"] = classification
    status["latest_model_latency_ms"] = frame_metadata.get(
        "model_latency_ms"
    )
    status["latest_frame_quality"] = frame_metadata.get(
        "frame_quality"
    )
    status["latest_lighting_status"] = frame_metadata.get(
        "lighting_status"
    )
    status["latest_primary_annotated_image_path"] = (
        frame_metadata.get(
            "annotated_image_path"
        )
    )
    status["last_error"] = None

    saved_event_id = None

    should_save_event = (
        EVENT_STORE_ENABLED
        and (
            trigger_reason in {
                "motion",
                "pir_motion",
            }
            or bool(objects)
            or SAVE_PERIODIC_EVENTS
        )
    )

    if should_save_event:
        try:
            multimodal_context = collect_multimodal_context(
                session=session,
                vision_result=result,
            )

            enrichment_status = multimodal_context["status"]

            if MULTIMODAL_ENRICHMENT_ENABLED:
                status[
                    "multimodal_enrichment_attempts"
                ] += 1

            if enrichment_status == "complete":
                status[
                    "multimodal_enrichment_successes"
                ] += 1

                decision = (
                    multimodal_context.get("decision")
                    or {}
                )

                status["last_decision_risk"] = (
                    decision.get("final_risk")
                )
                status["last_enrichment_error"] = None

            elif enrichment_status == "failed":
                status[
                    "multimodal_enrichment_failures"
                ] += 1

                status["last_enrichment_error"] = (
                    multimodal_context.get("error")
                )

            event_payload = {
                "schema_version": "1.1",
                "source": "motion-vision-worker",
                "trigger": {
                    "reason": trigger_reason,
                    "motion_percent": round(
                        motion_percent,
                        3,
                    ),
                    "motion_threshold_percent": (
                        MOTION_PERCENT_THRESHOLD
                    ),
                    "consecutive_frames_required": (
                        MOTION_CONSECUTIVE_FRAMES
                    ),
                    "triggered_at": status[
                        "last_trigger_at"
                    ],
                    "pir_gpio": PIR_GPIO,
                    "pir_trigger_count": status.get(
                        "pir_trigger_count"
                    ),
                },
                "classification": classification,
                "vision": {
                    "objects": objects,
                    "detection_count": len(objects),
                    "model": result.get("model"),
                    "mode": result.get("mode"),
                    "latency_ms": result.get("latency_ms"),
                    "fps": result.get("fps"),
                    "timestamp": result.get("timestamp"),
                    "frame_metadata": frame_metadata,
                },
                "capture": capture_metadata or {},
                "sensors": multimodal_context.get(
                    "sensors"
                ),
                "audio": multimodal_context.get(
                    "audio"
                ),
                "decision": multimodal_context.get(
                    "decision"
                ),
                "enrichment": {
                    "status": multimodal_context.get(
                        "status"
                    ),
                    "error": multimodal_context.get(
                        "error"
                    ),
                    "completed_at": utc_now_iso(),
                },
                "worker": {
                    "pid": os.getpid(),
                    "camera_mode": status.get(
                        "camera_mode"
                    ),
                    "frames_processed": status.get(
                        "frames_processed"
                    ),
                    "measured_fps": status.get(
                        "measured_fps"
                    ),
                    "motion_events": status.get(
                        "motion_events"
                    ),
                    "periodic_scans": status.get(
                        "periodic_scans"
                    ),
                },
                "evidence": {
                    "source_snapshot_path": result.get(
                        "snapshot_path"
                    ),
                },
            }

            additional_image_paths = {
                "primary": LATEST_IMAGE_PATH,
            }

            if ir_image_path is not None:
                additional_image_paths[
                    "ir"
                ] = ir_image_path

            saved_event = save_event(
                payload=event_payload,
                annotated_image_path=frame_metadata.get(
                    "annotated_image_path"
                ),
                additional_image_paths=(
                    additional_image_paths
                ),
            )

            saved_event_id = saved_event["event_id"]

            status["events_saved"] += 1
            status["last_event_id"] = saved_event_id
            status["last_event_path"] = saved_event.get(
                "event_path"
            )
            status["last_event_error"] = None

        except Exception as exc:
            status["event_save_failures"] += 1
            status["last_event_error"] = repr(exc)

            print(
                f"Event persistence failed: {exc!r}",
                flush=True,
            )

    write_status()

    print(
        "YOLO inference complete | "
        f"trigger={trigger_reason} | "
        f"motion={motion_percent:.2f}% | "
        f"detections={len(objects)} | "
        f"model_latency_ms="
        f"{status['latest_model_latency_ms']} | "
        f"event_id={saved_event_id or 'not_saved'}",
        flush=True,
    )


def prepare_motion_frame(frame_rgb):
    resized = cv2.resize(
        frame_rgb,
        (MOTION_WIDTH, MOTION_HEIGHT),
        interpolation=cv2.INTER_AREA,
    )

    gray = cv2.cvtColor(
        resized,
        cv2.COLOR_RGB2GRAY,
    )

    return cv2.GaussianBlur(
        gray,
        (21, 21),
        0,
    )


def main() -> None:
    global running

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    PID_PATH.write_text(
        str(os.getpid()),
        encoding="utf-8",
    )

    pir = None
    previous_pir_state = None
    last_capture_monotonic = 0.0
    last_status_write_at = 0.0
    started_at = time.monotonic()

    if PIR_ENABLED:
        try:
            pir = DigitalInputDevice(
                PIR_GPIO,
                pull_up=False,
            )

            status["pir_available"] = True
            status["pir_state"] = "initializing"
            status["pir_error"] = None

        except Exception as exc:
            status["pir_available"] = False
            status["pir_state"] = "error"
            status["pir_error"] = repr(exc)

            print(
                f"PIR initialization failed: {exc!r}",
                flush=True,
            )

    status["state"] = (
        "healthy"
        if pir is not None
        else "error"
    )
    status["started_at"] = utc_now_iso()
    status["camera_capture_state"] = "standby"
    status["measured_fps"] = 0.0
    write_status()

    print(
        "PIR-triggered dual-camera worker started.",
        flush=True,
    )
    print(
        f"PIR: GPIO{PIR_GPIO}",
        flush=True,
    )
    print(
        f"Primary camera: index "
        f"{PRIMARY_CAMERA_INDEX}",
        flush=True,
    )
    print(
        f"Secondary camera: index "
        f"{SECONDARY_CAMERA_INDEX}",
        flush=True,
    )
    print(
        "Both cameras remain closed until "
        "a PIR rising edge is detected.",
        flush=True,
    )

    try:
        with requests.Session() as session:
            while running:
                now = time.monotonic()

                if (
                    MAX_RUNTIME_SECONDS > 0
                    and now - started_at
                    >= MAX_RUNTIME_SECONDS
                ):
                    print(
                        "Maximum test runtime reached.",
                        flush=True,
                    )
                    break

                current_pir_state = False
                rising_edge = False

                if pir is not None:
                    current_pir_state = bool(
                        pir.value
                    )

                    status[
                        "pir_motion_detected"
                    ] = current_pir_state

                    status["pir_state"] = (
                        "motion"
                        if current_pir_state
                        else "clear"
                    )

                    if previous_pir_state is None:
                        previous_pir_state = (
                            current_pir_state
                        )

                        changed_at = utc_now_iso()
                        status[
                            "pir_last_change_at"
                        ] = changed_at

                        if current_pir_state:
                            status[
                                "pir_last_motion_at"
                            ] = changed_at
                        else:
                            status[
                                "pir_last_clear_at"
                            ] = changed_at

                    elif (
                        current_pir_state
                        != previous_pir_state
                    ):
                        changed_at = utc_now_iso()
                        status[
                            "pir_last_change_at"
                        ] = changed_at

                        rising_edge = (
                            not previous_pir_state
                            and current_pir_state
                        )

                        if rising_edge:
                            status[
                                "pir_trigger_count"
                            ] += 1

                            status[
                                "pir_last_motion_at"
                            ] = changed_at
                        else:
                            status[
                                "pir_last_clear_at"
                            ] = changed_at

                        previous_pir_state = (
                            current_pir_state
                        )
                        write_status()

                cooldown_ready = (
                    now - last_capture_monotonic
                    >= PIR_CAPTURE_COOLDOWN_SECONDS
                )

                if rising_edge and cooldown_ready:
                    capture_started = (
                        time.perf_counter()
                    )

                    status["captures_started"] += 1
                    status["motion_events"] += 1
                    status[
                        "last_capture_started_at"
                    ] = utc_now_iso()
                    status[
                        "camera_capture_state"
                    ] = "capturing_primary"
                    write_status()

                    primary_frame = None
                    primary_metadata = None
                    ir_metadata = None
                    ir_capture_succeeded = False

                    try:
                        primary_frame, primary_metadata = (
                            capture_best_camera_frame(
                                camera_index=(
                                    PRIMARY_CAMERA_INDEX
                                ),
                                camera_label="primary",
                            )
                        )

                        save_frame(
                            primary_frame,
                            LATEST_IMAGE_PATH,
                        )

                        status["frames_processed"] += 1
                        status[
                            "latest_primary_image_path"
                        ] = str(LATEST_IMAGE_PATH)
                        status[
                            "primary_camera_last_error"
                        ] = None

                    except Exception as exc:
                        status["capture_failures"] += 1
                        status["failures"] += 1
                        status[
                            "primary_camera_last_error"
                        ] = repr(exc)
                        status["last_error"] = repr(exc)
                        status[
                            "last_error_at"
                        ] = utc_now_iso()
                        status[
                            "camera_capture_state"
                        ] = "standby"
                        write_status()

                        print(
                            "Primary camera capture "
                            f"failed: {exc!r}",
                            flush=True,
                        )

                        last_capture_monotonic = (
                            time.monotonic()
                        )
                        time.sleep(PIR_POLL_SECONDS)
                        continue

                    status[
                        "camera_capture_state"
                    ] = "capturing_secondary"
                    write_status()

                    try:
                        ir_frame, ir_metadata = (
                            capture_best_camera_frame(
                                camera_index=(
                                    SECONDARY_CAMERA_INDEX
                                ),
                                camera_label="ir",
                            )
                        )

                        save_frame(
                            ir_frame,
                            IR_LATEST_IMAGE_PATH,
                        )

                        status["frames_processed"] += 1
                        status[
                            "latest_ir_image_path"
                        ] = str(
                            IR_LATEST_IMAGE_PATH
                        )
                        status[
                            "secondary_camera_last_error"
                        ] = None

                        ir_capture_succeeded = True

                    except Exception as exc:
                        status["capture_failures"] += 1
                        status[
                            "secondary_camera_last_error"
                        ] = repr(exc)

                        print(
                            "Secondary camera capture "
                            f"failed: {exc!r}",
                            flush=True,
                        )

                    capture_duration_ms = round(
                        (
                            time.perf_counter()
                            - capture_started
                        )
                        * 1000,
                        2,
                    )

                    status[
                        "last_capture_duration_ms"
                    ] = capture_duration_ms
                    status[
                        "camera_capture_state"
                    ] = "running_inference"
                    write_status()

                    capture_metadata = {
                        "trigger": "pir_rising_edge",
                        "pir_gpio": PIR_GPIO,
                        "capture_started_at": status[
                            "last_capture_started_at"
                        ],
                        "capture_duration_ms": (
                            capture_duration_ms
                        ),
                        "primary": primary_metadata,
                        "ir": ir_metadata,
                        "ir_capture_succeeded": (
                            ir_capture_succeeded
                        ),
                    }

                    try:
                        run_yolo(
                            session=session,
                            frame_rgb=primary_frame,
                            trigger_reason="pir_motion",
                            motion_percent=0.0,
                            ir_image_path=(
                                IR_LATEST_IMAGE_PATH
                                if ir_capture_succeeded
                                else None
                            ),
                            capture_metadata=(
                                capture_metadata
                            ),
                        )

                        status[
                            "captures_completed"
                        ] += 1
                        status[
                            "last_capture_completed_at"
                        ] = utc_now_iso()
                        status["state"] = "healthy"
                        status["last_error"] = None

                    except Exception as exc:
                        status["failures"] += 1
                        status[
                            "last_error_at"
                        ] = utc_now_iso()
                        status["last_error"] = repr(exc)

                        print(
                            "PIR-triggered inference "
                            f"failed: {exc!r}",
                            flush=True,
                        )

                    finally:
                        status[
                            "camera_capture_state"
                        ] = "standby"

                        last_capture_monotonic = (
                            time.monotonic()
                        )
                        write_status()

                if (
                    now - last_status_write_at
                    >= 1.0
                ):
                    if (
                        status["state"] != "error"
                        and pir is not None
                    ):
                        status["state"] = "healthy"

                    write_status()
                    last_status_write_at = now

                time.sleep(PIR_POLL_SECONDS)

    finally:
        status["state"] = "stopped"
        status["stopped_at"] = utc_now_iso()
        status["camera_capture_state"] = "stopped"
        write_status()

        if pir is not None:
            pir.close()

        try:
            PID_PATH.unlink(missing_ok=True)
        except Exception:
            pass

        print(
            "PIR-triggered dual-camera worker stopped.",
            flush=True,
        )


if __name__ == "__main__":
    main()
