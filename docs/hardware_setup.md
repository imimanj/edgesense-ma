# Hardware Setup

This document describes the hardware configuration used by the current EdgeSense-MA Raspberry Pi 5 deployment.

## Confirmed runtime configuration

| Interface | Confirmed configuration |
|---|---|
| BME280 | I2C bus 1, address `0x77` |
| MQ-135 ADC path | MQ-135 AO through a 10K/10K divider to MCP3008 CH0 |
| MCP3008 | SPI0, device 0, `/dev/spidev0.0`, CE0 |
| SPI speed | 1,350,000 Hz |
| PIR sensor | HC-SR501 on GPIO23, physical pin 16 |
| Primary camera | index 0, `imx708_wide` |
| Secondary camera | index 1, `ov5647` |
| Sensor service mode | real |
| Audio hardware | not connected; service remains in mock mode |

## Required hardware

- Raspberry Pi 5
- Raspberry Pi Camera Module 3 Wide
- MakerHawk OV5647 infrared fisheye camera
- HC-SR501 PIR motion sensor
- BME280 temperature, humidity, and pressure sensor
- AZDelivery MQ-135 module
- MCP3008 10-bit ADC
- two 10K resistors for the MQ-135 analog voltage divider
- breadboard and jumper wires
- Raspberry Pi active cooling
- suitable Raspberry Pi 5 power supply

## Electrical safety

Power down the Raspberry Pi before changing any wiring.

Raspberry Pi GPIO signals use 3.3V logic. Do not apply 5V directly to a GPIO input or to an SPI signal pin.

The MQ-135 module is powered from 5V in this installation. Its analog output must pass through the documented 10K/10K divider before reaching MCP3008 CH0.

Do not connect MQ-135 AO directly to a Raspberry Pi GPIO pin.

The MCP3008 is powered and referenced at 3.3V in this design. This keeps its SPI logic compatible with the Raspberry Pi and limits the ADC measurement range to the 3.3V reference.

All modules in the sensor path must share a common ground.

Check the MCP3008 notch or pin-1 marker before wiring. Reversing the IC orientation can damage the ADC or connected hardware.

## Raspberry Pi header signals

The reference wiring uses these 40-pin header signals:

| Function | BCM GPIO | Physical pin |
|---|---:|---:|
| 3.3V power | N/A | 1 or 17 |
| 5V power | N/A | 2 or 4 |
| Ground | N/A | 6, 9, 14, 20, 25, 30, 34, or 39 |
| I2C SDA | GPIO2 | 3 |
| I2C SCL | GPIO3 | 5 |
| SPI0 MOSI | GPIO10 | 19 |
| SPI0 MISO | GPIO9 | 21 |
| SPI0 SCLK | GPIO11 | 23 |
| SPI0 CE0 | GPIO8 | 24 |
| PIR input | GPIO23 | 16 |

Power and ground may use any matching header pin, provided all grounds are common and the chosen rail has the correct voltage.

## BME280 wiring

The current BME280 is detected on I2C bus 1 at address `0x77`.

| BME280 pin | Raspberry Pi connection |
|---|---|
| VCC or VIN | 3.3V |
| GND | Ground |
| SDA | GPIO2, physical pin 3 |
| SCL | GPIO3, physical pin 5 |

Use 3.3V unless the exact breakout-board documentation explicitly states that its VIN input and level shifting support another voltage.

## MCP3008 wiring

The code opens SPI bus 0, device 0. Therefore the ADC uses SPI0 CE0 and appears as `/dev/spidev0.0`.

With the MCP3008 notch facing upward, pin numbering runs down the left side from pin 1 to pin 8, then up the right side from pin 9 to pin 16.

| MCP3008 pin | Name | Connection |
|---:|---|---|
| 1 | CH0 | MQ-135 divider midpoint |
| 2-8 | CH1-CH7 | Unused |
| 9 | DGND | Ground |
| 10 | CS/SHDN | GPIO8 / SPI0 CE0 / physical pin 24 |
| 11 | DIN | GPIO10 / SPI0 MOSI / physical pin 19 |
| 12 | DOUT | GPIO9 / SPI0 MISO / physical pin 21 |
| 13 | CLK | GPIO11 / SPI0 SCLK / physical pin 23 |
| 14 | AGND | Ground |
| 15 | VREF | 3.3V |
| 16 | VDD | 3.3V |

Keep VREF and VDD at 3.3V for the current project configuration.

## MQ-135 and voltage-divider wiring

The MQ-135 module uses its analog output. The digital output is not used.

| MQ-135 module pin | Connection |
|---|---|
| VCC | Raspberry Pi 5V rail |
| GND | Common ground |
| AO | First 10K resistor leading to the divider midpoint |
| DO | Not connected |

Build the divider as follows:

```text
MQ-135 AO
    |
   10K
    |
    +------ MCP3008 CH0
    |
   10K
    |
   GND
```

