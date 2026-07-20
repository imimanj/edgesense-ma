# API Reference

EdgeSense-MA exposes six FastAPI services on the Raspberry Pi. The API Gateway on port `8000` is the primary application entry point, while ports `8001` through `8005` expose the individual services.

## Base URLs

| Service | Base URL |
|---|---|
| API Gateway | `http://127.0.0.1:8000` |
| Camera Service | `http://127.0.0.1:8001` |
| Sensor Service | `http://127.0.0.1:8002` |
| Audio Service | `http://127.0.0.1:8003` |
| Vision Inference Service | `http://127.0.0.1:8004` |
| Agent Service | `http://127.0.0.1:8005` |

Each FastAPI service exposes interactive Swagger documentation at `/docs` and its OpenAPI document at `/openapi.json`.

Examples:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8004/docs
```

## Common conventions

- JSON is used for normal API responses.
- Timestamps use ISO 8601 date-time strings in UTC.
- `POST /vision/detect` uses `multipart/form-data`.
- `POST /agents/analyze` uses a JSON request body.
- FastAPI returns `422` when path, query, or body validation fails.
- Gateway event endpoints may additionally return `400` or `404`.
- The current deployment has no authentication layer and is intended for trusted local-network use.

## API Gateway

Base URL: `http://127.0.0.1:8000`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Basic API Gateway health response |
| `GET` | `/system/status` | Aggregated status from camera, sensor, audio, vision, and agent services |
| `GET` | `/system/snapshot` | Current multimodal snapshot assembled by the Gateway |
| `GET` | `/system/live` | Current live system state |
| `GET` | `/system/worker-status` | Motion Vision Worker heartbeat and runtime telemetry |
| `POST` | `/system/analyze-live` | Run analysis using the current live system inputs |
| `POST` | `/system/analyze` | Run the current-system analysis and persist the resulting report |
| `GET` | `/agents/demo/{scenario}` | Proxy a predefined Agent Service demo scenario |
| `GET` | `/events` | List persisted events with optional filters |
| `GET` | `/events/latest` | Return the latest persisted event |
| `GET` | `/events/{event_id}` | Return one persisted event |
| `GET` | `/events/{event_id}/image` | Return the event annotated image as an image response |
| `GET` | `/reports/latest` | Return the latest persisted decision report |
| `GET` | `/reports/history` | List up to 20 persisted report filenames |

### Event history query parameters

`GET /events` accepts the following optional query parameters:

| Parameter | Type | Default | Behavior |
|---|---|---:|---|
| `limit` | integer | `50` | Clamped to the inclusive range `1` to `500` |
| `risk` | string | none | Filter by final risk level |
| `trigger` | string | none | Filter by trigger source |
| `object_label` | string | none | Filter by detected object label |
| `category` | string | none | Filter by event category |

Supported event categories currently include:

- `person`
- `animal`
- `vehicle`
- `carried_object`
- `general_object`
- `unknown_motion`

Example:

```bash
curl --get \
  'http://127.0.0.1:8000/events' \
  --data-urlencode 'limit=20' \
  --data-urlencode 'category=person' \
  --data-urlencode 'risk=MEDIUM'
```

The response contains `count`, the effective `limit`, the applied `filters`, and an `events` array.

### Event details and images

`GET /events/{event_id}` reads the event JSON record from the persistent event store.

Known error behavior:

- `400` for an invalid event identifier or rejected image path
- `404` when the event does not exist
- `404` when an event has no annotated image
- `404` when the referenced image file is missing

`GET /events/{event_id}/image` returns the annotated image as JPEG, PNG, or WebP according to the stored file suffix.

## Camera Service

Base URL: `http://127.0.0.1:8001`

| Method | Path | Description |
|---|---|---|
| `GET` | `/camera/status` | Return camera mode, hardware readiness, device, and resolution |
| `POST` | `/camera/snapshot` | Capture or return a current camera snapshot |

The deployed status identifies Camera Module 3 Wide as the primary camera. The PIR Motion Vision Worker manages the dual-camera event flow separately.

## Sensor Service

Base URL: `http://127.0.0.1:8002`

| Method | Path | Response |
|---|---|---|
| `GET` | `/sensors/status` | `ServiceStatus` with BME280 and MQ-135 configuration |
| `GET` | `/sensors/current` | `SensorReading` |

Example:

```bash
curl --fail --silent \
  'http://127.0.0.1:8002/sensors/current' \
  | python -m json.tool
```

The MQ-135 fields represent a device-specific relative response. They are not regulatory AQI or calibrated gas-specific ppm values.

## Audio Service

Base URL: `http://127.0.0.1:8003`

| Method | Path | Response |
|---|---|---|
| `GET` | `/audio/status` | `ServiceStatus` with source and trust metadata |
| `GET` | `/audio/latest` | `AudioResult` |

The current deployment uses mock audio:

- `source_mode` is `mock`
- `hardware_ready` is `false`
- synthetic audio is excluded from risk scoring

## Vision Inference Service

Base URL: `http://127.0.0.1:8004`

| Method | Path | Description |
|---|---|---|
| `GET` | `/vision/status` | Return model, thresholds, ONNX readiness, and supported classes |
| `POST` | `/vision/detect` | Run detection on one uploaded image |
| `GET` | `/vision/latest` | Return the latest `VisionResult` |
| `POST` | `/vision/reset` | Reset the cached latest result |
| `GET` | `/vision/benchmark` | Return the active inference configuration |

### Upload an image

`POST /vision/detect` requires one form field named `file`.

