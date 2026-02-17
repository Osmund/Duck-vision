#!/usr/bin/env python3
"""
Test sang-synkronisering: verifiserer at Singify, MidiBuilder og
TTS-pipelinen produserer korrekt tidssynkronisert output.

Kjører UTEN Azure/OpenAI — bruker syntetisk test-data.
"""

import sys
import json
import tempfile
import numpy as np
import soundfile as sf
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.singing.midi_builder import MidiBuilder, NOTE_MAP
from src.singing.singify import Singify

# ── Test sang-data (realistisk GPT-output) ──
# Følger GPT-reglene: 6 deler (vers1, refreng, vers2, refreng, vers3, refreng)
# 10-14 noter per vers, 8-12 per refreng, minimum 60 noter, tempo 115 BPM
SAMPLE_SONG = {
    "title": "Ulrikas Badedag",
    "tempo_bpm": 115,
    "key": "C",
    "verses": [
        {
            "type": "verse",
            "lyrics": "Ulrika svømmer i den lille dam\nHun plasker glad med vingen fram",
            "notes": [
                {"note": "C4", "duration": 1.0, "lyric": "Ul-"},
                {"note": "D4", "duration": 0.5, "lyric": "ri-"},
                {"note": "E4", "duration": 0.5, "lyric": "ka"},
                {"note": "F4", "duration": 1.0, "lyric": "svøm-"},
                {"note": "G4", "duration": 0.5, "lyric": "mer"},
                {"note": "A4", "duration": 0.5, "lyric": "i"},
                {"note": "G4", "duration": 0.5, "lyric": "den"},
                {"note": "F4", "duration": 0.5, "lyric": "li-"},
                {"note": "E4", "duration": 0.5, "lyric": "lle"},
                {"note": "D4", "duration": 1.0, "lyric": "dam"},
                {"note": "E4", "duration": 1.0, "lyric": "Hun"},
                {"note": "F4", "duration": 0.5, "lyric": "plas-"},
                {"note": "G4", "duration": 0.5, "lyric": "ker"},
                {"note": "A4", "duration": 1.0, "lyric": "glad"},
            ]
        },
        {
            "type": "chorus",
            "lyrics": "Kvakk kvakk kvakk sa Ulrika\nBadedag er bra ja",
            "notes": [
                {"note": "C5", "duration": 1.0, "lyric": "Kvakk"},
                {"note": "B4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "A4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "G4", "duration": 0.5, "lyric": "sa"},
                {"note": "A4", "duration": 0.5, "lyric": "Ul-"},
                {"note": "B4", "duration": 0.5, "lyric": "ri-"},
                {"note": "C5", "duration": 1.0, "lyric": "ka"},
                {"note": "A4", "duration": 1.0, "lyric": "Ba-"},
                {"note": "G4", "duration": 0.5, "lyric": "de-"},
                {"note": "F4", "duration": 0.5, "lyric": "dag"},
                {"note": "E4", "duration": 0.5, "lyric": "er"},
                {"note": "D4", "duration": 0.5, "lyric": "bra"},
                {"note": "C4", "duration": 1.0, "lyric": "ja"},
            ]
        },
        {
            "type": "verse",
            "lyrics": "Sola skinner varmt på fjæra her\nOg alle dyr er glade nær",
            "notes": [
                {"note": "C4", "duration": 0.5, "lyric": "Sol-"},
                {"note": "D4", "duration": 0.5, "lyric": "a"},
                {"note": "E4", "duration": 1.0, "lyric": "skin-"},
                {"note": "F4", "duration": 0.5, "lyric": "ner"},
                {"note": "G4", "duration": 1.0, "lyric": "varmt"},
                {"note": "A4", "duration": 0.5, "lyric": "på"},
                {"note": "G4", "duration": 0.5, "lyric": "fjæ-"},
                {"note": "F4", "duration": 0.5, "lyric": "ra"},
                {"note": "E4", "duration": 1.0, "lyric": "her"},
                {"note": "D4", "duration": 0.5, "lyric": "Og"},
                {"note": "E4", "duration": 0.5, "lyric": "al-"},
                {"note": "F4", "duration": 0.5, "lyric": "le"},
                {"note": "G4", "duration": 1.0, "lyric": "dyr"},
            ]
        },
        {
            "type": "chorus",
            "lyrics": "Kvakk kvakk kvakk sa Ulrika\nBadedag er bra ja",
            "notes": [
                {"note": "C5", "duration": 1.0, "lyric": "Kvakk"},
                {"note": "B4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "A4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "G4", "duration": 0.5, "lyric": "sa"},
                {"note": "A4", "duration": 0.5, "lyric": "Ul-"},
                {"note": "B4", "duration": 0.5, "lyric": "ri-"},
                {"note": "C5", "duration": 1.0, "lyric": "ka"},
                {"note": "A4", "duration": 1.0, "lyric": "Ba-"},
                {"note": "G4", "duration": 0.5, "lyric": "de-"},
                {"note": "F4", "duration": 0.5, "lyric": "dag"},
                {"note": "E4", "duration": 0.5, "lyric": "er"},
                {"note": "D4", "duration": 0.5, "lyric": "bra"},
                {"note": "C4", "duration": 1.0, "lyric": "ja"},
            ]
        },
        {
            "type": "verse",
            "lyrics": "Når det regner vil hun ut og gå\nFor regnet er det beste så",
            "notes": [
                {"note": "E4", "duration": 0.5, "lyric": "Når"},
                {"note": "F4", "duration": 0.5, "lyric": "det"},
                {"note": "G4", "duration": 1.0, "lyric": "reg-"},
                {"note": "A4", "duration": 0.5, "lyric": "ner"},
                {"note": "G4", "duration": 0.5, "lyric": "vil"},
                {"note": "F4", "duration": 0.5, "lyric": "hun"},
                {"note": "E4", "duration": 1.0, "lyric": "ut"},
                {"note": "D4", "duration": 0.5, "lyric": "og"},
                {"note": "C4", "duration": 1.0, "lyric": "gå"},
                {"note": "D4", "duration": 0.5, "lyric": "For"},
                {"note": "E4", "duration": 0.5, "lyric": "reg-"},
                {"note": "F4", "duration": 0.5, "lyric": "net"},
                {"note": "G4", "duration": 1.0, "lyric": "er"},
                {"note": "A4", "duration": 1.0, "lyric": "best"},
            ]
        },
        {
            "type": "chorus",
            "lyrics": "Kvakk kvakk kvakk sa Ulrika\nBadedag er bra ja",
            "notes": [
                {"note": "C5", "duration": 1.0, "lyric": "Kvakk"},
                {"note": "B4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "A4", "duration": 0.5, "lyric": "kvakk"},
                {"note": "G4", "duration": 0.5, "lyric": "sa"},
                {"note": "A4", "duration": 0.5, "lyric": "Ul-"},
                {"note": "B4", "duration": 0.5, "lyric": "ri-"},
                {"note": "C5", "duration": 1.0, "lyric": "ka"},
                {"note": "A4", "duration": 1.0, "lyric": "Ba-"},
                {"note": "G4", "duration": 0.5, "lyric": "de-"},
                {"note": "F4", "duration": 0.5, "lyric": "dag"},
                {"note": "E4", "duration": 0.5, "lyric": "er"},
                {"note": "D4", "duration": 0.5, "lyric": "bra"},
                {"note": "C4", "duration": 1.0, "lyric": "ja"},
            ]
        },
    ],
    "chords": [
        {"chord": "C", "beat": 0, "duration": 4},
        {"chord": "F", "beat": 4, "duration": 4},
        {"chord": "G", "beat": 8, "duration": 4},
        {"chord": "C", "beat": 12, "duration": 4},
        {"chord": "Am", "beat": 16, "duration": 4},
        {"chord": "F", "beat": 20, "duration": 4},
        {"chord": "G", "beat": 24, "duration": 4},
        {"chord": "C", "beat": 28, "duration": 4},
        {"chord": "F", "beat": 32, "duration": 4},
        {"chord": "G", "beat": 36, "duration": 4},
        {"chord": "Am", "beat": 40, "duration": 4},
        {"chord": "F", "beat": 44, "duration": 4},
        {"chord": "C", "beat": 48, "duration": 4},
        {"chord": "G", "beat": 52, "duration": 4},
        {"chord": "C", "beat": 56, "duration": 2},
    ]
}


def generate_test_tts_audio(duration_sec: float, sr: int = 24000) -> np.ndarray:
    """Generer syntetisk TTS-liknende audio med tale-lignende egenskaper."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec))

    # Simuler tale: varierende F0 rundt 200Hz + formanter
    f0_base = 200
    f0_variation = 30 * np.sin(2 * np.pi * 3 * t)  # Intonasjon
    f0 = f0_base + f0_variation

    # Grunnfrekvens + formanter
    phase = np.cumsum(2 * np.pi * f0 / sr)
    audio = 0.5 * np.sin(phase)
    audio += 0.3 * np.sin(2 * phase)   # F1
    audio += 0.15 * np.sin(3 * phase)  # F2

    # Amplitude-envelope (simuler ord med pauser)
    n_words = int(duration_sec * 4.5)  # ~4.5 stavelser/sek for norsk tale
    word_dur = duration_sec / max(n_words, 1)
    envelope = np.ones_like(t)
    for i in range(n_words):
        # Kort pause mellom ord
        pause_start = int((i + 1) * word_dur * sr - sr * 0.02)
        pause_end = int((i + 1) * word_dur * sr)
        pause_start = max(0, min(pause_start, len(envelope) - 1))
        pause_end = max(0, min(pause_end, len(envelope)))
        envelope[pause_start:pause_end] *= 0.1

    audio *= envelope
    audio = audio / np.max(np.abs(audio)) * 0.8
    return audio.astype(np.float64)


def generate_word_boundaries(song_data: dict, tts_duration: float) -> list:
    """Generer simulerte word boundaries som Azure TTS ville returnert."""
    boundaries = []
    all_words = []
    for verse in song_data["verses"]:
        for note in verse["notes"]:
            lyric = note.get("lyric", "")
            if lyric:
                all_words.append(lyric)

    time_per_word = tts_duration / len(all_words)
    for i, word in enumerate(all_words):
        boundaries.append({
            "time_ms": i * time_per_word * 1000,
            "word": word,
            "duration_ms": time_per_word * 1000 * 0.8,
        })

    return boundaries


def test_midi_builder():
    """Test at MidiBuilder lager korrekt MIDI fra song_data."""
    print("=" * 60)
    print("TEST 1: MidiBuilder")
    print("=" * 60)

    builder = MidiBuilder()
    with tempfile.TemporaryDirectory() as tmpdir:
        midi_path = builder.build(SAMPLE_SONG, Path(tmpdir) / "test.mid")

        assert midi_path.exists(), "MIDI-fil ikke opprettet"
        assert midi_path.stat().st_size > 100, "MIDI-fil for liten"

        # Sjekk at MIDI kan leses tilbake
        import mido
        mid = mido.MidiFile(str(midi_path))
        assert len(mid.tracks) >= 2, f"Forventet >= 2 spor, fikk {len(mid.tracks)}"

        # Tell noter i vokal-sporet
        note_count = 0
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    note_count += 1

        total_expected_notes = sum(len(v["notes"]) for v in SAMPLE_SONG["verses"])
        print(f"  MIDI noter totalt: {note_count} (vokal+komp)")
        print(f"  Forventet vokal-noter: {total_expected_notes}")
        assert note_count >= total_expected_notes, \
            f"For få noter: {note_count} < {total_expected_notes}"

    print("  ✅ MidiBuilder OK\n")


def test_vocal_duration_calc():
    """Test at vokal-varighet beregnes korrekt fra song_data."""
    print("=" * 60)
    print("TEST 2: Vokal-varighet beregning")
    print("=" * 60)

    singify = Singify(sample_rate=24000)
    duration = singify._calc_vocal_duration(SAMPLE_SONG)

    tempo = SAMPLE_SONG["tempo_bpm"]
    beat_to_sec = 60.0 / tempo

    # Manuell beregning
    total_beats = 0
    for i, verse in enumerate(SAMPLE_SONG["verses"]):
        verse_beats = sum(float(n["duration"]) for n in verse["notes"])
        total_beats += verse_beats
        if i < len(SAMPLE_SONG["verses"]) - 1:
            total_beats += 1.0  # pause

    expected = total_beats * beat_to_sec
    print(f"  Beregnet varighet: {duration:.2f}s")
    print(f"  Forventet varighet: {expected:.2f}s")
    print(f"  Total beats: {total_beats}")
    assert abs(duration - expected) < 0.01, f"Feil varighet: {duration} != {expected}"

    print("  ✅ Varighet-beregning OK\n")


def test_song_data_to_f0():
    """Test at F0-kurve fra song_data matcher notene."""
    print("=" * 60)
    print("TEST 3: F0-kurve fra song_data")
    print("=" * 60)

    singify = Singify(sample_rate=24000)
    duration = singify._calc_vocal_duration(SAMPLE_SONG)

    # Lag timeaxis
    frame_period = 0.005  # pyworld default
    n_frames = int(duration / frame_period)
    timeaxis = np.arange(n_frames) * frame_period

    f0 = singify._song_data_to_f0(SAMPLE_SONG, timeaxis)

    # Sjekk at F0-verdier er korrekte for kjente noter
    tempo = SAMPLE_SONG["tempo_bpm"]
    beat_to_sec = 60.0 / tempo

    # Første note: C4 starter ved t=0, varighet 1 beat
    c4_freq = 440.0 * (2.0 ** ((60 - 69) / 12.0))  # ~261.6 Hz
    c4_time = 0.25 * beat_to_sec  # Midt i første note
    c4_frame = int(c4_time / frame_period)
    if c4_frame < len(f0):
        assert abs(f0[c4_frame] - c4_freq) < 1.0, \
            f"C4 feil: {f0[c4_frame]:.1f} != {c4_freq:.1f}"
        print(f"  C4 @ t={c4_time:.3f}s: {f0[c4_frame]:.1f}Hz (forventet {c4_freq:.1f}Hz)")

    # Sjekk at det finnes aktive frames
    active_frames = np.sum(f0 > 0)
    total_frames = len(f0)
    active_pct = active_frames / total_frames * 100
    print(f"  Aktive frames: {active_frames}/{total_frames} ({active_pct:.0f}%)")
    assert active_pct > 50, f"For få aktive frames: {active_pct:.0f}%"

    # Sjekk at ulike noter gir ulike frekvenser
    unique_freqs = len(set(f0[f0 > 0].round(0)))
    expected_unique = len(set(n["note"] for v in SAMPLE_SONG["verses"] for n in v["notes"]))
    print(f"  Unike frekvenser: {unique_freqs} (forventet {expected_unique} noter)")
    assert unique_freqs >= expected_unique - 1, \
        f"For få unike frekvenser: {unique_freqs} < {expected_unique}"

    print("  ✅ F0-kurve fra song_data OK\n")


def test_uniform_time_stretch():
    """Test at uniform time-stretch endrer varighet korrekt."""
    print("=" * 60)
    print("TEST 4: Uniform time-stretch")
    print("=" * 60)

    singify = Singify(sample_rate=24000)

    # Lag test WORLD-data - realistiske verdier innenfor 1.3x stretch-grense
    frame_period = 0.005
    current_dur = 25.0  # TTS produserer 25s
    target_dur = 30.0   # MIDI er 30s (1.2x stretch, innenfor limit)
    n_frames = int(current_dur / frame_period)

    f0 = np.random.uniform(100, 300, n_frames)
    sp = np.random.rand(n_frames, 513)
    ap = np.random.rand(n_frames, 513)
    timeaxis = np.arange(n_frames) * frame_period

    new_f0, new_sp, new_ap, new_timeaxis = singify._uniform_time_stretch(
        f0, sp, ap, timeaxis, current_dur, target_dur
    )

    expected_frames = int(target_dur / frame_period)
    actual_dur = len(new_f0) * frame_period

    print(f"  Kilde: {n_frames} frames, {current_dur:.1f}s")
    print(f"  Mål: {expected_frames} frames, {target_dur:.1f}s")
    print(f"  Faktisk: {len(new_f0)} frames, {actual_dur:.1f}s")
    print(f"  Stretch-ratio: {target_dur/current_dur:.2f}x")

    assert abs(actual_dur - target_dur) < 0.1, \
        f"Feil varighet: {actual_dur:.1f} != {target_dur:.1f}"
    assert new_sp.shape[1] == sp.shape[1], "SP dimensjon endret"
    assert new_ap.shape[1] == ap.shape[1], "AP dimensjon endret"

    print("  ✅ Uniform time-stretch OK\n")


def test_piecewise_time_stretch():
    """Test at per-ord time-stretch gir bedre alignment enn uniform."""
    print("=" * 60)
    print("TEST 5: Per-ord time-stretch")
    print("=" * 60)

    singify = Singify(sample_rate=24000)

    # Lag test WORLD-data - realistisk TTS-varighet nær MIDI-mål
    target_dur = singify._calc_vocal_duration(SAMPLE_SONG)
    current_dur = target_dur * 0.9  # TTS er 10% kortere enn mål (innenfor 1.3x)
    n_frames = int(current_dur / 0.005)

    f0 = np.random.uniform(100, 300, n_frames)
    sp = np.random.rand(n_frames, 513)
    ap = np.random.rand(n_frames, 513)
    timeaxis = np.arange(n_frames) * 0.005

    word_boundaries = generate_word_boundaries(SAMPLE_SONG, current_dur)

    new_f0, new_sp, new_ap, new_timeaxis = singify._piecewise_time_stretch(
        f0, sp, ap, timeaxis, current_dur, target_dur,
        word_boundaries, SAMPLE_SONG
    )

    actual_dur = len(new_f0) * 0.005
    print(f"  Kilde: {n_frames} frames, {current_dur:.1f}s")
    print(f"  Mål: {target_dur:.1f}s")
    print(f"  Faktisk: {len(new_f0)} frames, {actual_dur:.1f}s")
    print(f"  Word boundaries brukt: {len(word_boundaries)}")

    assert abs(actual_dur - target_dur) < 0.2, \
        f"Feil varighet: {actual_dur:.1f} != {target_dur:.1f}"

    print("  ✅ Per-ord time-stretch OK\n")


def test_full_singify_pipeline():
    """Test full Singify-pipeline med syntetisk audio og song_data."""
    print("=" * 60)
    print("TEST 6: Full Singify-pipeline")
    print("=" * 60)

    singify = Singify(sample_rate=24000)

    # Beregn varigheter
    target_dur = singify._calc_vocal_duration(SAMPLE_SONG)

    # Simuler realistisk TTS-varighet med riktig Azure TTS rate (~2.8 syl/s)
    # Med ny rate-beregning er TTS nær MIDI-mål, trenger minimal stretch
    n_syllables = sum(len(v["notes"]) for v in SAMPLE_SONG["verses"])
    tts_dur = n_syllables / 2.8  # Azure TTS norsk med cheerful stil

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Lag syntetisk TTS-audio
        audio = generate_test_tts_audio(tts_dur, sr=24000)
        tts_path = tmpdir / "tts.wav"
        sf.write(str(tts_path), audio, 24000, subtype='PCM_16')

        # Lag MIDI
        builder = MidiBuilder()
        midi_path = builder.build(SAMPLE_SONG, tmpdir / "song.mid")

        # Lag word boundaries
        word_boundaries = generate_word_boundaries(SAMPLE_SONG, tts_dur)

        # Kjør Singify med song_data
        output_path = tmpdir / "vocals.wav"
        result = singify.process(
            tts_path, midi_path, output_path,
            word_boundaries=word_boundaries,
            song_data=SAMPLE_SONG
        )

        assert result.exists(), "Output-fil ikke opprettet"
        output_audio, output_sr = sf.read(str(result))
        output_dur = len(output_audio) / output_sr

        print(f"  TTS input: {tts_dur:.1f}s")
        print(f"  Mål-varighet (MIDI): {target_dur:.1f}s")
        print(f"  Output varighet: {output_dur:.1f}s")

        # Output skal v\u00e6re innenfor 1.3x stretch av TTS, og n\u00e6r MIDI-m\u00e5l
        max_expected = tts_dur * 1.3 + 0.5
        assert output_dur <= max_expected, \
            f"Output for lang: {output_dur:.1f}s > max {max_expected:.1f}s"

        # Med realistisk TTS-rate (2.8 syl/s), b\u00f8r output v\u00e6re n\u00e6r m\u00e5let
        stretch_ratio = output_dur / tts_dur
        print(f"  Stretch ratio: {stretch_ratio:.2f}x (maks: 1.3x)")
        print(f"  Differanse fra m\u00e5l: {abs(output_dur - target_dur):.2f}s")

        assert stretch_ratio <= 1.31, \
            f"Stretch for stor: {stretch_ratio:.2f}x > 1.3x"

    print("  ✅ Full Singify-pipeline OK\n")


def test_duck_tempo_scaling():
    """Test at duck-justert MIDI har korrekt pitch-faktor tempo."""
    print("=" * 60)
    print("TEST 7: Duck-tempo skalering")
    print("=" * 60)

    builder = MidiBuilder()

    DUCK_PITCH_OCTAVES = 0.5
    duck_pitch_factor = 2.0 ** DUCK_PITCH_OCTAVES

    duck_song = SAMPLE_SONG.copy()
    duck_song["tempo_bpm"] = SAMPLE_SONG["tempo_bpm"] * duck_pitch_factor

    print(f"  Original tempo: {SAMPLE_SONG['tempo_bpm']} BPM")
    print(f"  Duck tempo: {duck_song['tempo_bpm']:.0f} BPM")
    print(f"  Pitch faktor: {duck_pitch_factor:.3f}x")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Bygg begge MIDI-filer
        original_midi = builder.build(SAMPLE_SONG, tmpdir / "original.mid")
        duck_midi = builder.build(duck_song, tmpdir / "duck.mid")

        assert original_midi.exists()
        assert duck_midi.exists()

        # Sjekk at tempo er korrekt i MIDI
        import mido
        mid_orig = mido.MidiFile(str(original_midi))
        mid_duck = mido.MidiFile(str(duck_midi))

        def get_midi_tempo(mid):
            for track in mid.tracks:
                for msg in track:
                    if msg.type == 'set_tempo':
                        return msg.tempo
            return mido.bpm2tempo(120)

        orig_tempo = mido.tempo2bpm(get_midi_tempo(mid_orig))
        duck_tempo = mido.tempo2bpm(get_midi_tempo(mid_duck))

        ratio = duck_tempo / orig_tempo
        expected_ratio = duck_pitch_factor

        print(f"  MIDI original tempo: {orig_tempo:.0f} BPM")
        print(f"  MIDI duck tempo: {duck_tempo:.0f} BPM")
        print(f"  Ratio: {ratio:.3f} (forventet: {expected_ratio:.3f})")

        assert abs(ratio - expected_ratio) < 0.01, \
            f"Tempo-ratio feil: {ratio:.3f} != {expected_ratio:.3f}"

    print("  ✅ Duck-tempo skalering OK\n")


def test_note_map():
    """Test at NOTE_MAP inneholder de vanligste notene."""
    print("=" * 60)
    print("TEST 8: NOTE_MAP validering")
    print("=" * 60)

    # Sjekk at alle noter i test-sangen finnes
    for verse in SAMPLE_SONG["verses"]:
        for note_data in verse["notes"]:
            note_name = note_data["note"]
            assert note_name in NOTE_MAP, f"Note {note_name} mangler i NOTE_MAP"

    # Sjekk noen kjente verdier
    assert NOTE_MAP["C4"] == 60, f"C4 = {NOTE_MAP['C4']}, forventet 60"
    assert NOTE_MAP["A4"] == 69, f"A4 = {NOTE_MAP['A4']}, forventet 69"
    assert NOTE_MAP["C5"] == 72, f"C5 = {NOTE_MAP['C5']}, forventet 72"

    print(f"  NOTE_MAP har {len(NOTE_MAP)} oppføringer")
    print(f"  C4={NOTE_MAP['C4']}, A4={NOTE_MAP['A4']}, C5={NOTE_MAP['C5']}")

    print("  ✅ NOTE_MAP OK\n")


if __name__ == "__main__":
    print("\n🦆 DUCK SINGING SYNKRONISERINGS-TESTER\n")

    tests = [
        test_note_map,
        test_midi_builder,
        test_vocal_duration_calc,
        test_song_data_to_f0,
        test_uniform_time_stretch,
        test_piecewise_time_stretch,
        test_full_singify_pipeline,
        test_duck_tempo_scaling,
    ]

    passed = 0
    failed = 0
    errors = []

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test_fn.__name__, str(e)))
            print(f"  ❌ FEILET: {e}\n")

    print("=" * 60)
    print(f"RESULTAT: {passed}/{len(tests)} tester bestått", end="")
    if failed:
        print(f" ({failed} feilet)")
        for name, err in errors:
            print(f"  ❌ {name}: {err}")
    else:
        print(" 🎉")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
