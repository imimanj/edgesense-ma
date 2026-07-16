from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI

from services.sensor_service.app.hardware.mq135 import MQ135Reader
from services.sensor_service.app.mq135_classifier import (
    MQ135SignalClassifier,
)
from shared.schemas import SensorReading, ServiceStatus

app = FastAPI(title="EdgeSense-MA Sensor Service", version="0.4.0")


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


mq135_classifier = MQ135SignalClassifier(
    baseline_raw=env_float(
        "MQ135_BASELINE_RAW",
        14.0,
    ),
    warning_raw_floor=env_float(
        "MQ135_WARNING_THRESHOLD",
        25.0,
    ),
    critical_raw_floor=env_float(
        "MQ135_CRITICAL_THRESHOLD",
        45.0,
    ),
    warning_ratio=env_float(
        "MQ135_WARNING_RATIO",
        1.8,
    ),
    critical_ratio=env_float(
        "MQ135_CRITICAL_RATIO",
        3.0,
    ),
    warning_clear_ratio=env_float(
        "MQ135_WARNING_CLEAR_RATIO",
        1.55,
    ),
    critical_clear_ratio=env_float(
        "MQ135_CRITICAL_CLEAR_RATIO",
        2.5,
    ),
    window_size=env_int(
        "MQ135_WINDOW_SIZE",
        5,
    ),
    confirmation_samples=env_int(
        "MQ135_CONFIRMATION_SAMPLES",
        3,
    ),
)

mq135_read_lock = Lock()


def get_sensor_mode() -> str:
    return os.getenv("SENSOR_MODE", "mock")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_air_quality(raw_value: int) -> str:
    """
    Classification for mock mode.

    Real MQ-135 classification is handled by MQ135Reader, because our real
    baseline is much lower after using the 10K/10K voltage divider.
    """
    if raw_value >= 750:
        return "critical"
    if raw_value >= 550:
        return "warning"
    return "normal"


def read_mock_sensors() -> SensorReading:
    air_quality_raw = random.randint(420, 760)

    return SensorReading(
        temperature_c=round(random.uniform(24.0, 31.0), 1),
        humidity_percent=round(random.uniform(35.0, 65.0), 1),
        pressure_hpa=round(random.uniform(1002.0, 1012.0), 1),
        air_quality_raw=air_quality_raw,
        air_quality_level=classify_air_quality(air_quality_raw),
        timestamp=utc_now(),
    )


def read_real_mq135() -> tuple[int, str]:
    """
    Reads the MQ-135 relative analog response through MCP3008 CH0.

    The raw ADC value is preserved. Classification uses a stateful,
    device-specific relative signal model with rolling-median smoothing,
    transition confirmation, hysteresis, and conservative raw floors.

    Sensor access is serialized because SPI and the shared classifier
    may be reached concurrently by multiple API consumers.

    The result is not a regulatory AQI or calibrated gas concentration.
    """
    with mq135_read_lock:
        reader = MQ135Reader(channel=0)

        try:
            mq135 = reader.read()
            classification = mq135_classifier.classify(
                mq135.raw
            )
            return mq135.raw, classification.level
        finally:
            reader.close()


def read_bme280_sensors() -> SensorReading:
    import board
    import busio
    from adafruit_bme280 import basic as adafruit_bme280

    i2c = busio.I2C(board.SCL, board.SDA)
    bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)

    air_quality_raw, air_quality_level = read_real_mq135()

    return SensorReading(
        temperature_c=round(bme280.temperature, 2),
        humidity_percent=round(bme280.relative_humidity, 2),
        pressure_hpa=round(bme280.pressure, 2),
        air_quality_raw=air_quality_raw,
        air_quality_level=air_quality_level,
        timestamp=utc_now(),
    )


@app.get("/sensors/status", response_model=ServiceStatus)
def status() -> ServiceStatus:
    mode = get_sensor_mode()

    return ServiceStatus(
        service="sensor-service",
        details={
            "mode": mode,
            "bme280_enabled": mode == "real",
            "mq135_enabled": mode == "real",
            "air_quality_source": "mq135_mcp3008_ch0" if mode == "real" else "mock",
            "mq135_classification_mode": (
                "stateful_relative_signal"
                if mode == "real"
                else "mock"
            ),
            "mq135_baseline_raw": mq135_classifier.baseline_raw,
            "mq135_warning_threshold": str(
                mq135_classifier.warning_raw_floor
            ),
            "mq135_critical_threshold": str(
                mq135_classifier.critical_raw_floor
            ),
            "mq135_effective_warning_threshold_raw": round(
                mq135_classifier.warning_threshold_raw,
                3,
            ),
            "mq135_effective_critical_threshold_raw": round(
                mq135_classifier.critical_threshold_raw,
                3,
            ),
            "mq135_warning_ratio": mq135_classifier.warning_ratio,
            "mq135_critical_ratio": mq135_classifier.critical_ratio,
            "mq135_window_size": mq135_classifier.window_size,
            "mq135_confirmation_samples": (
                mq135_classifier.confirmation_samples
            ),
            "mq135_current_level": (
                mq135_classifier.current_level
            ),
        },
    )


@app.get("/sensors/current", response_model=SensorReading)
def current() -> SensorReading:
    mode = get_sensor_mode()

    if mode == "real":
        return read_bme280_sensors()

    return read_mock_sensors()
