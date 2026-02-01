━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DUCK-VISION → SAMANTHA INTEGRASJONSGUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dato: 31. januar 2026
Fra: Duck-Vision Team (Pi 5 - oDuckberry-vision.local)
Til: Samantha Team (Pi 4 - oDuckberry-2.local)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ KONSEPTET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"Vi vil ha minst mulig latency" - Dette var utgangspunktet.

Vi har bygget et tre-lags vision system som gir Samantha både:
  ⚡️ Ultra-rask bevissthet (0.6ms)
  🧠 Dyp forståelse (5.3s)
  👤 Ansiktsgjenkjenning (hybrid)


█ ARKITEKTUR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────┐
│  SAMANTHA (Pi 4)                    DUCK-VISION (Pi 5)              │
│  oDuckberry-2.local                 oDuckberry-vision.local         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  chatgpt_voice.py                   IMX500 AI Camera                │
│    ↓                                   ↓                            │
│  DuckVisionHandler      ←MQTT→     duck_vision.py                   │
│  (integration)                         ↓                            │
│                                    ┌────────────────────┐            │
│  3 hovedfunksjoner:                │ 1. IMX500 (0.6ms)  │            │
│                                    │    - NanoDet Plus  │            │
│  1. look_around()      ←────────   │    - 35% threshold │            │
│     "Hva ser du?"                  │    - 80 objekter   │            │
│                                    └────────────────────┘            │
│  2. analyze_scene()    ←────────   ┌────────────────────┐            │
│     "Beskriv rommet"               │ 2. OpenAI Vision   │            │
│                                    │    - GPT-4o-mini   │            │
│  3. Face recognition   ←────────   │    - 512x384       │            │
│     "Hvem er du?"                  │    - rpicam-still  │            │
│                                    └────────────────────┘            │
│                                    ┌────────────────────┐            │
│                                    │ 3. Face Recog      │            │
│                                    │    - Hybrid system │            │
│                                    │    - Learning flow │            │
│                                    └────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘


█ KOMPONENTENE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  IMX500 OBJECT DETECTION
────────────────────────────────────────────────────────────────────────
Hva:      On-chip AI objekt-deteksjon
Model:    NanoDet Plus 416x416
Latency:  0.6ms (ja, under 1 millisekund!)
Objekter: 80 COCO classes (person, kopp, sofa, laptop, osv.)
Threshold: 35% (balansert mellom sensitivitet og noise)

Hvorfor så raskt?
- AI kjører PÅ kamera-chippen (ikke Pi 5 CPU)
- Ingen bildeprosessering nødvendig
- Direkte neural network output

Bruksområde:
- Kontinuerlig rombevissthet
- Rask respons på "Hva ser du?"
- Bevegelsesdeteksjon


2️⃣  OPENAI VISION (GPT-4O-MINI)
────────────────────────────────────────────────────────────────────────
Hva:      Dyp scene-analyse med GPT-4o-mini
Latency:  ~5.3 sekunder
Kostnad:  $0.0004 per analyse (10x billigere enn GPT-4o)
Kvalitet: Utmerket - detaljerte beskrivelser på norsk

Hvorfor GPT-4o-mini?
- 10x billigere enn GPT-4o
- Nesten samme kvalitet
- God nok for scene-beskrivelser

Hvorfor rpicam-still?
- Picamera2 med IMX500 gir blå tint (dårlig ISP)
- rpicam-still har bedre bildeprosessering
- Korrekte farger og hvitbalanse

Optimalisering:
- 512x384 oppløsning (god nok for GPT-4o-mini)
- 500ms stabiliseringstid
- JPEG quality 85
- "low" detail mode

Output eksempel:
"Bildet viser en mann som sitter på en sofa i et rom med trevegger. 
Han har grått skjegg og bruker en svart caps og en mørk t-skjorte. 
Mannen ser ned på en laptop som han har foran seg. Rommet er pyntet 
med flere bilder og rammer på veggen. Det er også en klokke på veggen, 
og en grønn lampe gir et mykt lys til området."

