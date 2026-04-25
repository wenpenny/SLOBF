#!/bin/bash
# Run all experiments for SLOBF

THREADS=${1:-4}

echo "Running full SLOBF experimental suite with $THREADS threads..."

# 1. RQ1
echo "Running RQ1..."
python3 -m slobf.cli rq1 --threads $THREADS

# 2. RQ2
echo "Running RQ2..."
python3 -m slobf.cli rq2 --threads $THREADS

# 3. RQ3
echo "Running RQ3..."
python3 -m slobf.cli rq3 --threads $THREADS

# 4. Final Cleanup and Paper-Ready generation
echo "Generating paper-ready artifacts..."
python3 -m slobf.cli sanity-check --results results/

echo "All experiments complete. Results are in the results/ directory."
