#!/usr/bin/env python3
"""
YOLOv8 Object Detection (CPU-basert, høy nøyaktighet)
Brukes når Samantha spør direkte og kan vente 250ms
"""

import logging
from ultralytics import YOLO
from picamera2 import Picamera2
import numpy as np
from pathlib import Path
import time

# COCO klasser på norsk (samme som IMX500)
COCO_CLASSES_NO = {
    0: "person", 1: "sykkel", 2: "bil", 3: "motorsykkel", 4: "fly",
    5: "buss", 6: "tog", 7: "lastebil", 8: "båt", 9: "trafikklys",
    10: "brannhydrant", 11: "stoppskilt", 12: "parkeringsmåler", 13: "benk", 14: "fugl",
    15: "katt", 16: "hund", 17: "hest", 18: "sau", 19: "ku",
    20: "elefant", 21: "bjørn", 22: "sebra", 23: "giraff", 24: "ryggsekk",
    25: "paraply", 26: "veske", 27: "slips", 28: "koffert", 29: "frisbee",
    30: "ski", 31: "snowboard", 32: "ball", 33: "drage", 34: "baseball-kølle",
    35: "baseball-hanske", 36: "skateboard", 37: "surfebrett", 38: "tennis-racket", 39: "flaske",
    40: "vinglass", 41: "kopp", 42: "gaffel", 43: "kniv", 44: "skje",
    45: "bolle", 46: "banan", 47: "eple", 48: "smørbrød", 49: "appelsin",
    50: "brokkoli", 51: "gulrot", 52: "pølse", 53: "pizza", 54: "donut",
    55: "kake", 56: "stol", 57: "sofa", 58: "potteplante", 59: "seng",
    60: "spisebord", 61: "toalett", 62: "TV", 63: "laptop", 64: "mus",
    65: "fjernkontroll", 66: "tastatur", 67: "mobiltelefon", 68: "mikrobølgeovn", 69: "ovn",
    70: "brødrister", 71: "vask", 72: "kjøleskap", 73: "bok", 74: "klokke",
    75: "vase", 76: "saks", 77: "teddybjørn", 78: "hårføner", 79: "tannbørste"
}

class YOLOv8ObjectDetector:
    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        """
        YOLOv8 object detector (CPU-basert)
        
        Args:
            model_path: Path til YOLOv8 modell
            confidence_threshold: Minimum confidence (0.5 = 50%)
        """
        self.confidence_threshold = confidence_threshold
        self.picam2 = None
        self.model = None
        
        logging.info("🎯 Initialiserer YOLOv8 object detector...")
        
        # Last ned modell hvis den ikke finnes
        model_file = Path(model_path)
        if not model_file.exists():
            logging.info(f"📥 Laster ned {model_path}...")
        
        self.model = YOLO(model_path)
        logging.info(f"✓ YOLOv8 modell lastet: {model_path}")
    
    def start_camera(self):
        """Start kamera for YOLOv8 deteksjon"""
        if self.picam2 is not None:
            logging.warning("Kamera allerede startet")
            return
        
        logging.info("📸 Starter kamera for YOLOv8...")
        self.picam2 = Picamera2()
        
        config = self.picam2.create_still_configuration(
            main={"size": (1280, 720), "format": "RGB888"}
        )
        
        self.picam2.configure(config)
        self.picam2.start()
        
        # Vent litt for eksponering
        time.sleep(1)
        
        logging.info("✓ Kamera startet for YOLOv8")
    
    def stop_camera(self):
        """Stopp kamera"""
        if self.picam2 is not None:
            self.picam2.stop()
            self.picam2.close()
            self.picam2 = None
            logging.info("✓ Kamera stoppet")
    
    def detect_objects(self):
        """
        Detekter objekter med YOLOv8
        
        Returns:
            List[(object_name, confidence, bbox)]
        """
        if self.picam2 is None:
            self.start_camera()
        
        start_time = time.time()
        
        # Ta bilde
        image = self.picam2.capture_array("main")
        
        # Kjør YOLOv8 inferens
        results = self.model(image, verbose=False)[0]
        
        detections = []
        
        for box in results.boxes:
            confidence = float(box.conf[0])
            
            if confidence >= self.confidence_threshold:
                class_id = int(box.cls[0])
                obj_name = COCO_CLASSES_NO.get(class_id, f"ukjent_{class_id}")
                
                # Normalized bbox [x1, y1, x2, y2]
                bbox = box.xyxyn[0].cpu().numpy()
                
                detections.append((obj_name, confidence, bbox))
        
        elapsed = (time.time() - start_time) * 1000
        
        logging.info(f"🎯 YOLOv8 detekterte {len(detections)} objekter ({elapsed:.1f}ms)")
        
        # Sorter etter confidence
        detections.sort(key=lambda x: x[1], reverse=True)
        
        return detections

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("🧪 Tester YOLOv8 object detection...\n")
    
    detector = YOLOv8ObjectDetector(confidence_threshold=0.35)
    
    print("📷 Tar bilde og detekterer objekter...\n")
    detections = detector.detect_objects()
    
    print(f"📊 Fant {len(detections)} objekter:\n")
    for obj_name, conf, bbox in detections:
        marker = "✅" if conf >= 0.5 else "⚠️"
        print(f"{marker} {obj_name:20s} {conf:6.2%}")
    
    detector.stop_camera()
    print("\n✓ Test fullført")
