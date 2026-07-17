#!/usr/bin/env bash
set -e

PROJECT_DIR="$HOME/edgesense-ma"
VENV_DIR="$HOME/edgesense-pi-venv"

cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

echo "Starting EdgeSense-MA services on Raspberry Pi..."
echo "Project path: $(pwd)"
echo "Python: $(which python)"

export PYTHONPATH=.
export CAMERA_MODE=real
export SENSOR_MODE=real
export MQ135_BASELINE_RAW=14
export MQ135_WARNING_THRESHOLD=25
export MQ135_CRITICAL_THRESHOLD=45
export MQ135_WARNING_RATIO=1.8
export MQ135_CRITICAL_RATIO=3.0
export MQ135_WARNING_CLEAR_RATIO=1.55
export MQ135_CRITICAL_CLEAR_RATIO=2.5
export MQ135_WINDOW_SIZE=5
export MQ135_CONFIRMATION_SAMPLES=3
export VISION_WORKER_ENABLED=true
export VISION_WORKER_INTERVAL_SECONDS=10
export VISION_WORKER_START_DELAY_SECONDS=3
export MOTION_VISION_WORKER_ENABLED=true
export MOTION_CAMERA_FRAME_WIDTH=1280
export MOTION_CAMERA_FRAME_HEIGHT=720
export MOTION_CAMERA_FPS=10
export MOTION_ANALYSIS_WIDTH=320
export MOTION_ANALYSIS_HEIGHT=180
export MOTION_PIXEL_DIFFERENCE_THRESHOLD=25
export MOTION_PERCENT_THRESHOLD=1.0
export MOTION_CONSECUTIVE_FRAMES=2
export MOTION_COOLDOWN_SECONDS=5
export MOTION_PERIODIC_SCAN_SECONDS=30
export MOTION_PIR_ENABLED=true
export MOTION_PIR_GPIO=23
export MOTION_PRIMARY_CAMERA_INDEX=0
export MOTION_SECONDARY_CAMERA_INDEX=1
export MOTION_CAMERA_WARMUP_SECONDS=1.0
export MOTION_CAPTURE_FRAME_COUNT=3
export MOTION_CAPTURE_INTERFRAME_SECONDS=0.08
export MOTION_PIR_POLL_SECONDS=0.05
export MOTION_PIR_CAPTURE_COOLDOWN_SECONDS=10
export USE_BACKGROUND_VISION_CACHE=true
export VISION_WORKER_STATUS_PATH="data/runtime/motion_vision_worker_status.json"
export EDGESENSE_EVENTS_DIR="data/events"
export EDGESENSE_MAX_EVENTS=500
export EDGESENSE_EVENT_RETENTION_DAYS=30
export YOLO_HIGH_PRIORITY_MIN_CONFIDENCE=0.35
export YOLO_CONTEXT_MIN_CONFIDENCE=0.45
export VISION_BLUR_THRESHOLD=4.7
export VISION_DARK_THRESHOLD=40.0
export VISION_BRIGHT_THRESHOLD=220.0

mkdir -p data/logs data/runtime

echo "Stopping old services on ports 8000-8005 if they exist..."
for port in 8000 8001 8002 8003 8004 8005; do
  pid=$(lsof -ti tcp:$port || true)
  if [ -n "$pid" ]; then
    echo "Killing process on port $port: $pid"
    kill -9 $pid || true
  fi
done

echo "Starting camera service on port 8001..."
python -m uvicorn services.camera_service.app.main:app --host 0.0.0.0 --port 8001 > data/logs/camera_service.log 2>&1 &

echo "Starting sensor service on port 8002..."
python -m uvicorn services.sensor_service.app.main:app --host 0.0.0.0 --port 8002 > data/logs/sensor_service.log 2>&1 &

echo "Starting audio service on port 8003..."
python -m uvicorn services.audio_service.app.main:app --host 0.0.0.0 --port 8003 > data/logs/audio_service.log 2>&1 &

echo "Starting vision service on port 8004..."
python -m uvicorn services.vision_inference_service.app.main:app --host 0.0.0.0 --port 8004 > data/logs/vision_service.log 2>&1 &

echo "Starting agent service on port 8005..."
python -m uvicorn services.agent_service.app.main:app --host 0.0.0.0 --port 8005 > data/logs/agent_service.log 2>&1 &

echo "Starting API gateway on port 8000..."
python -m uvicorn services.api_gateway.app.main:app --host 0.0.0.0 --port 8000 > data/logs/api_gateway.log 2>&1 &

echo
echo "Services are starting..."
sleep 6

echo
echo "Checking open ports:"
for port in 8000 8001 8002 8003 8004 8005; do
  if lsof -ti tcp:$port > /dev/null; then
    echo "Port $port: running"
  else
    echo "Port $port: not running"
  fi
done

echo
echo "Checking system status:"
curl -s http://127.0.0.1:8000/system/status || true

echo
echo "Starting motion-triggered vision worker..."

MOTION_WORKER_PID_FILE="data/runtime/motion_vision_worker.pid"

if [ -f "$MOTION_WORKER_PID_FILE" ]; then
  old_worker_pid=$(cat "$MOTION_WORKER_PID_FILE" || true)

  if [ -n "$old_worker_pid" ] && kill -0 "$old_worker_pid" 2>/dev/null; then
    echo "Stopping old motion worker: $old_worker_pid"
    kill "$old_worker_pid" || true
    sleep 1
  fi

  rm -f "$MOTION_WORKER_PID_FILE"
fi

if [ "$MOTION_VISION_WORKER_ENABLED" = "true" ]; then
  /usr/bin/python3 scripts/motion_vision_worker.py     > data/logs/motion_vision_worker.log 2>&1 &

  worker_pid=$!
  echo "$worker_pid" > "$MOTION_WORKER_PID_FILE"
  echo "Motion vision worker started with PID: $worker_pid"
else
  echo "Motion vision worker is disabled."
fi

echo
echo "Done."
echo "Logs are saved in data/logs/"
echo "Stop services with:"
echo "  ./scripts/stop_pi_services.sh"
