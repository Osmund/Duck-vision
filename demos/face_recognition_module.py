#!/usr/bin/env python3
"""
Duck-Vision Face Recognition
Håndterer ansiktsgjenkjenning og lagring av kjente personer
"""

import pickle
import time
from pathlib import Path
from typing import List, Tuple, Optional
import face_recognition
import numpy as np
from PIL import Image
from config import FACE_CONFIG, KNOWN_FACES_DIR


class FaceRecognizer:
    """Ansiktsgjenkjenning med face_recognition bibliotek"""
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.encodings_file = FACE_CONFIG["encodings_file"]
        self.tolerance = FACE_CONFIG["tolerance"]
        
        # Last inn kjente ansikter
        self.load_known_faces()
    
    def load_known_faces(self):
        """Last inn kjente ansikter fra fil"""
        if self.encodings_file.exists():
            try:
                with open(self.encodings_file, "rb") as f:
                    data = pickle.load(f)
                    self.known_face_encodings = data["encodings"]
                    self.known_face_names = data["names"]
                print(f"✓ Lastet {len(self.known_face_names)} kjente ansikter")
            except Exception as e:
                print(f"⚠️  Kunne ikke laste ansikter: {e}")
                self.known_face_encodings = []
                self.known_face_names = []
        else:
            print("ℹ️  Ingen lagrede ansikter funnet")
            self.known_face_encodings = []
            self.known_face_names = []
    
    def save_known_faces(self):
        """Lagre kjente ansikter til fil"""
        try:
            data = {
                "encodings": self.known_face_encodings,
                "names": self.known_face_names,
            }
            with open(self.encodings_file, "wb") as f:
                pickle.dump(data, f)
            print(f"✓ Lagret {len(self.known_face_names)} ansikter")
        except Exception as e:
            print(f"❌ Kunne ikke lagre ansikter: {e}")
    
    def detect_faces(self, image: np.ndarray) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        Finn ansikter i bilde og identifiser dem
        
        Returns:
            Liste med (navn, confidence, (top, right, bottom, left))
        """
        # Konverter til RGB hvis nødvendig
        if len(image.shape) == 2:
            image = np.stack([image] * 3, axis=-1)
        
        # Finn ansikter
        face_locations = face_recognition.face_locations(image, model="hog")
        
        if not face_locations:
            return []
        
        # Generer encodings for alle ansikter
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        results = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Sammenlign med kjente ansikter
            name, confidence = self._match_face(face_encoding)
            results.append((name, confidence, face_location))
        
        return results
    
    def _match_face(self, face_encoding: np.ndarray) -> Tuple[str, float]:
        """
        Match et ansikt mot kjente ansikter
        
        Returns:
            (navn, confidence) eller ("Unknown", 0.0)
        """
        if not self.known_face_encodings:
            return "Unknown", 0.0
        
        # Beregn face distances
        distances = face_recognition.face_distance(
            self.known_face_encodings, 
            face_encoding
        )
        
        # Finn beste match
        best_match_idx = np.argmin(distances)
        best_distance = distances[best_match_idx]
        
        # Sjekk om det er godt nok match
        if best_distance <= self.tolerance:
            name = self.known_face_names[best_match_idx]
            confidence = 1.0 - best_distance  # Konverter distance til confidence
            return name, confidence
        
        return "Unknown", 0.0
    
    def add_person(self, name: str, image: np.ndarray) -> bool:
        """
        Legg til ny person i databasen
        
        Args:
            name: Personens navn
            image: Bilde med ansiktet (numpy array)
        
        Returns:
            True hvis vellykket, False ellers
        """
        try:
            # Finn ansikt i bildet
            face_locations = face_recognition.face_locations(image, model="hog")
            
            if not face_locations:
                print("❌ Fant ingen ansikter i bildet")
                return False
            
            if len(face_locations) > 1:
                print("⚠️  Fant flere ansikter, bruker det første")
            
            # Generer encoding
            face_encodings = face_recognition.face_encodings(image, face_locations)
            face_encoding = face_encodings[0]
            
            # Sjekk om person allerede finnes
            if name in self.known_face_names:
                print(f"⚠️  {name} finnes allerede, oppdaterer...")
                idx = self.known_face_names.index(name)
                self.known_face_encodings[idx] = face_encoding
            else:
                # Legg til ny person
                self.known_face_encodings.append(face_encoding)
                self.known_face_names.append(name)
            
            # Lagre bilde
            person_dir = KNOWN_FACES_DIR / name
            person_dir.mkdir(exist_ok=True)
            timestamp = int(time.time())
            image_path = person_dir / f"{timestamp}.jpg"
            Image.fromarray(image).save(image_path)
            
            # Lagre encodings
            self.save_known_faces()
            
            print(f"✓ Lagt til {name} i databasen")
            return True
            
        except Exception as e:
            print(f"❌ Kunne ikke legge til person: {e}")
            return False
    
    def remove_person(self, name: str) -> bool:
        """Fjern person fra databasen"""
        try:
            if name not in self.known_face_names:
                print(f"⚠️  {name} finnes ikke i databasen")
                return False
            
            idx = self.known_face_names.index(name)
            del self.known_face_encodings[idx]
            del self.known_face_names[idx]
            
            self.save_known_faces()
            print(f"✓ Fjernet {name} fra databasen")
            return True
            
        except Exception as e:
            print(f"❌ Kunne ikke fjerne person: {e}")
            return False
    
    def get_all_known_people(self) -> List[str]:
        """Få liste over alle kjente personer"""
        return self.known_face_names.copy()


# Test funksjon
if __name__ == "__main__":
    print("Testing Duck-Vision Face Recognition...")
    
    recognizer = FaceRecognizer()
    
    print(f"\n✓ Face recognizer initialisert")
    print(f"  Kjente personer: {recognizer.get_all_known_people()}")
