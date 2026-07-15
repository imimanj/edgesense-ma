from __future__ import annotations

from pathlib import Path

import cv2

IMAGE_PATH = Path("data/samples/real_camera_latest.jpg")
MODEL_INPUT_SIZE = (640, 640)
BLUR_THRESHOLD = 20.0
DARK_THRESHOLD = 40.0
BRIGHT_THRESHOLD = 220.0


def main() -> None:
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(
            f"{IMAGE_PATH} does not exist. Run POST /camera/snapshot first."
        )

    image = cv2.imread(str(IMAGE_PATH))

    if image is None:
        raise RuntimeError(f"OpenCV could not read {IMAGE_PATH}")

    height, width, channels = image.shape

    print("Real camera image loaded successfully")
    print(f"Path: {IMAGE_PATH}")
    print(f"Width: {width}")
    print(f"Height: {height}")
    print(f"Channels: {channels}")

    resized = cv2.resize(image, MODEL_INPUT_SIZE)
    print(f"Resized shape for model input: {resized.shape}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = gray.mean()

    print(f"Blur score: {blur_score:.2f}")
    print(f"Average brightness: {brightness:.2f}")

    if blur_score < BLUR_THRESHOLD:
        print("Frame quality: blurry")
    else:
        print("Frame quality: usable")

    if brightness < DARK_THRESHOLD:
        print("Lighting: too dark")
    elif brightness > BRIGHT_THRESHOLD:
        print("Lighting: too bright")
    else:
        print("Lighting: acceptable")


if __name__ == "__main__":
    main()
