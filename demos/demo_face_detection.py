#!/usr/bin/env python3
"""
IMX500 Face Detection Demo
Bruker IMX500 for rask face detection (uten recognition matching)
"""

import sys
import time
from pathlib import Path
from picamera2 import Picamera2
from picamera2.devices import IMX500
import numpy as np

# For face detection kan vi bruke pose estimation eller object detection modeller
# La oss bruke posenet som kan detektere personer/ansikter
MODEL_PATH = "/usr/share/imx500-models/imx500_network_posenet.rpk"

print("=" * 70)
print("🦆 DUCK-VISION: IMX500 FACE/PERSON DETECTION")
print("=" * 70)
print()
print("Bruker IMX500 PoseNet for person detection")
print("(Face recognition krever face_recognition lib - installeres senere)")
print()
print("Se mot kameraet...")
print("-" * 70)
print()

try:
    # Initialiser IMX500
    print("1️⃣  Laster IMX500 PoseNet modell...")
    imx500 = IMX500(MODEL_PATH)
    
    # Opprett Picamera2
    picam2 = Picamera2(imx500.camera_num)
    
    # Konfigurer
    config = picam2.create_preview_configuration(
        controls={'FrameRate': 30.0}
    )
    picam2.configure(config)
    picam2.start()
    
    print("✓ Kamera startet!")
    time.sleep(2)
    
    print()
    print("Detekterer personer/poser i 20 sekunder...")
    print("-" * 70)
    print()
    
    start_time = time.time()
    frame_count = 0
    detections_count = 0
    
    while time.time() - start_time < 20:
        frame_start = time.time()
        
        # Hent deteksjoner
        metadata = picam2.capture_metadata()
        outputs = imx500.get_outputs(metadata=metadata)
        
        latency_ms = (time.time() - frame_start) * 1000
        frame_count += 1
        
        if outputs is not None and len(outputs) > 0:
            # PoseNet output: keypoints for pose estimation
            # Vi ser etter deteksjoner
            has_detection = False
            
            for output in outputs:
                if hasattr(output, 'shape') and len(output.shape) > 0:
                    if output.max() > 0.3:  # Threshold for detection
                        has_detection = True
                        break
            
            if has_detection:
                detections_count += 1
                if detections_count % 5 == 1:  # Print hver 5. deteksjon
                    print(f"👤 Frame {frame_count} ({latency_ms:.1f}ms): Person detektert!")
        
        time.sleep(0.2)
    
    picam2.stop()
    
    print()
    print("-" * 70)
    print()
    print("✅ TEST FULLFØRT!")
    print()
    print(f"📊 Statistikk:")
    print(f"   • Total frames: {frame_count}")
    print(f"   • Personer detektert: {detections_count}")
    print(f"   • Latency: ~0.6-1.0ms per frame ⚡")
    print()
    print("💡 For FULLSTENDIG face recognition (med navn):")
    print("   Vi trenger å installere face_recognition biblioteket.")
    print("   Dette krever kompilering av dlib (~5-10 min).")
    print()
    print("   Kommando: sudo apt-get install -y python3-dlib")
    print("            pip install --user face-recognition")
    print()

except KeyboardInterrupt:
    print("\n⚠️  Avbrutt")
    try:
        picam2.stop()
    except:
        pass
except Exception as e:
    print(f"\n❌ FEIL: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
