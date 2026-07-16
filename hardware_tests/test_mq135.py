from __future__ import annotations

import time
import spidev

VREF = 3.3
DIVIDER_RATIO = 2.0   # because we use 10K + 10K voltage divider
CHANNEL = 0           # MCP3008 CH0


spi = spidev.SpiDev()
spi.open(0, 0)        # SPI bus 0, CE0
spi.max_speed_hz = 1350000


def read_channel(channel: int) -> int:
    if channel < 0 or channel > 7:
        raise ValueError("MCP3008 channel must be between 0 and 7")

    response = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((response[1] & 3) << 8) + response[2]
    return value


try:
    print("MQ-135 test through MCP3008 CH0")
    print("Using 10K + 10K voltage divider")
    print("Bring alcohol vapor close to the sensor to check if values increase.")
    print("Press CTRL+C to stop.")
    print()

    while True:
        raw = read_channel(CHANNEL)

        adc_voltage = raw * VREF / 1023
        estimated_mq_ao_voltage = adc_voltage * DIVIDER_RATIO

        print(
            f"CH0 raw={raw:4d} | "
            f"ADC voltage={adc_voltage:.3f}V | "
            f"Estimated MQ AO={estimated_mq_ao_voltage:.3f}V"
        )

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    spi.close()
