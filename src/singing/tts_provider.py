"""
Azure Neural TTS med viseme-støtte.
Visemes gir presis nebb-animasjon – mye bedre enn RMS-analyse.
"""

import azure.cognitiveservices.speech as speechsdk
import json
import os
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    audio_path: Path
    visemes: list = field(default_factory=list)
    word_boundaries: list = field(default_factory=list)
    duration_ms: int = 0


class AzureTTS:
    """
    Azure Neural TTS med norsk stemme + viseme-data.

    Stemmer:
      - nb-NO-IselinNeural   (kvinne, varm) ← Ulrikas stemme!
      - nb-NO-FinnNeural     (mann, naturlig)
      - nb-NO-PernilleNeural (kvinne, naturlig)
    """

    # Viseme ID → nebb-åpning (0.0 = lukket, 1.0 = åpen)
    VISEME_TO_BEAK = {
        0: 0.0, 1: 0.15, 2: 0.1, 3: 0.3, 4: 0.5, 5: 0.2,
        6: 0.7, 7: 0.05, 8: 0.6, 9: 0.1, 10: 0.3, 11: 0.4,
        12: 0.8, 13: 0.0, 14: 0.1, 15: 0.05, 16: 0.2, 17: 0.3,
        18: 0.1, 19: 0.05, 20: 0.0, 21: 0.0,
    }

    def __init__(self, voice: str = "nb-NO-IselinNeural",
                 speech_key: str = None, speech_region: str = None):
        self.voice = voice
        key = speech_key or os.getenv("AZURE_SPEECH_KEY") or os.getenv("AZURE_TTS_KEY")
        region = speech_region or os.getenv("AZURE_SPEECH_REGION") or os.getenv("AZURE_TTS_REGION", "westeurope")

        if not key:
            raise ValueError("Azure Speech key mangler. Sett AZURE_SPEECH_KEY eller AZURE_TTS_KEY i .env")

        self.speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
        )

    def synthesize(self, text: str, output_path: Path) -> TTSResult:
        """Syntetiser tekst med viseme- og word boundary-data."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=audio_config,
        )

        visemes = []
        word_boundaries = []

        def on_viseme(evt):
            visemes.append({
                "time_ms": evt.audio_offset / 10000,
                "id": evt.viseme_id,
                "beak": self.VISEME_TO_BEAK.get(evt.viseme_id, 0.0),
            })

        def on_word(evt):
            word_boundaries.append({
                "time_ms": evt.audio_offset / 10000,
                "word": evt.text,
                "duration_ms": evt.duration.total_seconds() * 1000 if evt.duration else 0,
            })

        synthesizer.viseme_received.connect(on_viseme)
        synthesizer.synthesis_word_boundary.connect(on_word)

        # SSML for bedre kontroll
        ssml = self._build_ssml(text)
        logger.info(f"🗣️ Azure TTS ({self.voice}): '{text[:60]}...'")

        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            duration_ms = len(result.audio_data) / (24000 * 2) * 1000
            logger.info(
                f"  ✅ TTS ferdig: {len(visemes)} visemes, "
                f"{len(word_boundaries)} ord, {duration_ms:.0f}ms"
            )
            return TTSResult(
                audio_path=output_path,
                visemes=visemes,
                word_boundaries=word_boundaries,
                duration_ms=int(duration_ms),
            )
        else:
            details = ""
            if result.cancellation_details:
                details = result.cancellation_details.error_details
            raise RuntimeError(f"Azure TTS feilet: {result.reason} - {details}")

    def _build_ssml(self, text: str) -> str:
        """Bygg SSML med sang-prosodi."""
        return f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
               xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="nb-NO">
            <voice name="{self.voice}">
                <prosody rate="-25%" pitch="+10%" volume="+10%">
                    <mstts:express-as style="cheerful">
                        {text}
                    </mstts:express-as>
                </prosody>
            </voice>
        </speak>"""
