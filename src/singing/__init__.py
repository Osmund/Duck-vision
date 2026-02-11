"""
Singing Duck Module
Genererer sanger fra fri-tekst forespørsler og streamer til anda.
Pipeline: GPT-4o → Azure TTS → pyworld singify → FluidSynth → WAV
"""

from .song_service import SongService

__all__ = ["SongService"]
