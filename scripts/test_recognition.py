#!/usr/bin/env python3
"""
Test ansikts- og stemmegjenkjenning.
Tar ett bilde og ett lydopptak, og viser score.
"""

import sys
import os
import time
import logging
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.WARNING)

from config import VOICE_CONFIG, FACE_CONFIG
from speaker_recognition import SpeakerRecognition
from imx500_face_recognition import IMX500FaceRecognizer


def test_face():
    print("\n📷 ANSIKTSGJENKJENNING")
    print("─" * 45)
    
    recognizer = IMX500FaceRecognizer()
    recognizer.start()
    time.sleep(2)  # La kamera varme opp
    
    input("  Se mot kameraet og trykk ENTER... ")
    
    print("  📸 Tar bilde...", end="", flush=True)
    results = recognizer.detect_faces()
    
    if results:
        print(f" Fant {len(results)} ansikt(er)!\n")
        for name, confidence, location in results:
            bar = "█" * int(confidence * 30) + "░" * (30 - int(confidence * 30))
            status = "✅" if name != "ukjent" else "❌"
            print(f"  {status} Navn:    {name}")
            print(f"     Score:   {confidence:.1%}  [{bar}]")
            print(f"     Posisjon: top={location[0]}, right={location[1]}, bottom={location[2]}, left={location[3]}")
            print()
    else:
        print(" ⚠️  Ingen ansikter funnet.")
    
    recognizer.stop()
    return bool(results)


def test_voice():
    print("\n🎤 STEMMEGJENKJENNING")
    print("─" * 45)
    
    sr = SpeakerRecognition(VOICE_CONFIG)
    
    if not sr.known_voices:
        print("  ⚠️  Ingen kjente stemmeprofiler funnet.")
        return False
    
    print(f"  Kjente stemmer: {', '.join(sr.list_known_speakers())}")
    
    import sounddevice as sd
    mic_sr = VOICE_CONFIG["mic_sample_rate"]
    target_sr = VOICE_CONFIG["target_sample_rate"]
    duration = 5.0
    
    print(f"\n  Si noe i {int(duration)} sekunder (f.eks. \"Hei, det er meg\")")
    input("  Trykk ENTER for å starte opptak... ")
    
    print(f"  🔴 TAR OPP ({int(duration)}s)...", end="", flush=True)
    audio = sd.rec(
        int(mic_sr * duration),
        samplerate=mic_sr,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    audio = audio.flatten()
    print(" ✅ Ferdig!")
    
    # Resample
    audio_16k = sr._resample(audio, mic_sr, target_sr)
    
    # Ekstraher tale
    speech_segments = sr._extract_speech_segments(audio_16k)
    
    if not speech_segments:
        print("  ⚠️  Ingen tale detektert. Prøv å snakke høyere.")
        return False
    
    total_speech = sum(len(s) for s in speech_segments) / target_sr
    print(f"  📊 Tale detektert: {total_speech:.1f}s")
    
    if total_speech < 1.0:
        print("  ⚠️  For lite tale for pålitelig matching.")
        return False
    
    # Bruk all tale for embedding
    all_speech = np.concatenate(speech_segments)
    embedding = sr._compute_embedding(all_speech)
    
    if embedding is None:
        print("  ❌ Kunne ikke generere embedding.")
        return False
    
    # Match mot alle kjente
    print()
    matched = False
    for name, known_emb in sr.known_voices.items():
        similarity = np.dot(embedding, known_emb) / (
            np.linalg.norm(embedding) * np.linalg.norm(known_emb)
        )
        threshold = VOICE_CONFIG["match_threshold"]
        bar = "█" * int(similarity * 30) + "░" * (30 - int(similarity * 30))
        status = "✅" if similarity >= threshold else "❌"
        
        print(f"  {status} Navn:      {name}")
        print(f"     Score:    {similarity:.1%}  [{bar}]")
        print(f"     Terskel:  {threshold:.1%}")
        
        if similarity >= threshold:
            matched = True
        print()
    
    return matched


def main():
    print("\n" + "=" * 45)
    print("  🦆 Duck-Vision: Test gjenkjenning")
    print("=" * 45)
    
    face_ok = test_face()
    voice_ok = test_voice()
    
    print("=" * 45)
    print("  RESULTAT")
    print("─" * 45)
    print(f"  Ansikt: {'✅ Gjenkjent' if face_ok else '❌ Ikke gjenkjent'}")
    print(f"  Stemme: {'✅ Gjenkjent' if voice_ok else '❌ Ikke gjenkjent'}")
    print("=" * 45)


if __name__ == "__main__":
    main()
