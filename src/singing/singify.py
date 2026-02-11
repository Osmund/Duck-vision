"""
Singify - konverterer tale (TTS) til sang med pyworld vocoder.
Erstatter F0 (pitch) i TTS-audio med noter fra MIDI-melodi.

pip install pyworld mido numpy soundfile
"""

import numpy as np
import pyworld as pw
import soundfile as sf
import mido
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Singify:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def process(self, tts_path: Path, midi_path: Path,
                output_path: Path, word_boundaries: list = None) -> Path:
        """
        TTS-audio + MIDI-melodi → syngende vokal.

        pyworld brukes KUN for melodi-matching (MIDI pitch).
        Duck-stemme (pitch opp) gjøres etterpå med enkel resampling
        i song_service._create_mix() — samme metode som Pi 4.
        """
        # Les TTS-audio
        audio, sr = sf.read(str(tts_path))
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Mono

        if sr != self.sample_rate:
            audio = np.interp(
                np.linspace(0, len(audio), int(len(audio) * self.sample_rate / sr)),
                np.arange(len(audio)),
                audio
            )
            sr = self.sample_rate

        audio = audio.astype(np.float64)

        logger.info(f"🎵 Analyserer TTS ({len(audio)/sr:.1f}s)...")

        # WORLD analyse
        f0, timeaxis = pw.harvest(audio, sr)
        sp = pw.cheaptrick(audio, f0, timeaxis, sr)
        ap = pw.d4c(audio, f0, timeaxis, sr)

        # Les MIDI pitch-kurve og skaler til TTS-lengde
        midi_f0 = self._midi_to_f0_curve(midi_path, timeaxis, len(audio) / sr)

        # Blend: 60% MIDI-pitch + 40% original TTS-pitch for naturlig lyd
        voiced = f0 > 0
        new_f0 = f0.copy()

        midi_blend = 0.85  # Følg MIDI-melodi tett, minimal TTS-intonasjon
        for i in range(len(new_f0)):
            if voiced[i] and midi_f0[i] > 0:
                new_f0[i] = midi_f0[i] * midi_blend + f0[i] * (1 - midi_blend)

        # Glatt overganger
        new_f0 = self._smooth_f0(new_f0, window=5)

        logger.info("🎤 Resyntetiserer med MIDI-melodi...")

        # Resyntetiser (kun melodi — INGEN duck pitch her)
        output = pw.synthesize(new_f0, sp, ap, sr)

        # Normaliser
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 0.9

        # Lagre
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), output, sr, subtype='PCM_16')

        logger.info(f"  ✅ Singify ferdig: {output_path} ({len(output)/sr:.1f}s)")
        return output_path

    def _midi_to_f0_curve(self, midi_path: Path, timeaxis: np.ndarray,
                          audio_duration: float) -> np.ndarray:
        """
        Konverter MIDI spor 0 (vokal) til F0-kurve.
        Skalerer MIDI-varighet til å matche TTS audio-varigheten.
        """
        mid = mido.MidiFile(str(midi_path))
        tempo = self._get_tempo(mid)

        # Samle alle note on/off events med absolutt tid
        # midiutil lager: track 0 = tempo, track 1 = vokal, track 2 = komp
        # Søk gjennom alle spor for å finne vokal-noter
        events = []
        vocal_track = None

        for track_idx, track in enumerate(mid.tracks):
            track_events = []
            current_time = 0.0
            for msg in track:
                current_time += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
                if msg.type == 'note_on' and msg.velocity > 0:
                    track_events.append((current_time, msg.note, 'on'))
                elif msg.type in ('note_off',) or (msg.type == 'note_on' and msg.velocity == 0):
                    track_events.append((current_time, msg.note, 'off'))
            if track_events and not events:
                events = track_events
                vocal_track = track_idx
                logger.info(f"  🎵 Vokal-noter funnet i MIDI spor {track_idx} ({len(track_events)} events)")

        if not vocal_track:
            logger.info(f"  ℹ️ MIDI har {len(mid.tracks)} spor, søkte alle")

        if not events:
            logger.warning("Ingen noter funnet i MIDI")
            return np.zeros_like(timeaxis)

        # MIDI total varighet
        midi_duration = events[-1][0]
        if midi_duration <= 0:
            return np.zeros_like(timeaxis)

        # Skaleringsfaktor: strekk/krympmapp MIDI til TTS-lengde
        time_scale = audio_duration / midi_duration
        logger.info(f"  ⏱️ MIDI: {midi_duration:.1f}s → TTS: {audio_duration:.1f}s (scale: {time_scale:.2f}x)")

        # Bygg F0-kurve
        f0_curve = np.zeros_like(timeaxis)

        for i, t in enumerate(timeaxis):
            # Finn aktiv note ved skalert tidspunkt
            midi_time = t / time_scale  # Konverter TTS-tid til MIDI-tid
            current_note = None

            for event_time, note_num, event_type in events:
                if event_time > midi_time:
                    break
                if event_type == 'on':
                    current_note = note_num
                elif event_type == 'off':
                    current_note = None

            if current_note is not None:
                f0_curve[i] = 440.0 * (2.0 ** ((current_note - 69) / 12.0))

        return f0_curve

    def _get_tempo(self, mid: mido.MidiFile) -> int:
        """Hent tempo fra MIDI-fil."""
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    return msg.tempo
        return mido.bpm2tempo(120)

    def _smooth_f0(self, f0: np.ndarray, window: int = 3) -> np.ndarray:
        """Glatt F0-kurve for å unngå harde hopp."""
        smoothed = f0.copy()
        voiced = f0 > 0

        for i in range(window, len(f0) - window):
            if voiced[i]:
                region = f0[i - window:i + window + 1]
                voiced_region = region[region > 0]
                if len(voiced_region) > 0:
                    smoothed[i] = np.median(voiced_region)

        return smoothed
