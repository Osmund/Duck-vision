# 🦆 Duck-Vision

**AI-drevet syn for Samantha - Din personlige and-assistent**

Duck-Vision er et Raspberry Pi 5-basert visjonssystem med Pi AI Camera som gir Samantha (din and-assistent på Pi 4) evnen til å se og gjenkjenne ansikter og objekter. Systemet kommuniserer via MQTT og kan lære å kjenne igjen personer ved navn.

---

## 🎯 Funksjoner

### Ansiktsgjenkjenning
- **Automatisk deteksjon**: Kontinuerlig scanning etter ansikter
- **Gjenkjennelse**: Identifiserer kjente personer med navn
- **Læring**: Samantha kan spørre om å få huske nye personer
- **Personlig hilsen**: "Hei [navn]!" når kjente personer oppdages

### Objektgjenkjenning
- **YOLOv8**: State-of-the-art objektdeteksjon
- **80+ objekter**: Gjenkjenner vanlige hverdagsobjekter
- **Norske navn**: Alle objekter oversatt til norsk
- **På forespørsel**: Aktiveres når du viser noe til Samantha

### MQTT-kommunikasjon
- **Real-time events**: Sender deteksjoner til Samantha umiddelbart
- **Kommandoer**: Mottar instruksjoner fra Samantha
- **Workflow-integrasjon**: Sømløs kommunikasjon mellom Pi 4 og Pi 5

---

## 🔧 Maskinvare

### Påkrevd
- **Raspberry Pi 5** (4GB eller 8GB anbefalt)
- **Raspberry Pi AI Camera** (eller Camera Module 3)
- **microSD-kort** (32GB+, Class 10)
- **Strømforsyning** (5V/5A USB-C for Pi 5)

### Nettverk
- Begge Pi-er må være på samme nettverk
- MQTT broker på Pi 4 (Samantha) eller ekstern broker

---

## 📦 Installasjon

### 1. System-forberedelser

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. System-avhengigheter

```bash
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    libopencv-dev \
    cmake \
    build-essential \
    libatlas-base-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libharfbuzz0b \
    libwebp7 \
    libtiff6 \
    libjasper-dev \
    libilmbase-dev \
    libopenexr-dev \
    libgstreamer1.0-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev
```

### 3. Virtuelt miljø

```bash
cd /home/admog/Code/Duck-Vision
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Python-pakker

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Merk**: Installasjon av `dlib` og `face-recognition` kan ta 10-30 minutter på Pi 5 pga kompilering.

### 5. Konfigurer miljøvariabler

```bash
cp .env.example .env
nano .env
```

Rediger `.env` og sett riktig IP-adresse til Pi 4 (Samantha):

```
MQTT_BROKER=192.168.1.100  # Bytt til Samantha's IP
```

### 6. Test komponenter

Test kamera:
```bash
python camera.py
```

Test MQTT (krever at broker kjører på Pi 4):
```bash
python mqtt_client.py
```

Test ansiktsgjenkjenning:
```bash
python face_recognition_module.py
```

Test objektdeteksjon (laster ned modell første gang):
```bash
python object_detection.py
```

---

## 🚀 Kjøring

### Start Duck-Vision

```bash
source .venv/bin/activate
python duck_vision.py
```

### Kjør som systemd service (valgfritt)

Opprett service-fil:

```bash
sudo nano /etc/systemd/system/duck-vision.service
```

Innhold:

```ini
[Unit]
Description=Duck-Vision Camera System
After=network.target

[Service]
Type=simple
User=admog
WorkingDirectory=/home/admog/Code/Duck-Vision
ExecStart=/home/admog/Code/Duck-Vision/.venv/bin/python /home/admog/Code/Duck-Vision/duck_vision.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable og start:

```bash
sudo systemctl enable duck-vision
sudo systemctl start duck-vision
sudo systemctl status duck-vision
```

Se logger:

```bash
sudo journalctl -u duck-vision -f
```

---

## 🎮 Bruk

### Workflow: Lære nye personer

1. **Ukjent person oppdages**: Duck-Vision sender MQTT-event til Samantha
2. **Samantha spør**: "Hei, hvem er du?"
3. **Person svarer**: "Jeg heter [Navn]"
4. **Samantha spør tillatelse**: "Får jeg lov å huske deg?"
5. **Person sier ja**: Samantha sender MQTT-kommando: `learn_person` med navn
6. **Duck-Vision tar bilde**: Lagrer ansiktet i databasen
7. **Bekreftelse**: Samantha bekrefter at personen er lagret

### Workflow: Gjenkjenne objekter

1. **Hold objekt foran kamera**
2. **Si til Samantha**: "Hva er dette?"
3. **Samantha sender kommando**: `detect_object`
4. **Duck-Vision analyserer**: Detekterer objekt med YOLOv8
5. **Respons**: Samantha forteller hva objektet er

### MQTT-kommandoer (fra Samantha)

Topic: `duck/samantha/commands`

#### Lær ny person
```json
{
  "command": "learn_person",
  "name": "Osmund"
}
```

