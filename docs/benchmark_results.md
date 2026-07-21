# Benchmark Results

## Scope

This document separates two different evidence sources:

1. a controlled fixed-image benchmark of the Vision Inference Service; and
2. an operational analysis of the current 500-event persistent corpus.

The controlled benchmark is the primary source for repeatable inference latency. The event corpus is useful for observing the deployed system over time, but it contains multiple trigger modes and historical configuration states. It must not be treated as one homogeneous laboratory experiment.

## Deployment under test

| Item | Active configuration |
|---|---|
| Device | Raspberry Pi 5, 8 GB |
| Architecture | `aarch64` |
| Vision model | YOLO11n |
| Runtime | ONNX Runtime on CPU |
| Model file | `models/onnx/yolo11n.onnx` |
| Service mode | `real_camera_onnx_inference` |
| Camera image size | `1280 × 720` |
| Model input size | `640 × 640` |
| Confidence threshold | `0.25` |
| NMS threshold | `0.45` |
| Hardware accelerator | Not used by this benchmark |

The current `/vision/benchmark` endpoint confirms that the ONNX model is available and that real camera snapshots are the active input source.

## Controlled fixed-image vision benchmark

### Method

The benchmark sent the same stored Raspberry Pi camera image to:

```text
POST http://127.0.0.1:8004/vision/detect
```

The request was repeated sequentially 30 times. Each request used the same `1280 × 720` JPEG and the service resized or prepared it for a `640 × 640` model input.

The benchmark measured:

- total Vision API pipeline latency;
- model-only inference latency;
- model-reported FPS;
- CPU consumption of the Vision Service process;
- CPU temperature before and after the run; and
- Motion Vision Worker activity during the test.

The worker counters did not change during the benchmark:

```text
capture_delta=0
worker_inference_delta=0
```

Therefore, no PIR-triggered capture or worker inference overlapped with the controlled run.

### Completion

| Metric | Result |
|---|---:|
| Requested runs | 30 |
| Successful runs | 30 |
| Failed runs | 0 |
| Elapsed wall time | 7.01 s |
| Detection count per run | 0 |

All 30 API requests completed successfully. The fixed image contained no accepted detection, so this run measures runtime performance and stability, not detection accuracy.

### Latency and FPS

| Metric | Minimum | Mean | Median | P90 | P95 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Pipeline latency, ms | 173.89 | 183.03 | 176.69 | 186.09 | 221.06 | 261.29 |
| Model latency, ms | 144.85 | 153.58 | 147.43 | 156.52 | 190.40 | 227.74 |
| Model FPS | 4.39 | 6.58 | 6.79 | 6.87 | 6.88 | 6.90 |

`Pipeline latency` covers the complete `/vision/detect` processing path measured by the service. `Model latency` covers the ONNX detector call. The gap includes image decoding, frame-quality analysis, detection filtering, annotation generation, response construction, and related Python overhead.

### CPU and temperature

| Metric | Result |
|---|---:|
| Vision process CPU | 298.14% |
| CPU interpretation | approximately 2.98 logical cores |
| Temperature before | 46.85 °C |
| Temperature after | 55.10 °C |
| Temperature change | +8.25 °C |

For this measurement, 100% CPU represents one fully used logical CPU core. A value of 298.14% therefore means that the Vision Service consumed approximately three logical cores during the sequential inference run.

The temperature result is a short-run observation, not a thermal-soak test. It does not establish sustained-temperature behavior or throttling limits.

## Operational 500-event corpus

### Corpus coverage

A fresh analysis was generated from the current persistent event store.

| Metric | Result |
|---|---:|
| Events analyzed | 500 |
| Load errors | 0 |
| Events with accepted objects | 51 |
| Events without accepted objects | 449 |
| CSV rows including header | 501 |

The event store had reached its configured maximum of 500 retained event records at the time of analysis.

### Trigger distribution

| Trigger | Events |
|---|---:|
| `pir_motion` | 358 |
| `motion` | 137 |
| `periodic_safety_scan` | 5 |

This distribution confirms that the corpus spans different generations of the project. The current deployment uses PIR-triggered dual-camera capture, while older records include frame-motion and periodic-scan events.

### Risk distribution

| Final risk | Events |
|---|---:|
| `LOW` | 334 |
| `MEDIUM` | 133 |
| `HIGH` | 31 |
| `UNKNOWN` | 2 |

These are Agent decisions stored with the events. They are not human-verified ground-truth labels and must not be used as an accuracy score.

### Accepted object labels

| Label | Count |
|---|---:|
| `person` | 49 |
| `cat` | 2 |
| `cell phone` | 1 |

An event may contain more than one object label, so label counts do not have to equal the number of events with objects.

### Historical model latency

