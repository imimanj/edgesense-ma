#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH=.
mkdir -p data/logs

cleanup() {
  echo ""
  echo "Stopping EdgeSense-MA services..."
  kill 0
}

trap cleanup EXIT

echo "Starting EdgeSense-MA local services..."

python -m uvicorn services.camera_service.app.main:app --host 127.0.0.1 --port 8001 > data/logs/camera.log 2>&1 &
echo "Camera Service:  http://127.0.0.1:8001/docs"

python -m uvicorn services.sensor_service.app.main:app --host 127.0.0.1 --port 8002 > data/logs/sensor.log 2>&1 &
echo "Sensor Service:  http://127.0.0.1:8002/docs"

python -m uvicorn services.audio_service.app.main:app --host 127.0.0.1 --port 8003 > data/logs/audio.log 2>&1 &
echo "Audio Service:   http://127.0.0.1:8003/docs"

python -m uvicorn services.vision_inference_service.app.main:app --host 127.0.0.1 --port 8004 > data/logs/vision.log 2>&1 &
echo "Vision Service:  http://127.0.0.1:8004/docs"

python -m uvicorn services.agent_service.app.main:app --host 127.0.0.1 --port 8005 > data/logs/agent.log 2>&1 &
echo "Agent Service:   http://127.0.0.1:8005/docs"

python -m uvicorn services.api_gateway.app.main:app --host 127.0.0.1 --port 8000 > data/logs/api_gateway.log 2>&1 &
echo "API Gateway:     http://127.0.0.1:8000/docs"

echo ""
echo "All services started."
echo "Open: http://127.0.0.1:8000/docs"
echo "Press CTRL+C to stop all services."

wait
