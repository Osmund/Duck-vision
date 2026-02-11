"""
MIDI Builder - konverterer LLM-generert sang-data til MIDI-fil.
Lager to spor: vokal-melodi og akkord-komp.
"""

from midiutil import MIDIFile
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Note-name til MIDI-nummer
NOTE_MAP = {}
for _oct in range(0, 9):
    for _i, _name in enumerate(["C", "C#", "D", "D#", "E", "F",
                                  "F#", "G", "G#", "A", "A#", "B"]):
        NOTE_MAP[f"{_name}{_oct}"] = 12 + _oct * 12 + _i
# Flats
NOTE_MAP.update({
    f"Db{o}": NOTE_MAP[f"C#{o}"] for o in range(9) if f"C#{o}" in NOTE_MAP
})
NOTE_MAP.update({
    f"Eb{o}": NOTE_MAP[f"D#{o}"] for o in range(9) if f"D#{o}" in NOTE_MAP
})
NOTE_MAP.update({
    f"Gb{o}": NOTE_MAP[f"F#{o}"] for o in range(9) if f"F#{o}" in NOTE_MAP
})
NOTE_MAP.update({
    f"Ab{o}": NOTE_MAP[f"G#{o}"] for o in range(9) if f"G#{o}" in NOTE_MAP
})
NOTE_MAP.update({
    f"Bb{o}": NOTE_MAP[f"A#{o}"] for o in range(9) if f"A#{o}" in NOTE_MAP
})

# Akkord-definisjoner (halvtoner fra C0)
CHORD_INTERVALS = {
    "C":  [0, 4, 7],     "Cm":  [0, 3, 7],
    "C#": [1, 5, 8],     "Db":  [1, 5, 8],
    "D":  [2, 6, 9],     "Dm":  [2, 5, 9],
    "D#": [3, 7, 10],    "Eb":  [3, 7, 10],
    "E":  [4, 8, 11],    "Em":  [4, 7, 11],
    "F":  [5, 9, 12],    "Fm":  [5, 8, 12],
    "F#": [6, 10, 13],   "Gb":  [6, 10, 13],
    "G":  [7, 11, 14],   "Gm":  [7, 10, 14],
    "G#": [8, 12, 15],   "Ab":  [8, 12, 15],
    "A":  [9, 13, 16],   "Am":  [9, 12, 16],
    "A#": [10, 14, 17],  "Bb":  [10, 14, 17],
    "B":  [11, 15, 18],  "Bm":  [11, 14, 18],

    # Dur7 / Moll7
    "C7":  [0, 4, 7, 10],  "Cmaj7": [0, 4, 7, 11],
    "D7":  [2, 6, 9, 12],  "Dm7":   [2, 5, 9, 12],
    "E7":  [4, 8, 11, 14], "Em7":   [4, 7, 11, 14],
    "F7":  [5, 9, 12, 15], "Fmaj7": [5, 9, 12, 16],
    "G7":  [7, 11, 14, 17],
    "A7":  [9, 13, 16, 19], "Am7":  [9, 12, 16, 19],
    "B7":  [11, 15, 18, 21],
}


