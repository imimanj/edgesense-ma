from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    device_target: str

    camera_mode: str
    sensor_mode: str
    audio_mode: str
    vision_mode: str

    api_gateway_host: str
    api_gateway_port: int

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_raspberry_pi_target(self) -> bool:
        return self.device_target == "raspberry_pi_5"

    @property
    def uses_mock_inputs(self) -> bool:
        return (
            self.camera_mode == "mock"
            or self.sensor_mode == "mock"
            or self.audio_mode == "mock"
            or self.vision_mode == "mock"
        )


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        device_target=os.getenv("DEVICE_TARGET", "raspberry_pi_5"),
        camera_mode=os.getenv("CAMERA_MODE", "mock"),
        sensor_mode=os.getenv("SENSOR_MODE", "mock"),
        audio_mode=os.getenv("AUDIO_MODE", "mock"),
        vision_mode=os.getenv("VISION_MODE", "mock"),
        api_gateway_host=os.getenv("API_GATEWAY_HOST", "127.0.0.1"),
        api_gateway_port=int(os.getenv("API_GATEWAY_PORT", "8000")),
    )
