from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


@dataclass
class ONNXDetection:
    label: str
    class_id: int
    confidence: float
    bbox: list[int]


@dataclass
class ONNXDetectionResult:
    detections: list[ONNXDetection]
    model_latency_ms: float
    fps: float
    input_name: str
    output_name: str


class YOLO11ONNXDetector:
    def __init__(
        self,
        model_path: Path,
        input_size: int = 640,
        confidence_threshold: float = 0.25,
        nms_threshold: float = 0.45,
    ) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX model not found: {model_path}")

        self.model_path = model_path
        self.input_size = input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

        options = ort.SessionOptions()
        options.log_severity_level = 3

        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def letterbox(self, image: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        height, width = image.shape[:2]
        scale = min(self.input_size / width, self.input_size / height)

        new_width = int(round(width * scale))
        new_height = int(round(height * scale))

        resized = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_LINEAR,
        )

        pad_width = self.input_size - new_width
        pad_height = self.input_size - new_height

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

    def prepare_input(self, image: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        padded, scale, pad_left, pad_top = self.letterbox(image)
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0
        chw = np.transpose(normalized, (2, 0, 1))
        batch = np.expand_dims(chw, axis=0)
        return batch, scale, pad_left, pad_top

    def parse_output(
        self,
        output: np.ndarray,
        original_shape: tuple[int, int, int],
        scale: float,
        pad_left: float,
        pad_top: float,
    ) -> list[ONNXDetection]:
        predictions = np.squeeze(output)

        if predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T

        boxes_xywh = predictions[:, :4]
        class_scores = predictions[:, 4:]

        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(class_scores.shape[0]), class_ids]

        keep = confidences >= self.confidence_threshold
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
            self.confidence_threshold,
            self.nms_threshold,
        )

        detections = []

        if len(indices) > 0:
            for index in np.array(indices).flatten():
                x, y, width, height = boxes[index]
                class_id = int(class_ids[index])

                if 0 <= class_id < len(COCO_CLASSES):
                    label = COCO_CLASSES[class_id]
                else:
                    label = f"class_{class_id}"

                detections.append(
                    ONNXDetection(
                        label=label,
                        class_id=class_id,
                        confidence=round(float(confidences[index]), 4),
                        bbox=[x, y, x + width, y + height],
                    )
                )

        detections.sort(key=lambda item: item.confidence, reverse=True)
        return detections

    def detect(self, image: np.ndarray) -> ONNXDetectionResult:
        input_tensor, scale, pad_left, pad_top = self.prepare_input(image)

        start = time.perf_counter()
        outputs = self.session.run(
            [self.output_name],
            {self.input_name: input_tensor},
        )
        model_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        fps = round(1000 / max(model_latency_ms, 1), 2)

        detections = self.parse_output(
            outputs[0],
            image.shape,
            scale,
            pad_left,
            pad_top,
        )

        return ONNXDetectionResult(
            detections=detections,
            model_latency_ms=model_latency_ms,
            fps=fps,
            input_name=self.input_name,
            output_name=self.output_name,
        )
