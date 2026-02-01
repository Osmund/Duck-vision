━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MULTI-ANGLE FACE LEARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For BEST MULIG Face Recognition Accuracy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


█ HVA ER NYE FORBEDRINGEN?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I stedet for å ta ETT bilde når vi lærer en ny person, tar vi nå 5 BILDER
med 0.8 sekunders mellomrom. Dette gir:

✅ Bedre accuracy
   - Flere vinkler = bedre matching
   - Ulike ansiktsuttrykk = mer robust
   - Ulik belysning = bedre generalisering

✅ Mer robust gjenkjenning
   - Fungerer bedre når personen beveger seg
   - Fungerer bedre med ulik belysning
   - Fungerer bedre med briller/hatt/etc

✅ Feiltoleranse
   - Hvis 1-2 bilder mislykkes, har vi fortsatt 3-4 gode
   - Minimum 60% suksess kreves (3/5)
   - Logger fremgang for hvert bilde


█ HVORDAN FUNGERER DET?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIDSLINJE (5 bilder):
──────────────────────────────────────────────────────────────────────

T+0.0s:  📸 Bilde 1/5
         "Se mot kameraet"
         
T+0.8s:  📸 Bilde 2/5
         "Beveg hodet litt til venstre"
         
T+1.6s:  📸 Bilde 3/5
         "Beveg hodet litt til høyre"
         
T+2.4s:  📸 Bilde 4/5
         "Se litt opp"
         
T+3.2s:  📸 Bilde 5/5
         "Se litt ned"
         
T+3.5s:  ✅ Ferdig! 5 face encodings lagret


LOGGING EKSEMPEL:
──────────────────────────────────────────────────────────────────────
📸 Tar 5 bilder av Bjarne...
💡 Beveg hodet litt mellom bildene (venstre, høyre, opp, ned)
  ✓ Bilde 1/5
  ✓ Bilde 2/5
  ✓ Bilde 3/5
  ⚠ Bilde 4/5: Ingen ansikt funnet, hopper over
  ✓ Bilde 5/5
✅ Lærte Bjarne med 4 bilder!


█ MQTT KOMMANDO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STANDARD (5 bilder - anbefalt):
──────────────────────────────────────────────────────────────────────
{
  "command": "learn_person",
  "name": "Bjarne"
}


MED CUSTOM ANTALL BILDER:
──────────────────────────────────────────────────────────────────────
{
  "command": "learn_person",
  "name": "Bjarne",
  "num_samples": 7
}


RASK VERSJON (3 bilder):
──────────────────────────────────────────────────────────────────────
{
  "command": "learn_person",
  "name": "Bjarne",
  "num_samples": 3
}


BESTE ACCURACY (10 bilder):
──────────────────────────────────────────────────────────────────────
{
  "command": "learn_person",
  "name": "Bjarne",
  "num_samples": 10
}


█ SAMANTHA INTEGRASJON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIALOG EKSEMPEL:
──────────────────────────────────────────────────────────────────────

Bruker: "Hei Samantha"
Samantha: "Hei, hvem er du?"
Bruker: "Jeg heter Bjarne"
Samantha: "Hyggelig å møte deg, Bjarne! Kan jeg lagre deg?"
         "Jeg tar 5 bilder - kan du bevege hodet litt mellom bildene?"
Bruker: "Ja"
Samantha: → Sender learn_person command
         [0.0s] "Første bilde..."
         [0.8s] "Bilde 2 - se litt til venstre..."
         [1.6s] "Bilde 3 - se litt til høyre..."
         [2.4s] "Bilde 4 - se litt opp..."
         [3.2s] "Bilde 5 - se litt ned..."
         [3.5s] "Ferdig! Nå husker jeg deg, Bjarne!"


KODE EKSEMPEL:
──────────────────────────────────────────────────────────────────────
def on_user_consent_to_learn(self, name: str):
    """Når bruker samtykker til å bli lagret"""
    
    # Informer bruker
    self.speak(f"Flott! Jeg tar 5 bilder av deg.")
    self.speak("Beveg hodet litt mellom bildene.")
    
    # Send kommando (5 bilder default)
    self.vision.learn_person(name, num_samples=5)
    
    # Alternativt: raskere versjon
    # self.vision.learn_person(name, num_samples=3)
    
    # Alternativt: beste accuracy
    # self.vision.learn_person(name, num_samples=10)