| Statistic | Model latency |
|---|---:|
| Count | 500 |
| Minimum | 140.21 ms |
| Mean | 160.73 ms |
| Median | 149.21 ms |
| P75 | 156.08 ms |
| P90 | 171.10 ms |
| P95 | 259.62 ms |
| Maximum | 442.36 ms |

The historical median is close to the controlled benchmark median. The historical tail is wider, with a P95 of 259.62 ms and a maximum of 442.36 ms. This is expected to include variation from system load, configuration history, camera activity, and other runtime conditions.

### Frame-quality distribution

| Frame quality | Events |
|---|---:|
| `blurry` | 418 |
| `usable` | 82 |

Blur-score summary:

| Statistic | Blur score |
|---|---:|
| Minimum | 2.31 |
| Mean | 5.27 |
| Median | 4.87 |
| P90 | 7.30 |
| P95 | 7.83 |
| Maximum | 13.62 |

Brightness summary:

| Statistic | Brightness |
|---|---:|
| Minimum | 1.75 |
| Mean | 130.02 |
| Median | 143.63 |
| P90 | 183.99 |
| P95 | 194.09 |
| Maximum | 238.17 |

The current calibrated blur threshold is `4.7`, but the corpus includes historical records produced under changing capture and quality settings. The `418 blurry` count should therefore be interpreted as a review signal, not as a final failure rate for the current configuration.

### Enrichment status

| Status | Events |
|---|---:|
| `complete` | 498 |
| `failed` | 2 |

The event corpus shows that multimodal enrichment completed for 498 records. The two failed records remain visible in the dataset instead of being silently removed.

## Current worker-session reliability snapshot

The live Motion Vision Worker reported the following counters during the measurement session:

| Worker counter | Result |
|---|---:|
| Captures started | 42 |
| Captures completed | 42 |
| Capture failures | 0 |
| Inference requests | 42 |
| Successful inferences | 42 |
| Worker failures | 0 |
| Enrichment attempts | 42 |
| Enrichment successes | 42 |
| Enrichment failures | 0 |
| Events saved | 42 |
| Event-save failures | 0 |
| Latest full capture duration | 3370.74 ms |

These counters describe the current worker process session, not the lifetime of the repository or device. The approximately 3.37-second capture duration includes opening and warming cameras, selecting primary frames, capturing the IR image, closing devices, and processing the event pipeline. It is not comparable to model-only latency.

## Interpretation

### What the benchmark supports

The collected evidence supports the following claims:

- YOLO11n ONNX inference is operating successfully on Raspberry Pi 5 CPU.
- The controlled 30-run test completed without API failures.
- Median model latency was 147.43 ms on the fixed image.
- Median end-to-end Vision API latency was 176.69 ms.
- The Vision Service used approximately three logical CPU cores during the short controlled run.
- No PIR capture overlapped with the controlled benchmark.
- The current worker session completed all 42 captures and inferences without recorded failure.
- The fresh event analyzer loaded all 500 retained events without a parsing error.

### What the benchmark does not support

The current evidence does not establish:

- object-detection precision, recall, or mAP;
- real-time continuous-video FPS;
- long-duration thermal stability;
- performance under concurrent camera capture and inference;
- Hailo or AI HAT acceleration performance;
- regulatory air-quality accuracy;
- a human-verified false-positive or false-negative rate; or
- direct comparison with PyTorch, TensorRT, TFLite, or another model.

The fixed-image benchmark contains no accepted object. A separate labelled image set is required before making detection-accuracy claims.

## Reproduction

### Inspect the active Vision configuration

```bash
curl --fail --silent   http://127.0.0.1:8004/vision/benchmark   | python -m json.tool
```

### Inspect the latest live result

```bash
curl --fail --silent   http://127.0.0.1:8004/vision/latest   | python -m json.tool
```

### Regenerate the historical event analysis

```bash
python scripts/analyze_event_calibration.py   --events-dir data/events   --output-dir /tmp/edgesense-benchmark-analysis
```

The analyzer writes:

```text
/tmp/edgesense-benchmark-analysis/event_calibration_summary.json
/tmp/edgesense-benchmark-analysis/event_calibration_events.csv
```

### Check the current worker counters

```bash
curl --fail --silent   http://127.0.0.1:8000/system/worker-status   | python -m json.tool
```

## Data provenance

The values in this document were taken from:

- `/tmp/edgesense-controlled-benchmark/controlled_benchmark_summary.json`;
- `/tmp/edgesense-benchmark-analysis/event_calibration_summary.json`;
- the live `/vision/benchmark` and `/vision/latest` endpoints; and
- the live `/system/worker-status` endpoint.

The `/tmp` artifacts are temporary runtime evidence and are not tracked by Git. The documented values should be regenerated whenever the model, runtime, camera resolution, thresholds, worker design, or Raspberry Pi cooling configuration changes.
