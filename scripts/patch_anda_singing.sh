#!/bin/bash
# Patch-script for å legge til create_song tool på Pi 4 (anda)
# Kjøres en gang for å modifisere duck_config.py, duck_ai.py og .env
set -e

BASE=~/Code/chatgpt-and
cd "$BASE"

echo "🦆 Legger til Singing Duck support på anda..."

# ═══════════════════════════════════════════
# 1. Legg til ENABLE_SINGING feature flag i duck_config.py
# ═══════════════════════════════════════════
echo "  1/4 Feature flag i duck_config.py..."

# Sjekk om den allerede finnes
if grep -q "ENABLE_SINGING" src/duck_config.py; then
    echo "    → Allerede lagt til, hopper over"
else
    sed -i "/ENABLE_NETATMO/a ENABLE_SINGING = os.getenv('ENABLE_SINGING', 'true').lower() == 'true'" src/duck_config.py
    echo "    ✅ ENABLE_SINGING lagt til"
fi

# ═══════════════════════════════════════════
# 2. Legg til ENABLE_SINGING i .env
# ═══════════════════════════════════════════
echo "  2/4 Oppdaterer .env..."

if grep -q "ENABLE_SINGING" .env; then
    echo "    → Allerede i .env, hopper over"
else
    echo "" >> .env
    echo "# Singing Duck (Pi 5 genererer sanger)" >> .env
    echo "ENABLE_SINGING=true" >> .env
    echo "    ✅ ENABLE_SINGING=true lagt til i .env"
fi

# ═══════════════════════════════════════════
# 3. Legg til create_song tool-definisjon i duck_ai.py
# ═══════════════════════════════════════════
echo "  3/4 create_song tool i duck_ai.py..."

if grep -q "create_song" src/duck_ai.py; then
    echo "    → create_song allerede i duck_ai.py, hopper over"
else
    # Vi bruker python for presis innsetting
    python3 << 'PYEOF'
import re

filepath = "src/duck_ai.py"
with open(filepath, 'r') as f:
    content = f.read()

# ── A. Legg til ENABLE_SINGING i import ──
old_import = "from src.duck_config import ENABLE_HOME_ASSISTANT, ENABLE_PRUSALINK, ENABLE_DUCK_VISION, ENABLE_HUE, ENABLE_NETATMO"
new_import = "from src.duck_config import ENABLE_HOME_ASSISTANT, ENABLE_PRUSALINK, ENABLE_DUCK_VISION, ENABLE_HUE, ENABLE_NETATMO, ENABLE_SINGING"
content = content.replace(old_import, new_import)

# ── B. Legg til SINGING_TOOLS set + filter ──
old_netatmo_tools = "    NETATMO_TOOLS = {'get_netatmo_temperature'}"
new_netatmo_tools = """    NETATMO_TOOLS = {'get_netatmo_temperature'}
    
    # Tools som krever Singing Duck (Pi 5)
    SINGING_TOOLS = {'create_song'}"""
content = content.replace(old_netatmo_tools, new_netatmo_tools)

old_netatmo_filter = """        if name in NETATMO_TOOLS and not ENABLE_NETATMO:
            continue"""
new_netatmo_filter = """        if name in NETATMO_TOOLS and not ENABLE_NETATMO:
            continue
        if name in SINGING_TOOLS and not ENABLE_SINGING:
            continue"""
content = content.replace(old_netatmo_filter, new_netatmo_filter)

# ── C. Legg til create_song tool-definisjon etter sing_song ──
# Finn sing_song tool og legg inn create_song rett etter
sing_song_end = '''                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_face_recognition",'''

create_song_tool = '''                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_song",
                "description": "Komponer og lag en helt ny, original sang basert på et tema eller en forespørsel. Bruk dette NÅR brukeren ber deg lage, komponere, dikte eller skrive en ny sang. En AI på Pi 5 skriver tekst, melodi og instrumental. Det tar ca 15-20 sekunder. Si noe morsomt mens du venter. IKKE bruk denne for å synge eksisterende sanger (bruk sing_song for det).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Beskrivelse av hva sangen skal handle om, f.eks. 'en sang om at våren kommer tidlig' eller 'en morsom sang om å spise pizza'"
                        }
                    },
                    "required": ["prompt"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_face_recognition",'''

content = content.replace(sing_song_end, create_song_tool)

