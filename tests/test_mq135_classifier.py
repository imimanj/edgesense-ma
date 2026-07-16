from services.sensor_service.app.mq135_classifier import (
    MQ135SignalClassifier,
)


def build_classifier() -> MQ135SignalClassifier:
    return MQ135SignalClassifier(
        baseline_raw=14,
        warning_raw_floor=25,
        critical_raw_floor=45,
        warning_ratio=1.8,
        critical_ratio=3.0,
        window_size=3,
        confirmation_samples=2,
    )


def test_stable_baseline_remains_normal():
    classifier = build_classifier()

    results = [
        classifier.classify(value)
        for value in [14, 15, 14, 15, 14]
    ]

    assert all(
        result.level == "normal"
        for result in results
    )

    assert results[-1].response_ratio == 1.0


def test_isolated_spike_does_not_trigger_warning():
    classifier = build_classifier()

    results = [
        classifier.classify(value)
        for value in [14, 14, 60, 14, 14]
    ]

    assert all(
        result.level == "normal"
        for result in results
    )


def test_sustained_elevation_triggers_warning():
    classifier = build_classifier()

    results = [
        classifier.classify(value)
        for value in [14, 14, 30, 30, 30, 30]
    ]

    assert results[-1].level == "warning"
    assert results[-1].smoothed_raw == 30


def test_sustained_high_response_triggers_critical():
    classifier = build_classifier()

    results = [
        classifier.classify(value)
        for value in [14, 14, 60, 60, 60, 60]
    ]

    assert results[-1].level == "critical"
    assert results[-1].smoothed_raw == 60


def test_warning_hysteresis_prevents_flapping():
    classifier = build_classifier()

    for value in [14, 14, 30, 30, 30, 30]:
        result = classifier.classify(value)

    assert result.level == "warning"

    for value in [23, 23, 23, 23]:
        result = classifier.classify(value)

    assert result.level == "warning"

    for value in [18, 18, 18, 18]:
        result = classifier.classify(value)

    assert result.level == "normal"


def test_raw_floors_protect_low_baselines():
    classifier = MQ135SignalClassifier(
        baseline_raw=12,
    )

    assert classifier.warning_threshold_raw == 25
    assert classifier.critical_threshold_raw == 45


def test_relative_thresholds_protect_high_baselines():
    classifier = MQ135SignalClassifier(
        baseline_raw=20,
    )

    assert classifier.warning_threshold_raw == 36
    assert classifier.critical_threshold_raw == 60
