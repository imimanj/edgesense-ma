from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass


VALID_LEVELS = ("normal", "warning", "critical")


@dataclass(frozen=True)
class MQ135Classification:
    level: str
    smoothed_raw: float
    baseline_raw: float
    response_ratio: float
    warning_threshold_raw: float
    critical_threshold_raw: float
    message: str


class MQ135SignalClassifier:
    def __init__(
        self,
        baseline_raw: float = 14.0,
        warning_raw_floor: float = 25.0,
        critical_raw_floor: float = 45.0,
        warning_ratio: float = 1.8,
        critical_ratio: float = 3.0,
        warning_clear_ratio: float = 1.55,
        critical_clear_ratio: float = 2.5,
        window_size: int = 5,
        confirmation_samples: int = 3,
    ) -> None:
        if baseline_raw <= 0:
            raise ValueError("baseline_raw must be positive")
        if warning_raw_floor <= 0:
            raise ValueError("warning_raw_floor must be positive")
        if critical_raw_floor <= warning_raw_floor:
            raise ValueError(
                "critical_raw_floor must exceed warning_raw_floor"
            )
        if warning_ratio <= 1:
            raise ValueError("warning_ratio must exceed 1")
        if critical_ratio <= warning_ratio:
            raise ValueError(
                "critical_ratio must exceed warning_ratio"
            )
        if warning_clear_ratio >= warning_ratio:
            raise ValueError(
                "warning_clear_ratio must be below warning_ratio"
            )
        if critical_clear_ratio >= critical_ratio:
            raise ValueError(
                "critical_clear_ratio must be below critical_ratio"
            )
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        if confirmation_samples < 1:
            raise ValueError(
                "confirmation_samples must be at least 1"
            )

        self.baseline_raw = float(baseline_raw)
        self.warning_raw_floor = float(warning_raw_floor)
        self.critical_raw_floor = float(critical_raw_floor)
        self.warning_ratio = float(warning_ratio)
        self.critical_ratio = float(critical_ratio)
        self.warning_clear_ratio = float(warning_clear_ratio)
        self.critical_clear_ratio = float(critical_clear_ratio)
        self.confirmation_samples = confirmation_samples
        self.window_size = window_size

        self.values: deque[int] = deque(
            maxlen=window_size
        )

        self.current_level = "normal"
        self.pending_level: str | None = None
        self.pending_count = 0

    @property
    def warning_threshold_raw(self) -> float:
        return max(
            self.warning_raw_floor,
            self.baseline_raw * self.warning_ratio,
        )

    @property
    def critical_threshold_raw(self) -> float:
        return max(
            self.critical_raw_floor,
            self.baseline_raw * self.critical_ratio,
        )

    @property
    def warning_clear_threshold_raw(self) -> float:
        return max(
            self.warning_raw_floor * 0.88,
            self.baseline_raw * self.warning_clear_ratio,
        )

    @property
    def critical_clear_threshold_raw(self) -> float:
        return max(
            self.critical_raw_floor * 0.90,
            self.baseline_raw * self.critical_clear_ratio,
        )

    def _candidate_level(
        self,
        smoothed_raw: float,
    ) -> str:
        if self.current_level == "critical":
            if (
                smoothed_raw
                >= self.critical_clear_threshold_raw
            ):
                return "critical"

        if self.current_level == "warning":
            if (
                smoothed_raw
                >= self.critical_threshold_raw
            ):
                return "critical"

            if (
                smoothed_raw
                >= self.warning_clear_threshold_raw
            ):
                return "warning"

        if smoothed_raw >= self.critical_threshold_raw:
            return "critical"

        if smoothed_raw >= self.warning_threshold_raw:
            return "warning"

        return "normal"

    def _confirm_transition(
        self,
        candidate_level: str,
    ) -> None:
        if candidate_level == self.current_level:
            self.pending_level = None
            self.pending_count = 0
            return

        if candidate_level == self.pending_level:
            self.pending_count += 1
        else:
            self.pending_level = candidate_level
            self.pending_count = 1

        if self.pending_count >= self.confirmation_samples:
            self.current_level = candidate_level
            self.pending_level = None
            self.pending_count = 0

    def classify(
        self,
        raw: int,
    ) -> MQ135Classification:
        if raw < 0:
            raise ValueError("raw must not be negative")

        self.values.append(raw)

        smoothed_raw = float(
            statistics.median(self.values)
        )

        candidate_level = self._candidate_level(
            smoothed_raw
        )

        self._confirm_transition(candidate_level)

        response_ratio = (
            smoothed_raw / self.baseline_raw
        )

        messages = {
            "normal": (
                "MQ-135 relative response is within "
                "the calibrated device range"
            ),
            "warning": (
                "Sustained elevated MQ-135 relative "
                "response detected"
            ),
            "critical": (
                "Sustained high MQ-135 relative "
                "response detected"
            ),
        }

        return MQ135Classification(
            level=self.current_level,
            smoothed_raw=round(smoothed_raw, 3),
            baseline_raw=round(self.baseline_raw, 3),
            response_ratio=round(response_ratio, 3),
            warning_threshold_raw=round(
                self.warning_threshold_raw,
                3,
            ),
            critical_threshold_raw=round(
                self.critical_threshold_raw,
                3,
            ),
            message=messages[self.current_level],
        )
