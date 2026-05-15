#!/bin/bash
# Run RQ1 experiments

set -e

source venv/bin/activate

echo "Running RQ1: Impact of Single Obfuscations..."
python -m slobf.cli rq1 --config configs/experiments.yaml

echo "RQ1 complete."
