#!/usr/bin/env bash
# Creates .venv and installs dependencies from requirements.txt.
# Run once after cloning onto a new machine: ./setup.sh
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
echo "Done. Activate with: source .venv/bin/activate"
