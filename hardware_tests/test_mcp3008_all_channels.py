from __future__ import annotations

import time
import spidev


spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000


def read_channel(channel: int) -> int:
    response = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((response[1] & 3) << 8) + response[2]


try:
    print("MCP3008 all channels test")
    print("-------------------------")
    print("Expected: one channel should be close to 1023 if it is connected to 3.3V.")
    print("Press CTRL+C to stop.")
    print()

    while True:
        values = [read_channel(ch) for ch in range(8)]
        print(values)
        time.sleep(1)

except KeyboardInterrupt:
    print("Stopped.")

finally:
    spi.close()
