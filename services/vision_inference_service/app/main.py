from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile

from services.vision_inference_service.app.yolo_onnx import YOLO11ONNXDetector
from shared.schemas import Detection, ServiceStatus, VisionResult

app = FastAPI(
    title="EdgeSense-MA Vision Inference Service",
    version="0.5.0",
)

MODEL_NAME = "yolo11n-onnx"
VISION_MODE = "real_camera_onnx_inference"
MODEL_INPUT_SIZE = (640, 640)

ONNX_MODEL_PATH = Path(os.getenv("VISION_ONNX_MODEL_PATH", "models/onnx/yolo11n.onnx"))
SNAPSHOT_DIR = Path(os.getenv("VISION_SNAPSHOT_DIR", "data/samples"))
ANNOTATED_IMAGE_PATH = Path(
    os.getenv(
        "VISION_ANNOTATED_IMAGE_PATH",
        "data/samples/vision_annotated_latest.jpg",
    )
)
CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))
NMS_THRESHOLD = float(os.getenv("YOLO_NMS_THRESHOLD", "0.45"))
ENABLE_MOCK_FALLBACK = os.getenv("VISION_ENABLE_MOCK_FALLBACK", "true").lower() == "true"

BLUR_THRESHOLD = float(
    os.getenv("VISION_BLUR_THRESHOLD", "4.7")
)
DARK_THRESHOLD = float(
    os.getenv("VISION_DARK_THRESHOLD", "40.0")
)
BRIGHT_THRESHOLD = float(
    os.getenv("VISION_BRIGHT_THRESHOLD", "220.0")
)

DEFAULT_RELEVANT_CLASSES = {
    "person",
    "car",
    "motorcycle",
    "bus",
    "truck",
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

MOTION_SUBJECT_CLASSES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
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

DEFAULT_RELEVANT_CLASSES.update(
    MOTION_SUBJECT_CLASSES
)

RELEVANT_CLASSES = {
    label.strip().lower()
    for label in os.getenv(
        "VISION_RELEVANT_CLASSES",
        ",".join(sorted(DEFAULT_RELEVANT_CLASSES)),
    ).split(",")
    if label.strip()
}

HIGH_PRIORITY_CLASSES = {
    "person",
    "car",
    "motorcycle",
    "bus",
    "truck",
}

HIGH_PRIORITY_MIN_CONFIDENCE = float(
    os.getenv("YOLO_HIGH_PRIORITY_MIN_CONFIDENCE", "0.35")
)

CONTEXT_MIN_CONFIDENCE = float(
    os.getenv("YOLO_CONTEXT_MIN_CONFIDENCE", "0.45")
)

DETECTOR: YOLO11ONNXDetector | None = None

LATEST_RESULT = VisionResult(
    model=MODEL_NAME,
    mode=VISION_MODE,
)


def get_detector() -> YOLO11ONNXDetector:
    global DETECTOR

    if DETECTOR is None:
        DETECTOR = YOLO11ONNXDetector(
            model_path=ONNX_MODEL_PATH,
            input_size=MODEL_INPUT_SIZE[0],
            confidence_threshold=CONF_THRESHOLD,
            nms_threshold=NMS_THRESHOLD,
        )

    return DETECTOR


def decode_image(content: bytes) -> np.ndarray:
    image_array = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file could not be decoded as an image.",
        )

    return image


def analyze_frame_quality(image: np.ndarray, filename: str | None) -> dict:
    height, width, channels = image.shape

    resized = cv2.resize(image, MODEL_INPUT_SIZE)
    resized_height, resized_width, resized_channels = resized.shape

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    if blur_score < BLUR_THRESHOLD:
        frame_quality = "blurry"
    else:
        frame_quality = "usable"

    if brightness < DARK_THRESHOLD:
        lighting_status = "too_dark"
    elif brightness > BRIGHT_THRESHOLD:
        lighting_status = "too_bright"
    else:
        lighting_status = "acceptable"

    return {
        "input_source": "real_camera_snapshot",
        "inference_type": "onnx_object_detection",
        "input_filename": filename,
        "input_width": width,
        "input_height": height,
        "input_channels": channels,
        "model_input_width": resized_width,
        "model_input_height": resized_height,
        "model_input_channels": resized_channels,
        "blur_score": round(blur_score, 2),
        "brightness": round(brightness, 2),
        "frame_quality": frame_quality,
        "lighting_status": lighting_status,
        "blur_threshold": BLUR_THRESHOLD,
        "dark_threshold": DARK_THRESHOLD,
        "bright_threshold": BRIGHT_THRESHOLD,
    }


