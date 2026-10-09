#!/bin/bash
set -e

echo "Starting Audio Processor..."

# Wait for dependencies
echo "Waiting for services to be ready..."
sleep 30

# Run the processor
python main.py
