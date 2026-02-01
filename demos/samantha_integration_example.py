"""
Eksempel på hvordan Samantha (Pi 4) kan integrere Duck-Vision

Legg til dette i chatgpt_voice.py på Pi 4
"""

import paho.mqtt.client as mqtt
import json
import threading

# MQTT Setup
MQTT_BROKER = "localhost"  # Broker kjører på samme Pi
mqtt_client = None
waiting_for_person_name = False

def on_vision_message(client, userdata, msg):
    """Håndter meldinger fra Duck-Vision"""
    global waiting_for_person_name
    
    try:
        data = json.loads(msg.payload.decode())
        
        if msg.topic == "duck/vision/face":
            # Ansikt detektert
            if data["is_known"]:
                person_name = data["person_name"]
                speak(f"Hei {person_name}! Hyggelig å se deg igjen!", speech_config, beak)
            else:
                # Ukjent person
                speak("Hei på du! Hvem er du?", speech_config, beak)
                waiting_for_person_name = True
        
        elif msg.topic == "duck/vision/object":
            # Objekt detektert
            obj_name = data["object_name"]
            confidence = data["confidence"]
            speak(f"Dette er en {obj_name}!", speech_config, beak)
        
        elif msg.topic == "duck/vision/events":
            event = data.get("event")
            
            if event == "person_learned":
                if data["data"]["success"]:
                    name = data["data"]["name"]
                    speak(f"Flott! Nå husker jeg deg, {name}!", speech_config, beak)
                else:
                    speak("Beklager, jeg klarte ikke å lære ansiktet ditt.", speech_config, beak)
    
    except Exception as e:
        print(f"Feil ved håndtering av vision melding: {e}")

def setup_mqtt():
    """Sett opp MQTT-tilkobling til Duck-Vision"""
    global mqtt_client
    
    mqtt_client = mqtt.Client(client_id="samantha")
    mqtt_client.on_message = on_vision_message
    
    mqtt_client.connect(MQTT_BROKER, 1883, 60)
    
    # Subscribe til Duck-Vision topics
    mqtt_client.subscribe("duck/vision/#")
    
    # Start MQTT loop i bakgrunnen
    mqtt_client.loop_start()
    
    print("✓ MQTT tilkoblet - kan kommunisere med Duck-Vision")

def send_learn_person(name):
    """Send kommando til Duck-Vision for å lære ny person"""
    command = {
        "command": "learn_person",
        "name": name
    }
    mqtt_client.publish("duck/samantha/commands", json.dumps(command))
    speak(f"Se mot kameraet, {name}!", speech_config, beak)

def send_detect_object():
    """Send kommando til Duck-Vision for å detektere objekt"""
    command = {
        "command": "detect_object"
    }
    mqtt_client.publish("duck/samantha/commands", json.dumps(command))

# Legg til i main()-funksjonen:
def main():
    global waiting_for_person_name
    
    beak = Beak(GPIO_SERVO, CLOSE_DEG, OPEN_DEG, TRIM_DEG)
    load_dotenv()
    
    # ... eksisterende setup ...
    
    # Start MQTT
    setup_mqtt()
    
    print("Anda venter på wake word... (si 'ulrika')")
    while True:
        wait_for_wake_word()
        speak("Hei på du, hva kan jeg hjelpe deg med?", speech_config, beak)
        messages = []
        
        while True:
            prompt = recognize_speech_from_mic(device_name)
            
            if not prompt:
                speak("Beklager, jeg hørte ikke hva du sa. Prøv igjen.", speech_config, beak)
                continue
            
            # Sjekk om vi venter på personnavn
            if waiting_for_person_name:
                if "nei" in prompt.lower():
                    speak("Ok, ingen problem!", speech_config, beak)
                    waiting_for_person_name = False
                    continue
                else:
                    # Ekstraher navn fra prompt
                    # Enkel parsing - kan forbedres
                    words = prompt.split()
                    if len(words) >= 2 and words[0].lower() in ["jeg", "heter"]:
                        name = " ".join(words[2:]) if words[1].lower() == "heter" else words[1]
                    else:
                        name = prompt
                    
                    speak(f"Hyggelig å møte deg, {name}! Får jeg lov å huske deg?", speech_config, beak)
                    
                    # Vent på ja/nei
                    response = recognize_speech_from_mic(device_name)
                    if response and "ja" in response.lower():
                        send_learn_person(name)
                    else:
                        speak("Ok, ingen problem!", speech_config, beak)
                    
                    waiting_for_person_name = False
                    continue
            
            # Sjekk for spesielle kommandoer
            if "hva er dette" in prompt.lower() or "hva er det" in prompt.lower():
                speak("La meg se...", speech_config, beak)
                send_detect_object()
                continue
            
            if "stopp" in prompt.strip().lower():
                speak("Da venter jeg til du sier navnet mitt igjen.", speech_config, beak)
                break
            
            # Normal ChatGPT samtale
            messages.append({"role": "user", "content": prompt})
            try:
                blink_yellow_purple()
                reply = chatgpt_query(messages, api_key)
                off()
                print("ChatGPT svar:", reply, flush=True)
                speak(reply, speech_config, beak)
                messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                off()
                print("Feil:", e)
                speak("Beklager, det oppstod en feil.", speech_config, beak)
            
            set_green()

if __name__ == "__main__":
    main()
