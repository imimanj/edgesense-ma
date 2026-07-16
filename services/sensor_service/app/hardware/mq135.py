from __future__ import annotations

import os
import time
from dataclasses import dataclass

import spidev


@dataclass
class MQ135Reading:
    raw: int
    adc_voltage: float
    estimated_sensor_voltage: float
    level: str
    message: str


class MQ135Reader:
    """
    Reads MQ-135 analog output through MCP3008.

    Hardware path:
    MQ-135 AO -> 10K/10K voltage divider -> MCP3008 CH0 -> Raspberry Pi SPI
    """

    def __init__(
        self,
        channel: int = 0,
        vref: float = 3.3,
        divider_ratio: float = 2.0,
        spi_bus: int = 0,
        spi_device: int = 0,
        spi_speed_hz: int = 1_350_000,
    ) -> None:
        if channel < 0 or channel > 7:
            raise ValueError("MCP3008 channel must be between 0 and 7")

        self.channel = channel
        self.vref = vref
        self.divider_ratio = divider_ratio

        self.warning_threshold = int(os.getenv("MQ135_WARNING_THRESHOLD", "25"))
        self.critical_threshold = int(os.getenv("MQ135_CRITICAL_THRESHOLD", "45"))

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = spi_speed_hz

    def read_raw_once(self) -> int:
        response = self.spi.xfer2([1, (8 + self.channel) << 4, 0])
        return ((response[1] & 3) << 8) + response[2]

    def read_raw_average(self, samples: int = 5, delay_seconds: float = 0.05) -> int:
        values = []

        for _ in range(samples):
            values.append(self.read_raw_once())
            time.sleep(delay_seconds)

        return round(sum(values) / len(values))

    def classify(self, raw: int) -> tuple[str, str]:
        if raw >= self.critical_threshold:
            return "critical", "High MQ-135 response detected"
        if raw >= self.warning_threshold:
            return "warning", "Elevated MQ-135 response detected"
        return "normal", "MQ-135 response is within the current baseline range"

    def read(self) -> MQ135Reading:
        raw = self.read_raw_average()

        adc_voltage = raw * self.vref / 1023
        estimated_sensor_voltage = adc_voltage * self.divider_ratio

        level, message = self.classify(raw)

        return MQ135Reading(
            raw=raw,
            adc_voltage=round(adc_voltage, 4),
            estimated_sensor_voltage=round(estimated_sensor_voltage, 4),
            level=level,
            message=message,
        )

    def close(self) -> None:
        self.spi.close()
