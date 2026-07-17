#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest

echo "MVP checks passed. Start services with: docker compose up --build"
