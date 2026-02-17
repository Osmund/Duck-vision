"""
Singify - tidssynkroniserer TTS-audio til MIDI-beat-posisjoner.

Ny pipeline (rubberband, ingen WORLD vocoder):
  1. Azure TTS genererer tale med per-note SSML pitch (allerede omtrent riktig melodi)
  2. Rubberband time-stretcher audio til MIDI-varighet (høy kvalitet)
  3. Resultat: vokal som følger MIDI-tempo med naturlig TTS-lyd

pip install pyrubberband mido numpy soundfile
"""

import numpy as np
import pyrubberband as pyrb
import soundfile as sf
import mido
from pathlib import Path
import logging

from .midi_builder import NOTE_MAP

logger = logging.getLogger(__name__)


class Singify:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def process(self, tts_path: Path, midi_path: Path,
                output_path: Path, word_boundaries: list = None,
                song_data: dict = None) -> Path:
        """
        TTS-audio → tidssynkronisert vokal med rubberband.

        Ny pipeline (ingen WORLD vocoder):
          1. TTS har allerede per-note pitch fra SSML
          2. Rubberband time-stretcher til MIDI-varighet
          3. Resultat: naturlig TTS-lyd synkronisert med MIDI-tempo

        Duck-stemme (pitch opp) gjøres etterpå i song_service._create_mix().
        """
        # Les TTS-audio
        audio, sr = sf.read(str(tts_path))
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Mono

        audio = audio.astype(np.float64)
        tts_duration = len(audio) / sr

        if song_data:
            # ── Rubberband-basert synkronisering ──
            target_duration = self._calc_vocal_duration(song_data)
            # pyrubberband rate = hastighet: >1 = raskere/kortere, <1 = saktere/lengre
            speed_rate = tts_duration / target_duration

            logger.info(f"🎵 TTS ({tts_duration:.1f}s) → Mål: {target_duration:.1f}s "
                        f"(rate: {speed_rate:.2f}x)")

            # Begrens for kvalitet
            max_rate = 1.5
            if speed_rate > max_rate:
                logger.warning(f"  ⚠️ Rate {speed_rate:.2f}x > maks {max_rate}x, begrenser")
                speed_rate = max_rate
            elif speed_rate < 1.0 / max_rate:
                logger.warning(f"  ⚠️ Rate {speed_rate:.2f}x < min, begrenser")
                speed_rate = 1.0 / max_rate

            # Rubberband time-stretch — bevarer pitch og formanter
            if abs(speed_rate - 1.0) > 0.02:
                audio = pyrb.time_stretch(audio, sr, speed_rate)
                logger.info(f"  📐 Rubberband rate: {speed_rate:.2f}x "
                            f"→ {len(audio)/sr:.1f}s")
            else:
                logger.info(f"  📐 Ingen stretch nødvendig (rate {speed_rate:.2f}x)")

        # Normaliser
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.9

        # Lagre
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, sr, subtype='PCM_16')

        output_dur = len(audio) / sr
        logger.info(f"  ✅ Singify ferdig: {output_path} ({output_dur:.1f}s)")
        return output_path

    # ────────────────────────────────────────────────────────
    #  Tidssynkronisering
    # ────────────────────────────────────────────────────────

    def _calc_vocal_duration(self, song_data: dict) -> float:
        """Beregn mål-varighet for vokalen fra MIDI-data (sekunder)."""
        tempo = song_data["tempo_bpm"]
        beat_to_sec = 60.0 / tempo

        total_beats = 0.0
        n_verses = len(song_data["verses"])
        for i, verse in enumerate(song_data["verses"]):
            for note in verse["notes"]:
                total_beats += float(note["duration"])
            # Pause mellom vers (matcher MidiBuilder: 1 beat)
            if i < n_verses - 1:
                total_beats += 1.0

        return total_beats * beat_to_sec

    def _uniform_time_stretch(self, f0, sp, ap, timeaxis,
                              current_dur: float, target_dur: float):
        """
        Uniform time-stretch av WORLD-frames.
        Skalerer antall frames proporsjonalt til tid-ratio.
        Pitch påvirkes IKKE — kun timing endres.
        Bruker lineær interpolering for SP/AP for bedre lydkvalitet.
        """
        n_current = len(f0)
        frame_period = timeaxis[1] - timeaxis[0] if len(timeaxis) > 1 else 0.005

        # Begrens stretch-ratio for å unngå artefakter
        ratio = target_dur / current_dur
        max_stretch = 1.3
        if ratio > max_stretch:
            logger.warning(f"  ⚠️ Stretch {ratio:.2f}x overstiger maks {max_stretch}x, begrenser")
            target_dur = current_dur * max_stretch
        elif ratio < 1.0 / max_stretch:
            logger.warning(f"  ⚠️ Komprimering {ratio:.2f}x overstiger maks, begrenser")
            target_dur = current_dur / max_stretch

        n_target = max(1, int(target_dur / frame_period))

        logger.info(f"  📐 Uniform stretch: {n_current} → {n_target} frames "
                    f"({current_dur:.1f}s → {target_dur:.1f}s, ratio: {target_dur/current_dur:.2f}x)")

        # Resampling-indekser (fra target-frames til source-frames)
        indices = np.linspace(0, n_current - 1, n_target)

        # F0: lineær interpolering
        new_f0 = np.interp(indices, np.arange(n_current), f0)

        # SP og AP: lineær interpolering per frekvens-bin for jevnere lyd
        new_sp = self._interpolate_spectral(sp, indices, n_current)
        new_ap = self._interpolate_spectral(ap, indices, n_current)

        # Ny timeaxis
        new_timeaxis = np.arange(n_target) * frame_period

        return new_f0, new_sp, new_ap, new_timeaxis

    def _piecewise_time_stretch(self, f0, sp, ap, timeaxis,
                                current_dur: float, target_dur: float,
                                word_boundaries: list, song_data: dict):
        """
        Per-ord time-stretch: mapper hvert ord fra TTS-posisjon til
        MIDI beat-posisjon. Gir mye bedre synkronisering enn uniform stretch.

        Bygger en stykkevis lineær mapping mellom source og target tid,
        og resampler WORLD-frames deretter.

        Begrenser total stretch til maks 1.3x for å bevare lydkvalitet.
        """
        # Sjekk total stretch-ratio
        max_stretch = 1.3
        ratio = target_dur / current_dur
        if ratio > max_stretch:
            logger.warning(f"  ⚠️ Piecewise stretch {ratio:.2f}x > maks {max_stretch}x, "
                           f"begrenser mål fra {target_dur:.1f}s til {current_dur * max_stretch:.1f}s")
            target_dur = current_dur * max_stretch
        elif ratio < 1.0 / max_stretch:
            logger.warning(f"  ⚠️ Piecewise komprimering {ratio:.2f}x > maks, "
                           f"begrenser mål fra {target_dur:.1f}s til {current_dur / max_stretch:.1f}s")
            target_dur = current_dur / max_stretch

        tempo = song_data["tempo_bpm"]
        beat_to_sec = 60.0 / tempo

        # ── Bygg mål-tidspunkter fra song_data ──
        # Hvert vers har noter med lyric per stavelse. Grupper stavelser til ord.
        target_word_times = []  # [(start_sec, end_sec, word_text), ...]
        beat_pos = 0.0
        for v_idx, verse in enumerate(song_data["verses"]):
            # Grupper stavelser til ord
            word_start_beat = beat_pos
            current_word = ""

            for note in verse["notes"]:
                lyric = note.get("lyric", "")
                duration = float(note["duration"])

                if lyric.endswith("-"):
                    # Stavelse midt i et ord
                    if not current_word:
                        word_start_beat = beat_pos
                    current_word += lyric.rstrip("-")
                else:
                    # Slutten av et ord (eller enkeltstående ord)
                    if current_word:
                        current_word += lyric
                    else:
                        current_word = lyric
                        word_start_beat = beat_pos

                    word_end_beat = beat_pos + duration
                    if current_word.strip():
                        target_word_times.append((
                            word_start_beat * beat_to_sec,
                            word_end_beat * beat_to_sec,
                            current_word.strip()
                        ))
                    current_word = ""

                beat_pos += duration

            # Avslutt evt. ufullstendig ord
            if current_word.strip():
                target_word_times.append((
                    word_start_beat * beat_to_sec,
                    beat_pos * beat_to_sec,
                    current_word.strip()
                ))
                current_word = ""

            # Pause mellom vers
            if v_idx < len(song_data["verses"]) - 1:
                beat_pos += 1.0

        # ── Bygg kilde-tidspunkter fra word_boundaries ──
        source_word_times = []
        for wb in word_boundaries:
            start_sec = wb["time_ms"] / 1000.0
            dur_sec = wb.get("duration_ms", 0) / 1000.0
            word = wb.get("word", "")
            if word.strip():
                source_word_times.append((start_sec, start_sec + max(dur_sec, 0.01), word))

        # ── Match ord mellom source og target ──
        # Enkel sekvensiell matching (TTS og song_data har samme tekst)
        n_match = min(len(source_word_times), len(target_word_times))

        if n_match < 2:
            logger.info("  ⚠️ For få ord-matcher, bruker uniform stretch")
            return self._uniform_time_stretch(f0, sp, ap, timeaxis,
                                              current_dur, target_dur)

        logger.info(f"  📐 Per-ord stretch: {n_match} ord matchet "
                    f"(source: {len(source_word_times)}, target: {len(target_word_times)})")

        # Bygg stykkevis lineær mapping: source_time → target_time
        # Ankerpunkter: (source_sec, target_sec)
        anchors = [(0.0, 0.0)]  # Start

        for i in range(n_match):
            src_start = source_word_times[i][0]
            tgt_start = target_word_times[i][0]
            anchors.append((src_start, tgt_start))

            # Legg til sluttanker for siste ord
            if i == n_match - 1:
                src_end = source_word_times[i][1]
                tgt_end = target_word_times[i][1]
                anchors.append((src_end, tgt_end))

        # Legg til endepunkt
        anchors.append((current_dur, target_dur))

        # Fjern duplikater og sorter
        seen = set()
        unique_anchors = []
        for s, t in anchors:
            if s not in seen:
                seen.add(s)
                unique_anchors.append((s, t))
        anchors = sorted(unique_anchors, key=lambda x: x[0])

        # Sikre at source-verdiene er strengt stigende
        clean_anchors = [anchors[0]]
        for i in range(1, len(anchors)):
            if anchors[i][0] > clean_anchors[-1][0]:
                clean_anchors.append(anchors[i])
        anchors = clean_anchors

        src_times = np.array([a[0] for a in anchors])
        tgt_times = np.array([a[1] for a in anchors])

        # ── Resampler WORLD-frames med piecewise mapping ──
        frame_period = timeaxis[1] - timeaxis[0] if len(timeaxis) > 1 else 0.005
        n_target = max(1, int(target_dur / frame_period))
        new_timeaxis = np.arange(n_target) * frame_period

        # For hvert target-frame, finn tilsvarende source-tid
        source_for_target = np.interp(new_timeaxis, tgt_times, src_times)

        # Konverter source-tid til source-frame-indeks
        n_current = len(f0)
        source_frame_idx = source_for_target / frame_period
        source_frame_idx = np.clip(source_frame_idx, 0, n_current - 1)

        # F0: lineær interpolering
        new_f0 = np.interp(source_frame_idx, np.arange(n_current), f0)

        # SP og AP: lineær interpolering for bedre lydkvalitet
        new_sp = self._interpolate_spectral(sp, source_frame_idx, n_current)
        new_ap = self._interpolate_spectral(ap, source_frame_idx, n_current)

        return new_f0, new_sp, new_ap, new_timeaxis

    # ────────────────────────────────────────────────────────
    #  Pitch fra song_data
    # ────────────────────────────────────────────────────────

    def _song_data_to_f0(self, song_data: dict, timeaxis: np.ndarray) -> np.ndarray:
        """
        Generer F0-kurve direkte fra song_data noter.
        Bruker presise beat-posisjoner → sekunder, ingen MIDI-fil parsing nødvendig.
        """
        tempo = song_data["tempo_bpm"]
        beat_to_sec = 60.0 / tempo

        # Bygg note-events: [(start_sec, end_sec, freq), ...]
        events = []
        beat_pos = 0.0
        for v_idx, verse in enumerate(song_data["verses"]):
            for note_data in verse["notes"]:
                duration = float(note_data["duration"])
                note_name = note_data["note"]
                midi_note = NOTE_MAP.get(note_name)
                if midi_note is not None:
                    start_sec = beat_pos * beat_to_sec
                    end_sec = (beat_pos + duration) * beat_to_sec
                    freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                    events.append((start_sec, end_sec, freq))
                beat_pos += duration
            # Pause mellom vers
            if v_idx < len(song_data["verses"]) - 1:
                beat_pos += 1.0

        # Bygg F0-kurve
        f0 = np.zeros_like(timeaxis)
        for start, end, freq in events:
            mask = (timeaxis >= start) & (timeaxis < end)
            f0[mask] = freq

        # ── Fyll korte gaps mellom noter (legato) ──
        # Uten dette får vi f0=0 mellom noter, som trigger mørk pitch eller
        # unvoiced artefakter. Gaps < 80ms fylles med forrige notes pitch.
        frame_period = timeaxis[1] - timeaxis[0] if len(timeaxis) > 1 else 0.005
        max_gap_frames = int(0.08 / frame_period)  # 80ms
        last_freq = 0.0
        gap_start = -1
        for i in range(len(f0)):
            if f0[i] > 0:
                if gap_start >= 0 and last_freq > 0:
                    gap_len = i - gap_start
                    if gap_len <= max_gap_frames:
                        # Kort gap — fyll med forrige notes pitch (legato)
                        f0[gap_start:i] = last_freq
                last_freq = f0[i]
                gap_start = -1
            else:
                if gap_start < 0:
                    gap_start = i

        n_notes = len(events)
        n_active = np.sum(f0 > 0)
        logger.info(f"  🎵 F0 fra song_data: {n_notes} noter, "
                    f"{n_active}/{len(f0)} frames aktive")

        return f0

    # ────────────────────────────────────────────────────────
    #  Fallback: MIDI-fil-basert pipeline (for bakover-kompatibilitet)
    # ────────────────────────────────────────────────────────

    def _midi_to_f0_curve(self, midi_path: Path, timeaxis: np.ndarray,
                          audio_duration: float) -> np.ndarray:
        """
        Konverter MIDI spor 0 (vokal) til F0-kurve.
        Skalerer MIDI-varighet til å matche TTS audio-varigheten.
        (Fallback — brukes kun når song_data ikke er tilgjengelig.)
        """
        mid = mido.MidiFile(str(midi_path))
        tempo = self._get_tempo(mid)

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

        midi_duration = events[-1][0]
        if midi_duration <= 0:
            return np.zeros_like(timeaxis)

        time_scale = audio_duration / midi_duration
        logger.info(f"  ⏱️ MIDI: {midi_duration:.1f}s → TTS: {audio_duration:.1f}s (scale: {time_scale:.2f}x)")

        f0_curve = np.zeros_like(timeaxis)
        for i, t in enumerate(timeaxis):
            midi_time = t / time_scale
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

    def _interpolate_spectral(self, data: np.ndarray, indices: np.ndarray,
                               n_source: int) -> np.ndarray:
        """
        Lineær interpolering av spektrale parametere (SP/AP) mellom frames.
        Gir mye jevnere lyd enn nærmeste-nabo ved time-stretching.
        """
        idx_floor = np.clip(np.floor(indices).astype(int), 0, n_source - 1)
        idx_ceil = np.clip(np.ceil(indices).astype(int), 0, n_source - 1)
        frac = (indices - idx_floor).reshape(-1, 1)  # Blend-faktor

        # Lineær blend mellom nabo-frames
        result = data[idx_floor] * (1.0 - frac) + data[idx_ceil] * frac
        return result

    def _smooth_f0(self, f0: np.ndarray, window: int = 2) -> np.ndarray:
        """Glatt F0-kurve for å unngå harde hopp, med lite vindu."""
        smoothed = f0.copy()
        voiced = f0 > 0

        for i in range(window, len(f0) - window):
            if voiced[i]:
                region = f0[i - window:i + window + 1]
                voiced_region = region[region > 0]
                if len(voiced_region) > 0:
                    smoothed[i] = np.median(voiced_region)

        return smoothed

    def _shift_spectral_envelope(self, sp: np.ndarray, old_f0: np.ndarray,
                                  new_f0: np.ndarray, sr: int) -> np.ndarray:
        """
        Skift spectral envelope (SP) for å bevare formanter når F0 endres.

        Uten dette høres vokaler feil ut: 'a' som 'e' osv.
        Vi beregner pitch-ratio per frame og shifter SP langs frekvens-aksen
        med invers ratio slik at formant-frekvensene forblir på rett sted.

        Metode: frequency warping av SP basert på pitch-endring.
        """
        n_frames, n_freq = sp.shape
        sp_shifted = sp.copy()
        freq_axis = np.arange(n_freq)

        for i in range(n_frames):
            if old_f0[i] > 0 and new_f0[i] > 0:
                ratio = new_f0[i] / old_f0[i]
                # Når pitch øker, formantene må flyttes NED (invers)
                # for å kompensere og beholde naturlig vokallyd
                if abs(ratio - 1.0) > 0.05:  # Bare skift ved >5% endring
                    # Warp frekvens-aksen: kompenser F0-endring
                    warped_idx = freq_axis / ratio
                    warped_idx = np.clip(warped_idx, 0, n_freq - 1)

                    # Lineær interpolering langs warped frekvens-akse
                    sp_shifted[i] = np.interp(freq_axis, warped_idx, sp[i])

        return sp_shifted
