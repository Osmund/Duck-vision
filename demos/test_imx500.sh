#!/bin/bash
# Test IMX500 object detection med system Python
# (picamera2 er kun tilgjengelig som system package)

cd /home/admog/Code/Duck-Vision

echo "🦆 Testing IMX500 Object Detection"
echo "===================================="
echo ""
echo "Note: Bruker system Python (picamera2 er system-only)"
echo ""

# Kjør test med system Python
/usr/bin/python3 imx500_object_detection.py
