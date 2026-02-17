# Quick Reference: Duck-Vision Service

## 🚀 Fersk installasjon (fra scratch)

```bash
cd ~/Code
git clone https://github.com/Osmund/Duck-vision.git
cd Duck-vision
./setup.sh                    # Installerer ALT automatisk
nano .env                     # Legg inn API-nøkler
```

## 👤 Registrer ansikt og stemme

```bash
source .venv/bin/activate

# Stopp tjenesten først (frigjør kameraet)
sudo systemctl stop duck-vision

# Ansikt: 5 bilder, du trykker ENTER mellom hvert
python3 scripts/register_face.py "Åsmund"

# Stemme: 3 tekster, du leser høyt
python3 scripts/register_voice.py "Åsmund"

# Test at du blir gjenkjent
python3 scripts/test_recognition.py

# Start tjenesten igjen
sudo systemctl start duck-vision
```

## 🔧 Tjeneste-kommandoer

```bash
sudo systemctl start duck-vision      # Start
sudo systemctl stop duck-vision       # Stopp
sudo systemctl restart duck-vision    # Restart
sudo systemctl status duck-vision     # Status
sudo journalctl -u duck-vision -f     # Live logger
```

## 📁 Viktige stier

- **Kildekode:** `src/`
- **Skript:** `scripts/` (register_face, register_voice, test_recognition)
- **Demoer:** `demos/`
- **Ansiktsdata:** `data/known_faces/`
- **Stemmeprofiler:** `data/known_voices/`
- **Konfigurasjon:** `.env`
- **Service-fil:** `duck-vision.service`

## ⚙️ .env konfigurasjon

```ini
# MQTT (broker kjører på Pi 4)
MQTT_BROKER=oduckberry-2.local
MQTT_PORT=1883

# API-nøkler
OPENAI_API_KEY=sk-...
AZURE_TTS_KEY=...
AZURE_TTS_REGION=westeurope
```

## 📚 Full dokumentasjon

Se `docs/`-mappen:
- `INTEGRATION_GUIDE.md` - Pi 4 integrasjon
- `ARKITEKTUR_ANBEFALINGER.md` - Arkitekturbeslutninger
- `INSTALLATION_STATUS.md` - Installasjon-sjekkliste

---

**Rask start:** `./setup.sh && sudo systemctl start duck-vision` 🦆⚡
