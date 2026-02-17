#!/usr/bin/env python3
"""
Registrer stemme - tar opp tale og lager stemmeprofil.
Bruk: python3 scripts/register_voice.py "Åsmund"
"""

import sys
import os
import time
import logging
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

from config import VOICE_CONFIG
from speaker_recognition import SpeakerRecognition


TEXTS = [
    {
        "title": "Oppvarming",
        "text": (
            "Hei, jeg heter Åsmund og dette er stemmen min.\n"
            "    Jeg bor i Norge og liker å jobbe med teknologi."
        ),
    },
    {
        "title": "Hverdagslig tale",
        "text": (
            "I dag er det fint vær ute, og jeg tenkte å gå en tur.\n"
            "    Kanskje jeg tar med meg hunden ut i skogen etterpå."
        ),
    },
    {
        "title": "Spørsmål og uttrykk",
        "text": (
            "Hva synes du om været i dag? Jeg lurer på om det\n"
            "    blir regn senere. Det hadde vært kjekt å vite."
        ),
    },
]

RECORD_SECONDS = 8  # Per opptak


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "Åsmund"

    print(f"\n🎤 Duck-Vision: Registrerer stemme for '{name}'")
    print("=" * 55)
    print()
    print(f"Du leser {len(TEXTS)} korte tekster høyt.")
    print(f"Hver tekst tas opp i {RECORD_SECONDS} sekunder.")
    print("Les i normalt tempo — ikke stress!")
    print()

    sr = SpeakerRecognition(VOICE_CONFIG)

    import sounddevice as sd

    mic_sr = VOICE_CONFIG["mic_sample_rate"]
    target_sr = VOICE_CONFIG["target_sample_rate"]
    all_speech = []

    for i, item in enumerate(TEXTS):
        print(f"\n{'─' * 55}")
        print(f"  📖 Tekst {i+1}/{len(TEXTS)}: {item['title']}")
        print(f"{'─' * 55}")
        print()
        print(f"    \"{item['text']}\"")
        print()
        input(f"  👉 Trykk ENTER når du er klar å lese... ")

        print(f"  🔴 TAR OPP ({RECORD_SECONDS}s)...", end="", flush=True)
        audio = sd.rec(
            int(mic_sr * RECORD_SECONDS),
            samplerate=mic_sr,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        audio = audio.flatten()
        print(" ✅ Ferdig!")

        # Resample til 16kHz
        audio_16k = sr._resample(audio, mic_sr, target_sr)

        # Ekstraher tale via VAD
        speech_segments = sr._extract_speech_segments(audio_16k)

        if speech_segments:
            speech_sec = sum(len(s) for s in speech_segments) / target_sr
            print(f"  📊 Tale detektert: {speech_sec:.1f}s")
            all_speech.extend(speech_segments)
        else:
            print(f"  ⚠️  Ingen tale detektert — prøv å snakke litt høyere.")

    # Oppsummering og lagring
    print(f"\n{'═' * 55}")

    if not all_speech:
        print("❌ Ingen tale ble fanget opp. Sjekk mikrofon-innstillinger.")
        return

    total_audio = np.concatenate(all_speech)
    total_sec = len(total_audio) / target_sr
    print(f"  📊 Totalt {total_sec:.1f}s tale samlet inn")

    if total_sec < 3.0:
        print(f"  ⚠️  Litt lite tale ({total_sec:.1f}s). Anbefaler minst 5s.")
        cont = input("  Vil du fortsette likevel? (j/n): ")
        if cont.lower() != 'j':
            print("  Avbrutt.")
            return

    print(f"  🧠 Genererer stemmeprofil...", end="", flush=True)
    embedding = sr._compute_embedding(total_audio)

    if embedding is None:
        print(" ❌ Feil ved generering av embedding.")
        return

    success = sr._save_voice_profile(name, embedding)

    if success:
        print(f" ✅")
        print(f"\n✅ Stemmeprofil for '{name}' er lagret!")
        print(f"   Kjente stemmer: {', '.join(sr.list_known_speakers())}")
        print(f"\n   Restart duck-vision for å aktivere:")
        print(f"   sudo systemctl restart duck-vision")
    else:
        print(f" ❌ Feil ved lagring.")


if __name__ == "__main__":
    main()
