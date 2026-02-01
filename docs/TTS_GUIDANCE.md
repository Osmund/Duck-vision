━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REAL-TIME TTS GUIDANCE FOR FACE LEARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Samantha guider brukeren gjennom prosessen!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ HVA ER NYTT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ REAL-TIME VOICE GUIDANCE
   - Duck-Vision sender "learning_progress" event for HVERT bilde
   - Samantha sier instruksjonen til brukeren
   - Perfekt timing - brukeren vet NØYAKTIG hva de skal gjøre

✅ INSTRUKSJONER PER BILDE
   Bilde 1: "Se rett frem"
   Bilde 2: "Se litt til venstre"
   Bilde 3: "Se litt til høyre"
   Bilde 4: "Se litt opp"
   Bilde 5: "Se litt ned"
   
   For flere bilder:
   Bilde 6: "Se rett frem igjen"
   Bilde 7: "Se litt til venstre og opp"
   osv.

✅ SMOOTH USER EXPERIENCE
   - Ingen gjettelek
   - Brukeren vet alltid hva som skjer
   - Profesjonell guided experience


█ IMPLEMENTERING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PÅ DUCK-VISION SIDEN (Pi 5):
──────────────────────────────────────────────────────────────────────
✅ Allerede implementert!

1. IMX500FaceRecognizer tar imot progress_callback
2. Sender event for hvert bilde med instruction
3. DuckVision videresender til MQTT som "learning_progress" event


PÅ SAMANTHA SIDEN (Pi 4):
──────────────────────────────────────────────────────────────────────

1. Legg til callback i DuckVisionHandler init:

```python
def on_learning_progress(name, step, total, instruction):
    """Kalles når Duck-Vision tar hvert bilde"""
    # Si instruksjonen til brukeren
    self.speak(instruction)

self.vision = DuckVisionHandler(
    mqtt_broker="localhost", 
    mqtt_port=1883,
    on_learning_progress=on_learning_progress  # 🆕 Legg til!
)
```

2. Når bruker samtykker til lagring:

```python
if "ja" in text.lower() or "ok" in text.lower():
    # Start learning med voice guidance
    self.speak("Perfekt! Vi tar 5 bilder.")
    self.speak("Beveg hodet litt når jeg ber deg om det.")
    
    # Start learning - callbacks vil håndtere instruksjonene
    self.vision.learn_person(self.pending_name, num_samples=5)
```

3. Når alt er ferdig (listen for person_learned event):

```python
def on_person_learned(self, name, samples):
    self.speak(f"Ferdig! Nå husker jeg deg, {name}!")
```


█ MQTT EVENT FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAMANTHA SENDER:
──────────────────────────────────────────────────────────────────────
Topic: duck/vision/command
{
  "command": "learn_person",
  "name": "Bjarne",
  "num_samples": 5
}


DUCK-VISION SENDER (for hvert bilde):
──────────────────────────────────────────────────────────────────────
Topic: duck/vision/events

Event 1 (Bilde 1):
{
  "event": "learning_progress",
  "timestamp": "2026-01-31T23:55:27.891",
  "name": "Bjarne",
  "step": 1,
  "total": 5,
  "instruction": "se rett frem"
}

Event 2 (0.8s senere):
{
  "event": "learning_progress",
  "timestamp": "2026-01-31T23:55:28.691",
  "name": "Bjarne",
  "step": 2,
  "total": 5,
  "instruction": "se litt til venstre"
}

... (3 flere events) ...

Final event:
{
  "event": "person_learned",
  "timestamp": "2026-01-31T23:55:31.500",
  "name": "Bjarne",
  "samples": 5
}


█ BRUKER OPPLEVELSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIDLIGERE (uten voice guidance):
──────────────────────────────────────────────────────────────────────
Bruker: "Ja, du kan lagre meg"
Samantha: "Flott! Hold deg stille..."
[Lang pause... bruker usikker på hva som skjer]
Samantha: "Ferdig!"


NYE OPPLEVELSE (med voice guidance):
──────────────────────────────────────────────────────────────────────
Bruker: "Ja, du kan lagre meg"

Samantha: "Perfekt! Vi tar 5 bilder."
Samantha: "Beveg hodet litt når jeg ber deg om det."

[0.0s] Samantha: "Se rett frem"
       💡 Bruker vet NØYAKTIG hva de skal gjøre

