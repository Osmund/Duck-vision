━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MQTT TOPICS QUICK REFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For Samantha (Pi 4) ↔ Duck-Vision (Pi 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ TOPICS OVERSIKT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────────────────────────────────────────────────────┐
│                    SAMANTHA (Pi 4 - oDuckberry-2)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PUBLISERER TIL: duck/samantha/commands                             │
│  ├─ check_person                                                    │
│  ├─ learn_person                                                    │
│  ├─ forget_person                                                   │
│  ├─ list_people                                                     │
│  ├─ look_around                                                     │
│  └─ analyze_scene                                                   │
│                                                                      │
│  LYTTER PÅ: duck/vision/#                                           │
│  ├─ duck/vision/events (VIKTIGST - alle generiske events)           │
│  │  ├─ face_recognized                                              │
│  │  ├─ unknown_person                                               │
│  │  ├─ learning_progress  🆕                                        │
│  │  ├─ person_learned                                               │
│  │  ├─ person_forgotten                                             │
│  │  ├─ check_person_result                                          │
│  │  ├─ openai_analysis                                              │
│  │  └─ openai_analysis_error                                        │
│  │                                                                   │
│  ├─ duck/vision/face (legacy face events)                           │
│  └─ duck/vision/object (object detection events)                    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                 DUCK-VISION (Pi 5 - oDuckberry-vision)               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LYTTER PÅ: duck/samantha/commands                                  │
│  └─ Mottar kommandoer fra Samantha                                  │
│                                                                      │
│  PUBLISERER TIL:                                                     │
│  ├─ duck/vision/events (primær - alle events går hit)               │
│  ├─ duck/vision/face (legacy - face detection)                      │
│  └─ duck/vision/object (legacy - object detection)                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘


█ SAMANTHA KODE EKSEMPEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
from duck_vision_integration import DuckVisionHandler

# Initialiser handler
vision = DuckVisionHandler(
    mqtt_broker="oDuckberry-vision.local",  # Pi 5 hostname
    mqtt_port=1883,
    on_learning_progress=lambda name, step, total, instruction: 
        self.speak(instruction)
)

# Connect
vision.connect()

# Send kommando
vision.check_person()  # -> publiserer til duck/samantha/commands

# Events kommer automatisk via callbacks på duck/vision/events
```


█ TESTING FRA COMMAND LINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FRA SAMANTHA (Pi 4):
──────────────────────────────────────────────────────────────────────

# Lytt på ALT fra Duck-Vision:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/# -v

# Lytt bare på events:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v

# Send check_person kommando:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/commands \
  -m '{"command":"check_person"}'

# Send learn_person kommando:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/commands \
  -m '{"command":"learn_person", "name":"TestPerson", "num_samples":5}'


FRA DUCK-VISION (Pi 5):
──────────────────────────────────────────────────────────────────────

# Lytt på kommandoer fra Samantha:
mosquitto_sub -h localhost -t duck/samantha/commands -v

# Test manuell event sending:
mosquitto_pub -h localhost -t duck/vision/events \
  -m '{"event":"face_recognized","data":{"name":"Osmund","confidence":0.85}}'


█ EVENT FORMATER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Topic: duck/vision/events
──────────────────────────────────────────────────────────────────────

FACE_RECOGNIZED:
{
  "event": "face_recognized",
  "timestamp": 1738450345.123,
  "data": {
    "name": "Osmund",
    "confidence": 0.85
  }
}

UNKNOWN_PERSON:
{
  "event": "unknown_person",
  "timestamp": 1738450345.123,
  "data": {}
}

LEARNING_PROGRESS:  🆕
{
  "event": "learning_progress",
  "timestamp": 1738450345.123,
  "data": {
    "name": "Bjarne",
    "step": 2,
    "total": 5,
    "instruction": "se litt til venstre"
  }
}

PERSON_LEARNED:
{
  "event": "person_learned",
  "timestamp": 1738450345.123,
  "data": {
    "name": "Bjarne",
    "success": true,
    "samples": 5
  }
}

CHECK_PERSON_RESULT:
{
  "event": "check_person_result",
  "timestamp": 1738450345.123,
  "data": {
    "found": false,
    "reason": "no_person_detected"
  }
}


█ KOMMANDO FORMATER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Topic: duck/samantha/commands
──────────────────────────────────────────────────────────────────────

CHECK_PERSON:
{
  "command": "check_person"
}

LEARN_PERSON:
{
  "command": "learn_person",
  "name": "Bjarne",
  "num_samples": 5
}

FORGET_PERSON:
{
  "command": "forget_person",
  "name": "Bjarne"
}

LIST_PEOPLE:
{
  "command": "list_people"
}

LOOK_AROUND:
{
  "command": "look_around"
}

ANALYZE_SCENE:
{
  "command": "analyze_scene",
  "question": "Hva ser du?"
}


█ FEILSØKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBLEM: Får ikke events fra Duck-Vision
──────────────────────────────────────────────────────────────────────

1. Sjekk at du lytter på RIKTIG topic:
   mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v
   
   IKKE: duck/vision/command (dette er feil!)

2. Sjekk at Duck-Vision kjører:
   ssh admog@oDuckberry-vision.local
   sudo systemctl status duck-vision

3. Sjekk MQTT broker:
   mosquitto_sub -h oDuckberry-2.local -t '#' -v
   (lytter på ALT)


PROBLEM: Kommandoer kommer ikke frem
──────────────────────────────────────────────────────────────────────

1. Sjekk at du sender til RIKTIG topic:
   duck/samantha/commands
   
   IKKE: duck/vision/command (dette er feil!)

2. Sjekk på Duck-Vision:
   ssh admog@oDuckberry-vision.local
   mosquitto_sub -h localhost -t duck/samantha/commands -v

3. Sjekk logs:
   sudo journalctl -u duck-vision -f


PROBLEM: DuckVisionHandler får ikke events
──────────────────────────────────────────────────────────────────────

1. Sjekk at mqtt_broker er riktig:
   mqtt_broker="oDuckberry-vision.local"  # IKKE "localhost"!

2. Sjekk at callbacks er satt:
   DuckVisionHandler(..., on_learning_progress=your_callback)

3. Test manuelt:
   mosquitto_sub -h oDuckberry-vision.local -t duck/vision/# -v


█ KONFIGURASJON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DUCK-VISION (.env):
──────────────────────────────────────────────────────────────────────
MQTT_BROKER=oDuckberry-2.local
MQTT_PORT=1883
MQTT_CLIENT_ID=duck-vision
MQTT_TOPIC_VISION_TO_SAMANTHA=duck/vision/events
MQTT_TOPIC_SAMANTHA_TO_VISION=duck/samantha/commands


SAMANTHA (config):
──────────────────────────────────────────────────────────────────────
vision = DuckVisionHandler(
    mqtt_broker="oDuckberry-vision.local",  # Duck-Vision hostname
    mqtt_port=1883
)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUICK ANSWER: Samantha lytter på "duck/vision/events"! 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
