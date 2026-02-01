Duck-Vision Project Structure
=============================

Duck-Vision/
├── README.md                       # Main documentation & overview
├── QUICKSTART.md                   # Quick reference for daily use
├── .env                            # Configuration (MQTT broker, etc)
├── .env.example                    # Example configuration
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
│
├── duck-vision.service             # Systemd service definition
├── install_service.sh              # Service installation script (executable)
├── start_duck_vision.sh            # Manual start script (executable)
│
├── src/                            # SOURCE CODE
│   ├── duck_vision.py             # Main orchestrator (entry point)
│   ├── config.py                  # Configuration loader
│   ├── mqtt_client.py             # MQTT communication
│   ├── imx500_object_detection.py # Object detection (IMX500)
│   ├── imx500_face_recognition.py # Face recognition (IMX500 + CPU)
│   └── duck_vision_integration.py # Pi 4 integration handler
│
├── docs/                           # DOCUMENTATION
│   ├── README.md                  # Detailed documentation
│   ├── QUICKSTART.md              # Quick reference
│   ├── INTEGRATION_GUIDE.md       # Complete Pi 4 integration guide
│   ├── ARKITEKTUR_ANBEFALINGER.md # Architecture decisions & recommendations
│   ├── INSTALLATION_STATUS.md     # Installation checklist & status
│   ├── IMX500_OPTIMIZATION.md     # Technical optimization details
│   ├── RESULTS.md                 # Performance benchmarks
│   ├── CLEANUP_STATUS.md          # Project reorganization details
│   └── MQTT_SETUP.md              # MQTT setup instructions
│
├── demos/                          # DEMOS & TESTS
│   ├── demo_imx500.py             # Live object detection demo ✅
│   ├── demo_face_detection.py     # Person detection demo ✅
│   ├── test_imx500_simple.py      # Basic IMX500 test ✅
│   ├── test_face_recognition.py   # Face recognition test
│   ├── benchmark_imx500.py        # Performance benchmark
│   ├── test_imx500.sh             # Shell test script
│   │
│   └── (legacy modules for reference:)
│       ├── camera.py               # Old camera wrapper
│       ├── object_detection.py     # Old CPU-based detection
│       ├── face_recognition_module.py # Old face recognition
│       └── samantha_integration_example.py
│
├── data/                           # DATA STORAGE
│   ├── known_faces/               # Face encodings database
│   │   └── {person_name}/
│   │       ├── encodings.pkl      # Face encoding vectors
│   │       └── metadata.json      # Metadata (confidence, date, etc)
│   └── logs/                      # Application logs
│       └── duck_vision.log
│
├── models/                         # AI MODELS
│   └── (IMX500 models stored in /usr/share/imx500-models/)
│
├── tests/                          # UNIT TESTS (empty, for future)
│
└── .venv/                          # Python virtual environment
    └── (all Python packages installed here)

Key Features:
=============
✅ IMX500 AI chip: 0.6ms object detection (417x faster than CPU!)
✅ Face recognition: Hybrid approach (IMX500 + CPU matching)
✅ MQTT integration: Real-time communication with AI assistants
✅ Norwegian language: Object names in Norwegian
✅ Systemd service: Auto-start on boot, restart on crash
✅ Production ready: Logging, error handling, configuration

Hardware:
=========
- Raspberry Pi 5 (8GB)
- Sony IMX500 AI Camera
- Raspberry Pi OS Bookworm 64-bit

Installation Status:
====================
✅ Pi 5: Fully installed and tested
✅ IMX500 SDK: Installed (23 pre-trained models)
✅ Python dependencies: Installed (face_recognition, dlib, etc)
✅ Service files: Created (ready to install with ./install_service.sh)
⏳ Service: Not yet installed (run ./install_service.sh)
⏳ Pi 4 integration: Pending (see docs/INTEGRATION_GUIDE.md)

Next Steps:
===========
1. Install service: ./install_service.sh
2. Start service: sudo systemctl start duck-vision
3. View logs: sudo journalctl -u duck-vision -f
4. Integrate with Pi 4 (see docs/INTEGRATION_GUIDE.md)

