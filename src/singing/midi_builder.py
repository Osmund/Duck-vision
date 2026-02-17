"""
MIDI Builder - konverterer LLM-generert sang-data til MIDI-fil.
Lager to spor: vokal-melodi og akkord-komp med variasjon."""

import random
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

        # Velg tilfeldig stil for variasjon
        STYLES = [
            {  # Pop
                "name": "Pop",
                "chord_prog": 25,   # Akustisk gitar
                "bass_prog": 33,    # Fingered bass
                "pad_prog": 48,     # Strings
                "drum_pattern": "standard",
            },
            {  # Funk
                "name": "Funk",
                "chord_prog": 1,    # Bright Piano
                "bass_prog": 34,    # Pick bass
                "pad_prog": 80,     # Square synth
                "drum_pattern": "funky",
            },
            {  # Ballade
                "name": "Ballade",
                "chord_prog": 0,    # Grand Piano
                "bass_prog": 32,    # Acoustic bass
                "pad_prog": 49,     # String Ensemble 2
                "drum_pattern": "soft",
            },
            {  # Latin
                "name": "Latin",
                "chord_prog": 24,   # Nylon guitar
                "bass_prog": 33,    # Fingered bass
                "pad_prog": 11,     # Vibraphone
                "drum_pattern": "latin",
            },
            {  # Reggae
                "name": "Reggae",
                "chord_prog": 4,    # Electric Piano
                "bass_prog": 33,    # Fingered bass
                "pad_prog": 16,     # Drawbar Organ
                "drum_pattern": "reggae",
            },
            {  # Rock
                "name": "Rock",
                "chord_prog": 29,   # Overdriven Guitar
                "bass_prog": 34,    # Pick bass
                "pad_prog": 89,     # Warm Pad
                "drum_pattern": "rock",
            },
        ]

        style = random.choice(STYLES)
        logger.info(f"  🎶 Stil: {style['name']}")

        # Kanal 1: Akkord-instrument
        midi.addProgramChange(1, 1, 0, style["chord_prog"])
        # Kanal 2: Bass
        midi.addProgramChange(1, 2, 0, style["bass_prog"])
        # Kanal 3: Pad/lead
        midi.addProgramChange(1, 3, 0, style["pad_prog"])
        # Kanal 9: Trommer (GM standard)

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
        drum_pattern = style["drum_pattern"]
        while beat < total_beats:
            if drum_pattern == "standard":
                self._drums_standard(midi, beat, total_beats)
            elif drum_pattern == "funky":
                self._drums_funky(midi, beat, total_beats)
            elif drum_pattern == "soft":
                self._drums_soft(midi, beat, total_beats)
            elif drum_pattern == "latin":
                self._drums_latin(midi, beat, total_beats)
            elif drum_pattern == "reggae":
                self._drums_reggae(midi, beat, total_beats)
            elif drum_pattern == "rock":
                self._drums_rock(midi, beat, total_beats)
            else:
                self._drums_standard(midi, beat, total_beats)
            beat += 4.0  # Neste takt

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            midi.writeFile(f)

        logger.info(f"  🎼 MIDI skrevet: {output_path} ({beat_pos:.0f} beats)")
        return output_path

    # ── Drum patterns ──
    KICK = 36
    SNARE = 38
    HIHAT_C = 42
    HIHAT_O = 46
    CLAP = 39
    RIMSHOT = 37
    CONGA_H = 63
    CONGA_L = 64
    COWBELL = 56
    RIDE = 51
    TOM_H = 50
    TOM_L = 45

    def _add_drum(self, midi, pitch, time, total, vol=80, dur=0.25):
        if time < total:
            midi.addNote(track=1, channel=9, pitch=pitch,
                         time=time, duration=dur, volume=vol)

    def _drums_standard(self, midi, beat, total):
        """Standard pop-beat."""
        self._add_drum(midi, self.KICK, beat, total, 95)
        self._add_drum(midi, self.KICK, beat + 2, total, 85)
        self._add_drum(midi, self.SNARE, beat + 1, total, 90)
        self._add_drum(midi, self.SNARE, beat + 3, total, 85)
        for e in range(8):
            vel = 70 if e % 2 == 0 else 55
            self._add_drum(midi, self.HIHAT_C, beat + e * 0.5, total, vel)

    def _drums_funky(self, midi, beat, total):
        """Funky beat med synkopering."""
        self._add_drum(midi, self.KICK, beat, total, 95)
        self._add_drum(midi, self.KICK, beat + 1.5, total, 80)
        self._add_drum(midi, self.KICK, beat + 2.5, total, 75)
        self._add_drum(midi, self.SNARE, beat + 1, total, 90)
        self._add_drum(midi, self.SNARE, beat + 3, total, 85)
        self._add_drum(midi, self.CLAP, beat + 1, total, 60)
        for e in range(16):
            vel = 65 if e % 2 == 0 else 45
            self._add_drum(midi, self.HIHAT_C, beat + e * 0.25, total, vel)
        self._add_drum(midi, self.HIHAT_O, beat + 3.75, total, 60)

    def _drums_soft(self, midi, beat, total):
        """Myk ballade — minimal, luftig."""
        self._add_drum(midi, self.KICK, beat, total, 70)
        self._add_drum(midi, self.KICK, beat + 2, total, 60)
        self._add_drum(midi, self.RIMSHOT, beat + 1, total, 55)
        self._add_drum(midi, self.RIMSHOT, beat + 3, total, 50)
        for e in range(4):
            self._add_drum(midi, self.RIDE, beat + e, total, 45)

    def _drums_latin(self, midi, beat, total):
        """Latin/bossa nova med conga."""
        self._add_drum(midi, self.KICK, beat, total, 85)
        self._add_drum(midi, self.KICK, beat + 2.5, total, 75)
        self._add_drum(midi, self.RIMSHOT, beat + 1, total, 70)
        self._add_drum(midi, self.RIMSHOT, beat + 3, total, 65)
        self._add_drum(midi, self.CONGA_H, beat + 0.5, total, 70)
        self._add_drum(midi, self.CONGA_L, beat + 1.5, total, 65)
        self._add_drum(midi, self.CONGA_H, beat + 2.5, total, 60)
        self._add_drum(midi, self.CONGA_L, beat + 3.5, total, 55)
        for e in range(8):
            self._add_drum(midi, self.HIHAT_C, beat + e * 0.5, total, 50)

    def _drums_reggae(self, midi, beat, total):
        """Reggae — betontoner på bakslag."""
        self._add_drum(midi, self.KICK, beat + 1.5, total, 90)
        self._add_drum(midi, self.KICK, beat + 3.5, total, 80)
        self._add_drum(midi, self.RIMSHOT, beat + 1, total, 85)
        self._add_drum(midi, self.RIMSHOT, beat + 3, total, 80)
        self._add_drum(midi, self.HIHAT_C, beat + 0.5, total, 60)
        self._add_drum(midi, self.HIHAT_C, beat + 1.5, total, 55)
        self._add_drum(midi, self.HIHAT_C, beat + 2.5, total, 60)
        self._add_drum(midi, self.HIHAT_C, beat + 3.5, total, 55)

    def _drums_rock(self, midi, beat, total):
        """Rock — tung kick, crashende hihat."""
        self._add_drum(midi, self.KICK, beat, total, 100)
        self._add_drum(midi, self.KICK, beat + 1.5, total, 85)
        self._add_drum(midi, self.KICK, beat + 2, total, 95)
        self._add_drum(midi, self.SNARE, beat + 1, total, 95)
        self._add_drum(midi, self.SNARE, beat + 3, total, 95)
        for e in range(8):
            vel = 80 if e % 2 == 0 else 60
            h = self.HIHAT_O if e in (3, 7) else self.HIHAT_C
            self._add_drum(midi, h, beat + e * 0.5, total, vel)