```bash
curl --fail --silent \
  -X POST \
  -F 'file=@data/samples/real_camera_latest.jpg' \
  'http://127.0.0.1:8004/vision/detect' \
  | python -m json.tool
```

Content type:

```text
multipart/form-data
```

The response is a `VisionResult` containing filtered detections, total pipeline latency, model FPS, model information, snapshot path when available, and frame metadata.

Frame metadata can include:

- ONNX model input and output names
- model-only latency
- confidence and NMS thresholds
- raw and filtered detection counts
- frame-quality measurements
- lighting state
- blur state
- annotated image path

If ONNX inference fails and mock fallback is enabled, the response identifies `mock_fallback` in frame metadata. If fallback is disabled, inference failure returns `500`.

## Agent Service

Base URL: `http://127.0.0.1:8005`

| Method | Path | Description |
|---|---|---|
| `GET` | `/agents/status` | Return Agent Service mode and readiness |
| `POST` | `/agents/analyze` | Analyze one complete multimodal input |
| `GET` | `/agents/demo/{scenario}` | Run a predefined demonstration scenario |

### Analyze multimodal input

`POST /agents/analyze` requires an `AgentInput` JSON object.

Example:

```bash
curl --fail --silent \
  -X POST \
  -H 'Content-Type: application/json' \
  'http://127.0.0.1:8005/agents/analyze' \
  --data '{
    "vision": {
      "objects": [
        {
          "label": "person",
          "confidence": 0.91,
          "bbox": [120, 80, 540, 700]
        }
      ],
      "latency_ms": 182.4,
      "fps": 5.48,
      "model": "yolo11n-onnx",
      "mode": "real_camera_onnx_inference",
      "snapshot_path": null,
      "frame_metadata": {}
    },
    "sensors": {
      "temperature_c": 26.0,
      "humidity_percent": 36.5,
      "pressure_hpa": 1015.8,
      "air_quality_raw": 14,
      "air_quality_level": "normal"
    },
    "audio": {
      "event": "normal",
      "confidence": 1.0,
      "volume_db": 0.0,
      "source_mode": "mock",
      "hardware_ready": false
    }
  }' \
  | python -m json.tool
```

The response is an `AgentDecision` containing:

- `final_risk`
- `reason`
- `recommended_action`
- `modality_summary`
- `timestamp`

Possible final risk values are:

- `LOW`
- `MEDIUM`
- `HIGH`
- `UNKNOWN`

## Core schemas

### ServiceStatus

| Field | Type | Required | Notes |
|---|---|---:|---|
| `service` | string | yes | Service identifier |
| `status` | string | no | Defaults to `online` |
| `timestamp` | date-time | no | Generated in UTC |
| `details` | object | no | Service-specific metadata |

### SensorReading

| Field | Type | Required |
|---|---|---:|
| `temperature_c` | number | yes |
| `humidity_percent` | number | yes |
| `pressure_hpa` | number | yes |
| `air_quality_raw` | integer | yes |
| `air_quality_level` | string | yes |
| `timestamp` | date-time | no |

### AudioResult

| Field | Type | Required | Default |
|---|---|---:|---|
| `event` | string | yes | none |
| `confidence` | number from `0` to `1` | yes | none |
| `volume_db` | number | yes | none |
| `source_mode` | string | no | `unknown` |
| `hardware_ready` | boolean | no | `false` |
| `timestamp` | date-time | no | generated |

### Detection

| Field | Type | Required | Notes |
|---|---|---:|---|
| `label` | string | yes | Detected class |
| `confidence` | number from `0` to `1` | yes | Model confidence |
| `bbox` | array of integers | no | Bounding box coordinates |

### VisionResult

| Field | Type | Required | Default |
|---|---|---:|---|
| `objects` | array of `Detection` | no | empty array |
| `latency_ms` | number | no | `0.0` |
| `fps` | number | no | `0.0` |
| `model` | string | no | schema default is `mock-yolo-edge` |
| `mode` | string | no | schema default is `mock` |
| `snapshot_path` | string or null | no | `null` |
| `frame_metadata` | object | no | empty object |
| `timestamp` | date-time | no | generated |

Runtime services override the schema defaults with the active YOLO11n ONNX model and current operating mode.

### AgentInput

| Field | Type | Required |
|---|---|---:|
| `vision` | `VisionResult` | yes |
| `sensors` | `SensorReading` | yes |
| `audio` | `AudioResult` | yes |

### AgentDecision

| Field | Type | Required |
|---|---|---:|
| `final_risk` | `LOW`, `MEDIUM`, `HIGH`, or `UNKNOWN` | yes |
| `reason` | string | yes |
| `recommended_action` | string | yes |
| `modality_summary` | object | yes |
| `timestamp` | date-time | no |

## OpenAPI verification

Retrieve and validate a live OpenAPI document with:

```bash
curl --fail --silent \
  'http://127.0.0.1:8000/openapi.json' \
  -o /tmp/edgesense-gateway-openapi.json

python -m json.tool \
  /tmp/edgesense-gateway-openapi.json \
  >/dev/null
```

The API Gateway uses generic dictionary responses for several aggregation endpoints, so some Gateway response schemas are intentionally not expanded in generated OpenAPI. The individual typed services expose their Pydantic schemas directly.

## Operational notes

- Prefer the API Gateway for application-level access.
- Use individual service ports for diagnostics and development.
- Keep the systemd stack active when using the production deployment.
- Do not start the manual scripts at the same time as systemd because the ports will conflict.
- The API is currently HTTP-only and unauthenticated.
- Do not expose these ports directly to an untrusted network.
