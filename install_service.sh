#!/bin/bash
# Install Duck-Vision as systemd service

set -e

echo "🦆 Installing Duck-Vision Service"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run without sudo"
    echo "Usage: ./install_service.sh"
    exit 1
fi

SERVICE_FILE="duck-vision.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_FILE"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service file not found: $SERVICE_FILE"
    exit 1
fi

# Copy service file
echo "📋 Copying service file..."
sudo cp "$SERVICE_FILE" "$SERVICE_PATH"
sudo chmod 644 "$SERVICE_PATH"

# Reload systemd
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable service
echo "✅ Enabling service..."
sudo systemctl enable duck-vision.service

# Install Duck-Singing service
SINGING_FILE="duck-singing.service"
SINGING_PATH="/etc/systemd/system/$SINGING_FILE"
if [ -f "$SINGING_FILE" ]; then
    echo ""
    echo "🎵 Installing Duck-Singing Service..."
    sudo cp "$SINGING_FILE" "$SINGING_PATH"
    sudo chmod 644 "$SINGING_PATH"
    sudo systemctl daemon-reload
    sudo systemctl enable duck-singing.service
    echo "✅ Duck-Singing service enabled"
fi

echo ""
echo "✅ Duck-Vision service installed successfully!"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start duck-vision duck-singing"
echo "  Stop:    sudo systemctl stop duck-vision duck-singing"
echo "  Status:  sudo systemctl status duck-vision duck-singing"
echo "  Logs:    sudo journalctl -u duck-vision -u duck-singing -f"
echo "  Disable: sudo systemctl disable duck-vision duck-singing"
echo ""
echo "Service will start automatically on boot"
