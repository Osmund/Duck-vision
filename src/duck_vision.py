#!/usr/bin/env python3
"""
Duck-Vision Main Program - IMX500 OPTIMALISERT! 🚀
Koordinerer kamera, ansiktsgjenkjenning, objektdeteksjon og MQTT-kommunikasjon
Bruker IMX500 AI-chip for ultra-lav latency (5-10ms)
"""

import time
import signal
import sys
import os
from pathlib import Path
from enum import Enum
from typing import Optional
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from imx500_face_recognition import IMX500FaceRecognizer
from imx500_object_detection import IMX500ObjectDetector
from openai_vision import OpenAIVision
from mqtt_client import DuckMQTT
from config import FACE_CONFIG, TOPICS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class VisionMode(Enum):
    """Driftsmodus for vision-systemet"""
    IDLE = "idle"
    FACE_DETECTION = "face_detection"
    OBJECT_DETECTION = "object_detection"
    LEARNING_FACE = "learning_face"
    OPENAI_ANALYSIS = "openai_analysis"
    CHECK_PERSON = "check_person"


class DuckVision:
    """Hovedklasse for Duck-Vision systemet - IMX500 OPTIMALISERT! ⚡"""
    
    def __init__(self):
        self.running = False
        self.mode = VisionMode.FACE_DETECTION
        
        # IMX500-optimaliserte komponenter
        # Face recognizer først (starter kamera)
        self.face_recognizer = IMX500FaceRecognizer(progress_callback=self._on_learning_progress)
        # Object detector deler kamera-instans
        self.object_detector = None  # Initialiseres etter at kamera starter
        # OpenAI Vision for dyp forståelse
        self.openai_vision = None  # Initialiseres ved første bruk
        self.mqtt = DuckMQTT()
        
        # State
        self.last_face_detection = 0
        self.pending_person_name = None  # Navn på person vi venter på å lære
        self.pending_num_samples = 5  # Antall bilder å ta ved læring (default: 5)
        self.last_seen_faces = set()  # Cache av nylig sette ansikter
        self.last_unknown_alert = 0  # Timestamp for siste ukjent-person alert
        
        logging.info("✓ DuckVision initialisert med IMX500-støtte")
    
    def setup(self) -> bool:
        """Initialiser alle komponenter"""
        print("=" * 60)
        print("🦆 Duck-Vision Starter Opp (IMX500 AI-CHIP!) ⚡")
        print("=" * 60)
        
        # Start MQTT
        if not self.mqtt.connect():
            print("❌ Kunne ikke koble til MQTT. Sjekk konfigurasjon.")
            return False
        
        # Registrer MQTT callbacks
        self.mqtt.register_callback(
            TOPICS["samantha_to_vision"],
            self._handle_samantha_command
        )
        
        # Start IMX500 komponenter
        try:
            # Start face recognizer først (starter kamera)
            self.face_recognizer.start()
            
            # Object detector bruker samme kamera, men med sin egen IMX500 instans
            # Vi lager den først når vi trenger den (lazy init)
            self.object_detector = IMX500ObjectDetector()
            
            print("✓ IMX500 kamera startet - AI kjører på chip!")
        except Exception as e:
            print(f"❌ Kunne ikke starte IMX500: {e}")
            return False
        
        print(f"\n✓ Alle komponenter initialisert!")
        print(f"✓ Kjente personer: {len(self.face_recognizer.list_known_people())}")
        print(f"✓ Latency: ~5-10ms (AI på chip!) 🚀")
        return True
    
    def run(self):
        """Hovedløkke"""
        self.running = True
        
        print("\n" + "=" * 60)
        print("👁️  Duck-Vision Kjører")
        print("=" * 60)
        print("\nModus:")
        print("  - Ansiktsgjenkjenning: Kontinuerlig")
        print("  - Objektgjenkjenning: På forespørsel\n")
        print("Trykk Ctrl+C for å stoppe\n")
        
        try:
            while self.running:
                current_time = time.time()
                
                # Ansiktsdeteksjon med intervall
                if current_time - self.last_face_detection >= FACE_CONFIG["detection_interval"]:
                    self._check_faces()
                    self.last_face_detection = current_time
                
                # Objektdeteksjon hvis i riktig modus
                if self.mode == VisionMode.OBJECT_DETECTION:
                    self._check_objects()
                    # Gå tilbake til face detection etter en deteksjon
                    self.mode = VisionMode.FACE_DETECTION
                
                # OpenAI Vision analyse hvis forespurt
                if self.mode == VisionMode.OPENAI_ANALYSIS:
                    self._analyze_with_openai()
                    # Gå tilbake til face detection
                    self.mode = VisionMode.FACE_DETECTION
                
                # Små pauser for å ikke overbelaste CPU
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Avbryter...")
        finally:
            self.shutdown()
    
    def _check_faces(self):
        """Sjekk for ansikter - KJØRER PÅ IMX500 CHIP! ⚡"""
        try:
            # Detekter ansikter (hybrid: IMX500 detection + CPU recognition)
            faces = self.face_recognizer.detect_faces()
            
            if not faces:
                # Ingen ansikter funnet
                self.last_seen_faces.clear()
                return
            
            current_faces = set()
            
            for name, confidence, location in faces:
                current_faces.add(name)
                
                # Hvis vi er i læremodus og venter på å ta bilde
                if self.mode == VisionMode.LEARNING_FACE and self.pending_person_name:
                    self._learn_new_person()
                    return
                
                # Sjekk om dette er et nytt ansikt siden sist
                if name not in self.last_seen_faces:
                    if name == "ukjent":
                        # Ukjent person - send alert (men ikke for ofte)
                        if time.time() - self.last_unknown_alert > 10:  # Max én gang per 10 sek
                            logging.info("👤 Ukjent person oppdaget!")
                            self.mqtt.send_event("unknown_person", {})
                            self.last_unknown_alert = time.time()
                    else:
                        # Kjent person
                        logging.info(f"👋 Hei {name}! (confidence: {confidence:.2%})")
                        self.mqtt.send_event("face_recognized", {
                            "name": name,
                            "confidence": confidence
                        })
            
            self.last_seen_faces = current_faces
            
        except Exception as e:
            logging.error(f"❌ Feil ved ansiktsdeteksjon: {e}")
    
    def _check_objects(self):
        """Sjekk for objekter - KJØRER PÅ IMX500 CHIP! ⚡"""
        try:
            # Start object detector hvis ikke allerede startet
            if not hasattr(self.object_detector, 'picam2') or not self.object_detector.picam2:
                logging.info("⚙️ Starter object detector...")
                # Stopp face recognizer midlertidig
                self.face_recognizer.stop()
                time.sleep(0.5)  # Vent litt før vi starter ny kamera-instans
                # Start object detector
                self.object_detector.start()
                time.sleep(1)  # Vent på at IMX500 laster firmware
            
            logging.info("🔍 Ser etter objekter på IMX500...")
            
            # Detekter ALLE objekter (direkte på IMX500 chip!)
            all_objects = self.object_detector.detect_objects()
            
            if not all_objects:
                logging.info("  Ingen objekter funnet")
                self.mqtt.send_event("no_object_detected", {})
            else:
                # Lag en liste over alle objekter
                objects_list = []
                logging.info(f"  Funnet {len(all_objects)} objekt(er):")
                for obj_name, confidence, bbox in all_objects:
                    objects_list.append({
                        "name": obj_name,
                        "confidence": float(confidence),  # Konverter fra numpy float32
                        "bbox": [float(x) for x in bbox]  # Konverter bbox til Python floats
                    })
                    logging.info(f"    • {obj_name}: {confidence:.2%}")
                
                # Finn mest prominente objekt
                most_prominent = max(all_objects, key=lambda x: x[1])
                obj_name, confidence, _ = most_prominent
                
                # Send til Samantha (med hovedobjekt + alle objekter)
                logging.info(f"📦 Sender {len(objects_list)} objekt(er) til Samantha")
                self.mqtt.send_object_detected(obj_name, float(confidence), objects_list)
            
        except Exception as e:
            logging.error(f"❌ Feil ved objektdeteksjon: {e}")
            # Send feilmelding til Samantha
            self.mqtt.send_event("detection_error", {"error": str(e)})
        finally:
            # Alltid gå tilbake til face detection
            logging.info("⚙️ Bytter tilbake til face detection...")
            if hasattr(self.object_detector, 'picam2') and self.object_detector.picam2:
                self.object_detector.stop()
                time.sleep(0.5)
            self.face_recognizer.start()
            time.sleep(1)
    
    def _analyze_with_openai(self):
        """Analyser scene med OpenAI Vision API"""
        try:
            # Initialiser OpenAI Vision ved første bruk
            if not self.openai_vision:
                from openai_vision import OpenAIVision
                self.openai_vision = OpenAIVision()
            
            logging.info("🤖 Tar bilde for OpenAI Vision analyse...")
            
            # Ta et høykvalitets bilde fra normal kamera (ikke IMX500 mode)
            # Stopp face recognizer midlertidig
            self.face_recognizer.stop()
            time.sleep(0.5)
            
            # Bruk rpicam-still for bedre bildekvalitet (bedre ISP enn Picamera2/IMX500)
            import subprocess
            import tempfile
            from PIL import Image
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            
            # Ta bilde med rpicam-still (optimalisert for hastighet)
            cmd = [
                "rpicam-still",
                "-o", tmp_path,
                "--width", "512",
                "--height", "384",
                "-t", "500",  # 500ms - raskere, fortsatt god kvalitet
                "--awb", "auto",
                "-n"  # No preview
            ]
            
            logging.info("📸 Tar bilde med rpicam-still...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"rpicam-still feilet: {result.stderr}")
            
            # Last inn bildet
            image = Image.open(tmp_path)
            os.unlink(tmp_path)  # Slett temp-fil
            
            logging.info("📸 Bilde tatt, sender til OpenAI Vision...")
            
            # Analyser med OpenAI Vision
            question = getattr(self, 'openai_question', None)
            result = self.openai_vision.analyze_image(
                pil_image=image,
                question=question,
                max_tokens=200  # Redusert for hastighet
            )
            
            if result["success"]:
                description = result["description"]
                tokens = result.get("tokens_used", {})
                logging.info(f"✓ OpenAI Vision: {description[:100]}...")
                logging.info(f"  Tokens: {tokens.get('total_tokens', 'N/A')}")
                
                # Send resultat til Samantha
                self.mqtt.send_event("openai_analysis", {
                    "description": description,
                    "question": question,
                    "tokens_used": tokens
                })
            else:
                error = result.get("error", "Ukjent feil")
                logging.error(f"❌ OpenAI Vision feilet: {error}")
                self.mqtt.send_event("openai_analysis_error", {"error": error})
            
        except Exception as e:
            logging.error(f"❌ Feil ved OpenAI Vision analyse: {e}")
            self.mqtt.send_event("openai_analysis_error", {"error": str(e)})
        finally:
            # Restart face recognizer
            logging.info("⚙️ Starter face detection igjen...")
            self.openai_question = None  # Reset spørsmål
            self.face_recognizer.start()
            time.sleep(1)
    
    def _on_learning_progress(self, progress: dict):
        """Callback når face learning tar bilde - send til Samantha for TTS guidance"""
        step = progress.get("step", 0)
        total = progress.get("total", 0)
        instruction = progress.get("instruction", "")
        
        logging.info(f"   📸 Progress: {step}/{total} - {instruction}")
        
        # Send event til Samantha så hun kan si instruksjonen
        self.mqtt.send_event("learning_progress", {
            "name": self.pending_person_name,
            "step": step,
            "total": total,
            "instruction": instruction
        })
    
    def _learn_new_person(self):
        """Lær en ny person med flere bilder for bedre accuracy"""
        if not self.pending_person_name:
            return
        
        num_samples = getattr(self, 'pending_num_samples', 5)  # Default 5 bilder
        
        logging.info(f"📸 Lærer ansikt for: {self.pending_person_name}")
        logging.info(f"   Tar {num_samples} bilder - beveg hodet litt!")
        
        # Legg til person med flere bilder (tar bilder automatisk)
        success = self.face_recognizer.add_person(
            name=self.pending_person_name,
            num_samples=num_samples
        )
        
        if success:
            logging.info(f"✅ {self.pending_person_name} lagt til i databasen!")
            self.mqtt.send_event("person_learned", {
                "name": self.pending_person_name,
                "success": True,
                "samples": num_samples
            })
        else:
            logging.error(f"❌ Kunne ikke lære {self.pending_person_name}")
            self.mqtt.send_event("person_learned", {
                "name": self.pending_person_name,
                "success": False
            })
        
        # Tilbakestill state
        self.pending_person_name = None
        self.pending_num_samples = 5
        self.mode = VisionMode.FACE_DETECTION
    
    def _handle_samantha_command(self, message: dict):
        """Håndter kommandoer fra Samantha"""
        command = message.get("command")
        
        logging.info(f"\n📬 Kommando fra Samantha: {command}")
        
        if command == "detect_object":
            # Bytt til objektdeteksjonsmodus
            self.mode = VisionMode.OBJECT_DETECTION
            logging.info("  → Bytter til objektdeteksjon")
        
        elif command == "analyze_scene":
            # Analyser scene med OpenAI Vision
            question = message.get("question")
            self.openai_question = question
            self.mode = VisionMode.OPENAI_ANALYSIS
            if question:
                logging.info(f"  → OpenAI Vision analyse: {question}")
            else:
                logging.info(f"  → OpenAI Vision generell analyse")
        
        elif command == "check_person":
            # Sjekk hvem som er der akkurat nå
            logging.info("👀 Sjekk hvem som er tilstede...")
            faces = self.face_recognizer.detect_faces()
            
            if not faces or len(faces) == 0:
                logging.info("Ingen personer funnet")
                self.mqtt.send_event("check_person_result", {
                    "found": False,
                    "reason": "no_person_detected"
                })
            else:
                # Ta første person
                name, confidence, location = faces[0]
                
                if name == "ukjent":
                    logging.info("👤 Ukjent person funnet")
                    self.mqtt.send_event("unknown_person", {})
                else:
                    logging.info(f"👋 Kjent person funnet: {name} ({confidence:.2%})")
                    self.mqtt.send_event("face_recognized", {
                        "name": name,
                        "confidence": confidence
                    })
        
        elif command == "learn_person":
            # Start læring av ny person med flere bilder for bedre nøyaktighet
            name = message.get("name")
            num_samples = message.get("num_samples", 5)  # Default: 5 bilder
            if name:
                self.pending_person_name = name
                self.pending_num_samples = num_samples
                self.mode = VisionMode.LEARNING_FACE
                logging.info(f"  → Lærer ny person: {name}")
                logging.info(f"     Tar {num_samples} bilder for best mulig accuracy")
                logging.info(f"     💡 Beveg hodet litt mellom bildene!")
        
        elif command == "forget_person":
            # Fjern person fra database
            name = message.get("name")
            if name:
                success = self.face_recognizer.forget_person(name)
                self.mqtt.send_event("person_forgotten", {
                    "name": name,
                    "success": success
                })
        
        elif command == "list_people":
            # List alle kjente personer
            people = self.face_recognizer.list_known_people()
            self.mqtt.send_event("known_people", {
                "people": people,
                "count": len(people)
            })
            logging.info(f"  → Kjente personer: {people}")
        
        elif command == "ping":
            # Svar på ping
            self.mqtt.send_event("pong", {"timestamp": time.time()})
        
        else:
            logging.warning(f"  ⚠️  Ukjent kommando: {command}")
    
    def shutdown(self):
        """Rydd opp og stopp systemet"""
        logging.info("\n\n🛑 Stopper Duck-Vision...")
        self.running = False
        
        self.face_recognizer.stop()
        if hasattr(self.object_detector, 'stop'):
            self.object_detector.stop()
        self.mqtt.disconnect()
        
        logging.info("✓ Duck-Vision stoppet")


def main():
    """Hovedfunksjon"""
    vision = DuckVision()
    
    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        vision.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start systemet
    if vision.setup():
        vision.run()
    else:
        print("\n❌ Oppstart feilet")
        sys.exit(1)


if __name__ == "__main__":
    main()
