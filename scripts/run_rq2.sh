#!/bin/bash
# Run RQ2 experiments

set -e

source venv/bin/activate

echo "Running RQ2: RL-guided Obfuscation Combination Search..."
python -m slobf.cli rq2 --config configs/experiments.yaml

echo "RQ2 complete."
