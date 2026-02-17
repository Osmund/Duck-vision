#!/usr/bin/env python3
"""
Registrer ansikt - tar 5 bilder fra ulike vinkler og lagrer ansiktsenkoding.
Bruk: python3 scripts/register_face.py "Åsmund"
"""

import sys
import os
import time
import logging

# Legg til src i path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

from imx500_face_recognition import IMX500FaceRecognizer


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Åsmund"
    
    instructions = [
        "Se RETT FREM mot kameraet",
        "Snu hodet litt til VENSTRE",
        "Snu hodet litt til HØYRE",
        "Vipp hodet litt OPP",
        "Vipp hodet litt NED",
    ]
    
    print(f"\n🦆 Duck-Vision: Registrerer ansikt for '{name}'")
    print("=" * 50)
    print()
    print(f"Du tar {len(instructions)} bilder fra ulike vinkler.")
    print("Trykk ENTER for å ta hvert bilde.")
    print()
    
    input("Trykk ENTER for å starte... ")
    print()
    
    recognizer = IMX500FaceRecognizer()
    recognizer.start()
    
    print("📷 Kameraet varmer opp...")
    time.sleep(2)
    
    import face_recognition
    from PIL import Image
    import pickle
    import numpy as np
    
    encodings_collected = []
    images_collected = []
    
    for i, instruction in enumerate(instructions):
        print(f"\n  📸 Bilde {i+1}/{len(instructions)}: {instruction}")
        input(f"     👉 Trykk ENTER når du er klar... ")
        
        img = recognizer.picam2.capture_array()
        print(f"     📷 Bilde tatt! Analyserer...", end="", flush=True)
        
        face_locations = face_recognition.face_locations(img)
        
        if not face_locations:
            print(f" ⚠️  Ingen ansikt funnet, prøv igjen.")
            # Gi mulighet til å prøve på nytt
            while True:
                retry = input(f"     👉 Prøv igjen? Trykk ENTER (eller 's' for å hoppe over): ")
                if retry.lower() == 's':
                    print(f"     ⏭️  Hoppet over bilde {i+1}")
                    break
                img = recognizer.picam2.capture_array()
                print(f"     📷 Bilde tatt! Analyserer...", end="", flush=True)
                face_locations = face_recognition.face_locations(img)
                if face_locations:
                    break
                print(f" ⚠️  Fortsatt ingen ansikt, prøv igjen.")
        
        if face_locations:
            face_encs = face_recognition.face_encodings(img, [face_locations[0]])
            if face_encs:
                encodings_collected.append(face_encs[0])
                images_collected.append(img)
                print(f" ✅ Ansikt registrert!")
            else:
                print(f" ⚠️  Kunne ikke enkode ansikt.")
    
    if not encodings_collected:
        print(f"\n❌ Ingen gyldige bilder av {name}")
        recognizer.stop()
        return
    
    # Lagre til database
    for encoding in encodings_collected:
        recognizer.known_face_encodings.append(encoding)
        recognizer.known_face_names.append(name)
    
    for img, encoding in zip(images_collected, encodings_collected):
        recognizer._save_person_data(name, img, encoding)
    
    recognizer.save_known_faces()
    
    people = recognizer.list_known_people()
    print(f"\n✅ Ansiktsmodell for '{name}' er lagret med {len(encodings_collected)} bilder!")
    print(f"   Kjente personer: {', '.join(people)}")
    print(f"\n   Restart duck-vision for å aktivere:")
    print(f"   sudo systemctl restart duck-vision")
    
    recognizer.stop()


if __name__ == "__main__":
    main()
