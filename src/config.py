#!/usr/bin/env python3
"""
Duck-Vision Configuration
Laster konfigurasjon fra .env fil
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Last .env fil fra project root
load_dotenv(PROJECT_ROOT / '.env')

print(f"✓ Konfigurasjon lastet fra {PROJECT_ROOT}")

# Base paths (all relative to project root)
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
KNOWN_FACES_DIR = DATA_DIR / "known_faces"
LOGS_DIR = DATA_DIR / "logs"

# Opprett mapper hvis de ikke finnes
DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
KNOWN_FACES_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# MQTT Configuration
MQTT_CONFIG = {
    "broker": os.getenv("MQTT_BROKER", "localhost"),
    "port": int(os.getenv("MQTT_PORT", "1883")),
    "client_id": os.getenv("MQTT_CLIENT_ID", "duck-vision"),
    "username": os.getenv("MQTT_USERNAME", ""),
    "password": os.getenv("MQTT_PASSWORD", ""),
}

# MQTT Topics
TOPICS = {
    "vision_to_samantha": os.getenv("MQTT_TOPIC_VISION_TO_SAMANTHA", "duck/vision/events"),
    "samantha_to_vision": os.getenv("MQTT_TOPIC_SAMANTHA_TO_VISION", "duck/samantha/commands"),
    "face_detected": os.getenv("MQTT_TOPIC_FACE_DETECTED", "duck/vision/face"),
    "object_detected": os.getenv("MQTT_TOPIC_OBJECT_DETECTED", "duck/vision/object"),
}

# Camera Settings
CAMERA_CONFIG = {
    "width": int(os.getenv("CAMERA_WIDTH", "1280")),
    "height": int(os.getenv("CAMERA_HEIGHT", "720")),
    "fps": int(os.getenv("CAMERA_FPS", "30")),
}

# Face Recognition Settings
FACE_CONFIG = {
    "data_dir": KNOWN_FACES_DIR,
    "known_faces_file": DATA_DIR / "known_faces.pkl",
    "tolerance": float(os.getenv("FACE_RECOGNITION_TOLERANCE", "0.6")),
    "detection_interval": float(os.getenv("FACE_DETECTION_INTERVAL", "1.0")),
    "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.5")),
    "encodings_file": DATA_DIR / "face_encodings.pkl",
}

# Object Detection Settings
OBJECT_CONFIG = {
    "model_path": MODELS_DIR / "yolov8n.pt",
    "confidence_threshold": 0.35,  # 35% minimum - balanced threshold
    "iou_threshold": 0.45,
    # IMX500: NanoDet Plus (416x416) - best balance of speed and accuracy
    "imx500_model": "/usr/share/imx500-models/imx500_network_nanodet_plus_416x416_pp.rpk"
}

# Speaker / Voice Recognition Settings
KNOWN_VOICES_DIR = DATA_DIR / "known_voices"
KNOWN_VOICES_DIR.mkdir(exist_ok=True)

VOICE_CONFIG = {
    "enabled": os.getenv("VOICE_RECOGNITION_ENABLED", "true").lower() == "true",
    "data_dir": KNOWN_VOICES_DIR,
    # Mikrofon
    "mic_device": os.getenv("MIC_DEVICE", "plughw:0,0"),  # ALSA device
    "mic_sample_rate": 48000,  # Native rate for USB PnP Sound Device
    "target_sample_rate": 16000,  # Resemblyzer krever 16kHz
    # VAD (Voice Activity Detection)
    "vad_aggressiveness": int(os.getenv("VAD_AGGRESSIVENESS", "2")),  # 0-3, 3 = mest aggressiv
    "vad_frame_ms": 30,  # 10, 20 eller 30 ms frames for WebRTC VAD
    # Speaker matching
    "match_threshold": float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.75")),  # Cosine similarity
    # Automatisk profilbygging
    "auto_enroll": os.getenv("VOICE_AUTO_ENROLL", "true").lower() == "true",
    "min_speech_duration": float(os.getenv("MIN_SPEECH_DURATION", "10.0")),  # Sek tale for profil
    "max_collect_duration": float(os.getenv("MAX_COLLECT_DURATION", "60.0")),  # Maks ventetid
}

# MQTT Topics for voice/audio
TOPICS.update({
    "speaker_recognized": os.getenv("MQTT_TOPIC_SPEAKER_RECOGNIZED", "duck/audio/speaker"),
    "voice_profile_created": os.getenv("MQTT_TOPIC_VOICE_LEARNED", "duck/audio/voice_learned"),
    "samantha_speaking": os.getenv("MQTT_TOPIC_SAMANTHA_SPEAKING", "duck/samantha/speaking"),
    "samantha_conversation": os.getenv("MQTT_TOPIC_SAMANTHA_CONVERSATION", "duck/samantha/conversation"),
})

print(f"  - MQTT Broker: {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
print(f"  - Data dir: {DATA_DIR}")
print(f"  - Known faces: {KNOWN_FACES_DIR}")
print(f"  - Known voices: {KNOWN_VOICES_DIR}")
print(f"  - Voice recognition: {'ON' if VOICE_CONFIG['enabled'] else 'OFF'}")
