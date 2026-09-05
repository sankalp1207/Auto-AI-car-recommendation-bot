#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "[Render Build] Updating pip..."
python -m pip install --upgrade pip

echo "[Render Build] Installing lightweight production dependencies..."
pip install --no-cache-dir -r requirements-prod.txt

echo "[Render Build] Build completed successfully."
