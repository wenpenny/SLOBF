#!/bin/bash
# Setup environment for SLOBF reproducibility package

echo "Setting up SLOBF environment..."

# 1. System dependencies
sudo apt-get update
sudo apt-get install -y build-essential gcc g++ python3-pip python3-venv libmagic-dev

# 2. Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -r requirements.txt

# 3. Directories
mkdir -p data/raw data/normalized data/metadata
mkdir -p results/rq1 results/rq2 results/rq3 results/figures results/tables results/reports results/paper_ready

echo "Environment setup complete."
