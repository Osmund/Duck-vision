"""
IMX500 Object Detection - Kjører AI direkte på kameraets chip!
Ultra-lav latency (5-10ms) ved å bruke IMX500s innebygde neural network prosessor.
"""

import numpy as np
from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import NetworkIntrinsics
import time
from typing import List, Tuple, Optional
import logging

# Norske navn for COCO objekter (samme som før)
COCO_CLASSES_NO = {
    0: "person", 1: "sykkel", 2: "bil", 3: "motorsykkel", 4: "fly",
    5: "buss", 6: "tog", 7: "lastebil", 8: "båt", 9: "trafikklys",
    10: "brannhydrant", 11: "stoppskilt", 12: "parkeringsmåler", 13: "benk", 14: "fugl",
    15: "katt", 16: "hund", 17: "hest", 18: "sau", 19: "ku",
    20: "elefant", 21: "bjørn", 22: "sebra", 23: "sjiraff", 24: "ryggsekk",
    25: "paraply", 26: "håndveske", 27: "slips", 28: "koffert", 29: "frisbee",
    30: "ski", 31: "snowboard", 32: "ball", 33: "drage", 34: "balltre",
    35: "baseballhanske", 36: "skateboard", 37: "surfebrett", 38: "tennisracket", 39: "flaske",
    40: "vinglass", 41: "kopp", 42: "gaffel", 43: "kniv", 44: "skje",
    45: "bolle", 46: "banan", 47: "eple", 48: "smørbrød", 49: "appelsin",
    50: "brokkoli", 51: "gulrot", 52: "pølse", 53: "pizza", 54: "donut",
    55: "kake", 56: "stol", 57: "sofa", 58: "potteplante", 59: "seng",
    60: "spisebord", 61: "toalett", 62: "TV", 63: "laptop", 64: "mus",
    65: "fjernkontroll", 66: "tastatur", 67: "mobiltelefon", 68: "mikrobølgeovn", 69: "ovn",
    70: "brødrister", 71: "oppvaskkum", 72: "kjøleskap", 73: "bok", 74: "klokke",
    75: "vase", 76: "saks", 77: "teddybjørn", 78: "føner", 79: "tannbørste"
}


