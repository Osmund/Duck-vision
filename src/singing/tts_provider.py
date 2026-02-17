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
from .midi_builder import NOTE_MAP

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

    def synthesize_song(self, song_data: dict, output_path: Path) -> TTSResult:
        """
        Syntetiser sangtekst med tempo-tilpasset hastighet og pauser mellom vers.
        
        Beregner naturlig talehastighet vs. MIDI-varighet og justerer
        SSML prosody rate for bedre synkronisering med instrumentalen.
        """
        tempo = song_data["tempo_bpm"]
        beat_to_sec = 60.0 / tempo

        # Beregn mål-varighet fra MIDI-noter
        total_beats = 0.0
        n_verses = len(song_data["verses"])
        for i, verse in enumerate(song_data["verses"]):
            for note in verse["notes"]:
                total_beats += float(note["duration"])
            if i < n_verses - 1:
                total_beats += 1.0  # Pause mellom vers

        target_duration_sec = total_beats * beat_to_sec

        # Estimer naturlig tale-varighet for norsk Azure TTS.
        # nb-NO-IselinNeural med cheerful stil + SSML pauser ≈ 2.8 stavelser/sek.
        # Verifisert fra logg: 104 stavelser @ rate=-42% → 60.7s
        #   → ved 0% rate: ~60.7 * 0.58 = 35.2s → 104/35.2 ≈ 3.0 syl/s
        #   → med pauser og SSML overhead → effektiv ~2.8 syl/s
        syllable_count = sum(len(v["notes"]) for v in song_data["verses"])
        natural_syl_rate = 2.8
        natural_duration_sec = syllable_count / natural_syl_rate

        # Legg til estimert tid for SSML-pauser
        n_pauses = n_verses - 1
        pause_total_sec = n_pauses * beat_to_sec
        natural_duration_sec += pause_total_sec

        # Beregn rate-justering: vi vil at TTS-varighet ≈ mål-varighet
        # Positiv rate = raskere, negativ = tregere
        if natural_duration_sec > 0 and target_duration_sec > 0:
            rate_factor = natural_duration_sec / target_duration_sec
            rate_percent = int((rate_factor - 1) * 100)
            # Begrens til ±20% for å bevare naturlig lydkvalitet
            rate_percent = max(-20, min(20, rate_percent))
        else:
            rate_percent = 0  # Nøytral som fallback

        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
        logger.info(f"  📐 TTS rate: {rate_str} (mål: {target_duration_sec:.1f}s, "
                    f"{syllable_count} stavelser)")

        # Bygg per-note SSML med pitch per stavelse
        # Gir Azure TTS omtrent riktig melodi direkte — eliminerer behov for vocoder
        pause_ms = int(beat_to_sec * 1000)  # 1 beat pause mellom vers
        verse_parts = []

        for i, verse in enumerate(song_data["verses"]):
            notes = verse.get("notes", [])
            if notes:
                # Bygg SSML med per-note pitch
                note_parts = []
                for note_data in notes:
                    lyric = note_data.get("lyric", "")
                    if not lyric:
                        continue
                    note_name = note_data.get("note", "C4")
                    midi_note = NOTE_MAP.get(note_name, 60)
                    freq_hz = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                    # Azure TTS prosody pitch i Hz — tilnærmer melodien
                    note_parts.append(
                        f'<prosody pitch="{freq_hz:.0f}Hz">{lyric}</prosody>'
                    )
                verse_parts.append(f'<s>{" ".join(note_parts)}</s>')
            else:
                # Fallback: bare lyrics uten pitch
                lyrics = verse.get("lyrics", "la la la")
                text = lyrics.replace("\n", " ").strip()
                verse_parts.append(f'<s>{text}</s>')

            if i < n_verses - 1:
                verse_parts.append(f'<break time="{pause_ms}ms"/>')

        lyrics_ssml = "\n                        ".join(verse_parts)

        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
               xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="nb-NO">
            <voice name="{self.voice}">
                <prosody rate="{rate_str}" pitch="+10%" volume="+10%">
                    <mstts:express-as style="cheerful">
                        {lyrics_ssml}
                    </mstts:express-as>
                </prosody>
            </voice>
        </speak>"""

        # Syntetiser med SSML
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

        logger.info(f"🗣️ Azure TTS sang ({self.voice}): {syllable_count} stavelser, "
                    f"rate={rate_str}, pauser={pause_ms}ms")

        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            duration_ms = len(result.audio_data) / (24000 * 2) * 1000
            logger.info(
                f"  ✅ TTS sang ferdig: {len(visemes)} visemes, "
                f"{len(word_boundaries)} ord, {duration_ms:.0f}ms "
                f"(mål: {target_duration_sec*1000:.0f}ms)"
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
        """Bygg SSML med sang-prosodi (fallback for ikke-sang bruk)."""
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