# ── D. Legg til create_song handler i _handle_tool_calls ──
# Finn "elif function_name == "check_face_recognition":" og legg til create_song rett før
old_check_face = '        elif function_name == "check_face_recognition":'
new_create_song_handler = '''        elif function_name == "create_song":
            prompt = function_args.get("prompt", "").strip()
            if not prompt:
                result = "Ingen prompt oppgitt"
            else:
                try:
                    from src.duck_singing_client import request_song
                    song_result = request_song(prompt, timeout=90)
                    if song_result and song_result.get("status") == "complete":
                        title = song_result.get("title", "Ny sang")
                        song_path = song_result.get("path", "")
                        render_time = song_result.get("render_time", 0)
                        result = f"🎵 SANG LAGET: {title}. Si KORT 'Nå synger jeg {title}!' + [AVSLUTT]. IKKE spør om mer."
                        force_end = True
                        # Spill sangen via event bus
                        if song_path and os.path.exists(song_path):
                            from src.duck_event_bus import get_event_bus, Event
                            bus = get_event_bus()
                            bus.post(Event.PLAY_SONG, {'path': song_path, 'announce': False})
                            print(f"✅ AI-sang queued: {title} (rendered in {render_time}s)", flush=True)
                        else:
                            print(f"⚠️ Sang-mappe ikke funnet: {song_path}", flush=True)
                            result = f"Sangen ble laget men filen ble ikke funnet. Prøv igjen."
                    elif song_result and song_result.get("status") == "busy":
                        result = "Jeg holder allerede på med å lage en annen sang! Prøv igjen om litt."
                    else:
                        error_msg = song_result.get("message", "Ukjent feil") if song_result else "Ingen respons fra Pi 5"
                        result = f"Beklager, jeg klarte ikke å lage sangen: {error_msg}"
                        print(f"⚠️ create_song feilet: {error_msg}", flush=True)
                except Exception as e:
                    result = f"Feil ved sangopprettelse: {str(e)}"
                    print(f"❌ create_song exception: {e}", flush=True)
        elif function_name == "check_face_recognition":'''

content = content.replace(old_check_face, new_create_song_handler)

with open(filepath, 'w') as f:
    f.write(content)

print("    ✅ create_song tool + handler lagt til i duck_ai.py")
PYEOF
fi

# ═══════════════════════════════════════════
# 4. Opprett duck_singing_client.py
# ═══════════════════════════════════════════
echo "  4/4 Oppretter duck_singing_client.py..."

cat > src/duck_singing_client.py << 'CLIENTEOF'
"""
Duck Singing Client
MQTT-klient som sender sang-forespørsler til Pi 5 og venter på resultat.
"""

import json
import time
import threading
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Pi 5 (Duck-Vision) MQTT - broker kjører på Pi 4 (localhost)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883


def request_song(prompt: str, timeout: int = 90) -> dict:
    """
    Send sang-forespørsel til Pi 5 og vent på resultat.
    
    Args:
        prompt: Hva sangen skal handle om
        timeout: Maks antall sekunder å vente
    
    Returns:
        dict med {status, title, path, render_time} eller {status, message}
    """
    song_id = f"song_{int(time.time())}"
    result = {"status": "timeout", "message": "Tidsavbrudd - Pi 5 svarte ikke"}
    result_ready = threading.Event()
    status_messages = []
    
    client = mqtt.Client(client_id=f"singing-request-{song_id}")
    
    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            c.subscribe("duck/singing/complete")
            c.subscribe("duck/singing/status")
    
    def on_message(c, userdata, msg):
        nonlocal result
        try:
            data = json.loads(msg.payload.decode())
            
            if msg.topic == "duck/singing/complete":
                if data.get("song_id") == song_id or data.get("status") == "complete":
                    result = data
                    result_ready.set()
            
            elif msg.topic == "duck/singing/status":
                status = data.get("status", "")
                message = data.get("message", "")
                
                if status == "busy":
                    result = {"status": "busy", "message": message}
                    result_ready.set()
                elif status == "error":
                    result = {"status": "error", "message": message}
                    result_ready.set()
                else:
                    status_messages.append(message)
                    logger.info(f"🎵 Sang-status: {message}")
                    print(f"🎵 Sang-status: {message}", flush=True)
        except Exception as e:
            logger.error(f"Feil ved parsing av sang-respons: {e}")
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        
        # Vent litt på tilkobling
        time.sleep(0.5)
        
        # Send forespørsel
        request = json.dumps({
            "prompt": prompt,
            "song_id": song_id
        })
        client.publish("duck/singing/request", request, qos=1)
        print(f"📡 Sang-forespørsel sendt: '{prompt}' (id: {song_id})", flush=True)
        
        # Vent på resultat
        result_ready.wait(timeout=timeout)
        
        return result
        
    except Exception as e:
        logger.error(f"MQTT-feil: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        client.loop_stop()
        client.disconnect()
CLIENTEOF

echo ""
echo "✅ Singing Duck support installert på anda!"
echo ""
echo "Filer modifisert:"
echo "  src/duck_config.py  → ENABLE_SINGING flag"
echo "  src/duck_ai.py      → create_song tool + handler"
echo "  .env                → ENABLE_SINGING=true"
echo ""
echo "Filer opprettet:"
echo "  src/duck_singing_client.py → MQTT-klient for sang-forespørsler"
echo ""
echo "🔄 Restart anda for å aktivere: sudo systemctl restart chatgpt-and"