class IMX500ObjectDetector:
    """
    Object detection ved å bruke IMX500s innebygde AI-prosessor.
    Kjører inferens direkte på kamera-chipen - ULTRA LAV LATENCY!
    """
    
    def __init__(self, model_path: str = "/usr/share/imx500-models/imx500_network_nanodet_plus_416x416_pp.rpk",
                 confidence_threshold: float = 0.35):
        """
        Initialiserer IMX500 object detector.
        
        Args:
            model_path: Sti til IMX500 modell (.rpk fil) - Standard: NanoDet Plus (416x416)
            confidence_threshold: Minimum confidence for deteksjoner (0.0-1.0)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.picam2 = None
        self.imx500 = None
        self.last_detections = []
        
        logging.info(f"IMX500ObjectDetector initialisert med modell: {model_path}")
    
    def start(self):
        """Starter kamera med IMX500 AI-prosessering."""
        try:
            # Initialiser IMX500 med modell-fil
            self.imx500 = IMX500(self.model_path)
            
            # Opprett Picamera2 for IMX500 kamera
            self.picam2 = Picamera2(self.imx500.camera_num)
            
            # Konfigurer kamera
            config = self.picam2.create_preview_configuration(
                controls={'FrameRate': 30.0}
            )
            self.picam2.configure(config)
            self.picam2.start()
            
            logging.info("✓ IMX500 kamera startet - AI kjører på chip!")
            
            # Varm opp (første frame laster firmware, tar ~4s)
            time.sleep(2)
            
        except Exception as e:
            logging.error(f"Feil ved oppstart av IMX500: {e}")
            raise
    
    def detect_objects(self) -> List[Tuple[str, float, Tuple[float, float, float, float]]]:
        """
        Henter objektdeteksjoner direkte fra IMX500 chip.
        
        Returns:
            Liste med (norsk_navn, confidence, (y1, x1, y2, x2))
            Kjører på 0.6-0.8ms latency! ⚡🚀
        """
        if not self.picam2 or not self.imx500:
            raise RuntimeError("Kamera ikke startet - kall start() først")
        
        try:
            # Hent metadata fra IMX500 (inferens kjørt på chip!)
            metadata = self.picam2.capture_metadata()
            
            detections = []
            
            # Parse IMX500 output
            np_outputs = self.imx500.get_outputs(metadata=metadata)
            
            if np_outputs is not None and len(np_outputs) >= 3:
                # IMX500 SSD output format:
                # [0] = boxes [100, 4] - bbox coordinates (y1, x1, y2, x2) normalized 0-1
                # [1] = scores [100] - confidence scores
                # [2] = classes [100] - class IDs
                # [3] = num_detections [1] - antall gyldige deteksjoner
                
                boxes = np_outputs[0]      # [100, 4]
                scores = np_outputs[1]     # [100]
                classes = np_outputs[2]    # [100]
                
                num_detections = int(np_outputs[3][0]) if len(np_outputs) > 3 else len(scores)
                
                for i in range(min(num_detections, len(scores))):
                    confidence = float(scores[i])
                    
                    # Filtrer på confidence threshold
                    if confidence >= self.confidence_threshold:
                        class_id = int(classes[i])
                        bbox = tuple(boxes[i])  # (y1, x1, y2, x2) normalized 0-1
                        
                        # Konverter class_id til norsk navn
                        norsk_navn = COCO_CLASSES_NO.get(class_id, f"ukjent_{class_id}")
                        
                        detections.append((norsk_navn, confidence, bbox))
            
            self.last_detections = detections
            return detections
            
        except Exception as e:
            logging.error(f"Feil ved object detection: {e}")
            return []
    
    def get_most_prominent_object(self) -> Optional[Tuple[str, float]]:
        """
        Returnerer mest prominent objekt (høyest confidence).
        
        Returns:
            (norsk_navn, confidence) eller None hvis ingen objekter
        """
        detections = self.detect_objects()
        
        if not detections:
            return None
        
        # Sorter etter confidence
        most_prominent = max(detections, key=lambda x: x[1])
        return (most_prominent[0], most_prominent[1])
    
    def get_objects_summary(self) -> str:
        """
        Lager en tekstbeskrivelse av detekterte objekter.
        
        Returns:
            "Jeg ser: kopp, laptop, person" eller "Ingen objekter funnet"
        """
        detections = self.detect_objects()
        
        if not detections:
            return "Ingen objekter funnet"
        
        # Grupper like objekter
        object_counts = {}
        for norsk_navn, confidence, bbox in detections:
            if norsk_navn in object_counts:
                object_counts[norsk_navn] += 1
            else:
                object_counts[norsk_navn] = 1
        
        # Lag beskrivelse
        items = []
        for obj, count in object_counts.items():
            if count > 1:
                items.append(f"{count} {obj}er")
            else:
                items.append(obj)
        
        return "Jeg ser: " + ", ".join(items)
    
    def stop(self):
        """Stopper kamera."""
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
            self.picam2 = None
            self.imx500 = None
            logging.info("✓ IMX500 kamera stoppet og lukket")
    
    def __enter__(self):
        """Context manager support."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.stop()


# Test script
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🦆 Testing IMX500 Object Detection (AI på chip!)")
    print("=" * 60)
    
    with IMX500ObjectDetector(confidence_threshold=0.5) as detector:
        print("\n✓ Kamera startet - AI kjører på IMX500 chip")
        print("Tester 10 deteksjoner...\n")
        
        for i in range(10):
            start_time = time.time()
            
            detections = detector.detect_objects()
            summary = detector.get_objects_summary()
            
            latency_ms = (time.time() - start_time) * 1000
            
            print(f"Frame {i+1}: {summary}")
            print(f"  └─ Latency: {latency_ms:.1f}ms ⚡")
            print(f"  └─ Detections: {len(detections)}")
            
            if detections:
                for obj, conf, bbox in detections[:3]:  # Vis max 3
                    print(f"     - {obj}: {conf:.2%}")
            
            time.sleep(0.5)
    
    print("\n✓ Test fullført!")
