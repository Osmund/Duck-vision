"""
FluidSynth instrumental renderer.
Render MIDI akkord-spor til audio.

sudo apt install fluidsynth fluid-soundfont-gm
"""

import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DEFAULT_SOUNDFONT = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
ALT_SOUNDFONT = "/usr/share/sounds/sf2/default-GM.sf2"


class InstrumentalRenderer:
    def __init__(self, soundfont_path: str = None, sample_rate: int = 24000):
        self.sample_rate = sample_rate

        # Finn soundfont
        if soundfont_path and Path(soundfont_path).exists():
            self.soundfont = Path(soundfont_path)
        elif Path(DEFAULT_SOUNDFONT).exists():
            self.soundfont = Path(DEFAULT_SOUNDFONT)
        elif Path(ALT_SOUNDFONT).exists():
            self.soundfont = Path(ALT_SOUNDFONT)
        else:
            # Søk etter en SF2-fil
            import glob
            sf2_files = glob.glob("/usr/share/sounds/sf2/*.sf2")
            if sf2_files:
                self.soundfont = Path(sf2_files[0])
            else:
                raise FileNotFoundError(
                    "Ingen SoundFont funnet. Installer: sudo apt install fluid-soundfont-gm"
                )

        logger.info(f"🎹 SoundFont: {self.soundfont}")

    def render(self, midi_path: Path, output_path: Path) -> Path:
        """Render MIDI til WAV med FluidSynth."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"🎹 Rendrer instrumental fra {midi_path}")

        result = subprocess.run([
            "fluidsynth",
            "-ni",                          # Ikke-interaktiv
            "-g", "2.0",                    # Gain (kraftig lyd)
            "-r", str(self.sample_rate),
            "-F", str(output_path),
            str(self.soundfont),
            str(midi_path),
        ], capture_output=True, timeout=30)

        if result.returncode != 0:
            raise RuntimeError(f"FluidSynth feilet: {result.stderr.decode()}")

        logger.info(f"  ✅ Instrumental ferdig: {output_path}")
        return output_path