def filter_relevant_detections(
    objects: list[Detection],
) -> tuple[list[Detection], list[dict]]:
    filtered = []
    raw_detections = []

    for obj in objects:
        label = obj.label.strip().lower()

        raw_detections.append(
            {
                "label": obj.label,
                "confidence": obj.confidence,
                "bbox": obj.bbox,
            }
        )

        if label not in RELEVANT_CLASSES:
            continue

        if (
            label in HIGH_PRIORITY_CLASSES
            or label in MOTION_SUBJECT_CLASSES
        ):
            minimum_confidence = HIGH_PRIORITY_MIN_CONFIDENCE
        else:
            minimum_confidence = CONTEXT_MIN_CONFIDENCE

        if obj.confidence >= minimum_confidence:
            filtered.append(obj)

    return filtered, raw_detections


def save_annotated_image(
    image: np.ndarray,
    objects: list[Detection],
) -> str:
    annotated = image.copy()

    for obj in objects:
        if len(obj.bbox) != 4:
            continue

        x1, y1, x2, y2 = [int(value) for value in obj.bbox]

        cv2.rectangle(
            annotated,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2,
        )

        label_text = f"{obj.label} {obj.confidence:.2f}"

        text_size, baseline = cv2.getTextSize(
            label_text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            2,
        )

        text_width, text_height = text_size
        text_y = max(text_height + 6, y1)

        cv2.rectangle(
            annotated,
            (x1, text_y - text_height - 8),
            (x1 + text_width + 8, text_y + baseline),
            (0, 255, 0),
            -1,
        )

        cv2.putText(
            annotated,
            label_text,
            (x1 + 4, text_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    if not objects:
        cv2.putText(
            annotated,
            "No detections above threshold",
            (30, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )

    ANNOTATED_IMAGE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved = cv2.imwrite(
        str(ANNOTATED_IMAGE_PATH),
        annotated,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save annotated image: {ANNOTATED_IMAGE_PATH}"
        )

    return str(ANNOTATED_IMAGE_PATH)


def mock_fallback_detections(filename: str | None) -> list[Detection]:
    objects = [
        Detection(
            label="person",
            confidence=0.91,
            bbox=[180, 120, 440, 620],
        )
    ]

    if filename and "bag" in filename.lower():
        objects.append(
            Detection(
                label="bag",
                confidence=0.76,
                bbox=[500, 380, 640, 620],
            )
        )

    return objects


@app.get("/vision/status", response_model=ServiceStatus)
def status() -> ServiceStatus:
    onnx_ready = ONNX_MODEL_PATH.exists()

    return ServiceStatus(
        service="vision-inference-service",
        details={
            "mode": VISION_MODE,
            "model": MODEL_NAME,
            "onnx_ready": onnx_ready,
            "onnx_model_path": str(ONNX_MODEL_PATH),
            "input_source": "real_camera_snapshot",
            "inference_type": "onnx_object_detection",
            "confidence_threshold": CONF_THRESHOLD,
            "nms_threshold": NMS_THRESHOLD,
            "high_priority_min_confidence": HIGH_PRIORITY_MIN_CONFIDENCE,
            "context_min_confidence": CONTEXT_MIN_CONFIDENCE,
            "relevant_classes": sorted(RELEVANT_CLASSES),
            "motion_subject_classes": sorted(
                MOTION_SUBJECT_CLASSES
            ),
            "mock_fallback_enabled": ENABLE_MOCK_FALLBACK,
            "frame_quality_enabled": True,
            "note": "The input image comes from the real Raspberry Pi camera and object detection runs through YOLO11n ONNX on CPU.",
        },
    )


@app.post("/vision/detect", response_model=VisionResult)
async def detect(file: UploadFile = File(...)) -> VisionResult:
    global LATEST_RESULT

    pipeline_start = time.perf_counter()
    content = await file.read()

    image = decode_image(content)
    frame_metadata = analyze_frame_quality(image, file.filename)

    try:
        detector = get_detector()
        detection_result = detector.detect(image)

        objects = [
            Detection(
                label=item.label,
                confidence=item.confidence,
                bbox=item.bbox,
            )
            for item in detection_result.detections
        ]

        frame_metadata.update(
            {
                "detector_status": "onnx",
                "onnx_model_path": str(ONNX_MODEL_PATH),
                "onnx_input_name": detection_result.input_name,
                "onnx_output_name": detection_result.output_name,
                "model_latency_ms": detection_result.model_latency_ms,
                "confidence_threshold": CONF_THRESHOLD,
                "nms_threshold": NMS_THRESHOLD,
                "detection_count": len(objects),
            }
        )

        model_fps = detection_result.fps

    except Exception as exc:
        if not ENABLE_MOCK_FALLBACK:
            raise HTTPException(
                status_code=500,
                detail=f"ONNX detection failed: {exc}",
            ) from exc

        objects = mock_fallback_detections(file.filename)
        model_fps = 0.0

        frame_metadata.update(
            {
                "detector_status": "mock_fallback",
                "fallback_reason": str(exc),
                "detection_count": len(objects),
            }
        )

    raw_detection_count = len(objects)

    objects, raw_detections = filter_relevant_detections(
        objects,
    )

    frame_metadata.update(
        {
            "raw_detection_count": raw_detection_count,
            "filtered_detection_count": len(objects),
            "detection_count": len(objects),
            "raw_detections": raw_detections,
            "relevant_classes": sorted(RELEVANT_CLASSES),
            "high_priority_min_confidence": HIGH_PRIORITY_MIN_CONFIDENCE,
            "context_min_confidence": CONTEXT_MIN_CONFIDENCE,
        }
    )

    annotated_image_path = save_annotated_image(
        image,
        objects,
    )

    frame_metadata["annotated_image_path"] = annotated_image_path
    frame_metadata["annotated_image_generated"] = True

    latency_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)

    snapshot_path = None
    if file.filename:
        candidate_path = SNAPSHOT_DIR / Path(file.filename).name
        if candidate_path.exists():
            snapshot_path = str(candidate_path)

    result = VisionResult(
        objects=objects,
        latency_ms=latency_ms,
        fps=model_fps,
        model=MODEL_NAME,
        mode=VISION_MODE,
        snapshot_path=snapshot_path,
        frame_metadata=frame_metadata,
    )

    LATEST_RESULT = result
    return result


@app.get("/vision/latest", response_model=VisionResult)
def latest() -> VisionResult:
    return LATEST_RESULT


@app.post("/vision/reset", response_model=VisionResult)
def reset() -> VisionResult:
    global LATEST_RESULT
    LATEST_RESULT = VisionResult(
        model=MODEL_NAME,
        mode=VISION_MODE,
    )
    return LATEST_RESULT


@app.get("/vision/benchmark")
def benchmark() -> dict:
    return {
        "model": MODEL_NAME,
        "mode": VISION_MODE,
        "onnx_ready": ONNX_MODEL_PATH.exists(),
        "onnx_model_path": str(ONNX_MODEL_PATH),
        "input_source": "real_camera_snapshot",
        "inference_type": "onnx_object_detection",
        "confidence_threshold": CONF_THRESHOLD,
        "nms_threshold": NMS_THRESHOLD,
        "frame_quality_enabled": True,
        "note": "Use /system/snapshot or /vision/detect for live latency measured from real camera frames.",
    }