class MidiBuilder:
    def build(self, song_data: dict, output_path: Path) -> Path:
        """
        Bygg MIDI-fil fra sang-data.

        Spor 0: Vokal-melodi (brukes av pyworld for pitch)
        Spor 1: Akkorder + trommer (brukes av FluidSynth for komp)
        """
        tempo = song_data["tempo_bpm"]
        midi = MIDIFile(numTracks=2)

        # Spor 0: Vokal
        midi.addTrackName(0, 0, "Vocals")
        midi.addTempo(0, 0, tempo)
        midi.addProgramChange(0, 0, 0, 0)

        # Spor 1: Komp (flere instrumenter + trommer)
        midi.addTrackName(1, 0, "Band")
        midi.addTempo(1, 0, tempo)
        # Kanal 1: Akustisk gitar (program 25)
        midi.addProgramChange(1, 1, 0, 25)
        # Kanal 2: Bass (program 33 = fingered bass)
        midi.addProgramChange(1, 2, 0, 33)
        # Kanal 3: Strings pad (program 48)
        midi.addProgramChange(1, 3, 0, 48)
        # Kanal 9: Trommer (GM standard, ingen programChange nødvendig)

        # Skriv vokal-noter
        beat_pos = 0.0
        for verse in song_data["verses"]:
            for note_data in verse["notes"]:
                note_name = note_data["note"]
                midi_note = NOTE_MAP.get(note_name)
                if midi_note is None:
                    logger.warning(f"Ukjent note: {note_name}, hopper over")
                    continue
                duration = float(note_data["duration"])
                midi.addNote(
                    track=0, channel=0,
                    pitch=midi_note,
                    time=beat_pos,
                    duration=duration,
                    volume=100
                )
                beat_pos += duration
            # Litt pause mellom vers (1 beat)
            beat_pos += 1.0

        # Skriv akkorder med flere instrumenter
        for chord_data in song_data["chords"]:
            chord_name = chord_data["chord"]
            beat = float(chord_data["beat"])
            chord_dur = float(chord_data.get("duration", 4.0))
            intervals = CHORD_INTERVALS.get(chord_name, [0, 4, 7])

            # Kanal 1: Gitar-akkorder (midtre register)
            for interval in intervals:
                midi.addNote(
                    track=1, channel=1,
                    pitch=48 + interval,  # C3 base
                    time=beat,
                    duration=chord_dur * 0.9,
                    volume=85
                )

            # Kanal 2: Bass (grunntonn, lavt register)
            root = intervals[0] if intervals else 0
            midi.addNote(
                track=1, channel=2,
                pitch=36 + root,  # C2 base
                time=beat,
                duration=chord_dur,
                volume=90
            )

            # Kanal 3: Strings pad (høyt register)
            for interval in intervals[:3]:  # Maks 3 toner
                midi.addNote(
                    track=1, channel=3,
                    pitch=60 + interval,  # C4 base
                    time=beat,
                    duration=chord_dur,
                    volume=60
                )

        # ── Kanal 9: Trommer (GM drums) ──
        # Enkel beat: kick, snare, hihat
        KICK = 36    # Bass Drum 1
        SNARE = 38   # Acoustic Snare
        HIHAT_C = 42 # Closed Hi-Hat
        HIHAT_O = 46 # Open Hi-Hat

        # Finn total lengde — bruk maks av vokal-noter og akkorder
        total_beats_chords = 0
        for chord_data in song_data["chords"]:
            end = float(chord_data["beat"]) + float(chord_data.get("duration", 4.0))
            if end > total_beats_chords:
                total_beats_chords = end

        # beat_pos = slutten av siste vokal-note + pauser
        # Legg til litt ekstra for outro
        total_beats = max(beat_pos + 2.0, total_beats_chords)
        logger.info(f"  🎵 Instrumental lengde: {total_beats:.0f} beats (vokal: {beat_pos:.0f}, akkorder: {total_beats_chords:.0f})")

        # Utvid akkorder til å dekke hele sangen om nødvendig
        if total_beats_chords < beat_pos and song_data["chords"]:
            # Repeter akkordmønsteret for å fylle resten
            chord_cycle = song_data["chords"]
            cycle_len = total_beats_chords
            fill_beat = total_beats_chords
            while fill_beat < beat_pos + 2.0:
                for cd in chord_cycle:
                    c_name = cd["chord"]
                    c_dur = float(cd.get("duration", 4.0))
                    c_intervals = CHORD_INTERVALS.get(c_name, [0, 4, 7])
                    for interval in c_intervals:
                        midi.addNote(track=1, channel=1, pitch=48 + interval,
                                     time=fill_beat, duration=c_dur * 0.9, volume=85)
                    root = c_intervals[0] if c_intervals else 0
                    midi.addNote(track=1, channel=2, pitch=36 + root,
                                 time=fill_beat, duration=c_dur, volume=90)
                    for interval in c_intervals[:3]:
                        midi.addNote(track=1, channel=3, pitch=60 + interval,
                                     time=fill_beat, duration=c_dur, volume=60)
                    fill_beat += c_dur
                    if fill_beat >= beat_pos + 2.0:
                        break
            logger.info(f"  🔄 Akkorder utvidet fra {total_beats_chords:.0f} til {fill_beat:.0f} beats")

        # Generer drum-pattern for hele sangen
        beat = 0.0
        while beat < total_beats:
            # Kick på 1 og 3
            midi.addNote(track=1, channel=9, pitch=KICK,
                         time=beat, duration=0.5, volume=95)
            if beat + 2 < total_beats:
                midi.addNote(track=1, channel=9, pitch=KICK,
                             time=beat + 2, duration=0.5, volume=85)

            # Snare på 2 og 4
            if beat + 1 < total_beats:
                midi.addNote(track=1, channel=9, pitch=SNARE,
                             time=beat + 1, duration=0.5, volume=90)
            if beat + 3 < total_beats:
                midi.addNote(track=1, channel=9, pitch=SNARE,
                             time=beat + 3, duration=0.5, volume=85)

            # Hi-hat på hver 8-del
            for eighth in range(8):
                hh_time = beat + eighth * 0.5
                if hh_time < total_beats:
                    hh_vel = 70 if eighth % 2 == 0 else 55
                    midi.addNote(track=1, channel=9, pitch=HIHAT_C,
                                 time=hh_time, duration=0.25, volume=hh_vel)

            beat += 4.0  # Neste takt

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            midi.writeFile(f)

        logger.info(f"  🎼 MIDI skrevet: {output_path} ({beat_pos:.0f} beats)")
        return output_path
