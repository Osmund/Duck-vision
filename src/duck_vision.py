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
import re
from pathlib import Path
from enum import Enum
from typing import Optional
import logging
from PIL import Image

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from imx500_face_recognition import IMX500FaceRecognizer
from imx500_object_detection import IMX500ObjectDetector
from openai_vision import OpenAIVision
from speaker_recognition import SpeakerRecognition
from mqtt_client import DuckMQTT
from config import FACE_CONFIG, VOICE_CONFIG, TOPICS, OBJECT_CONFIG

try:
    from hailo_object_detection import HailoObjectDetector
except Exception:
    HailoObjectDetector = None

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
        self.object_backend = OBJECT_CONFIG.get("backend", "imx500")
        
        # IMX500-optimaliserte komponenter
        # Face recognizer først (starter kamera)
        self.face_recognizer = IMX500FaceRecognizer(progress_callback=self._on_learning_progress)
        # Object detectors
        self.object_detector = None  # IMX500 detector
        self.hailo_detector = None   # Hailo detector (on-demand)
        # OpenAI Vision for dyp forståelse
        self.openai_vision = None  # Initialiseres ved første bruk
        # Speaker recognition (passiv lytting)
        self.speaker_recognition = None  # Initialiseres i setup()
        self.mqtt = DuckMQTT()
        
        # State
        self.last_face_detection = 0
        self.pending_person_name = None  # Navn på person vi venter på å lære
        self.pending_num_samples = 5  # Antall bilder å ta ved læring (default: 5)
        self.last_seen_faces = set()  # Cache av nylig sette ansikter
        self.last_unknown_alert = 0  # Timestamp for siste ukjent-person alert

        # Live preview for web dashboard
        self.live_preview_enabled = os.getenv("VISION_WEB_PREVIEW_ENABLED", "true").lower() == "true"
        self.live_preview_interval = max(0.2, float(os.getenv("VISION_WEB_PREVIEW_INTERVAL", "0.7")))
        self.live_preview_max_width = max(320, int(os.getenv("VISION_WEB_PREVIEW_MAX_WIDTH", "960")))
        self.live_preview_color_order = os.getenv("VISION_WEB_PREVIEW_COLOR_ORDER", "bgr").lower()
        default_live_path = Path(__file__).resolve().parents[1] / "data" / "logs" / "duck_vision_live.jpg"
        self.live_preview_path = Path(os.getenv("VISION_WEB_PREVIEW_PATH", str(default_live_path)))
        self._last_live_preview = 0.0
        self._last_live_preview_error_log = 0.0
        self.openai_identity_first = False
        self.last_speaker_name = None
        self.last_speaker_confidence = 0.0
        self.last_speaker_ts = 0.0
        
        logging.info("✓ DuckVision initialisert (object backend: %s)", self.object_backend)
    
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
        
        # Lytt på Samantha speaking-status (mute mikrofon når hun snakker)
        self.mqtt.register_callback(
            TOPICS["samantha_speaking"],
            self._handle_samantha_speaking
        )
        
        # Lytt på samtale-status (samtale-modus for stemmegjenkjenning)
        self.mqtt.register_callback(
            TOPICS["samantha_conversation"],
            self._handle_samantha_conversation
        )
        
        # Start IMX500 komponenter
        try:
            # Start face recognizer først (starter kamera)
            self.face_recognizer.start()
            
            # IMX500 object detector (for imx500/hybrid)
            if self.object_backend in ("imx500", "hybrid"):
                self.object_detector = IMX500ObjectDetector(
                    model_path=OBJECT_CONFIG["imx500_model"],
                    confidence_threshold=OBJECT_CONFIG["confidence_threshold"],
                )

            # Hailo object detector (for hailo/hybrid)
            if self.object_backend in ("hailo", "hybrid"):
                if HailoObjectDetector is None:
                    raise RuntimeError("HailoObjectDetector kunne ikke importeres")
                self.hailo_detector = HailoObjectDetector(
                    confidence_threshold=OBJECT_CONFIG.get("hailo_threshold", 0.35),
                    duration_ms=OBJECT_CONFIG.get("hailo_duration_ms", 1800),
                    width=OBJECT_CONFIG.get("hailo_width", 1280),
                    height=OBJECT_CONFIG.get("hailo_height", 720),
                    fps=OBJECT_CONFIG.get("hailo_fps", 15),
                )
            
            print("✓ IMX500 kamera startet - AI kjører på chip!")
        except Exception as e:
            print(f"❌ Kunne ikke starte IMX500: {e}")
            return False
        
        # Start speaker recognition (passiv lytting i bakgrunnstråd)
        try:
            self.speaker_recognition = SpeakerRecognition(
                VOICE_CONFIG,
                event_callback=self._on_speaker_event
            )
            self.speaker_recognition.start()
            print(f"✓ Speaker recognition startet (passiv lytting)")
            print(f"✓ Kjente stemmer: {len(self.speaker_recognition.list_known_speakers())}")
        except Exception as e:
            print(f"⚠️ Speaker recognition kunne ikke starte: {e}")
            print(f"  (Vision fortsetter uten stemmegjenkjenning)")
        
        print(f"\n✓ Alle komponenter initialisert!")
        print(f"✓ Kjente personer: {len(self.face_recognizer.list_known_people())}")
        print(f"✓ Object backend: {self.object_backend}")
        print(f"✓ Latency: ~5-10ms (AI på chip!) 🚀")
        return True
    
    def run(self):
        """Hovedløkke"""
        self.running = True
        
        print("\n" + "=" * 60)
        print("👁️  Duck-Vision Kjører")
        print("=" * 60)
        print("\nModus:")
        print("  - Ansiktsgjenkjenning: På forespørsel")
        print("  - Objektgjenkjenning: På forespørsel\n")
        print("Trykk Ctrl+C for å stoppe\n")
        
        try:
            while self.running:
                current_time = time.time()
                
                # Ansiktsdeteksjon: Kun på forespørsel (ikke kontinuerlig)
                # if current_time - self.last_face_detection >= FACE_CONFIG["detection_interval"]:
                #     self._check_faces()
                #     self.last_face_detection = current_time
                
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

                # Eksporter lavoppløselig live frame for web-dashboard.
                if (
                    self.live_preview_enabled
                    and self.mode == VisionMode.FACE_DETECTION
                    and (current_time - self._last_live_preview) >= self.live_preview_interval
                ):
                    self._write_live_preview_frame()
                    self._last_live_preview = current_time
                
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
                        
                        # Auto-enroll stemme hvis vi ikke har profil
                        if (self.speaker_recognition 
                                and self.speaker_recognition.config.get("auto_enroll")
                                and not self.speaker_recognition.has_voice_profile(name)
                                and len(current_faces) == 1):  # Kun én person synlig
                            self.speaker_recognition.start_auto_enroll(name)
            
            self.last_seen_faces = current_faces
            
        except Exception as e:
            logging.error(f"❌ Feil ved ansiktsdeteksjon: {e}")

    def _write_live_preview_frame(self):
        """Lagre et komprimert live-bilde for web-UI."""
        picam = getattr(self.face_recognizer, "picam2", None)
        if not picam:
            return

        try:
            self.live_preview_path.parent.mkdir(parents=True, exist_ok=True)
            frame = picam.capture_array()

            # Picamera2 frames can arrive in BGR order for preview paths.
            if self.live_preview_color_order == "bgr" and len(frame.shape) == 3 and frame.shape[2] >= 3:
                frame = frame[:, :, ::-1]

            image = Image.fromarray(frame)
            width, height = image.size
            if width > self.live_preview_max_width:
                new_height = int(height * self.live_preview_max_width / width)
                image = image.resize((self.live_preview_max_width, new_height))

            tmp_path = self.live_preview_path.with_name(self.live_preview_path.stem + ".tmp.jpg")
            image.save(tmp_path, format="JPEG", quality=72, optimize=True)
            os.replace(tmp_path, self.live_preview_path)
        except Exception as e:
            now_ts = time.time()
            if now_ts - self._last_live_preview_error_log > 30:
                logging.warning(f"Kunne ikke skrive live preview frame: {e}")
                self._last_live_preview_error_log = now_ts
    
    def _check_objects(self):
        """Sjekk for objekter via valgt backend (imx500/hailo/hybrid)."""
        try:
            # Stopp face recognizer midlertidig for å frigjøre kamera
            self.face_recognizer.stop()
            time.sleep(0.5)

            detections_imx500 = []
            detections_hailo = []

            if self.object_backend in ("imx500", "hybrid") and self.object_detector:
                logging.info("🔍 Ser etter objekter på IMX500...")
                self.object_detector.start()
                time.sleep(1)  # Vent på modell-warmup
                detections_imx500 = self.object_detector.detect_objects()

                # Frigi kamera før Hailo-pass i hybrid-modus.
                if self.object_backend == "hybrid":
                    self.object_detector.stop()
                    time.sleep(0.4)

            if self.object_backend in ("hailo", "hybrid") and self.hailo_detector:
                logging.info("🧠 Ser etter objekter på Hailo...")
                detections_hailo = self.hailo_detector.detect_objects()

            # Merge ved navn, behold hoyeste confidence per objekt
            merged = {}
            for name, confidence, bbox in detections_imx500 + detections_hailo:
                existing = merged.get(name)
                if not existing or confidence > existing[0]:
                    merged[name] = (confidence, bbox)

            all_objects = [(name, conf, bbox) for name, (conf, bbox) in merged.items()]
            
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

                detailed_description = None
                openai_tokens = {}

                if OBJECT_CONFIG.get("enrich_with_openai", True):
                    context_objects = [o["name"] for o in objects_list]
                    question = (
                        "Beskriv scenen detaljert på norsk. "
                        f"Objekter detektert lokalt: {', '.join(context_objects)}. "
                        "Forklar hva som skjer, plassering i rommet, relasjoner mellom objekter, "
                        "belysning og relevante detaljer som hjelper en blind bruker."
                    )
                    logging.info("🤖 Ber OpenAI om detaljbeskrivelse av scenen...")
                    result = self._capture_scene_with_openai(
                        question=question,
                        max_tokens=OBJECT_CONFIG.get("openai_max_tokens", 900)
                    )
                    if result.get("success"):
                        detailed_description = result.get("description")
                        openai_tokens = result.get("tokens_used", {})
                        logging.info("✓ OpenAI detaljbeskrivelse mottatt")
                    else:
                        logging.warning("⚠️ OpenAI enrichment feilet: %s", result.get("error", "ukjent"))
                
                # Finn mest prominente objekt
                most_prominent = max(all_objects, key=lambda x: x[1])
                obj_name, confidence, _ = most_prominent
                
                # Send til Samantha (med hovedobjekt + alle objekter)
                logging.info(f"📦 Sender {len(objects_list)} objekt(er) til Samantha")
                self.mqtt.send_object_detected(
                    obj_name,
                    float(confidence),
                    objects_list,
                    detailed_description=detailed_description,
                    openai_tokens=openai_tokens,
                )

                # Behold eksisterende event-kanal for kompatibilitet.
                if detailed_description:
                    self.mqtt.send_event("openai_analysis", {
                        "description": detailed_description,
                        "question": question,
                        "tokens_used": openai_tokens,
                        "source": "detect_object_enrichment",
                    })
            
        except Exception as e:
            logging.error(f"❌ Feil ved objektdeteksjon: {e}")
            # Send feilmelding til Samantha
            self.mqtt.send_event("detection_error", {"error": str(e)})
        finally:
            # Alltid gå tilbake til face detection
            logging.info("⚙️ Bytter tilbake til face detection...")
            if self.object_detector and hasattr(self.object_detector, 'picam2') and self.object_detector.picam2:
                self.object_detector.stop()
                time.sleep(0.5)
            self.face_recognizer.start()
            time.sleep(1)
    
    def _analyze_with_openai(self):
        """Analyser scene med OpenAI Vision API"""
        try:
            logging.info("🤖 Tar bilde for OpenAI Vision analyse...")

            question = getattr(self, 'openai_question', None)
            identity_result = None

            if self.openai_identity_first:
                logging.info("🪪 Identitetsfokus oppdaget - kjører check_person før sceneanalyse")
                identity_result = self._run_check_person(publish_event=True)

                if identity_result.get("found"):
                    name = identity_result.get("name", "ukjent")
                    confidence = float(identity_result.get("confidence", 0.0))
                    confidence_pct = round(confidence * 100)
                    confidence_note = "lav sikkerhet" if identity_result.get("low_confidence") else "høy sikkerhet"
                    identity_hint = (
                        f"Lokal ansiktsgjenkjenning: sannsynligvis {name} "
                        f"({confidence_pct}% confidence, {confidence_note})."
                    )
                else:
                    identity_hint = "Lokal ansiktsgjenkjenning fant ikke sikker identitet."

                if question:
                    question = f"{question}\n\n{identity_hint}"
                else:
                    question = identity_hint

            # Ta et høykvalitets bilde fra normal kamera (ikke IMX500 mode)
            self.face_recognizer.stop()
            time.sleep(0.5)
            result = self._capture_scene_with_openai(question=question, max_tokens=800)
            
            if result["success"]:
                description = result["description"]
                tokens = result.get("tokens_used", {})

                if identity_result:
                    if identity_result.get("found"):
                        cleaned = self._strip_identity_fallback_text(description)
                        if cleaned != description:
                            logging.info("🧹 Fjernet selvmotsigende identitets-fraser fra OpenAI-tekst")
                        description = cleaned or ""

                    if identity_result.get("found"):
                        name = identity_result.get("name", "ukjent")
                        confidence = float(identity_result.get("confidence", 0.0))
                        confidence_pct = round(confidence * 100)
                        if identity_result.get("low_confidence"):
                            identity_prefix = f"Jeg tror det kan være {name} ({confidence_pct}% sikkerhet), men dette er usikkert."
                        else:
                            identity_prefix = f"Det ser ut til å være {name} ({confidence_pct}% sikkerhet)."
                    else:
                        identity_prefix = "Jeg klarte ikke å bekrefte identiteten sikkert."

                    description = f"{identity_prefix}\n\n{description}" if description else identity_prefix

                logging.info(f"✓ OpenAI Vision: {description[:100]}...")
                logging.info(f"  Tokens: {tokens.get('total_tokens', 'N/A')}")
                
                # Send resultat til Samantha
                self.mqtt.send_event("openai_analysis", {
                    "description": description,
                    "question": question,
                    "tokens_used": tokens,
                    "identity_result": identity_result,
                })

                if identity_result:
                    self.mqtt.send_event("scene_identity_result", {
                        "question": question,
                        "identity_result": identity_result,
                        "description": description,
                        "tokens_used": tokens,
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
            self.openai_identity_first = False
            self.face_recognizer.start()
            time.sleep(1)

    def _is_identity_question(self, question: Optional[str]) -> bool:
        """Vurder om spørsmålet egentlig handler om identitet/person."""
        if not question:
            return False

        ql = question.lower()
        cues = [
            "hvem er",
            "hvem ser du",
            "hvem sitter",
            "er det meg",
            "er dette meg",
            "er det osmund",
            "er det åsmund",
            "kjenner du meg",
            "who is",
            "am i",
        ]
        return any(c in ql for c in cues)

    def _strip_identity_fallback_text(self, text: str) -> str:
        """Fjern selvmotsigende fallback-setninger, men behold scenedetaljer."""
        if not text:
            return text

        blocked_phrases = [
            "jeg kan ikke identifisere personer på bilder",
            "kan ikke identifisere personer på bilder",
            "jeg kan ikke se identiteten",
            "kan ikke se identiteten",
            "beklager, jeg kan ikke identifisere personer",
            "beklager, men jeg kan ikke identifisere personer",
        ]

        segments = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        kept = []
        for seg in segments:
            candidate = seg.strip()
            if not candidate:
                continue
            lower = candidate.lower()
            if any(phrase in lower for phrase in blocked_phrases):
                continue
            kept.append(candidate)

        return " ".join(kept).strip()

    def _run_check_person(self, publish_event: bool = True, min_confidence: float = 0.50, max_attempts: int = 3) -> dict:
        """Kjør check_person med flere forsøk, og returner strukturert resultat."""
        logging.info("👀 Sjekk hvem som er tilstede (prøver opptil %d ganger)...", max_attempts)

        best_result = None
        best_confidence = 0.0

        for attempt in range(1, max_attempts + 1):
            faces = self.face_recognizer.detect_faces()

            if faces and len(faces) > 0:
                name, confidence, _location = faces[0]

                if confidence > best_confidence:
                    best_result = (name, confidence)
                    best_confidence = confidence

                recent_voice_match = self._recent_speaker_match(name)
                required_confidence = max(0.0, min_confidence - (0.08 if recent_voice_match else 0.0))

                if confidence >= required_confidence and name != "ukjent":
                    logging.info("✅ Forsøk %d/%d: Gjenkjent %s (%.2f%%)", attempt, max_attempts, name, confidence * 100)

                    has_voice = False
                    if self.speaker_recognition:
                        has_voice = self.speaker_recognition.has_voice_profile(name)
                        if not has_voice and self.speaker_recognition.config.get("auto_enroll"):
                            self.speaker_recognition.start_auto_enroll(name)

                    payload = {
                        "found": True,
                        "name": name,
                        "confidence": confidence,
                        "has_voice_profile": has_voice,
                        "voice_assisted": recent_voice_match,
                        "match_threshold_used": required_confidence,
                        "low_confidence": False,
                    }
                    if publish_event:
                        self.mqtt.send_event("check_person_result", payload)
                    return payload

                logging.info("⚠️ Forsøk %d/%d: %s (%.2f%%) - for lav confidence", attempt, max_attempts, name, confidence * 100)
            else:
                logging.info("⚠️ Forsøk %d/%d: Ingen ansikt detektert", attempt, max_attempts)

            if attempt < max_attempts:
                time.sleep(0.3)

        if best_result and best_result[0] != "ukjent":
            recent_voice_match = self._recent_speaker_match(best_result[0])
            if recent_voice_match and best_confidence >= max(0.0, min_confidence - 0.12):
                payload = {
                    "found": True,
                    "name": best_result[0],
                    "confidence": best_confidence,
                    "voice_assisted": True,
                    "match_threshold_used": max(0.0, min_confidence - 0.12),
                    "low_confidence": True,
                }
                logging.info(
                    "✅ Stemmehjelp: godtar %s (%.2f%%) etter %d forsøk",
                    best_result[0],
                    best_confidence * 100,
                    max_attempts,
                )
                if publish_event:
                    self.mqtt.send_event("check_person_result", payload)
                return payload

            payload = {
                "found": True,
                "name": best_result[0],
                "confidence": best_confidence,
                "voice_assisted": False,
                "low_confidence": True,
            }
            logging.info(
                "⚠️ Beste resultat etter %d forsøk: %s (%.2f%%) - under terskel",
                max_attempts,
                best_result[0],
                best_confidence * 100,
            )
            if publish_event:
                self.mqtt.send_event("check_person_result", payload)
            return payload

        payload = {
            "found": False,
            "reason": "no_person_detected",
            "low_confidence": True,
        }
        logging.info("❌ Ingen person gjenkjent etter %d forsøk", max_attempts)
        if publish_event:
            self.mqtt.send_event("check_person_result", payload)
        return payload

    def _recent_speaker_match(self, name: str, max_age_sec: float = 20.0, min_voice_confidence: float = 0.70) -> bool:
        """Sjekk om vi nylig hørte samme person på stemmen."""
        if not name or name == "ukjent":
            return False

        if not self.last_speaker_name:
            return False

        age = time.time() - float(self.last_speaker_ts or 0.0)
        if age > max_age_sec:
            return False

        return (
            self.last_speaker_name.lower() == name.lower()
            and float(self.last_speaker_confidence or 0.0) >= min_voice_confidence
        )

    def _capture_scene_with_openai(self, question: str = None, max_tokens: int = 800) -> dict:
        """Ta stillbilde og analyser med OpenAI Vision. Forutsetter at kamera er frigitt."""
        try:
            if not self.openai_vision:
                self.openai_vision = OpenAIVision()

            import subprocess
            import tempfile
            from PIL import Image

            def is_hand_question(q: str) -> bool:
                if not q:
                    return False
                ql = q.lower()
                keywords = ["holder", "hånden", "hånda", "hender", "hand", "tang", "grep", "griper"]
                return any(k in ql for k in keywords)

            def score_answer(ans: str) -> int:
                if not ans:
                    return -10_000
                ql = ans.lower()
                uncertain_phrases = [
                    "kan ikke si sikkert",
                    "ikke sikker",
                    "usikker",
                    "ikke tydelig",
                    "vanskelig å se",
                ]
                penalty = 0
                if any(p in ql for p in uncertain_phrases):
                    penalty -= 2000
                return min(len(ans), 2000) + penalty

            def is_non_visual_fallback(ans: str) -> bool:
                if not ans:
                    return True
                ql = ans.lower()
                bad_phrases = [
                    "jeg kan ikke se bilder",
                    "kan ikke se bilder",
                    "jeg kan ikke identifisere personer",
                    "jeg kan ikke se identiteten",
                    "basert på beskrivelsen",
                    "du nevner",
                ]
                return any(p in ql for p in bad_phrases)

            hand_mode = is_hand_question(question)
            max_shots = OBJECT_CONFIG.get("openai_hand_multishot", 3) if hand_mode else OBJECT_CONFIG.get("openai_default_multishot", 1)
            max_shots = max(1, min(int(max_shots), 4))
            adaptive = OBJECT_CONFIG.get("openai_adaptive_multishot", True)
            min_shots = max(1, min(int(OBJECT_CONFIG.get("openai_min_shots", 1)), max_shots))
            shots = min_shots if adaptive else max_shots

            detail = OBJECT_CONFIG.get("openai_detail_hand", "high") if hand_mode else OBJECT_CONFIG.get("openai_detail", "auto")
            detail = detail if detail in ("auto", "low", "high") else "auto"

            prompt = question
            if hand_mode and question:
                prompt = (
                    f"{question}\\n"
                    "Fokuser spesielt på hva personen holder i hendene. "
                    "Hvis du er usikker, gi 1-2 mest sannsynlige alternativer og hvorfor."
                )

            best = None
            last_error = None

            def run_single_shot(idx: int, total: int):
                nonlocal last_error
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name

                cmd = [
                    "rpicam-still",
                    "-o", tmp_path,
                    "--width", "1920",
                    "--height", "1080",
                    "-t", "800",
                    "--awb", "auto",
                    "-n",
                ]

                logging.info("📸 Tar bilde med rpicam-still... (%d/%d)", idx, total)
                shot = subprocess.run(cmd, capture_output=True, text=True)
                if shot.returncode != 0:
                    last_error = f"rpicam-still feilet: {shot.stderr.strip()}"
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                    return None

                image = Image.open(tmp_path)
                os.unlink(tmp_path)

                logging.info("📸 Bilde tatt, sender til OpenAI Vision... (%d/%d, detail=%s)", idx, total, detail)
                result = self.openai_vision.analyze_image(
                    pil_image=image,
                    question=prompt,
                    max_tokens=max_tokens,
                    detail=detail,
                )

                if not result.get("success"):
                    last_error = result.get("error", "ukjent feil")
                    return None

                ans = result.get("description", "")
                candidate_score = score_answer(ans)
                if is_non_visual_fallback(ans):
                    candidate_score -= 3000
                return candidate_score, result

            for i in range(shots):
                candidate = run_single_shot(i + 1, shots)
                if not candidate:
                    continue
                if not best or candidate[0] > best[0]:
                    best = candidate

            if adaptive and best and max_shots > shots:
                best_text = best[1].get("description", "")
                if is_non_visual_fallback(best_text) or score_answer(best_text) < 300:
                    extra = max_shots - shots
                    logging.info("⚡ Adaptiv multishot: utvider fra %d til %d snapshots pga lav kvalitet", shots, max_shots)
                    for i in range(extra):
                        idx = shots + i + 1
                        candidate = run_single_shot(idx, max_shots)
                        if not candidate:
                            continue
                        if candidate[0] > best[0]:
                            best = candidate
                    shots = max_shots

            if best:
                if shots > 1:
                    logging.info("✓ Valgte beste OpenAI-svar fra %d snapshots", shots)
                return best[1]

            return {
                "success": False,
                "error": last_error or "Ingen gyldige OpenAI-svar",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
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
            self.openai_identity_first = self._is_identity_question(question)
            self.mode = VisionMode.OPENAI_ANALYSIS
            if question:
                if self.openai_identity_first:
                    logging.info(f"  → OpenAI Vision analyse med identitetsfokus: {question}")
                else:
                    logging.info(f"  → OpenAI Vision analyse: {question}")
            else:
                logging.info(f"  → OpenAI Vision generell analyse")

        elif command == "inspect_scene":
            # Kombinert flyt: identitet + scenebeskrivelse i én operasjon
            question = message.get("question") or "Hvem er i bildet, og hva skjer i scenen akkurat nå?"
            self.openai_question = question
            self.openai_identity_first = True
            self.mode = VisionMode.OPENAI_ANALYSIS
            logging.info(f"  → Kombinert sceneinspeksjon: {question}")
        
        elif command == "check_person":
            self._run_check_person(publish_event=True)

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
        
        elif command == "learn_voice":
            # Manuell stemmelæring
            name = message.get("name")
            duration = message.get("duration", 10.0)
            if name and self.speaker_recognition:
                logging.info(f"🎤 Starter manuell stemmelæring for {name} ({duration}s)")
                success = self.speaker_recognition.learn_voice(name, duration)
                self.mqtt.send_voice_profile_created(name, success)
            elif not self.speaker_recognition:
                logging.warning("⚠️ Speaker recognition ikke tilgjengelig")
                self.mqtt.send_event("error", {"message": "Speaker recognition not available"})
        
        elif command == "save_conversation_voice":
            # Lag stemmeprofil fra samtale-audio (uten ekstra opptak)
            name = message.get("name")
            if name and self.speaker_recognition:
                logging.info(f"🎤 Lager stemmeprofil for {name} fra samtale-audio")
                success = self.speaker_recognition.create_profile_from_conversation(name)
                duration = 0.0  # Ikke relevant for samtale-basert profil
                self.mqtt.send_voice_profile_created(name, success, duration)
            elif not self.speaker_recognition:
                logging.warning("⚠️ Speaker recognition ikke tilgjengelig")
                self.mqtt.send_event("error", {"message": "Speaker recognition not available"})
        
        elif command == "forget_person":
            # Fjern person fra database (ansikt + stemme)
            name = message.get("name")
            if name:
                success = self.face_recognizer.forget_person(name)
                # Fjern også stemmeprofil
                if self.speaker_recognition:
                    self.speaker_recognition.forget_speaker(name)
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
    
    def _handle_samantha_speaking(self, message: dict):
        """Mute/unmute mikrofon når Samantha snakker/er stille"""
        speaking = message.get("speaking", False)
        if self.speaker_recognition:
            if speaking:
                self.speaker_recognition.mute()
            else:
                self.speaker_recognition.unmute()
    
    def _handle_samantha_conversation(self, message: dict):
        """Start/stopp samtale-modus.
        
        Når samtale starter (wake word):
        - Aktiver samtale-modus for stemmegjenkjenning (raskere matching)
        - Kjør ansiktssjekk automatisk (begge modaliteter jobber parallelt)
        """
        active = message.get("active", False)
        if active:
            logging.info("💬 Samtale startet - kjører identifisering")
            
            # Start samtale-modus for stemmegjenkjenning
            if self.speaker_recognition:
                self.speaker_recognition.start_conversation()
            
            # Proaktiv ansiktssjekk - vi vet at noen er der
            self._check_faces()
        else:
            logging.info("💬 Samtale avsluttet")
            if self.speaker_recognition:
                self.speaker_recognition.end_conversation()
    
    def _on_speaker_event(self, event_type: str, data: dict):
        """Callback fra speaker recognition"""
        if event_type == "speaker_recognized":
            name = data.get("name")
            confidence = data.get("confidence", 0)
            duration = data.get("speech_duration", 0)
            source = data.get("source", "passive")
            self.last_speaker_name = name
            self.last_speaker_confidence = float(confidence or 0.0)
            self.last_speaker_ts = time.time()
            logging.info(f"🔊 Stemme gjenkjent: {name} ({confidence:.2%}, {source})")
            self.mqtt.send_speaker_recognized(name, confidence, duration)
        
        elif event_type == "noise_level":
            db_rms = data.get("db_rms", -100)
            self.mqtt.send_noise_level(db_rms)
        
        elif event_type == "voice_profile_created":
            name = data.get("name")
            success = data.get("success", False)
            duration = data.get("speech_duration", 0)
            if success:
                logging.info(f"✅ Stemmeprofil opprettet for {name}")
            else:
                logging.warning(f"❌ Stemmeprofil feilet for {name}")
            self.mqtt.send_voice_profile_created(name, success, duration)
    
    def shutdown(self):
        """Rydd opp og stopp systemet"""
        logging.info("\n\n🛑 Stopper Duck-Vision...")
        self.running = False
        
        if self.speaker_recognition:
            self.speaker_recognition.stop()
        self.face_recognizer.stop()
        if self.object_detector and hasattr(self.object_detector, 'stop'):
            self.object_detector.stop()
        if self.hailo_detector and hasattr(self.hailo_detector, 'stop'):
            self.hailo_detector.stop()
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
