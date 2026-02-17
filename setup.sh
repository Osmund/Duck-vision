#!/bin/bash
# ============================================================
# Duck-Vision Setup Script
# Raspberry Pi 5 + Sony IMX500 AI Camera
# ============================================================
#
# Kjør: ./setup.sh
# Gjør ALT som trengs for en fersk installasjon.
#
set -e

echo ""
echo "🦆 Duck-Vision Setup"
echo "════════════════════════════════════════════════"
echo ""

# ── Sjekk at vi er på riktig maskin ─────────────────────────
if [ "$(uname -m)" != "aarch64" ]; then
    echo "⚠️  Dette skriptet er laget for Raspberry Pi (aarch64)."
    echo "   Du kjører: $(uname -m)"
    read -p "   Fortsett likevel? (j/n): " yn
    [[ "$yn" != "j" ]] && exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
echo "📁 Prosjektmappe: $PROJECT_DIR"
echo ""

# ── 1. System-pakker ────────────────────────────────────────
echo "📦 [1/6] Installerer system-pakker..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-venv \
    python3-libcamera python3-picamera2 python3-opencv \
    imx500-all \
    libportaudio2 portaudio19-dev libsndfile1 \
    libcap-dev \
    cmake build-essential libopenblas-dev liblapack-dev \
    git mosquitto-clients \
    2>&1 | tail -3
echo "   ✅ System-pakker OK"
echo ""

# ── 2. Python venv med system-pakker ────────────────────────
echo "🐍 [2/6] Setter opp Python virtualenv..."
if [ ! -d ".venv" ]; then
    python3 -m venv --system-site-packages .venv
    echo "   ✅ Nytt venv opprettet (med system-pakker)"
else
    # Sørg for at system-site-packages er aktivert
    sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
    echo "   ✅ Eksisterende venv oppdatert"
fi
echo ""

# ── 3. Python-avhengigheter ─────────────────────────────────
echo "📚 [3/6] Installerer Python-avhengigheter..."
source .venv/bin/activate
pip install --upgrade pip -q

# Installer dlib først (kan ta tid å bygge på ARM)
echo "   ⏳ Installerer dlib (kan ta et par minutter)..."
pip install "dlib>=19.24" -q 2>&1 | tail -1

# Installer resten (hopp over picamera2 og opencv - bruker system-versjonene)
grep -v "^#" requirements.txt | grep -v "^$" | grep -v "picamera2" | grep -v "opencv" | \
    pip install -r /dev/stdin -q 2>&1 | tail -3

echo "   ✅ Python-avhengigheter OK"
echo ""

# ── 4. Konfigurasjon ────────────────────────────────────────
echo "⚙️  [4/6] Konfigurerer..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   📝 .env opprettet fra .env.example"
    echo "   ⚠️  Rediger .env med dine API-nøkler!"
else
    echo "   ✅ .env finnes allerede"
fi
echo ""

# ── 5. Data-mapper ──────────────────────────────────────────
echo "📂 [5/6] Oppretter data-mapper..."
mkdir -p data/known_faces data/known_voices data/logs
echo "   ✅ data/known_faces, data/known_voices, data/logs"
echo ""

# ── 6. Systemd-tjeneste ─────────────────────────────────────
echo "🔧 [6/6] Installerer systemd-tjeneste..."
chmod +x install_service.sh start_duck_vision.sh
chmod +x scripts/*.py 2>/dev/null || true
./install_service.sh
echo ""

# ── Begrens logg-størrelse (viktig for 24/7 drift) ──────────
echo "📋 Konfigurerer logg-begrensning..."
sudo mkdir -p /etc/systemd/journald.conf.d
echo -e "[Journal]\nSystemMaxUse=50M\nMaxRetentionSec=7day" | \
    sudo tee /etc/systemd/journald.conf.d/duck-vision-limit.conf > /dev/null
sudo systemctl restart systemd-journald
echo "   ✅ Journald begrenset til 50MB / 7 dager"
echo ""

# ── Verifisering ────────────────────────────────────────────
echo "════════════════════════════════════════════════"
echo "🔍 Verifiserer installasjon..."
echo ""

ERRORS=0
for mod in "face_recognition" "paho.mqtt.client" "torch" "ultralytics" \
           "sounddevice" "resemblyzer" "webrtcvad" "openai" \
           "azure.cognitiveservices.speech" "pyworld" "dlib" \
           "picamera2" "libcamera"; do
    if python3 -c "import $mod" 2>/dev/null; then
        echo "   ✅ $mod"
    else
        echo "   ❌ $mod MANGLER"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "════════════════════════════════════════════════"
    echo "✅ Alt installert! Duck-Vision er klar."
    echo ""
    echo "Neste steg:"
    echo "  1. Rediger .env med API-nøkler (OPENAI_API_KEY, AZURE_TTS_KEY)"
    echo "  2. Registrer ansikt: python3 scripts/register_face.py \"Navn\""
    echo "  3. Registrer stemme: python3 scripts/register_voice.py \"Navn\""
    echo "  4. Start tjenesten:  sudo systemctl start duck-vision"
    echo "  5. Se logger:        sudo journalctl -u duck-vision -f"
    echo "════════════════════════════════════════════════"
else
    echo "⚠️  $ERRORS modul(er) mangler. Se feilmeldinger over."
fi
