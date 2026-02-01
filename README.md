# Duck-Vision 🦆⚡

Ultra-low latency AI vision system for Raspberry Pi 5 with Sony IMX500 AI Camera

## 🎯 Overview

Duck-Vision leverages the **IMX500 AI Camera's on-chip neural network processor** to achieve:
- **0.6ms object detection** (417x faster than CPU-based YOLOv8!)
- **10-30ms face recognition** (hybrid: IMX500 detection + CPU matching)
- Real-time MQTT communication with AI assistants
- Norwegian language support for object names

## 📁 Project Structure

```
Duck-Vision/
├── src/                          # Source code
│   ├── duck_vision.py           # Main orchestrator
│   ├── imx500_object_detection.py
│   ├── imx500_face_recognition.py
│   ├── mqtt_client.py
│   ├── config.py
│   └── duck_vision_integration.py
├── docs/                         # Documentation
│   ├── README.md                # Detailed documentation
│   ├── INTEGRATION_GUIDE.md     # Pi 4 integration guide
│   ├── ARKITEKTUR_ANBEFALINGER.md
│   ├── IMX500_OPTIMIZATION.md
│   ├── INSTALLATION_STATUS.md
│   └── RESULTS.md
├── demos/                        # Demo & test scripts
│   ├── demo_imx500.py           # Live object detection
│   ├── demo_face_detection.py   # Person detection
│   └── test_*.py                # Test scripts
├── data/                         # Data storage
│   ├── known_faces/             # Face encodings
│   └── logs/                    # Application logs
├── .env                         # Configuration
├── requirements.txt             # Python dependencies
├── duck-vision.service          # Systemd service file
├── install_service.sh           # Service installer
└── start_duck_vision.sh         # Manual start script
```

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi 5 (8GB recommended)
- Raspberry Pi AI Camera (Sony IMX500)
- Raspberry Pi OS Bookworm (64-bit)

### Installation

1. **Clone repository:**
```bash
cd ~/Code
git clone <repository-url> Duck-Vision
cd Duck-Vision
```

2. **Install IMX500 software stack:**
```bash
sudo apt update
sudo apt install -y imx500-all python3-picamera2
```

3. **Install Python dependencies:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or for system Python:
```bash
sudo apt-get install -y python3-pip
python3 -m pip install --user --break-system-packages face_recognition python-dotenv paho-mqtt
```

4. **Configure:**
```bash
cp .env.example .env
nano .env  # Edit MQTT broker settings
```

5. **Test installation:**
```bash
python3 demos/demo_imx500.py
```

## 🔧 Running as a Service

### Install Service:
```bash
./install_service.sh
```

### Service Commands:
```bash
# Start
sudo systemctl start duck-vision

# Stop
sudo systemctl stop duck-vision

# Status
sudo systemctl status duck-vision

# View logs
sudo journalctl -u duck-vision -f

# Enable autostart on boot
sudo systemctl enable duck-vision

# Disable autostart
sudo systemctl disable duck-vision
```

## 📊 Performance

| Metric | CPU (YOLOv8) | IMX500 | Improvement |
|--------|--------------|--------|-------------|
| Object Detection | 250ms | 0.6ms | **417x faster** ⚡ |
| Face Detection | 150ms | 10-30ms | **5-15x faster** |
| CPU Usage | High | Minimal | AI runs on camera chip |

## 🔌 MQTT Integration

Duck-Vision communicates via MQTT with AI assistants like Anda/Samantha.

**Topics:**
- `duck/vision/face` - Face detection events
- `duck/vision/object` - Object detection results
- `duck/samantha/commands` - Commands from AI assistant

See [INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) for complete integration instructions.

## 📚 Documentation

- [INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) - Complete integration with Anda
- [ARKITEKTUR_ANBEFALINGER.md](docs/ARKITEKTUR_ANBEFALINGER.md) - Architecture decisions
- [IMX500_OPTIMIZATION.md](docs/IMX500_OPTIMIZATION.md) - Technical optimization details
- [RESULTS.md](docs/RESULTS.md) - Performance benchmarks
- [INSTALLATION_STATUS.md](docs/INSTALLATION_STATUS.md) - Installation checklist

## 🧪 Testing

```bash
# Test IMX500 basic functionality
python3 demos/test_imx500_simple.py

# Live object detection demo
python3 demos/demo_imx500.py

# Person detection demo
python3 demos/demo_face_detection.py

# Test face recognition
python3 demos/test_face_recognition.py
```

## 🛠️ Development

### Manual Start (for development):
```bash
./start_duck_vision.sh
```

### Project Configuration

Edit `.env` file:
```ini
MQTT_BROKER=oDuckberry-2.local
MQTT_PORT=1883
FACE_DETECTION_INTERVAL=5
FACE_CONFIDENCE_THRESHOLD=0.6
OBJECT_CONFIDENCE_THRESHOLD=0.5
```

### Adding New Features

1. Add code to `src/`
2. Update imports in `src/duck_vision.py`
3. Test with demos
4. Restart service: `sudo systemctl restart duck-vision`

## 🤝 Integration with Anda

See [INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) for step-by-step instructions on:
- Installing MQTT broker on Pi 4
- Creating DuckVisionService
- Adding AI tools for vision capabilities
- Testing complete workflows

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- Sony IMX500 AI Camera SDK
- Raspberry Pi Foundation
- picamera2 library
- face_recognition library

---

**Status:** Production Ready ✅  
**Last Updated:** January 31, 2026  
**Hardware:** Raspberry Pi 5 + Sony IMX500 AI Camera
