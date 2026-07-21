# Demo Scenarios

This document describes the validated demonstration scenarios for EdgeSense-MA.

The predefined Agent Service scenarios are deterministic API demonstrations. They are separate from the live PIR-triggered camera pipeline and are intended to make the decision logic easy to verify during a presentation.

## Important trust boundary

The predefined demo scenarios use `source_mode=demo` and `hardware_ready=true` so that audio scoring can be demonstrated intentionally.

The production Raspberry Pi audio service currently reports:

- `source_mode=mock`
- `hardware_ready=false`
- `trusted_for_risk=false`

Therefore synthetic production audio is excluded from live risk scoring. Demo audio must not be presented as a reading from connected microphone hardware.

## Demo endpoint

The Agent Service exposes:

```text
GET http://127.0.0.1:8005/agents/demo/{scenario}
```

The API Gateway also proxies the same scenario route:

```text
GET http://127.0.0.1:8000/agents/demo/{scenario}
```

Supported names:

- `normal`
- `environmental-warning`
- `environment_warning`
- `multimodal-warning`
- `multimodal_warning`

The hyphenated and underscored environmental and multimodal names are aliases.

An unknown scenario returns HTTP `404`.

## Scenario summary

| Scenario | Vision score | Sensor score | Audio score | Total | Final risk |
|---|---:|---:|---:|---:|---|
| Normal | 1 | 0 | 0 | 1 | `LOW` |
| Environmental warning | 1 | 1 | 0 | 2 | `MEDIUM` |
| Multimodal warning | 2 | 2 | 1 | 5 | `HIGH` |

## Demo 1 — Normal environment

### Inputs

- one `person` detection at confidence `0.88`
- temperature `24.0 C`
- humidity `45.0%`
- pressure `1012.0 hPa`
- air-quality level `normal`
- demo audio event `normal_sound`
- demo audio volume `48 dB`

### Expected scoring

| Modality | Score | Reason |
|---|---:|---|
| Vision | 1 | A person is present |
| Sensors | 0 | Environmental readings are normal |
| Audio | 0 | Audio level is normal |
| Total | 1 | Low combined score |

### Expected decision

```text
LOW
```

Expected recommendation:

```text
No immediate action required. Continue monitoring.
```

### Command

```bash
curl --fail --silent \
  'http://127.0.0.1:8005/agents/demo/normal' \
  | python -m json.tool
```

## Demo 2 — Environmental warning

### Inputs

- one `person` detection at confidence `0.91`
- temperature `30.5 C`
- humidity `55.0%`
- pressure `1011.0 hPa`
- relative air-quality level `warning`
- demo audio event `normal_sound`
- demo audio volume `50 dB`

### Expected scoring

| Modality | Score | Reason |
|---|---:|---|
| Vision | 1 | A person is present |
| Sensors | 1 | Environmental warning is active |
| Audio | 0 | Audio level is normal |
| Total | 2 | Environmental warning raises the combined risk |

### Expected decision

```text
MEDIUM
```

Expected recommendation:

```text
Check the environment and verify ventilation or safety conditions.
```

### Commands

Hyphenated name:

```bash
curl --fail --silent \
  'http://127.0.0.1:8005/agents/demo/environmental-warning' \
  | python -m json.tool
```

Underscored alias:

```bash
curl --fail --silent \
  'http://127.0.0.1:8005/agents/demo/environment_warning' \
  | python -m json.tool
```

## Demo 3 — Multimodal warning

### Inputs

- one `person` detection at confidence `0.91`
- one `backpack` detection at confidence `0.76`
- temperature `33.2 C`
- humidity `65.0%`
- pressure `1008.0 hPa`
- relative air-quality level `critical`
- demo audio event `loud_noise`
- demo audio volume `78 dB`

### Expected scoring

| Modality | Score | Reason |
|---|---:|---|
| Vision | 2 | A person with a carried object is present |
| Sensors | 2 | A critical environmental condition is active |
| Audio | 1 | Loud demo audio is present |
| Total | 5 | Multiple modalities support immediate escalation |

### Expected decision

```text
HIGH
```

Expected recommendation:

