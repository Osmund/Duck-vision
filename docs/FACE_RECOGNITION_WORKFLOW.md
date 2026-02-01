━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FACE RECOGNITION WORKFLOW - IMPLEMENTERINGSGUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dato: 31. januar 2026
System: Duck-Vision → Samantha
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ KONSEPT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workflow:
1. Bruker sier wake word ("Samantha")
2. Samantha ber Duck-Vision sjekke hvem som er der
3. Duck-Vision svarer med kjent person ELLER ukjent person
4. Hvis kjent → "Hei Osmund!"
5. Hvis ukjent → "Hei, hvem er du?"
6. Bruker svarer: "Jeg heter Bjarne"
7. Samantha: "Kan jeg lagre deg?"
8. Bruker: "Ja"
9. Samantha sender learn_person kommando
10. Duck-Vision lagrer Bjarne i database
11. Neste gang → "Hei Bjarne!"


█ DUCK-VISION SIDE (Pi 5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ ALLEREDE IMPLEMENTERT:
────────────────────────────────────────────────────────────────────────
1. Face detection (kontinuerlig i bakgrunnen)
2. Face recognition (matching mot database)
3. check_person kommando (sjekker hvem som er der NÅ)
4. learn_person kommando (lærer ny person)
5. MQTT events: unknown_person, face_recognized, person_learned


█ MQTT TOPICS OVERSIKT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────┐
│                         MQTT KOMMUNIKASJON                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SAMANTHA (Pi 4)                          DUCK-VISION (Pi 5)       │
│                                                                     │
│  Publiserer til:                          Lytter på:               │
│  duck/samantha/commands ─────────────────► duck/samantha/commands  │
│  (check_person, learn_person)                                      │
│                                                                     │
│  Lytter på:                               Publiserer til:          │
│  duck/vision/events     ◄───────────────── duck/vision/events      │
│  (face_recognized, unknown_person,                                 │
│   learning_progress, person_learned)                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

ENKELT SAGT:
1. Samantha sender KOMMANDOER til: duck/samantha/commands
2. Samantha lytter på EVENTS fra: duck/vision/events


📤 MQTT KOMMANDOER (Samantha → Duck-Vision):
────────────────────────────────────────────────────────────────────────
Topic: duck/samantha/commands  ⬅️ DETTE ER TOPIC FOR KOMMANDOER!

1. Sjekk person (kalles ved wake word)
   {
     "command": "check_person"
   }

2. Lær ny person (kalles når bruker samtykker)
   {
     "command": "learn_person",
     "name": "Bjarne",
     "num_samples": 5
   }
   
   📸 VIKTIG: Systemet tar nå 5 bilder automatisk!
   - 0.8 sekunder mellom hvert bilde
   - Personen må bevege hodet litt mellom bildene
   - Gir MYE bedre face recognition accuracy
   - Du kan justere num_samples (3-10 anbefales)


📥 MQTT EVENTS (Duck-Vision → Samantha):
────────────────────────────────────────────────────────────────────────
Topic: duck/vision/events  ⬅️ DETTE ER TOPIC Å LYTTE PÅ!

📢 VIKTIG: Samantha må subscribe til "duck/vision/events"
   Dette er hvor ALLE events kommer fra Duck-Vision!

1. Ukjent person funnet
   {
     "event": "unknown_person",
     "timestamp": "2026-01-31T23:37:57.548"
   }

2. Kjent person funnet
   {
     "event": "face_recognized",
     "timestamp": "2026-01-31T23:37:57.548",
     "name": "Osmund",
     "confidence": 0.85
   }

3. Person lært
   {
     "event": "person_learned",
     "timestamp": "2026-01-31T23:37:57.548",
     "name": "Bjarne",
     "samples": 5
   }

4. Learning progress (real-time guidance for TTS) 🆕
   {
     "event": "learning_progress",
     "timestamp": "2026-01-31T23:37:57.548",
     "name": "Bjarne",
     "step": 2,
     "total": 5,
     "instruction": "se litt til venstre"
   }
   
   📢 VIKTIG: Samantha bør si instruksjonen med TTS!
   - "Se rett frem"
   - "Se litt til venstre"
   - "Se litt til høyre"
   - osv.

5. Ingen person funnet
   {
     "event": "check_person_result",
     "timestamp": "2026-01-31T23:37:57.548",
     "found": false,
     "reason": "no_person_detected"
   }


█ SAMANTHA SIDE (Pi 4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KODE SOM MÅ LEGGES TIL:
────────────────────────────────────────────────────────────────────────

# 1. Import
from duck_vision_integration import DuckVisionHandler

# 2. Initialiser med learning progress callback
def on_learning_progress(name, step, total, instruction):
    """Kalles når Duck-Vision tar hvert bilde"""
    # Si instruksjonen til brukeren
    self.speak(instruction)
    
self.vision = DuckVisionHandler(
    mqtt_broker="oDuckberry-vision.local",  # ⬅️ Duck-Vision Pi 5 hostname
    mqtt_port=1883,
    on_learning_progress=on_learning_progress  # 🆕 Legg til denne!
)
self.waiting_for_name = False  # Flag for learning flow

# 📢 VIKTIG: DuckVisionHandler subscriber automatisk til:
#    - duck/vision/events (alle events fra Duck-Vision)
#    - duck/vision/face (face detection events)
#    - duck/vision/object (object detection events)
#
#    Og publiserer kommandoer til:
#    - duck/samantha/commands (check_person, learn_person, etc)


# 3. Event handlers
def on_wake_word_detected(self):
    """Kalles når wake word detekteres"""
    # Sjekk hvem som er der
    self.vision.check_person()
    # Vent på respons (async via MQTT events)


def on_unknown_person(self):
    """Kalles når ukjent person detekteres"""
    self.speak("Hei! Hvem er du?")
    self.waiting_for_name = True


def on_face_recognized(self, name: str):
    """Kalles når kjent person detekteres"""
    self.speak(f"Hei {name}!")
    self.waiting_for_name = False


def on_user_speech(self, text: str):
    """Kalles når bruker snakker"""
    
    if self.waiting_for_name:
        # Parse navn fra "Jeg heter Bjarne"
        name = self.extract_name(text)
        
        if name:
            self.speak(f"Hyggelig å møte deg, {name}! Kan jeg lagre deg?")
            self.pending_name = name
            # Vent på bekreftelse
        else:
            self.speak("Beklager, jeg hørte ikke navnet ditt. Hvem er du?")
    
    elif hasattr(self, 'pending_name'):
        # Bruker bekrefter/avviser lagring
        if "ja" in text.lower() or "ok" in text.lower():
            # Start learning
            self.speak("Perfekt! Vi tar 5 bilder.")
            self.speak("Beveg hodet litt når jeg ber deg om det.")
            self.vision.learn_person(self.pending_name)
            # on_learning_progress callback vil si instruksjonene
            delattr(self, 'pending_name')
            self.waiting_for_name = False
        else:
            self.speak("Ok, jeg lagrer deg ikke.")
            delattr(self, 'pending_name')
            self.waiting_for_name = False


def extract_name(self, text: str) -> str:
    """Ekstrakter navn fra setninger som 'Jeg heter Bjarne'"""
    text = text.lower()
    
    patterns = [
        r"jeg heter (\w+)",
        r"mitt navn er (\w+)",
        r"navnet mitt er (\w+)",
        r"jeg er (\w+)",
        r"^(\w+)$"  # Bare navnet
    ]
    
    import re
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).capitalize()
    
    return None


█ WORKFLOW DIAGRAM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO 1: KJENT PERSON (Osmund)
──────────────────────────────────────────────────────────────────────

┌─────────────┐                              ┌─────────────┐
│  SAMANTHA   │                              │ DUCK-VISION │
│   (Pi 4)    │                              │   (Pi 5)    │
└─────────────┘                              └─────────────┘
       │                                            │
       │  [Wake word: "Hei Samantha"]              │
       │────────────────────────────────────────►  │
       │                                            │
       │  check_person                              │
       │───────────────────────────────────────►  │
       │                                            │
       │                        [Sjekker kamera]   │
       │                        [Finner Osmund]    │
       │                                            │
       │  ◄───────────────────────────────────────│
       │        face_recognized                    │
       │        { name: "Osmund", conf: 0.85 }     │
       │                                            │
       │  "Hei Osmund!"                             │
       │                                            │


SCENARIO 2: UKJENT PERSON (Bjarne)
──────────────────────────────────────────────────────────────────────

┌─────────────┐                              ┌─────────────┐
│  SAMANTHA   │                              │ DUCK-VISION │
│   (Pi 4)    │                              │   (Pi 5)    │
└─────────────┘                              └─────────────┘
       │                                            │
       │  [Wake word: "Hei Samantha"]              │
       │────────────────────────────────────────►  │
       │                                            │
       │  check_person                              │
       │───────────────────────────────────────►  │
       │                                            │
       │                        [Sjekker kamera]   │
       │                        [Ukjent ansikt]    │
       │                                            │
       │  ◄───────────────────────────────────────│
       │        unknown_person                     │
       │                                            │
       │  "Hei! Hvem er du?"                        │
       │  [waiting_for_name = true]                 │
       │                                            │
       │  ◄────────────────────────────────────────│
       │  [User: "Jeg heter Bjarne"]               │
       │                                            │
       │  [Parse navn: "Bjarne"]                    │
       │  "Hyggelig å møte deg, Bjarne!"            │
       │  "Kan jeg lagre deg?"                      │
       │                                            │
       │  ◄────────────────────────────────────────│
       │  [User: "Ja"]                             │
       │                                            │
       │  "Perfekt! Vi tar 5 bilder."               │
       │  "Beveg hodet litt når jeg ber deg."       │
       │  learn_person { name: "Bjarne",            │
       │                 num_samples: 5 }           │
       │───────────────────────────────────────►  │
       │                                            │
       │                         [Bilde 1]         │
       │  ◄───────────────────────────────────────│
       │        learning_progress                  │
       │        { step: 1, instruction:            │
       │          "se rett frem" }                 │
       │                                            │
       │  "Se rett frem"                            │
       │                                            │
       │                         [0.8s delay]      │
       │                         [Bilde 2]         │
       │  ◄───────────────────────────────────────│
       │        learning_progress                  │
       │        { step: 2, instruction:            │
       │          "se litt til venstre" }          │
       │                                            │
       │  "Se litt til venstre"                     │
       │                                            │
       │                         [0.8s delay]      │
       │                         [Bilde 3]         │
       │  ◄───────────────────────────────────────│
       │        learning_progress                  │
       │        { step: 3, instruction:            │
       │          "se litt til høyre" }            │
       │                                            │
       │  "Se litt til høyre"                       │
       │                                            │
       │                         [0.8s delay]      │
       │                         [Bilde 4]         │
       │  ◄───────────────────────────────────────│
       │        learning_progress                  │
       │        { step: 4, instruction:            │
       │          "se litt opp" }                  │
       │                                            │
       │  "Se litt opp"                             │
       │                                            │
       │                         [0.8s delay]      │
       │                         [Bilde 5]         │
       │  ◄───────────────────────────────────────│
       │        learning_progress                  │
       │        { step: 5, instruction:            │
       │          "se litt ned" }                  │
       │                                            │
       │  "Se litt ned"                             │
       │                                            │
       │                         [Processing...]   │
       │  ◄───────────────────────────────────────│
       │        person_learned                     │
       │        { name: "Bjarne", samples: 5 }     │
       │                                            │
       │  "Ferdig! Nå husker jeg deg, Bjarne!"     │
       │                                            │


SCENARIO 3: NESTE GANG BJARNE KOMMER
──────────────────────────────────────────────────────────────────────

┌─────────────┐                              ┌─────────────┐
│  SAMANTHA   │                              │ DUCK-VISION │
│   (Pi 4)    │                              │   (Pi 5)    │
└─────────────┘                              └─────────────┘
       │                                            │
       │  [Wake word: "Hei Samantha"]              │
       │────────────────────────────────────────►  │
       │                                            │
       │  check_person                              │
       │───────────────────────────────────────►  │
       │                                            │
       │                        [Sjekker kamera]   │
       │                        [Finner Bjarne!]   │
       │                                            │
       │  ◄───────────────────────────────────────│
       │        face_recognized                    │
       │        { name: "Bjarne", conf: 0.92 }     │
       │                                            │
       │  "Hei Bjarne! Hyggelig å se deg igjen!"   │
       │                                            │


█ TESTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST 1: Sjekk om system fungerer
────────────────────────────────────────────────────────────────────────

På Pi 5:
sudo systemctl status duck-vision

Output skal vise: Active: active (running)


TEST 2: Test check_person manuelt
────────────────────────────────────────────────────────────────────────

På Pi 4 (Samantha-maskin):

# Send kommando til Duck-Vision:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/commands \
  -m '{"command":"check_person"}'

# Lytt på events FRA Duck-Vision:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v

Forventet output på duck/vision/events:
- Hvis kjent person: face_recognized event
- Hvis ukjent: unknown_person event
- Hvis ingen: check_person_result with found=false


TEST 3: Test learn_person
────────────────────────────────────────────────────────────────────────

På Pi 4 (Samantha-maskin):

# Send kommando:
mosquitto_pub -h oDuckberry-vision.local -t duck/samantha/commands \
  -m '{"command":"learn_person", "name":"TestPerson"}'

# Lytt på events:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v

Forventet output på duck/vision/events:
- 5x learning_progress events (ett per bilde)
- 1x person_learned event (når ferdig)

Verifiser:
ssh admog@oDuckberry-vision.local
ls /home/admog/Code/Duck-Vision/known_faces/TestPerson/


TEST 4: Full integration test
────────────────────────────────────────────────────────────────────────

1. Start Samantha
2. Si wake word
3. Sjekk at check_person kalles
4. Verifiser korrekt respons (kjent/ukjent)
5. Test learning flow (hvis ukjent)
6. Verifiser at neste gang personen gjenkjennes


█ FEILSØKING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROBLEM: check_person gir ingen respons
────────────────────────────────────────────────────────────────────────
1. Sjekk duck-vision service: sudo systemctl status duck-vision
2. Sjekk logs: sudo journalctl -u duck-vision -f
3. Verifiser MQTT: mosquitto_sub -h localhost -t duck/vision/#


PROBLEM: Får alltid unknown_person selv om person er lært
────────────────────────────────────────────────────────────────────────
1. Sjekk at personen er lagret:
   ls /home/admog/Code/Duck-Vision/known_faces/
2. Sjekk confidence threshold (default: 0.6 i FACE_CONFIG)
3. Ta nye bilder i bedre lys


PROBLEM: Face detection er treg
────────────────────────────────────────────────────────────────────────
1. Face detection er hybrid - IMX500 detekterer ansikt raskt
2. CPU encoding tar ~100ms
3. Dette er normalt - ikke for tregt for wake word use case


█ NESTE STEG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ☐ Kopier duck_vision_integration.py til Pi 4
2. ☐ Implementer event handlers i Samantha
3. ☐ Test check_person på wake word
4. ☐ Test learning flow med 5 bilder
5. ☐ Verifiser at gjenkjenning fungerer mye bedre
6. ☐ Tune num_samples hvis nødvendig (3-10 anbefalt)


█ NYE FORBEDRINGER I DENNE VERSJONEN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ MULTI-ANGLE FACE LEARNING:
- Tar nå 5 bilder automatisk når ny person læres
- 0.8 sekunder pause mellom hvert bilde
- Personen beveger hodet litt mellom bildene
- Alle 5 face encodings lagres for bedre matching
- Resulterer i MYE bedre face recognition accuracy!

✅ ROBUST LEARNING:
- Håndterer hvis noen bilder mislykkes
- Krever minimum 60% suksessrate (3/5 bilder)
- Logger fremgang for hvert bilde
- Gir tydelig feedback til bruker

✅ KONFIGURERBAR:
- Default: 5 bilder (anbefalt)
- Kan justeres i MQTT kommando: "num_samples": 3-10
- 3 bilder = raskere, men litt lavere accuracy
- 10 bilder = beste accuracy, men tar lenger tid


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ SYSTEMET ER KLART! 
Duck-Vision face recognition er fullstendig implementert og kjører.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
