from importlib import util
from pathlib import Path
from types import SimpleNamespace

from services.sensor_service.app.mq135_classifier import (
    MQ135SignalClassifier,
)


def load_sensor_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "sensor_service"
        / "app"
        / "main.py"
    )

    spec = util.spec_from_file_location(
        "sensor_service_real_main",
        path,
    )

    module = util.module_from_spec(spec)

    assert spec.loader is not None
    spec.loader.exec_module(module)

    return module


def test_real_reader_uses_stateful_classifier():
    sensor_module = load_sensor_module()

    class FakeReader:
        values = iter([14, 14, 60, 60, 60, 60])
        close_count = 0

        def __init__(self, channel):
            assert channel == 0

        def read(self):
            return SimpleNamespace(
                raw=next(self.values)
            )

        def close(self):
            type(self).close_count += 1

    sensor_module.MQ135Reader = FakeReader

    sensor_module.mq135_classifier = (
        MQ135SignalClassifier(
            baseline_raw=14,
            warning_raw_floor=25,
            critical_raw_floor=45,
            warning_ratio=1.8,
            critical_ratio=3.0,
            window_size=3,
            confirmation_samples=2,
        )
    )

    results = [
        sensor_module.read_real_mq135()
        for _ in range(6)
    ]

    assert results[2][1] == "normal"
    assert results[3][1] == "normal"
    assert results[4][1] == "critical"
    assert results[5][1] == "critical"
    assert FakeReader.close_count == 6


def test_status_exposes_relative_calibration(
    monkeypatch,
):
    monkeypatch.setenv("SENSOR_MODE", "real")

    sensor_module = load_sensor_module()
    details = sensor_module.status().details

    assert (
        details["mq135_classification_mode"]
        == "stateful_relative_signal"
    )
    assert details["mq135_baseline_raw"] == 14.0
    assert (
        details[
            "mq135_effective_warning_threshold_raw"
        ]
        == 25.2
    )
    assert (
        details[
            "mq135_effective_critical_threshold_raw"
        ]
        == 45.0
    )
    assert details["mq135_window_size"] == 5
    assert details["mq135_confirmation_samples"] == 3
