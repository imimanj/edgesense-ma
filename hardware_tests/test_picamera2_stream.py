from __future__ import annotations

import time

import cv2
from picamera2 import Picamera2


FRAME_SIZE = (640, 360)
TARGET_FPS = 10
TEST_DURATION_SECONDS = 20
PIXEL_DIFFERENCE_THRESHOLD = 25
MOTION_PERCENT_THRESHOLD = 1.0


def main() -> None:
    camera = Picamera2()

    configuration = camera.create_video_configuration(
        main={
            "size": FRAME_SIZE,
            "format": "RGB888",
        },
        controls={
            "FrameRate": TARGET_FPS,
        },
        buffer_count=4,
    )

    camera.configure(configuration)

    previous_frame = None
    frame_count = 0
    motion_events = 0
    started_at = time.perf_counter()

    try:
        camera.start()
        time.sleep(2)

        print("Persistent Picamera2 stream started")
        print(f"Frame size: {FRAME_SIZE[0]}x{FRAME_SIZE[1]}")
        print(f"Target FPS: {TARGET_FPS}")
        print("Move your hand in front of the camera during the test.")
        print()

        while time.perf_counter() - started_at < TEST_DURATION_SECONDS:
            frame = camera.capture_array()

            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            motion_percent = 0.0
            motion_detected = False

            if previous_frame is not None:
                difference = cv2.absdiff(previous_frame, gray)
                changed_pixels = difference > PIXEL_DIFFERENCE_THRESHOLD
                motion_percent = float(changed_pixels.mean() * 100)
                motion_detected = motion_percent >= MOTION_PERCENT_THRESHOLD

                if motion_detected:
                    motion_events += 1

            frame_count += 1
            previous_frame = gray

            if frame_count % 10 == 0:
                elapsed = time.perf_counter() - started_at
                actual_fps = frame_count / max(elapsed, 0.001)

                print(
                    f"frames={frame_count:4d} | "
                    f"fps={actual_fps:5.2f} | "
                    f"motion={motion_percent:6.2f}% | "
                    f"detected={motion_detected}"
                )

    finally:
        camera.stop()
        camera.close()

    elapsed = time.perf_counter() - started_at
    actual_fps = frame_count / max(elapsed, 0.001)

    print()
    print("Persistent stream test complete")
    print(f"Frames captured: {frame_count}")
    print(f"Average FPS: {actual_fps:.2f}")
    print(f"Motion frames: {motion_events}")


if __name__ == "__main__":
    main()
