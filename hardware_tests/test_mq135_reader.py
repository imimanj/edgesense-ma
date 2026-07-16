from __future__ import annotations

import time

from services.sensor_service.app.hardware.mq135 import MQ135Reader


reader = MQ135Reader(channel=0)

try:
    print("Testing MQ-135 reader module")
    print("Bring alcohol vapor close to the sensor to check level changes.")
    print("Press CTRL+C to stop.")
    print()

    while True:
        reading = reader.read()

        print(
            f"raw={reading.raw:4d} | "
            f"adc={reading.adc_voltage:.4f}V | "
            f"mq_ao_est={reading.estimated_sensor_voltage:.4f}V | "
            f"level={reading.level} | "
            f"{reading.message}"
        )

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopped.")

finally:
    reader.close()