The equal-value divider halves the voltage presented to MCP3008 CH0. The software uses a divider ratio of `2.0` when estimating the original sensor-output voltage.

The application stores the raw 10-bit ADC reading. It does not claim that this value is regulatory AQI, CO2 concentration, or calibrated gas-specific ppm.

## PIR wiring

The current HC-SR501 installation uses:

| HC-SR501 pin | Raspberry Pi connection |
|---|---|
| VCC | 5V, physical pin 2 |
| OUT | GPIO23, physical pin 16 |
| GND | Ground, physical pin 14 |

The motion worker configures GPIO23 as an input and uses PIR rising edges to start the dual-camera capture pipeline.

## Camera connections

The Raspberry Pi currently detects:

| Camera index | Detected model | Role |
|---:|---|---|
| 0 | `imx708_wide` | Primary RGB capture |
| 1 | `ov5647` | Secondary infrared evidence |

The worker opens cameras only when a PIR event occurs and closes each camera after capture.

Camera indices can change after cable or device changes. Always verify enumeration before relying on index values.

## Enable Raspberry Pi interfaces

Enable I2C and SPI through Raspberry Pi configuration:

```bash
sudo raspi-config
```

Under Interface Options, enable:

- I2C
- SPI

Reboot after changing interface configuration.

## Hardware validation

Check the BME280:

```bash
i2cdetect -y 1
```

The expected address is `77`.

Check SPI device nodes:

```bash
ls -l /dev/spidev0.0 /dev/spidev0.1
```

Check the configured PIR pin:

```bash
pinctrl get 23
```

Check camera enumeration:

```bash
rpicam-hello --list-cameras
```

Expected order for the current installation:

```text
0 : imx708_wide
1 : ov5647
```

Check the real sensor API:

```bash
curl --fail --silent http://127.0.0.1:8002/sensors/current | python -m json.tool
```

Check the complete deployed stack:

```bash
./scripts/check_pi_stack.sh
```

## Device permissions

The repository systemd service files use `YOUR_USER` as a placeholder. Replace it with the Linux account that will run EdgeSense-MA before installing the units.

The account must retain membership in the hardware-access groups used by this project:

- `gpio`
- `i2c`
- `spi`
- `video`
- `render`
- `audio`

The deployed systemd units also define appropriate supplementary groups for their hardware responsibilities.

## MQ-135 warm-up and interpretation

The MQ-135 heater requires extended stabilization before establishing a baseline. The current project baseline was selected only after long-duration observation of this specific sensor installation.

Current classification parameters are:

| Parameter | Value |
|---|---:|
| Baseline raw | 14 |
| Warning raw floor | 25 |
| Critical raw floor | 45 |
| Warning ratio | 1.8 |
| Critical ratio | 3.0 |
| Warning clear ratio | 1.55 |
| Critical clear ratio | 2.5 |
| Rolling window | 5 samples |
| Confirmation | 3 samples |

Do not copy these values to another MQ-135 module without performing a new calibration. Sensor-to-sensor variation, heater history, temperature, humidity, airflow, supply conditions, and module circuitry can change the observed baseline.

## Troubleshooting

### BME280 is missing

- confirm I2C is enabled
- run `i2cdetect -y 1`
- verify address `0x77`
- check SDA, SCL, 3.3V, and common ground
- inspect `/dev/i2c-1`
- verify the service user belongs to the `i2c` group

### MCP3008 returns zero or unstable readings

- confirm SPI is enabled
- verify `/dev/spidev0.0`
- verify CE0 is connected to MCP3008 pin 10
- verify DIN and DOUT are not reversed
- verify VDD and VREF are both 3.3V
- verify AGND and DGND share common ground
- inspect the 10K/10K divider midpoint
- keep analog wiring short and away from noisy power cables

### PIR does not trigger

- confirm OUT is connected to GPIO23, physical pin 16
- confirm the worker reports `pir_available=true`
- allow the HC-SR501 startup stabilization period
- check the sensitivity and hold-time potentiometers
- inspect `journalctl -u edgesense-motion-worker.service`

### Camera capture fails

- power down before reseating CSI cables
- verify the connector latch is fully closed
- confirm cable orientation
- run `rpicam-hello --list-cameras`
- confirm `imx708_wide` is index 0 and `ov5647` is index 1
- inspect `journalctl -u edgesense-motion-worker.service`

## Technical references

- [Raspberry Pi computer hardware and GPIO functions](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- [Microchip MCP3004/MCP3008 data sheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/MCP3004-MCP3008-Data-Sheet-DS20001295.pdf)
- [Bosch BME280 data sheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf)
- [Winsen MQ135 manual](https://www.winsen-sensor.com/d/files/PDF/Semiconductor%20Gas%20Sensor/MQ135%20%28Ver1.4%29%20-%20Manual.pdf)
