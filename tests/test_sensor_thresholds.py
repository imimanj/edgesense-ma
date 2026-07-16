from pathlib import Path
import importlib.util


def load_sensor_module():
    path = Path(__file__).resolve().parents[1] / "services" / "sensor_service" / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("sensor_service_main", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_air_quality_thresholds():
    sensor_module = load_sensor_module()
    assert sensor_module.classify_air_quality(300) == "normal"
    assert sensor_module.classify_air_quality(550) == "warning"
    assert sensor_module.classify_air_quality(750) == "critical"
