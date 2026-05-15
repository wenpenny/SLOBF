#!/bin/bash
# Run RQ3 experiments

set -e

source venv/bin/activate

echo "Running RQ3: Impact of Compiler Optimization Levels..."
python -m slobf.cli rq3 --config configs/experiments.yaml

echo "RQ3 complete."