#### Detekter objekt
```json
{
  "command": "detect_object"
}
```

#### Glem person
```json
{
  "command": "forget_person",
  "name": "Osmund"
}
```

#### List kjente personer
```json
{
  "command": "list_people"
}
```

### MQTT-events (fra Duck-Vision)

Topic: `duck/vision/face`

#### Kjent person oppdaget
```json
{
  "event": "face_detected",
  "timestamp": 1738347600.123,
  "person_name": "Osmund",
  "is_known": true
}
```

#### Ukjent person oppdaget
```json
{
  "event": "face_detected",
  "timestamp": 1738347600.123,
  "person_name": null,
  "is_known": false
}
```

Topic: `duck/vision/object`

#### Objekt detektert
```json
{
  "event": "object_detected",
  "timestamp": 1738347600.123,
  "object_name": "flaske",
  "confidence": 0.95
}
```

---

## 📁 Prosjektstruktur

```
Duck-Vision/
├── .env                          # Konfigurasjon (ikke i git)
├── .env.example                  # Konfigurasjonmal
├── .gitignore
├── requirements.txt
├── README.md
│
├── config.py                     # Sentral konfigurasjon
├── duck_vision.py                # 🚀 HOVEDPROGRAM
│
├── camera.py                     # Pi AI Camera interface
├── mqtt_client.py                # MQTT-kommunikasjon
├── face_recognition_module.py    # Ansiktsgjenkjenning
├── object_detection.py           # Objektdeteksjon (YOLOv8)
│
├── data/                         # Genereres automatisk
│   ├── face_encodings.pkl        # Lagrede ansikter
│   └── known_faces/              # Bilder av kjente personer
│       ├── Osmund/
│       ├── Anna/
│       └── ...
│
└── models/                       # Genereres automatisk
    └── yolov8n.pt                # YOLOv8 modell (lastes ned)
```

---

## 🔧 Feilsøking

### Kamera fungerer ikke

```bash
# Sjekk om kamera er tilkoblet
libcamera-hello --list-cameras

# Test kamera
libcamera-still -o test.jpg
```

### MQTT-tilkobling feiler

- Sjekk at MQTT broker kjører på Pi 4
- Verifiser IP-adresse i `.env`
- Test ping: `ping 192.168.1.100`
- Sjekk firewall

### Face recognition installasjon feiler

Hvis `dlib` kompileringen feiler:

```bash
# Øk swap size for kompilering
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Sett CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# Prøv installasjon på nytt
pip install dlib
```

### YOLOv8 kjører tregt

- Pi 5 kan håndtere YOLOv8n (nano) i sanntid
- Vurder lavere oppløsning hvis det er for tregt
- Installer PyTorch for bedre ytelse

### Ansiktsgjenkjenning er unøyaktig

Juster toleranse i `.env`:

```
FACE_RECOGNITION_TOLERANCE=0.6  # Lavere = strengere (0.4-0.7)
```

---

## 🎨 Tilpasning

### Endre kameraoppløsning

I `.env`:

```
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
```

### Endre deteksjonsintervall

I `.env`:

```
FACE_DETECTION_INTERVAL=1.0  # sekunder mellom skanninger
```

### Legge til flere objekter

Objektdeteksjonen bruker YOLOv8 som støtter 80 COCO-klasser. Du kan bytte modell for flere objekter eller trene egen modell.

---

## 🔗 Integrasjon med Samantha

### På Pi 4 (Samantha-siden)

Du må legge til MQTT-håndtering i `chatgpt_voice.py` for å motta events fra Duck-Vision og sende kommandoer tilbake.

Eksempel integrasjon:

```python
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    if msg.topic == "duck/vision/face":
        data = json.loads(msg.payload)
        if not data["is_known"]:
            # Ukjent person
            speak("Hei, hvem er du?", speech_config, beak)
            # ... få navn via STT ...
            speak("Får jeg lov å huske deg?", speech_config, beak)
            # ... hvis ja, send learn_person kommando ...

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883)
mqtt_client.subscribe("duck/vision/#")
mqtt_client.loop_start()
```

---

## 📚 Teknologier

- **Python 3.11+**: Hovedspråk
- **picamera2**: Pi Camera interface
- **face_recognition**: Ansiktsgjenkjenning (basert på dlib)
- **YOLOv8 (Ultralytics)**: Objektdeteksjon
- **paho-mqtt**: MQTT-kommunikasjon
- **OpenCV**: Bildebehandling
- **NumPy**: Numeriske operasjoner

---

## 📝 Tips

- **Belysning**: God belysning forbedrer ansiktsgjenkjenning betydelig
- **Avstand**: Hold ansikt 0.5-2 meter fra kamera for beste resultat
- **Vinkel**: Se rett mot kamera når du læres inn
- **Flere bilder**: Lær samme person flere ganger fra ulike vinkler for bedre gjenkjenning

---

## 🤝 Bidra

Dette er et personlig prosjekt, men forslag og forbedringer er velkomne!

---

## 📄 Lisens

Dette prosjektet er laget for personlig bruk i Anda-prosjektet.

---

**God andeprat! 🦆**
