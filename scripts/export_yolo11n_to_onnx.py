from __future__ import annotations

from pathlib import Path
import shutil

from ultralytics import YOLO

PYTORCH_DIR = Path("models/pytorch")
ONNX_DIR = Path("models/onnx")

PYTORCH_DIR.mkdir(parents=True, exist_ok=True)
ONNX_DIR.mkdir(parents=True, exist_ok=True)

print("Loading YOLO11n model...")
model = YOLO("yolo11n.pt")

print("Exporting YOLO11n to ONNX...")
exported_path = Path(
    model.export(
        format="onnx",
        imgsz=640,
        opset=12,
        simplify=True,
        dynamic=False,
    )
)

target_path = ONNX_DIR / "yolo11n.onnx"
shutil.copy2(exported_path, target_path)

source_pt = Path("yolo11n.pt")
if source_pt.exists():
    shutil.copy2(source_pt, PYTORCH_DIR / "yolo11n.pt")

print("Export complete.")
print(f"Exported ONNX source: {exported_path}")
print(f"Project ONNX path: {target_path}")
print(f"ONNX file exists: {target_path.exists()}")
print(f"ONNX file size MB: {target_path.stat().st_size / 1024 / 1024:.2f}")
