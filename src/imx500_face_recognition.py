"""
Hybrid ansiktsgjenkjenning:
- IMX500 for rask face DETECTION (på chip, 5-10ms)
- CPU for face RECOGNITION (matching mot database)

Dette gir beste balanse mellom latency og accuracy.
"""

import numpy as np
import face_recognition
import pickle
from pathlib import Path
from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import NetworkIntrinsics
import time
from typing import List, Tuple, Optional
import logging
from PIL import Image

from config import FACE_CONFIG


class IMX500FaceRecognizer:
    """
    Hybrid face recognition:
    1. IMX500 detekterer ansikter på chip (ultra-rask)
    2. CPU gjør encoding + matching mot database
    """
    
    def __init__(self, tolerance: float = None, progress_callback=None):
        self.tolerance = tolerance or FACE_CONFIG["tolerance"]
        self.data_dir = FACE_CONFIG["data_dir"]
        self.known_faces_file = FACE_CONFIG["known_faces_file"]
        
        self.known_face_encodings = []
        self.known_face_names = []
        
        self.picam2 = None
        self.imx500 = None
        self.progress_callback = progress_callback  # Callback for learning progress
        
        # Last kjente ansikter fra disk
        self.load_known_faces()
        
        logging.info(f"IMX500FaceRecognizer initialisert med {len(self.known_face_names)} kjente personer")
    
    def start(self):
        """Starter kamera med IMX500 face detection."""
        try:
            # NOTE: Vi må sjekke om IMX500 har en face detection modell
            # Hvis ikke, må vi bruke en alternativ tilnærming
            
            # For nå: standard picamera2 for å få bildet
            # (IMX500 face detection modell må kanskje lastes separat)
            self.picam2 = Picamera2()
            
            config = self.picam2.create_still_configuration(
                main={"size": (1280, 720), "format": "RGB888"},
                buffer_count=2,
                controls={"FrameRate": 15}
            )
            
            self.picam2.configure(config)
            self.picam2.start()
            
            logging.info("✓ Kamera startet for face recognition")
            time.sleep(1)
            
        except Exception as e:
            logging.error(f"Feil ved oppstart av kamera: {e}")
            raise
    
    def detect_faces(self, image: Optional[np.ndarray] = None) -> List[Tuple[str, float, Tuple]]:
        """
        Detekterer og gjenkjenner ansikter.
        
        Args:
            image: Numpy array (RGB). Hvis None, tar nytt bilde.
        
        Returns:
            Liste med (navn, confidence, (top, right, bottom, left))
        """
        if not self.picam2:
            raise RuntimeError("Kamera ikke startet")
        
        try:
            # Ta bilde hvis ikke gitt
            if image is None:
                image = self.picam2.capture_array()
            
            start_time = time.time()
            
            # Bruk face_recognition for detection + recognition
            # (Senere kan vi optimalisere med IMX500 for detection)
            face_locations = face_recognition.face_locations(image, model="hog")
            
            if not face_locations:
                return []
            
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            results = []
            
            for face_encoding, face_location in zip(face_encodings, face_locations):
                name, confidence = self._match_face(face_encoding)
                results.append((name, confidence, face_location))
            
            latency_ms = (time.time() - start_time) * 1000
            logging.debug(f"Face detection latency: {latency_ms:.1f}ms")
            
            return results
            
        except Exception as e:
            logging.error(f"Feil ved face detection: {e}")
            return []
    
    def _match_face(self, face_encoding) -> Tuple[str, float]:
        """Matcher face encoding mot database."""
        if not self.known_face_encodings:
            return "ukjent", 0.0
        
        # Beregn distances
        distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
        
        if len(distances) == 0:
            return "ukjent", 0.0
        
        # Finn beste match
        min_distance = np.min(distances)
        
        if min_distance <= self.tolerance:
            best_match_idx = np.argmin(distances)
            name = self.known_face_names[best_match_idx]
            confidence = 1.0 - min_distance  # Konverter distance til confidence
            return name, confidence
        
        return "ukjent", 0.0
    
    def add_person(self, name: str, image: Optional[np.ndarray] = None, num_samples: int = 5) -> bool:
        """
        Lærer nytt ansikt ved å ta flere bilder for bedre nøyaktighet.
        
        Args:
            name: Navn på personen
            image: Bilde (RGB numpy array). Hvis None, tar flere nye bilder.
            num_samples: Antall bilder å ta (default: 5 for bedre accuracy)
        
        Returns:
            True hvis vellykket, False hvis feil
        """
        try:
            encodings_collected = []
            images_collected = []
            
            if image is not None:
                # Enkelt bilde gitt - prosesser det
                num_samples = 1
                images_to_process = [image]
            else:
                # Ta flere bilder
                if not self.picam2:
                    raise RuntimeError("Kamera ikke startet")
                
                logging.info(f"📸 Tar {num_samples} bilder av {name}...")
                
                # Instruksjoner for ulike posisjoner
                instructions = [
                    "se rett frem",
                    "se litt til venstre", 
                    "se litt til høyre",
                    "se litt opp",
                    "se litt ned",
                    "se rett frem igjen",
                    "se litt til venstre og opp",
                    "se litt til høyre og ned",
                    "smil litt",
                    "seriøst uttrykk"
                ]
                
                images_to_process = []
                for i in range(num_samples):
                    instruction = instructions[i] if i < len(instructions) else "se mot kameraet"
                    
                    # Send progress event til Samantha
                    if self.progress_callback:
                        self.progress_callback({
                            "step": i + 1,
                            "total": num_samples,
                            "instruction": instruction
                        })
                    
                    logging.info(f"  📸 Bilde {i+1}/{num_samples}: {instruction}")
                    
                    # Litt delay mellom bilder for å la personen bevege seg
                    if i > 0:
                        time.sleep(0.8)
                    
                    img = self.picam2.capture_array()
                    images_to_process.append(img)
                    logging.info(f"     ✓ Bilde tatt")
            
            # Prosesser hvert bilde
            for idx, img in enumerate(images_to_process):
                # Finn ansikt
                face_locations = face_recognition.face_locations(img)
                
                if not face_locations:
                    logging.warning(f"  ⚠ Bilde {idx+1}: Ingen ansikt funnet, hopper over")
                    continue
                
                if len(face_locations) > 1:
                    logging.warning(f"  ⚠ Bilde {idx+1}: Flere ansikter, bruker det første")
                
                # Encode ansikt
                face_encodings = face_recognition.face_encodings(img, [face_locations[0]])
                
                if not face_encodings:
                    logging.warning(f"  ⚠ Bilde {idx+1}: Kunne ikke encode, hopper over")
                    continue
                
                encodings_collected.append(face_encodings[0])
                images_collected.append(img)
            
            # Sjekk at vi fikk nok data
            if not encodings_collected:
                logging.error(f"❌ Ingen gyldige bilder av {name}")
                return False
            
            if len(encodings_collected) < num_samples * 0.6:  # Minst 60% suksess
                logging.warning(f"⚠ Kun {len(encodings_collected)}/{num_samples} bilder OK, men fortsetter...")
            
            # Legg alle encodings til i minne (bedre matching)
            for encoding in encodings_collected:
                self.known_face_encodings.append(encoding)
                self.known_face_names.append(name)
            
            # Lagre alle bilder til disk
            for img, encoding in zip(images_collected, encodings_collected):
                self._save_person_data(name, img, encoding)
            
            self.save_known_faces()
            
            logging.info(f"✅ Lærte {name} med {len(encodings_collected)} bilder!")
            return True
            
        except Exception as e:
            logging.error(f"❌ Feil ved læring av ansikt: {e}")
            return False
    
    def learn_person(self, name: str, image: Optional[np.ndarray] = None, num_samples: int = 5) -> bool:
        """Alias for add_person (for MQTT API compatibility)."""
        return self.add_person(name, image, num_samples)
    
    def _save_person_data(self, name: str, image: np.ndarray, face_encoding):
        """Lagrer person data (bilde + encoding) til disk."""
        person_dir = self.data_dir / name
        person_dir.mkdir(parents=True, exist_ok=True)
        
        # Lagre bilde
        img_path = person_dir / f"{int(time.time())}.jpg"
        pil_image = Image.fromarray(image)
        pil_image.save(img_path)
        
        # Lagre encoding
        encoding_path = person_dir / f"{int(time.time())}.pkl"
        with open(encoding_path, 'wb') as f:
            pickle.dump(face_encoding, f)
    
    def load_known_faces(self):
        """Laster alle kjente ansikter fra disk."""
        if not self.known_faces_file.exists():
            logging.info("Ingen kjente ansikter funnet")
            return
        
        try:
            with open(self.known_faces_file, 'rb') as f:
                data = pickle.load(f)
                self.known_face_encodings = data['encodings']
                self.known_face_names = data['names']
            
            logging.info(f"✓ Lastet {len(self.known_face_names)} kjente ansikter")
            
        except Exception as e:
            logging.error(f"Feil ved lasting av kjente ansikter: {e}")
    
    def save_known_faces(self):
        """Lagrer alle kjente ansikter til disk."""
        try:
            self.known_faces_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'encodings': self.known_face_encodings,
                'names': self.known_face_names
            }
            
            with open(self.known_faces_file, 'wb') as f:
                pickle.dump(data, f)
            
            logging.info(f"✓ Lagret {len(self.known_face_names)} kjente ansikter")
            
        except Exception as e:
            logging.error(f"Feil ved lagring av kjente ansikter: {e}")
    
    def forget_person(self, name: str) -> bool:
        """Sletter person fra database."""
        try:
            # Fjern fra minne
            indices_to_remove = [i for i, n in enumerate(self.known_face_names) if n == name]
            
            if not indices_to_remove:
                logging.warning(f"Person ikke funnet: {name}")
                return False
            
            # Fjern i omvendt rekkefølge for å unngå index issues
            for idx in sorted(indices_to_remove, reverse=True):
                del self.known_face_encodings[idx]
                del self.known_face_names[idx]
            
            # Slett fra disk
            person_dir = self.data_dir / name
            if person_dir.exists():
                import shutil
                shutil.rmtree(person_dir)
            
            self.save_known_faces()
            
            logging.info(f"✓ Slettet person: {name}")
            return True
            
        except Exception as e:
            logging.error(f"Feil ved sletting av person: {e}")
            return False
    
    def list_known_people(self) -> List[str]:
        """Returnerer liste med alle kjente personer."""
        return list(set(self.known_face_names))
    
    def stop(self):
        """Stopper kamera."""
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
            self.picam2 = None
            logging.info("✓ Kamera stoppet og lukket")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Test script
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🦆 Testing IMX500 Face Recognition")
    print("=" * 60)
    
    with IMX500FaceRecognizer() as recognizer:
        print(f"\n✓ Kamera startet")
        print(f"✓ {len(recognizer.list_known_people())} kjente personer i database")
        print("\nTester ansiktsgjenkjenning i 10 sekunder...\n")
        
        start = time.time()
        while time.time() - start < 10:
            faces = recognizer.detect_faces()
            
            if faces:
                print(f"Fant {len(faces)} ansikt(er):")
                for name, conf, location in faces:
                    print(f"  - {name}: {conf:.2%}")
            else:
                print("Ingen ansikter funnet")
            
            time.sleep(1)
    
    print("\n✓ Test fullført!")
