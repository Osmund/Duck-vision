#!/usr/bin/env python3
"""
Duck-Vision MQTT Client
Håndterer kommunikasjon med Samantha (anda-assistenten)
"""

import json
import time
from typing import Callable, Dict, Any
import paho.mqtt.client as mqtt
from config import MQTT_CONFIG, TOPICS


class DuckMQTT:
    """MQTT klient for Duck-Vision"""
    
    def __init__(self):
        self.client = mqtt.Client(client_id=MQTT_CONFIG["client_id"])
        self.connected = False
        self.message_callbacks = {}
        
        # Sett opp callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Status topic for Samantha å vite om vi er online
        self.STATUS_TOPIC = "duck/vision/status"
        
        # LWT (Last Will and Testament) - brokeren publiserer dette automatisk
        # når klienten forsvinner uventet
        self.client.will_set(
            self.STATUS_TOPIC,
            payload=json.dumps({"status": "offline"}),
            qos=1,
            retain=True
        )
        
        # Autentisering hvis konfigurert
        if MQTT_CONFIG["username"]:
            self.client.username_pw_set(
                MQTT_CONFIG["username"], 
                MQTT_CONFIG["password"]
            )
    
    def connect(self) -> bool:
        """Koble til MQTT broker"""
        try:
            print(f"Kobler til MQTT broker: {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
            self.client.connect(
                MQTT_CONFIG["broker"],
                MQTT_CONFIG["port"],
                keepalive=60
            )
            self.client.loop_start()
            
            # Vent på connection
            for _ in range(50):  # 5 sekunder timeout
                if self.connected:
                    return True
                time.sleep(0.1)
            
            return False
        except Exception as e:
            print(f"❌ MQTT tilkobling feilet: {e}")
            return False
    
    def disconnect(self):
        """Koble fra MQTT broker"""
        # Publiser offline-status før frakobling
        try:
            self.client.publish(
                self.STATUS_TOPIC,
                payload=json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )
            time.sleep(0.1)  # La meldingen bli sendt
        except Exception:
            pass
        self.client.loop_stop()
        self.client.disconnect()
        print("MQTT frakoblet")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback når tilkoblet"""
        if rc == 0:
            self.connected = True
            print("✓ MQTT tilkoblet!")
            # Publiser online-status (retained slik at Samantha vet vi er her)
            self.client.publish(
                self.STATUS_TOPIC,
                payload=json.dumps({"status": "online"}),
                qos=1,
                retain=True
            )
            print("  📡 Publisert online-status til duck/vision/status")
            # Subscribe til Samantha's kommandoer
            self.client.subscribe(TOPICS["samantha_to_vision"])
            self.client.subscribe(TOPICS["samantha_speaking"])
            self.client.subscribe(TOPICS["samantha_conversation"])
            print(f"  Lytter på: {TOPICS['samantha_to_vision']}")
            print(f"  Lytter på: {TOPICS['samantha_speaking']}")
            print(f"  Lytter på: {TOPICS['samantha_conversation']}")
        else:
            print(f"❌ MQTT tilkobling feilet med kode: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback når frakoblet"""
        self.connected = False
        if rc != 0:
            print(f"⚠️  Uventet frakobling (kode: {rc}). Prøver å koble til igjen...")
    
    def _on_message(self, client, userdata, msg):
        """Callback når melding mottas"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            print(f"📨 Mottatt melding på {topic}: {payload}")
            
            # Kall registrerte callbacks
            if topic in self.message_callbacks:
                for callback in self.message_callbacks[topic]:
                    callback(payload)
        except Exception as e:
            print(f"❌ Feil ved behandling av melding: {e}")
    
    def register_callback(self, topic: str, callback: Callable):
        """Registrer en callback for et topic"""
        if topic not in self.message_callbacks:
            self.message_callbacks[topic] = []
        self.message_callbacks[topic].append(callback)
    
    def send_face_detected(self, person_name: str = None, is_known: bool = False):
        """Send melding om ansiktsdeteksjon til Samantha"""
        message = {
            "event": "face_detected",
            "timestamp": time.time(),
            "person_name": person_name,
            "is_known": is_known,
        }
        self._publish(TOPICS["face_detected"], message)
    
    def send_object_detected(self, object_name: str, confidence: float, all_objects: list = None):
        """Send melding om objektdeteksjon til Samantha"""
        message = {
            "event": "object_detected",
            "timestamp": time.time(),
            "object_name": object_name,  # Hovedobjekt
            "confidence": confidence,
            "all_objects": all_objects or []  # Liste med alle objekter
        }
        self._publish(TOPICS["object_detected"], message)
    
    def send_speaker_recognized(self, name: str, confidence: float, speech_duration: float = 0.0):
        """Send melding om stemmegjenkjenning"""
        message = {
            "event": "speaker_recognized",
            "timestamp": time.time(),
            "name": name,
            "confidence": confidence,
            "speech_duration": speech_duration,
        }
        self._publish(TOPICS["speaker_recognized"], message)
    
    def send_voice_profile_created(self, name: str, success: bool, speech_duration: float = 0.0):
        """Send melding om at stemmeprofil er opprettet"""
        message = {
            "event": "voice_profile_created",
            "timestamp": time.time(),
            "name": name,
            "success": success,
            "speech_duration": speech_duration,
        }
        self._publish(TOPICS["voice_profile_created"], message)
    
    def send_event(self, event_type: str, data: Dict[str, Any]):
        """Send generisk event til Samantha"""
        message = {
            "event": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        self._publish(TOPICS["vision_to_samantha"], message)
    
    def _publish(self, topic: str, message: Dict[str, Any]):
        """Publiser melding til MQTT broker"""
        try:
            payload = json.dumps(message, ensure_ascii=False)
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"📤 Sendt til {topic}: {message.get('event', 'unknown')}")
            else:
                print(f"❌ Feil ved sending til {topic}: {result.rc}")
        except Exception as e:
            print(f"❌ Kunne ikke publisere melding: {e}")


# Test funksjon
if __name__ == "__main__":
    print("Testing Duck-Vision MQTT Client...")
    
    mqtt_client = DuckMQTT()
    
    if mqtt_client.connect():
        print("\n✓ MQTT klient fungerer!")
        
        # Test sending
        mqtt_client.send_face_detected("Test Person", is_known=False)
        time.sleep(1)
        mqtt_client.send_object_detected("flaske", 0.95)
        time.sleep(1)
        
        mqtt_client.disconnect()
    else:
        print("\n❌ Kunne ikke koble til MQTT broker")
