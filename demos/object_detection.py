#!/usr/bin/env python3
"""
Duck-Vision Object Detection
Håndterer objektgjenkjenning med YOLOv8
"""

from typing import List, Tuple
import numpy as np
from ultralytics import YOLO
from config import OBJECT_CONFIG


class ObjectDetector:
    """Objektgjenkjenning med YOLOv8"""
    
    def __init__(self):
        self.model = None
        self.confidence_threshold = OBJECT_CONFIG["confidence_threshold"]
        self.iou_threshold = OBJECT_CONFIG["iou_threshold"]
        
        # YOLO klasser på norsk
        self.class_names_no = {
            "person": "person",
            "bicycle": "sykkel",
            "car": "bil",
            "motorcycle": "motorsykkel",
            "airplane": "fly",
            "bus": "buss",
            "train": "tog",
            "truck": "lastebil",
            "boat": "båt",
            "traffic light": "trafikklys",
            "fire hydrant": "brannhydrant",
            "stop sign": "stoppskilt",
            "parking meter": "parkeringsmåler",
            "bench": "benk",
            "bird": "fugl",
            "cat": "katt",
            "dog": "hund",
            "horse": "hest",
            "sheep": "sau",
            "cow": "ku",
            "elephant": "elefant",
            "bear": "bjørn",
            "zebra": "sebra",
            "giraffe": "giraff",
            "backpack": "ryggsekk",
            "umbrella": "paraply",
            "handbag": "håndveske",
            "tie": "slips",
            "suitcase": "koffert",
            "frisbee": "frisbee",
            "skis": "ski",
            "snowboard": "snowboard",
            "sports ball": "sportsball",
            "kite": "drage",
            "baseball bat": "baseballkølle",
            "baseball glove": "baseballhanske",
            "skateboard": "skateboard",
            "surfboard": "surfebrett",
            "tennis racket": "tennisracket",
            "bottle": "flaske",
            "wine glass": "vinglass",
            "cup": "kopp",
            "fork": "gaffel",
            "knife": "kniv",
            "spoon": "skje",
            "bowl": "bolle",
            "banana": "banan",
            "apple": "eple",
            "sandwich": "sandwich",
            "orange": "appelsin",
            "broccoli": "brokkoli",
            "carrot": "gulrot",
            "hot dog": "pølse",
            "pizza": "pizza",
            "donut": "donut",
            "cake": "kake",
            "chair": "stol",
            "couch": "sofa",
            "potted plant": "potteplante",
            "bed": "seng",
            "dining table": "spisebord",
            "toilet": "toalett",
            "tv": "tv",
            "laptop": "laptop",
            "mouse": "mus",
            "remote": "fjernkontroll",
            "keyboard": "tastatur",
            "cell phone": "mobiltelefon",
            "microwave": "mikrobølgeovn",
            "oven": "ovn",
            "toaster": "brødrister",
            "sink": "vask",
            "refrigerator": "kjøleskap",
            "book": "bok",
            "clock": "klokke",
            "vase": "vase",
            "scissors": "saks",
            "teddy bear": "teddybjørn",
            "hair drier": "hårføner",
            "toothbrush": "tannbørste",
        }
    
    def load_model(self) -> bool:
        """Last inn YOLO-modell"""
        try:
            print("Laster YOLOv8 modell...")
            
            # Last ned modell hvis den ikke finnes
            if not OBJECT_CONFIG["model_path"].exists():
                print("  Laster ned YOLOv8n modell (første gang)...")
                self.model = YOLO("yolov8n.pt")
                # Flytt til models dir
                import shutil
                shutil.move("yolov8n.pt", OBJECT_CONFIG["model_path"])
            else:
                self.model = YOLO(str(OBJECT_CONFIG["model_path"]))
            
            print(f"✓ YOLOv8 modell lastet: {OBJECT_CONFIG['model_path']}")
            return True
            
        except Exception as e:
            print(f"❌ Kunne ikke laste modell: {e}")
            return False
    
    def detect_objects(self, image: np.ndarray) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        Detekter objekter i bilde
        
        Args:
            image: Bilde som numpy array (RGB)
        
        Returns:
            Liste med (objekt_navn_norsk, confidence, (x1, y1, x2, y2))
        """
        if self.model is None:
            raise RuntimeError("Modell er ikke lastet. Kall load_model() først.")
        
        # Kjør deteksjon
        results = self.model(
            image, 
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            verbose=False
        )
        
        detections = []
        
        # Parse resultater
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Hent bounding box koordinater
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
                # Hent klasse og confidence
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Hent klassenavn
                class_name = result.names[cls]
                
                # Oversett til norsk hvis mulig
                class_name_no = self.class_names_no.get(class_name, class_name)
                
                detections.append((
                    class_name_no,
                    conf,
                    (int(x1), int(y1), int(x2), int(y2))
                ))
        
        return detections
    
    def get_most_prominent_object(self, detections: List[Tuple[str, float, Tuple[int, int, int, int]]]) -> Tuple[str, float]:
        """
        Finn mest fremtredende objekt (høyest confidence)
        
        Returns:
            (objekt_navn, confidence) eller (None, 0.0)
        """
        if not detections:
            return None, 0.0
        
        # Sorter etter confidence
        sorted_detections = sorted(detections, key=lambda x: x[1], reverse=True)
        
        best = sorted_detections[0]
        return best[0], best[1]


# Test funksjon
if __name__ == "__main__":
    print("Testing Duck-Vision Object Detection...")
    
    detector = ObjectDetector()
    
    if detector.load_model():
        print("\n✓ Object detector initialisert")
        print(f"  Confidence threshold: {detector.confidence_threshold}")
        print(f"  Støttede objekter: {len(detector.class_names_no)}")
    else:
        print("\n❌ Kunne ikke initialisere object detector")