```text
Manual inspection recommended immediately. Check ventilation and investigate the detected event.
```

### Commands

Hyphenated name:

```bash
curl --fail --silent \
  'http://127.0.0.1:8005/agents/demo/multimodal-warning' \
  | python -m json.tool
```

Underscored alias:

```bash
curl --fail --silent \
  'http://127.0.0.1:8005/agents/demo/multimodal_warning' \
  | python -m json.tool
```

## Unknown scenario behavior

```bash
curl --silent \
  --output /tmp/edgesense-unknown-demo.json \
  --write-out '%{http_code}\n' \
  'http://127.0.0.1:8005/agents/demo/unknown-scenario'
```

Expected HTTP status:

```text
404
```

## Live PIR demonstration

The live demonstration uses the real HC-SR501, RGB camera, infrared camera, BME280, MQ-135, YOLO11n ONNX model, event store, Agent Service, API Gateway, and dashboard.

### Preparation

1. Confirm that the complete systemd stack is healthy.
2. Open the Streamlit dashboard.
3. Confirm that the Motion Vision Worker reports `healthy`.
4. Confirm that PIR is available.
5. Confirm that both cameras are in standby.
6. Confirm that the Audio Service is marked mock and excluded from risk scoring.

Health check:

```bash
./scripts/check_pi_stack.sh
```

Dashboard:

```text
http://127.0.0.1:8501
```

### Live demo A — Person event

1. Stand outside the PIR detection area.
2. Wait for the PIR state to return to clear.
3. Enter the detection area.
4. Allow the RGB and infrared capture pipeline to finish.
5. Open the latest event in the dashboard.

Expected evidence can include:

- PIR trigger metadata
- selected RGB frame
- annotated RGB frame
- infrared evidence image
- YOLO detection results
- current environmental readings
- event category such as `person`
- explainable risk decision
- capture and inference latency

### Live demo B — Unknown motion

1. Trigger PIR motion without presenting a clearly detectable supported object.
2. Wait for capture and inference to finish.
3. Open the latest event.

Expected classification:

```text
unknown_motion
```

The event is retained because PIR confirmed motion even though no accepted object detection was available.

### Live demo C — Relative MQ-135 response

Only perform this demonstration in a ventilated area and without exposing the sensor or people to dangerous concentrations.

The MQ-135 value is a relative device signal, not regulatory AQI or calibrated gas-specific ppm.

Expected behavior:

1. Stable room conditions remain `normal`.
2. A sufficiently elevated and sustained response can transition to `warning`.
3. A stronger sustained response can transition to `critical`.
4. Rolling-median smoothing, confirmation samples, and hysteresis prevent rapid state changes.

## Evidence review

List recent events:

```bash
curl --fail --silent \
  'http://127.0.0.1:8000/events?limit=10' \
  | python -m json.tool
```

Filter person events:

```bash
curl --fail --silent \
  'http://127.0.0.1:8000/events?limit=10&category=person' \
  | python -m json.tool
```

Filter unknown-motion events:

```bash
curl --fail --silent \
  'http://127.0.0.1:8000/events?limit=10&category=unknown_motion' \
  | python -m json.tool
```

Read the latest event:

```bash
curl --fail --silent \
  'http://127.0.0.1:8000/events/latest' \
  | python -m json.tool
```

## Automated validation

The software suite includes independent checks for:

- normal demo risk and total score
- environmental-warning aliases
- multimodal-warning aliases
- carried-object scoring with `backpack`
- unknown scenario HTTP `404`
- production mock-audio exclusion
- event classification
- category filtering
- MQ-135 stateful classification

Run all software tests:

```bash
python -m pytest -q
```

The current validated suite contains `33` tests.

## Presentation notes

During a presentation, clearly distinguish among:

- predefined deterministic Agent Service demos
- real PIR-triggered hardware events
- real environmental sensor readings
- simulated demo audio
- production mock audio that is excluded from risk scoring

Do not describe the MQ-135 signal as certified AQI, CO2 ppm, or gas-specific concentration.

Do not describe demo audio as microphone input from the current Raspberry Pi deployment.
