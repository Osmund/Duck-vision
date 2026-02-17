# Duck-Vision 🦆⚡

Ultra-low latency AI vision system for Raspberry Pi 5 with Sony IMX500 AI Camera

## 🎯 Overview

Duck-Vision leverages the **IMX500 AI Camera's on-chip neural network processor** to achieve:
- **0.6ms object detection** (417x faster than CPU-based YOLOv8!)
- **10-30ms face recognition** (hybrid: IMX500 detection + CPU matching)
- **Stemmegjenkjenning** (Resemblyzer d-vectors + WebRTC VAD)
- **Sang-tjeneste** (GPT-4o lyrics → Azure TTS → pyworld vocoder)
- Real-time MQTT communication with AI assistants
- Norwegian language support for object names

## 📁 Project Structure

```
Duck-Vision/
├── src/                          # Source code
│   ├── duck_vision.py           # Main orchestrator
│   ├── imx500_object_detection.py
│   ├── imx500_face_recognition.py
│   ├── speaker_recognition.py   # Stemmegjenkjenning (VAD + Resemblyzer)
│   ├── mqtt_client.py
│   ├── config.py
│   ├── duck_vision_integration.py
│   └── singing/                 # Sang-tjeneste
│       ├── song_service.py      # MQTT sang-pipeline
│       ├── song_generator.py    # GPT-4o lyrics + melodi
│       ├── tts_provider.py      # Azure Neural TTS
│       ├── singify.py           # pyworld vocoder
│       ├── instrumental.py      # Akkompagnement
│       └── midi_builder.py      # MIDI-generering
├── scripts/                      # Verktøy-skript
│   ├── register_face.py         # Registrer ansikt (interaktivt)
│   ├── register_voice.py        # Registrer stemme (interaktivt)
│   └── test_recognition.py      # Test ansikt + stemme
├── demos/                        # Demo & test scripts
│   ├── demo_imx500.py           # Live object detection
│   └── demo_face_detection.py   # Person detection
├── data/                         # Data storage
│   ├── known_faces/             # Ansiktsbilder + encodings
│   ├── known_voices/            # Stemmeprofiler (.pkl)
│   └── logs/                    # Application logs
├── docs/                         # Documentation
├── setup.sh                     # Full automatisk installasjon
├── .env                         # API-nøkler og konfigurasjon
├── requirements.txt             # Alle Python-avhengigheter
├── duck-vision.service          # Systemd service file
├── install_service.sh           # Service installer
└── start_duck_vision.sh         # Manual start script
```

## 🚀 Quick Start

### Prerequisites
- Raspberry Pi 5 (8GB recommended)
- Raspberry Pi AI Camera (Sony IMX500)
- Raspberry Pi OS Bookworm (64-bit)
- USB-mikrofon (for stemmegjenkjenning)

### Installation

1. **Clone repository:**
```bash
cd ~/Code
git clone https://github.com/Osmund/Duck-vision.git
cd Duck-vision
```

2. **Kjør setup (installerer alt automatisk):**
```bash
./setup.sh
```

3. **Konfigurer API-nøkler:**
```bash
nano .env
# Legg inn:
#   OPENAI_API_KEY=sk-...
#   AZURE_TTS_KEY=...
#   AZURE_TTS_REGION=westeurope
#   MQTT_BROKER=oduckberry-2.local
```

4. **Registrer ansikt og stemme:**
```bash
source .venv/bin/activate
python3 scripts/register_face.py "Navn"
python3 scripts/register_voice.py "Navn"
```

5. **Start tjenesten:**
```bash
sudo systemctl start duck-vision
```

### Manuell installasjon (hvis setup.sh ikke brukes)

Se kommentarene i `requirements.txt` for system-pakker som må installeres først.
Viktige poeng:
- `picamera2` og `libcamera` **må** installeres via `apt` (ikke pip)
- venv **må** bruke `--system-site-packages` for tilgang til libcamera
- `dlib` bygges fra kilde på ARM — versjon ≥19.24 fungerer

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
source .venv/bin/activate

# Test ansikt + stemmegjenkjenning (interaktiv)
python3 scripts/test_recognition.py

# Registrer nytt ansikt (5 bilder, ENTER mellom hver)
python3 scripts/register_face.py "Navn"

# Registrer ny stemme (3 tekster, ENTER mellom hver)
python3 scripts/register_voice.py "Navn"

# IMX500 object detection demo
python3 demos/demo_imx500.py

# Person detection demo
python3 demos/demo_face_detection.py
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
**Last Updated:** February 17, 2026  
**Hardware:** Raspberry Pi 5 + Sony IMX500 AI Camera + USB-mikrofon  
**OS:** Raspberry Pi OS Bookworm 64-bit (Debian 12)  
**Python:** 3.11
