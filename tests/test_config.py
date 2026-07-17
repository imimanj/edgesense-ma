from shared.config import get_settings


def test_default_settings_are_hardware_ready_but_mocked():
    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.device_target == "raspberry_pi_5"

    assert settings.camera_mode == "mock"
    assert settings.sensor_mode == "mock"
    assert settings.audio_mode == "mock"
    assert settings.vision_mode == "mock"

    assert settings.is_local is True
    assert settings.is_raspberry_pi_target is True
    assert settings.uses_mock_inputs is True