█ TEKNISKE DETALJER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LAGRING:
──────────────────────────────────────────────────────────────────────
Alle encodings lagres i minne og på disk:

known_faces/
└── Bjarne/
    ├── 1738364274.jpg       # Bilde 1
    ├── 1738364274.pkl       # Encoding 1
    ├── 1738364275.jpg       # Bilde 2
    ├── 1738364275.pkl       # Encoding 2
    ├── 1738364276.jpg       # Bilde 3
    ├── 1738364276.pkl       # Encoding 3
    ├── 1738364277.jpg       # Bilde 4
    └── 1738364277.pkl       # Encoding 4


MATCHING:
──────────────────────────────────────────────────────────────────────
Ved face recognition:
1. Detect ansikt i live frame
2. Encode detected face
3. Compare mot ALLE encodings for hver person
4. Velg beste match
5. Return navn hvis distance < 0.6

Med 5 encodings per person:
- Mye høyere sjanse for god match
- Mer robust mot ulike vinkler
- Bedre håndtering av tilbehør (briller, hatt)


PERFORMANCE:
──────────────────────────────────────────────────────────────────────
- Capture time: 5 bilder × 0.8s = 4 sekunder totalt
- Processing per bilde: ~100ms face encoding
- Total learn time: ~4.5 sekunder

Recognition time (unchanged):
- Face detection: ~100ms (face_recognition library)
- Matching: ~1-5ms per encoding × 5 = 5-25ms
- Fortsatt real-time performance!


█ TESTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST 1: Manuel test
──────────────────────────────────────────────────────────────────────
# På Pi 4 (Samantha):
mosquitto_pub -h oDuckberry-vision.local -t duck/vision/command \
  -m '{"command":"learn_person", "name":"TestPerson", "num_samples":5}'

# Overvåk events:
mosquitto_sub -h oDuckberry-vision.local -t duck/vision/events -v

# Forventet output:
# - person_learned event med "samples": 5


TEST 2: Verifiser lagrede bilder
──────────────────────────────────────────────────────────────────────
# På Pi 5:
ls -la /home/admog/Code/Duck-Vision/known_faces/TestPerson/

# Skal vise 5 jpg + 5 pkl filer


TEST 3: Test recognition
──────────────────────────────────────────────────────────────────────
# På Pi 4:
mosquitto_pub -h oDuckberry-vision.local -t duck/vision/command \
  -m '{"command":"check_person"}'

# Skal returnere face_recognized med TestPerson


█ ANBEFALINGER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTIMAL SETTING FOR ULIKE SCENARIOS:
──────────────────────────────────────────────────────────────────────

🏠 Hjemmebruk (family members):
   num_samples: 5-7
   - God balanse mellom tid og accuracy
   - Nok data for robust gjenkjenning
   - Ikke for lang ventetid

🏢 Kontor/Business:
   num_samples: 3
   - Raskere onboarding
   - Akseptabel accuracy
   - Folk er ikke så tålmodige

🔒 Sikkerhetskritisk:
   num_samples: 10
   - Beste mulige accuracy
   - Minimerer false positives
   - Verdt den ekstra tiden

🎯 Testing/Development:
   num_samples: 3
   - Rask iterasjon
   - Lett å slette og prøve igjen
   - God nok for testing


TIPS FOR BESTE RESULTAT:
──────────────────────────────────────────────────────────────────────

✅ GOD BELYSNING
   - Naturlig lys er best
   - Unngå backlight
   - Jevn belysning i ansiktet

✅ ULIKE VINKLER
   - Beveg hodet mellom bilder
   - Venstre → Senter → Høyre
   - Opp → Senter → Ned

✅ NATURLIGE UTTRYKK
   - Smile litt på noen bilder
   - Seriøs på andre
   - Variert = bedre

❌ UNNGÅ
   - For rask bevegelse (motion blur)
   - Store endringer (ta av briller mellom bilder)
   - Dramatisk lysendring


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ MULTI-ANGLE LEARNING IMPLEMENTERT OG KJØRER!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Service: Running (PID 308148)
Default: 5 bilder per person
Ready to test! 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