Bruksområde:
- "Beskriv rommet detaljert"
- "Hvilken farge har sofaen?"
- "Hva gjør personen?"
- Kontekstuell forståelse for samtaler


3️⃣  FACE RECOGNITION
────────────────────────────────────────────────────────────────────────
Hva:      Hybrid IMX500 detection + face_recognition library
System:   Kontinuerlig ansikts-scanning
Database: /home/admog/Code/Duck-Vision/known_faces/

Workflow:
1. IMX500 detekterer person (kontinuerlig)
2. Hvis ukjent ansikt → publiser "unknown_person" event
3. Samantha spør: "Hei! Hvem er du?"
4. Bruker svarer: "Jeg heter Thomas"
5. Samantha sender MQTT: {"command": "learn_person", "name": "Thomas"}
6. Duck-Vision tar bilde og lagrer i database
7. Neste gang → "Hei Thomas!"

Bruksområde:
- Personlig gjenkjenning
- Adaptiv learning (nye personer)
- Sikkerhet/tilgangskontroll


█ MQTT API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MQTT Broker: oDuckberry-2.local:1883
QoS: 1 (guaranteed delivery)


📤 KOMMANDOER (Samantha → Duck-Vision)
────────────────────────────────────────────────────────────────────────
Topic: duck/vision/command

1. Look around (IMX500)
   {
     "command": "look_around"
   }

2. Scene analysis (OpenAI Vision)
   {
     "command": "analyze_scene"
   }
   
   Med spesifikt spørsmål:
   {
     "command": "analyze_scene",
     "question": "Hvilken farge har sofaen?"
   }

3. Learn person (Face Recognition)
   {
     "command": "learn_person",
     "name": "Thomas"
   }


📥 EVENTS (Duck-Vision → Samantha)
────────────────────────────────────────────────────────────────────────
Topic: duck/vision/events

1. Objects detected (IMX500)
   {
     "event": "objects_detected",
     "timestamp": "2026-01-31T22:18:24.842",
     "primary_object": {
       "class": "person",
       "confidence": 0.73,
       "norwegian": "person"
     },
     "all_objects": [
       {"class": "person", "confidence": 0.73, "norwegian": "person"},
       {"class": "couch", "confidence": 0.50, "norwegian": "sofa"}
     ],
     "inference_time_ms": 0.6
   }

2. OpenAI Vision analysis
   {
     "event": "openai_analysis",
     "timestamp": "2026-01-31T22:18:24.842",
     "description": "Bildet viser en mann som sitter...",
     "question": null,  // eller spesifikt spørsmål
     "tokens_used": {
       "prompt_tokens": 2800,
       "completion_tokens": 207,
       "total_tokens": 3007
     }
   }

3. Face recognized
   {
     "event": "face_recognized",
     "timestamp": "2026-01-31T22:18:24.842",
     "name": "Thomas",
     "confidence": 0.85
   }

4. Unknown person
   {
     "event": "unknown_person",
     "timestamp": "2026-01-31T22:18:24.842"
   }

5. Person learned
   {
     "event": "person_learned",
     "timestamp": "2026-01-31T22:18:24.842",
     "name": "Thomas"
   }

6. Errors
   {
     "event": "openai_analysis_error",
     "error": "API timeout - tok for lang tid"
   }


█ INTEGRASJON I SAMANTHA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FILER SOM SKAL KOPIERES TIL PI 4:
────────────────────────────────────────────────────────────────────────
1. src/duck_vision_integration.py
   - Kopi til: ~/Code/chatgpt-duck-py/
   - Dette er integrasjons-handleren for Samantha


KODE FOR SAMANTHA (chatgpt_voice.py):
────────────────────────────────────────────────────────────────────────

# 1. Import
from duck_vision_integration import DuckVisionHandler

# 2. Initialiser (i __init__)
self.vision = DuckVisionHandler(mqtt_broker="localhost", mqtt_port=1883)

# 3. Registrer AI tools