[0.8s] Samantha: "Se litt til venstre"
       💡 Bruker dreier hodet til venstre

[1.6s] Samantha: "Se litt til høyre"
       💡 Bruker dreier hodet til høyre

[2.4s] Samantha: "Se litt opp"
       💡 Bruker ser opp

[3.2s] Samantha: "Se litt ned"
       💡 Bruker ser ned

[4.0s] Samantha: "Ferdig! Nå husker jeg deg, Bjarne!"
       ✅ Bruker er fornøyd og vet at det gikk bra


█ INSTRUKSJONER FOR ULIKE NUM_SAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3 BILDER (rask versjon):
──────────────────────────────────────────────────────────────────────
1. "se rett frem"
2. "se litt til venstre"
3. "se litt til høyre"


5 BILDER (anbefalt):
──────────────────────────────────────────────────────────────────────
1. "se rett frem"
2. "se litt til venstre"
3. "se litt til høyre"
4. "se litt opp"
5. "se litt ned"


7 BILDER (bedre):
──────────────────────────────────────────────────────────────────────
1. "se rett frem"
2. "se litt til venstre"
3. "se litt til høyre"
4. "se litt opp"
5. "se litt ned"
6. "se rett frem igjen"
7. "se litt til venstre og opp"


10 BILDER (best):
──────────────────────────────────────────────────────────────────────
1. "se rett frem"
2. "se litt til venstre"
3. "se litt til høyre"
4. "se litt opp"
5. "se litt ned"
6. "se rett frem igjen"
7. "se litt til venstre og opp"
8. "se litt til høyre og ned"
9. "smil litt"
10. "seriøst uttrykk"


█ TESTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST 1: Se events i real-time
──────────────────────────────────────────────────────────────────────
# Terminal 1 - Overvåk events:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v

# Terminal 2 - Start learning:
mosquitto_pub -h oDuckberry-vision.local -t duck/vision/command \
  -m '{"command":"learn_person", "name":"TestPerson", "num_samples":5}'

# Du skal se:
# - learning_progress events (5 stk)
# - person_learned event (1 stk)


TEST 2: Komplett workflow
──────────────────────────────────────────────────────────────────────
1. Si wake word til Samantha
2. Hun spør "hvem er du?"
3. Si et navn
4. Hun spør "kan jeg lagre deg?"
5. Si "ja"
6. Hun sier: "Perfekt! Vi tar 5 bilder."
7. Hun guider deg: "Se rett frem", "Se litt til venstre", osv.
8. Hun sier: "Ferdig! Nå husker jeg deg!"


█ FORDELER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ BEDRE UX
   - Bruker vet alltid hva som skjer
   - Ingen gjettelek eller usikkerhet
   - Profesjonell guided experience

✅ BEDRE DATA QUALITY
   - Brukeren gjør NØYAKTIG hva systemet ber om
   - Bedre variasjon i vinkler
   - Resulterer i bedre face recognition

✅ RASKERE PROSESS
   - Bruker trenger ikke tenke
   - Følger instruksjonene direkte
   - Mindre sjanse for feil

✅ SKALERBART
   - Fungerer for 3-10 bilder
   - Instruksjoner tilpasser seg antall
   - Konsistent opplevelse


█ TEKNISKE DETALJER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CALLBACK CHAIN:
──────────────────────────────────────────────────────────────────────
1. IMX500FaceRecognizer.add_person() 
   → Calls self.progress_callback(progress_dict)
   
2. DuckVision._on_learning_progress()
   → Receives progress_dict
   → Sends MQTT event "learning_progress"
   
3. DuckVisionHandler._handle_generic_event()
   → Receives MQTT event
   → Calls self.on_learning_progress(name, step, total, instruction)
   
4. Samantha.on_learning_progress()
   → Receives instruction
   → self.speak(instruction)
   
5. User hears instruction and follows it!


TIMING:
──────────────────────────────────────────────────────────────────────
- Capture: ~50ms per image
- MQTT latency: ~10-20ms
- TTS latency: ~300-500ms (varies)
- User movement: ~800ms pause between images

Total per image: ~1 second
Total for 5 images: ~5 seconds
Perfect timing for smooth experience!


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ REAL-TIME TTS GUIDANCE IMPLEMENTERT OG KJØRER!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service: Running (PID 308291)
Feature: learning_progress events sendes for hvert bilde
Ready: Samantha kan nå guide brukeren gjennom face learning! 🎤
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
