#!/usr/bin/env bash
set -e

PROJECT_DIR="$HOME/edgesense-ma"
WORKER_PID_FILE="$PROJECT_DIR/data/runtime/vision_worker.pid"
MOTION_WORKER_PID_FILE="$PROJECT_DIR/data/runtime/motion_vision_worker.pid"

cd "$PROJECT_DIR"

echo "Stopping EdgeSense-MA background workers..."

if [ -f "$MOTION_WORKER_PID_FILE" ]; then
  motion_worker_pid=$(cat "$MOTION_WORKER_PID_FILE" || true)

  if [ -n "$motion_worker_pid" ] && kill -0 "$motion_worker_pid" 2>/dev/null; then
    echo "Stopping motion vision worker: $motion_worker_pid"
    kill "$motion_worker_pid" || true
    sleep 1

    if kill -0 "$motion_worker_pid" 2>/dev/null; then
      echo "Force stopping motion vision worker: $motion_worker_pid"
      kill -9 "$motion_worker_pid" || true
    fi
  else
    echo "Motion vision worker is already stopped."
  fi

  rm -f "$MOTION_WORKER_PID_FILE"
else
  echo "No motion vision worker PID file found."
fi

if [ -f "$WORKER_PID_FILE" ]; then
  worker_pid=$(cat "$WORKER_PID_FILE" || true)

  if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null; then
    echo "Stopping vision worker: $worker_pid"
    kill "$worker_pid" || true
    sleep 1

    if kill -0 "$worker_pid" 2>/dev/null; then
      echo "Force stopping vision worker: $worker_pid"
      kill -9 "$worker_pid" || true
    fi
  else
    echo "Vision worker is already stopped."
  fi

  rm -f "$WORKER_PID_FILE"
else
  echo "No vision worker PID file found."
fi

echo
echo "Stopping EdgeSense-MA services on ports 8000-8005..."

for port in 8000 8001 8002 8003 8004 8005; do
  pid=$(lsof -ti tcp:$port || true)

  if [ -n "$pid" ]; then
    echo "Stopping port $port: $pid"
    kill -9 $pid || true
  else
    echo "Port $port is already free."
  fi
done

echo "Done."