tools = [
    {
        "type": "function",
        "function": {
            "name": "look_around",
            "description": "Se hva som er i rommet akkurat nå. Ultra-rask (0.6ms). Bruk dette for enkle spørsmål som 'Hva ser du?' eller 'Er det noen her?'",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_scene",
            "description": "Få en detaljert beskrivelse av scenen med OpenAI Vision. Tar ~5 sekunder. Bruk for spørsmål som 'Beskriv rommet', 'Hvilken farge har sofaen?', 'Hva gjør personen?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Et spesifikt spørsmål om scenen (valgfritt). Hvis ikke gitt, får du en generell beskrivelse."
                    }
                },
                "required": []
            }
        }
    }
]

# 4. Implementer tool handlers

def handle_tool_call(self, tool_name, arguments):
    if tool_name == "look_around":
        result = self.vision.look_around(timeout=5.0)
        if result:
            if result["object_count"] == 0:
                return "Jeg ser ingenting spesielt akkurat nå."
            elif result["object_count"] == 1:
                obj = result["objects"][0]
                return f"Jeg ser en {obj['norwegian']} ({obj['confidence']*100:.0f}% sikker)."
            else:
                objects = ", ".join([f"{o['norwegian']}" for o in result["objects"][:3]])
                return f"Jeg ser {objects} og {result['object_count']-3} andre ting."
        else:
            return "Jeg fikk ikke svar fra kameraet."
    
    elif tool_name == "analyze_scene":
        question = arguments.get("question")
        result = self.vision.analyze_scene(question=question, timeout=15.0)
        if result:
            return result
        else:
            return "Jeg klarte ikke å analysere scenen."


EKSEMPLER PÅ BRUK:
────────────────────────────────────────────────────────────────────────

Bruker: "Hva ser du?"
Samantha: [Kaller look_around()]
→ "Jeg ser en person og en sofa."

Bruker: "Beskriv rommet detaljert"
Samantha: [Kaller analyze_scene()]
→ "Bildet viser en mann som sitter på en sofa i et rom med trevegger..."

Bruker: "Hvilken farge har sofaen?"
Samantha: [Kaller analyze_scene(question="Hvilken farge har sofaen?")]
→ "Sofaen er mørk grønn/teal med et teppe over."

Bruker: "Hvem er jeg?"
[Ukjent ansikt detektert]
Samantha: [Mottar unknown_person event] → "Hei! Hvem er du?"
Bruker: "Jeg heter Thomas"
Samantha: [Sender learn_person command]
→ "Hyggelig å møte deg, Thomas! Nå kjenner jeg deg igjen."

[Neste gang Thomas kommer]
Samantha: [Mottar face_recognized event med name="Thomas"]
→ "Hei Thomas! Hyggelig å se deg igjen!"


█ YTELSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LATENCY:
────────────────────────────────────────────────────────────────────────
IMX500 look_around():      0.6ms   ⚡️⚡️⚡️⚡️⚡️
OpenAI analyze_scene():    5.3s    🧠🧠🧠
Face recognition:          ~100ms  👤

KOSTNAD (OpenAI Vision):
────────────────────────────────────────────────────────────────────────
Per analyse: $0.0004
100 analyser: $0.04
1000 analyser: $0.40

Sammenligning med GPT-4o:
GPT-4o:       $0.004 per analyse
GPT-4o-mini:  $0.0004 per analyse (10x billigere!)

TRADE-OFFS:
────────────────────────────────────────────────────────────────────────
✅ IMX500: Lynrask, gratis, men begrenset til 80 objektklasser
✅ OpenAI: Dyp forståelse, dyrt (men ok), 5 sekunders ventetid
✅ Hybrid: Best of both worlds!


█ STRATEGI FOR SAMANTHA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BRUK IMX500 for:
────────────────────────────────────────────────────────────────────────
- "Hva ser du?"
- "Er det noen her?"
- "Hvor mange personer er det?"
- Kontinuerlig bevissthet
- Rask feedback

