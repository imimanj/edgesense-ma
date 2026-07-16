from __future__ import annotations

import time
import spidev


spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000


def read_channel(channel: int) -> int:
    response = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((response[1] & 3) << 8) + response[2]
    return value


try:
    print("MCP3008 test")
    print("CH0 should be close to 1023 if connected to 3.3V.")
    print("Press CTRL+C to stop.")
    print()

    while True:
        raw = read_channel(0)
        voltage = raw * 3.3 / 1023
        print(f"CH0 raw={raw} voltage={voltage:.2f}V")
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    spi.close()
