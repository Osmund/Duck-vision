# Pi 4 - Fix for look_around() timeout

## Problem
`look_around()` får timeout fordi den ikke venter på svar fra Duck-Vision.

## Løsning

### 1. Kopier oppdatert fil fra Pi 5

```bash
scp ~/Code/Duck-Vision/src/duck_vision_integration.py admog@oDuckberry-2.local:~/Code/chatgpt-duck-py/
```

### 2. Endre look_around() til å bruke synkron metode

I `look_around()` AI-tool funksjonen, endre fra:

```python
# ❌ FEIL - venter ikke på svar:
vision.request_object_detection()
return "timeout eller ingen respons"
```

Til:

```python
# ✅ RIKTIG - venter på svar:
result = vision.look_around(timeout=10.0)
return result
```

### 3. Restart Samantha

```bash
sudo systemctl restart chatgpt-duck
```

### 4. Test

Si: "Hva ser du?" → Samantha skal svare med hva kameraet ser.

## Quick test

```bash
# Test MQTT kommunikasjon:
mosquitto_pub -h localhost -t "duck/samantha/commands" -m '{"command":"detect_object"}'
mosquitto_sub -h localhost -t "duck/vision/#" -v
```

## Deteksjoner sendt til Samantha (oppdatert med flere objekter)

**Nå sender Duck-Vision ALLE objekter, ikke bare ett!**

Eksempel payload:
```json
Topic: duck/vision/object
Payload: {
  "event": "object_detected",
  "timestamp": 1738350611.652,
  "object_name": "person",
  "confidence": 0.6797,
  "all_objects": [
    {"name": "person", "confidence": 0.6797, "bbox": [0.1, 0.2, 0.8, 0.9]},
    {"name": "laptop", "confidence": 0.45, "bbox": [0.3, 0.5, 0.6, 0.8]},
    {"name": "mobiltelefon", "confidence": 0.38, "bbox": [0.7, 0.3, 0.85, 0.5]}
  ]
}
```

**Forventet svar fra `look_around()`:**
```
"Jeg ser en person (68% sikker), en laptop og en mobiltelefon"
```

Eller hvis bare ett objekt:
```
"Jeg ser en person (68% sikker)"
```

**Test nå!** Samantha skal gi mye mer detaljert beskrivelse! 🦆✨