BRUK OPENAI VISION for:
────────────────────────────────────────────────────────────────────────
- "Beskriv rommet"
- "Hvilken farge har...?"
- "Hva gjør personen?"
- "Les teksten på..."
- Kontekstuell forståelse
- Når brukeren spør detaljerte spørsmål

BRUK FACE RECOGNITION for:
────────────────────────────────────────────────────────────────────────
- Personlig hilsen: "Hei Thomas!"
- Kontinuerlig scanning i bakgrunnen
- Unknown person → læringsflow
- Sikkerhet/tilgang


█ TEKNISKE DETALJER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HARDWARE:
────────────────────────────────────────────────────────────────────────
Raspberry Pi 5, 8GB RAM
Sony IMX500 AI Camera (4056x3040 sensor, on-chip neural network)

SOFTWARE STACK:
────────────────────────────────────────────────────────────────────────
- Python 3.11
- picamera2 (IMX500 interface)
- rpicam-still (high-quality captures)
- paho-mqtt (MQTT client)
- openai 2.16.0 (GPT-4o-mini API)
- face_recognition (face detection/recognition)
- numpy 1.26.4

SERVICE:
────────────────────────────────────────────────────────────────────────
systemd service: duck-vision.service
Status: Active (running) since 22:18:19
Auto-start: Enabled
Logs: sudo journalctl -u duck-vision -f

CONFIGURATION:
────────────────────────────────────────────────────────────────────────
.env file:
  OPENAI_API_KEY=sk-proj-...
  
config.py:
  CONFIDENCE_THRESHOLD = 0.35
  IMX500_MODEL = "imx500_network_nanodet_plus_416x416_pp.rpk"


█ FEILSØKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBLEM: look_around() returnerer None
────────────────────────────────────────────────────────────────────────
Løsning:
1. Sjekk at duck-vision service kjører:
   sudo systemctl status duck-vision
2. Sjekk MQTT connection:
   mosquitto_sub -h localhost -t duck/vision/# -v
3. Øk timeout i look_around(timeout=10.0)

PROBLEM: analyze_scene() tar for lang tid
────────────────────────────────────────────────────────────────────────
Forventet: ~5-6 sekunder
Hvis > 10 sekunder:
1. Sjekk internett-forbindelse
2. Sjekk OpenAI API status
3. Verifiser at rpicam-still fungerer:
   rpicam-still -o test.jpg -t 500 -n

PROBLEM: Face recognition ikke fungerer
────────────────────────────────────────────────────────────────────────
1. Sjekk at face_recognition er installert:
   python3 -c "import face_recognition; print('OK')"
2. Sjekk known_faces directory:
   ls -la /home/admog/Code/Duck-Vision/known_faces/
3. Test learning flow manuelt

PROBLEM: Blå tint i bilder
────────────────────────────────────────────────────────────────────────
LØST! Vi bruker rpicam-still i stedet for Picamera2.
Hvis problemet kommer tilbake:
1. Verifiser at rpicam-still brukes (sjekk logs)
2. Test manuelt: rpicam-still -o test.jpg --awb auto


█ FREMTIDIGE FORBEDRINGER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KORT SIKT:
────────────────────────────────────────────────────────────────────────
☐ Teste Gemini Flash (raskere og billigere)
☐ Cache OpenAI responses for repeterende spørsmål
☐ Multi-person face tracking
☐ Object tracking over tid

LANG SIKT:
────────────────────────────────────────────────────────────────────────
☐ Custom YOLOv8 model trent på norske husholdningsobjekter
☐ Edge-based vision model (ingen cloud API)
☐ Real-time video streaming
☐ Gesture recognition
☐ 3D depth mapping


█ KONTAKTINFORMASJON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Duck-Vision Repository:
  /home/admog/Code/Duck-Vision/

Systemd Service:
  /etc/systemd/system/duck-vision.service

Logs:
  sudo journalctl -u duck-vision -f

Integration Handler:
  src/duck_vision_integration.py

MQTT Topics:
  Command:  duck/vision/command
  Events:   duck/vision/events
  Face:     duck/vision/face


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUKSESS! 🎉
Duck-Vision er klar for integrasjon med Samantha!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
