#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FAILURES=0

cd "$PROJECT_DIR"

pass() {
  printf 'PASS  %s\n' "$1"
}

fail() {
  printf 'FAIL  %s\n' "$1"
  FAILURES=$((FAILURES + 1))
}

echo "=== EdgeSense-MA Health Check ==="
echo

TARGET="edgesense-ma.target"

if systemctl is-enabled --quiet "$TARGET"; then
  pass "$TARGET enabled"
else
  fail "$TARGET not enabled"
fi

if systemctl is-active --quiet "$TARGET"; then
  pass "$TARGET active"
else
  fail "$TARGET inactive"
fi

echo

UNITS=(
  edgesense-camera.service
  edgesense-sensor.service
  edgesense-audio.service
  edgesense-vision.service
  edgesense-agent.service
  edgesense-api.service
  edgesense-motion-worker.service
  edgesense-dashboard.service
)

for unit in "${UNITS[@]}"; do
  if systemctl is-active --quiet "$unit"; then
    pass "$unit active"
  else
    fail "$unit inactive"
  fi
done

echo

PORTS=(8000 8001 8002 8003 8004 8005 8501)

for port in "${PORTS[@]}"; do
  if ss -ltnH | awk '{print $4}' | grep -Eq "[:.]${port}$"; then
    pass "port $port listening"
  else
    fail "port $port not listening"
  fi
done

echo

if curl --fail --silent \
  http://127.0.0.1:8000/system/status \
  > /tmp/edgesense_system_status.json
then
  pass "API gateway health"
else
  fail "API gateway health"
fi

if curl --fail --silent \
  http://127.0.0.1:8002/sensors/current \
  > /tmp/edgesense_sensor_status.json
then
  pass "sensor health"
else
  fail "sensor health"
fi

if [ "$(curl --fail --silent \
  http://127.0.0.1:8501/_stcore/health \
  2>/dev/null)" = "ok" ]
then
  pass "dashboard health"
else
  fail "dashboard health"
fi

echo

python - <<'PY'
import json
from pathlib import Path

system_payload = json.loads(
    Path("/tmp/edgesense_system_status.json").read_text()
)

sensor_payload = json.loads(
    Path("/tmp/edgesense_sensor_status.json").read_text()
)

print(
    "System services:",
    ", ".join(
        f"{name}={details['status']}"
        for name, details
        in system_payload["services"].items()
    ),
)

print(
    "Sensor:",
    f"raw={sensor_payload['air_quality_raw']}",
    f"level={sensor_payload['air_quality_level']}",
    f"temperature={sensor_payload['temperature_c']}C",
    f"humidity={sensor_payload['humidity_percent']}%",
)
PY

WORKER_STATUS="data/runtime/motion_vision_worker_status.json"

if [ -f "$WORKER_STATUS" ]; then
  WORKER_STATE=$(python -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["state"])' \
    "$WORKER_STATUS")

  PIR_AVAILABLE=$(python -c \
    'import json,sys; print(str(json.load(open(sys.argv[1]))["pir_available"]).lower())' \
    "$WORKER_STATUS")

  if [ "$WORKER_STATE" = "healthy" ]; then
    pass "motion worker healthy"
  else
    fail "motion worker state=$WORKER_STATE"
  fi

  if [ "$PIR_AVAILABLE" = "true" ]; then
    pass "PIR available"
  else
    fail "PIR unavailable"
  fi
else
  fail "motion worker status file missing"
fi

echo

FAILED_UNITS=$(systemctl --failed \
  --no-legend \
  --plain \
  | grep -i edgesense \
  || true)

if [ -z "$FAILED_UNITS" ]; then
  pass "no failed EdgeSense units"
else
  fail "failed EdgeSense units detected"
  printf '%s\n' "$FAILED_UNITS"
fi

echo

if [ -z "$(git status --short)" ]; then
  pass "Git repository clean"
else
  echo "WARN  Git repository has uncommitted changes"
  git status --short
fi

echo
echo "=== Result ==="

if [ "$FAILURES" -eq 0 ]; then
  echo "HEALTHY: all EdgeSense-MA checks passed"
  exit 0
fi

echo "UNHEALTHY: $FAILURES check(s) failed"
exit 1
