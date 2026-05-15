#!/bin/bash
# Setup environment for SLOBF reproducibility package

set -e

echo "Setting up SLOBF environment..."

# 1. System dependencies
sudo apt-get update
sudo apt-get install -y build-essential gcc g++ python3-pip python3-venv

# 2. Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements.txt

# 3. Required directories
mkdir -p datasets/raw
mkdir -p workdir/build
mkdir -p results/rq1 results/rq2 results/rq3
mkdir -p results/figures results/tables results/reports results/paper_ready
mkdir -p logs

echo "Environment setup complete."
echo "Next: run 'bash scripts/download_datasets.sh' to download benchmarks."
