from __future__ import annotations

import os
import shutil
import subprocess
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from PIL import Image, ImageDraw

from shared.schemas import ServiceStatus

app = FastAPI(title="EdgeSense-MA Camera Service", version="0.3.0")

SAMPLES_DIR = Path("data/samples")
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

FRAME_WIDTH = int(os.getenv("CAMERA_FRAME_WIDTH", "1280"))
FRAME_HEIGHT = int(os.getenv("CAMERA_FRAME_HEIGHT", "720"))
CAMERA_MODE = os.getenv("CAMERA_MODE", "mock")
RPICAM_STILL_BIN = os.getenv("RPICAM_STILL_BIN", "rpicam-still")

PERSON_BBOX = [180, 120, 440, 620]
CAMERA_CAPTURE_LOCK = Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_camera_mode() -> str:
    return os.getenv("CAMERA_MODE", CAMERA_MODE)


def is_rpicam_available() -> bool:
    return shutil.which(RPICAM_STILL_BIN) is not None


def draw_mock_scene(path: Path) -> None:
    image = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), color=(28, 38, 49))
    draw = ImageDraw.Draw(image)

    for x in range(0, FRAME_WIDTH, 80):
        draw.line((x, 0, x, FRAME_HEIGHT), fill=(38, 52, 66), width=1)
    for y in range(0, FRAME_HEIGHT, 80):
        draw.line((0, y, FRAME_WIDTH, y), fill=(38, 52, 66), width=1)

    draw.text((40, 35), "EdgeSense-MA mock camera frame", fill=(235, 245, 255))
    draw.text((40, 65), "Raspberry Pi 5 local MVP - simulated camera input", fill=(150, 165, 180))

    x1, y1, x2, y2 = PERSON_BBOX
    head_center_x = (x1 + x2) // 2
    head_center_y = y1 + 55

    draw.ellipse(
        (head_center_x - 35, head_center_y - 35, head_center_x + 35, head_center_y + 35),
        fill=(95, 110, 125),
        outline=(180, 190, 200),
        width=2,
    )
    draw.rounded_rectangle(
        (head_center_x - 55, head_center_y + 45, head_center_x + 55, y2 - 30),
        radius=22,
        fill=(85, 100, 115),
        outline=(180, 190, 200),
        width=2,
    )

    draw.rectangle(PERSON_BBOX, outline=(255, 230, 0), width=5)
    draw.rectangle((x1, y1 - 35, x1 + 170, y1), fill=(255, 230, 0))
    draw.text((x1 + 8, y1 - 27), "person 0.91", fill=(20, 25, 30))

    draw.text((FRAME_WIDTH - 270, FRAME_HEIGHT - 35), "mock snapshot generated locally", fill=(150, 165, 180))

    image.save(path)


def capture_real_image(path: Path) -> None:
    if not is_rpicam_available():
        raise HTTPException(
            status_code=500,
            detail=f"{RPICAM_STILL_BIN} was not found. Install rpicam-apps/libcamera-apps first.",
        )

    command = [
        RPICAM_STILL_BIN,
        "-o",
        str(path),
        "--width",
        str(FRAME_WIDTH),
        "--height",
        str(FRAME_HEIGHT),
        "--timeout",
        "2500",
        "--autofocus-mode",
        "auto",
        "--autofocus-on-capture",
        "--nopreview",
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=500, detail=f"Camera capture timed out: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Real camera capture failed",
                "command": command,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        ) from exc

    if not path.exists() or path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Camera command finished but no image was saved.")


@app.get("/camera/status", response_model=ServiceStatus)
def status() -> ServiceStatus:
    mode = get_camera_mode()
    return ServiceStatus(
        service="camera-service",
        details={
            "mode": mode,
            "device": "Raspberry Pi Camera Module 3 Wide / imx708_wide",
            "resolution": f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
            "hardware_ready": mode == "real" and is_rpicam_available(),
            "capture_command": RPICAM_STILL_BIN if mode == "real" else "mock_pil_generator",
        },
    )


@app.post("/camera/snapshot")
def snapshot() -> dict:
    mode = get_camera_mode()

    if mode == "real":
        path = SAMPLES_DIR / "real_camera_latest.jpg"
        with CAMERA_CAPTURE_LOCK:
            capture_real_image(path)
        return {
            "status": "saved",
            "mode": "real",
            "path": str(path),
            "resolution": {
                "width": FRAME_WIDTH,
                "height": FRAME_HEIGHT,
            },
            "timestamp": utc_now_iso(),
        }

    path = SAMPLES_DIR / "mock_snapshot.jpg"
    draw_mock_scene(path)

    return {
        "status": "saved",
        "mode": "mock",
        "path": str(path),
        "resolution": {
            "width": FRAME_WIDTH,
            "height": FRAME_HEIGHT,
        },
        "timestamp": utc_now_iso(),
        "mock_objects": [
            {
                "label": "person",
                "confidence": 0.91,
                "bbox": PERSON_BBOX,
            }
        ],
    }
