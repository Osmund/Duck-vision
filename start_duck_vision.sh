#!/bin/bash
# Start Duck-Vision med venv Python (har alle packages vi trenger)

cd /home/admog/Code/Duck-Vision

echo "🦆 Starting Duck-Vision System..."
echo "=================================="
echo ""

# Aktiver venv og kjør main
source .venv/bin/activate
python3 src/duck_vision.py
