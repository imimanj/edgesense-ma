from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

MODEL_PATH = Path("models/onnx/yolo11n.onnx")
IMAGE_PATH = Path(os.getenv("YOLO_TEST_IMAGE", "data/samples/real_camera_latest.jpg"))
OUTPUT_PATH = Path("data/samples/yolo11n_onnx_result.jpg")

INPUT_SIZE = 640
CONF_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))
NMS_THRESHOLD = float(os.getenv("YOLO_NMS_THRESHOLD", "0.45"))

COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    39: "bottle",
    41: "cup",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    62: "tv",
    63: "laptop",
    64: "mouse",
    66: "keyboard",
    67: "cell phone",
    73: "book",
}


def letterbox(image: np.ndarray, size: int = INPUT_SIZE) -> tuple[np.ndarray, float, float, float]:
    height, width = image.shape[:2]
    scale = min(size / width, size / height)

    new_width = int(round(width * scale))
    new_height = int(round(height * scale))

    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    pad_width = size - new_width
    pad_height = size - new_height

    pad_left = pad_width / 2
    pad_top = pad_height / 2

    top = int(round(pad_top - 0.1))
    bottom = int(round(pad_top + 0.1))
    left = int(round(pad_left - 0.1))
    right = int(round(pad_left + 0.1))

    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )

    return padded, scale, pad_left, pad_top


def prepare_input(image: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    padded, scale, pad_left, pad_top = letterbox(image)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    batch = np.expand_dims(chw, axis=0)
    return batch, scale, pad_left, pad_top


def parse_output(
    output: np.ndarray,
    original_shape: tuple[int, int, int],
    scale: float,
    pad_left: float,
    pad_top: float,
) -> list[dict]:
    predictions = np.squeeze(output)

    if predictions.shape[0] < predictions.shape[1]:
        predictions = predictions.T

    boxes_xywh = predictions[:, :4]
    class_scores = predictions[:, 4:]

    class_ids = np.argmax(class_scores, axis=1)
    confidences = class_scores[np.arange(class_scores.shape[0]), class_ids]

    keep = confidences >= CONF_THRESHOLD
    boxes_xywh = boxes_xywh[keep]
    class_ids = class_ids[keep]
    confidences = confidences[keep]

    original_height, original_width = original_shape[:2]
    boxes = []

    for box in boxes_xywh:
        center_x, center_y, width, height = box

        x1 = (center_x - width / 2 - pad_left) / scale
        y1 = (center_y - height / 2 - pad_top) / scale
        x2 = (center_x + width / 2 - pad_left) / scale
        y2 = (center_y + height / 2 - pad_top) / scale

        x1 = max(0, min(original_width - 1, int(round(x1))))
        y1 = max(0, min(original_height - 1, int(round(y1))))
        x2 = max(0, min(original_width - 1, int(round(x2))))
        y2 = max(0, min(original_height - 1, int(round(y2))))

        boxes.append([x1, y1, max(0, x2 - x1), max(0, y2 - y1)])

    indices = cv2.dnn.NMSBoxes(
        boxes,
        confidences.astype(float).tolist(),
        CONF_THRESHOLD,
        NMS_THRESHOLD,
    )

    detections = []
    if len(indices) > 0:
        for index in np.array(indices).flatten():
            x, y, width, height = boxes[index]
            class_id = int(class_ids[index])
            label = COCO_CLASSES.get(class_id, f"class_{class_id}")

            detections.append(
                {
                    "label": label,
                    "class_id": class_id,
                    "confidence": round(float(confidences[index]), 4),
                    "bbox": [x, y, x + width, y + height],
                }
            )

    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return detections


def draw_detections(image: np.ndarray, detections: list[dict]) -> np.ndarray:
    output = image.copy()

    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]
        label = detection["label"]
        confidence = detection["confidence"]

        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            output,
            f"{label} {confidence:.2f}",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    return output


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

    print(f"Model: {MODEL_PATH}")
    print(f"Image: {IMAGE_PATH}")
    print(f"Confidence threshold: {CONF_THRESHOLD}")
    print(f"NMS threshold: {NMS_THRESHOLD}")

    image = cv2.imread(str(IMAGE_PATH))
    if image is None:
        raise RuntimeError(f"OpenCV could not read image: {IMAGE_PATH}")

    input_tensor, scale, pad_left, pad_top = prepare_input(image)

    session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=["CPUExecutionProvider"],
    )

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    print(f"ONNX input name: {input_name}")
    print(f"ONNX output name: {output_name}")

    warmup_start = time.perf_counter()
    session.run([output_name], {input_name: input_tensor})
    warmup_ms = (time.perf_counter() - warmup_start) * 1000

    start = time.perf_counter()
    outputs = session.run([output_name], {input_name: input_tensor})
    latency_ms = (time.perf_counter() - start) * 1000
    fps = 1000 / max(latency_ms, 1)

    detections = parse_output(outputs[0], image.shape, scale, pad_left, pad_top)

    annotated = draw_detections(image, detections)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT_PATH), annotated)

    print(f"Warmup latency: {warmup_ms:.2f} ms")
    print(f"Inference latency: {latency_ms:.2f} ms")
    print(f"Estimated FPS: {fps:.2f}")
    print(f"Detections: {len(detections)}")

    for detection in detections[:10]:
        print(detection)

    print(f"Annotated output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
