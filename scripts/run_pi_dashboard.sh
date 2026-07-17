#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${EDGESENSE_VENV_DIR:-$HOME/edgesense-pi-venv}"

cd "$PROJECT_DIR"
source "$VENV_DIR/bin/activate"

export PYTHONPATH=.
export API_BASE=http://127.0.0.1:8000

echo "Starting EdgeSense-MA Streamlit dashboard..."
echo "Dashboard URL on Raspberry Pi:"
echo "  http://127.0.0.1:8501"
echo
echo "For Mac SSH tunnel:"
echo "  ssh -N -L 8502:127.0.0.1:8501 ${USER}@<RASPBERRY_PI_IP>"
echo "Then open on Mac:"
echo "  http://127.0.0.1:8502"
echo

python -m streamlit run dashboard/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
