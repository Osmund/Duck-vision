#!/usr/bin/env python3
"""
Song Service - MQTT-tjeneste som lytter etter sang-forespørsler og
genererer sanger på Pi 5, leverer til Pi 4 (anda).

Pipeline:
  1. Motta forespørsel via MQTT (duck/singing/request)
  2. GPT-4o genererer lyrics + melodi
  3. Azure TTS genererer tale
  4. pyworld pitch-shifter tale til sang
  5. FluidSynth rendrer instrumental akkompagnement
  6. Mix vocals + instrumental
  7. SCP filer til Pi 4 musikk-mappe
  8. Publiser ferdig-melding (duck/singing/complete)

Bruk:
  python3 -m src.singing.song_service
"""

import json
import os
import time
import subprocess
import threading
import logging
import numpy as np
import soundfile as sf
from pathlib import Path
from dotenv import load_dotenv

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from .song_generator import SongGenerator
from .midi_builder import MidiBuilder
from .tts_provider import AzureTTS
from .singify import Singify
from .instrumental import InstrumentalRenderer

# Konfig
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("singing")

WORK_DIR = Path("/tmp/duck_singing")
WORK_DIR.mkdir(parents=True, exist_ok=True)

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "oDuckberry-2.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Anda (Pi 4) levering
ANDA_HOST = os.getenv("ANDA_HOST", "oDuckberry-2.local")
ANDA_USER = os.getenv("ANDA_USER", "admog")
ANDA_SSH_PASS = os.getenv("ANDA_SSH_PASS", "")
ANDA_MUSIKK_DIR = os.getenv("ANDA_MUSIKK_DIR", "/home/admog/Code/chatgpt-and/musikk")

# Azure TTS
AZURE_VOICE = os.getenv("AZURE_TTS_VOICE", "nb-NO-IselinNeural")

# Sample rate - må matche Pi 4 DAC (HiFiBerry krever 48kHz)
SAMPLE_RATE = 48000


class SongService:
    """MQTT-tjeneste som genererer sanger på forespørsel."""

    def __init__(self):
        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, client_id="duck-singing")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # Pipeline-komponenter (lazy init)
        self._generator = None
        self._midi_builder = None
        self._tts = None
        self._singify = None
        self._instrumental = None

        self._busy = False

    @property
    def generator(self):
        if self._generator is None:
            self._generator = SongGenerator()
        return self._generator

    @property
    def midi_builder(self):
        if self._midi_builder is None:
            self._midi_builder = MidiBuilder()
        return self._midi_builder

    @property
    def tts(self):
        if self._tts is None:
            self._tts = AzureTTS(voice=AZURE_VOICE)
        return self._tts

    @property
    def singify(self):
        if self._singify is None:
            self._singify = Singify(SAMPLE_RATE)
        return self._singify

    @property
    def instrumental(self):
        if self._instrumental is None:
            self._instrumental = InstrumentalRenderer(sample_rate=SAMPLE_RATE)
        return self._instrumental

    def start(self):
        """Start MQTT-tilkobling og lytt etter forespørsler."""
        logger.info(f"🦆 Singing Duck Service starter...")
        logger.info(f"  MQTT: {MQTT_BROKER}:{MQTT_PORT}")
        logger.info(f"  Anda: {ANDA_USER}@{ANDA_HOST}")
        logger.info(f"  Voice: {AZURE_VOICE}")

        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Avslutter...")
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0 or rc.value == 0:
            logger.info("✅ Koblet til MQTT broker")
            client.subscribe("duck/singing/request")
            logger.info("📡 Lytter på duck/singing/request")
        else:
            logger.error(f"❌ MQTT tilkobling feilet: {rc}")

    def _on_message(self, client, userdata, msg):
        """Håndter innkommende MQTT-meldinger."""
        if msg.topic != "duck/singing/request":
            return

        if self._busy:
            logger.warning("⚠️ Allerede opptatt med å lage en sang, ignorerer forespørsel")
            self._publish_status("busy", "Jeg holder allerede på med en sang!")
            return

        try:
            data = json.loads(msg.payload.decode())
            prompt = data.get("prompt", "")
            song_id = data.get("song_id", f"song_{int(time.time())}")

            if not prompt:
                logger.warning("Tom prompt mottatt")
                return

            logger.info(f"🎵 Mottok forespørsel: '{prompt}' (id: {song_id})")

            # Kjør generering i egen tråd for å ikke blokkere MQTT
            thread = threading.Thread(
                target=self._generate_song,
                args=(song_id, prompt),
                daemon=True
            )
            thread.start()

        except Exception as e:
            logger.error(f"Feil ved parsing av forespørsel: {e}")

    def _generate_song(self, song_id: str, prompt: str):
        """Komplett pipeline: prompt → ferdig sang levert til anda."""
        self._busy = True
        t0 = time.monotonic()
        work = WORK_DIR / song_id
        work.mkdir(parents=True, exist_ok=True)

        try:
            # ── 1. GPT-4o: Generer sang ──
            self._publish_status("generating", "Skriver tekst og melodi...")
            song_data = self.generator.generate(prompt)
            title = song_data["title"]
            t1 = time.monotonic()
            logger.info(f"  📝 '{title}' generert ({t1-t0:.1f}s)")

            # Lagre for debugging
            with open(work / "song.json", "w") as f:
                json.dump(song_data, f, indent=2, ensure_ascii=False)

            # ── 2. MIDI fra sang-data ──
            midi_path = self.midi_builder.build(song_data, work / "song.mid")

            # ── 3. Azure TTS med visemes ──
            self._publish_status("synthesizing", "Syntetiserer stemme...")
            lyrics = " ".join(v["lyrics"] for v in song_data["verses"])
            tts_result = self.tts.synthesize(lyrics, work / "tts.wav")
            t2 = time.monotonic()
            logger.info(f"  🗣️ TTS ferdig ({t2-t1:.1f}s)")

            # Lagre visemes
            with open(work / "visemes.json", "w") as f:
                json.dump(tts_result.visemes, f)

            # ── 4. Singify (pyworld) ──
            self._publish_status("singing", "Gjør tale om til sang...")
            vocals_path = self.singify.process(
                tts_result.audio_path, midi_path, work / "vocals.wav",
                word_boundaries=tts_result.word_boundaries
            )
            t3 = time.monotonic()
            logger.info(f"  🎤 Singify ferdig ({t3-t2:.1f}s)")

            # ── 5. Instrumental ──
            self._publish_status("mixing", "Legger til musikk...")
            inst_path = self.instrumental.render(midi_path, work / "instrumental.wav")
            t4 = time.monotonic()
            logger.info(f"  🎹 Instrumental ferdig ({t4-t3:.1f}s)")

            # ── 6. Mix ──
            mix_path, vocals_final = self._create_mix(
                vocals_path, inst_path, work
            )
            t5 = time.monotonic()
            total = t5 - t0
            logger.info(f"  ⏱️ Total renderingstid: {total:.1f}s")

            # ── 7. Lever til anda ──
            self._publish_status("delivering", "Sender sang til anda...")
            folder_name = f"AI - {title}"
            remote_path = self._deliver_to_anda(
                mix_path, vocals_final, folder_name
            )

            # ── 8. Ferdig! ──
            self._publish_complete(song_id, title, remote_path, total)
            logger.info(f"  🦆 '{title}' levert til anda! ({total:.1f}s totalt)")

        except Exception as e:
            logger.error(f"❌ Feil ved generering: {e}", exc_info=True)
            self._publish_status("error", str(e))
        finally:
            self._busy = False

    def _create_mix(self, vocals_path: Path, inst_path: Path,
                    work_dir: Path) -> tuple:
        """
        Lag duck_mix.wav (stereo vokal+instrumental) og
        vocals_duck.wav (stereo vokal alene, for nebb-analyse).
        Matcher formatet eksisterende sanger bruker.
        Singify gjør allerede duck-pitch i sitt ene vocoding-pass,
        så vi trenger IKKE andifisering her.
        Synkroniserer vokal med instrumental varighet.
        """
        from scipy.signal import resample

        vocals, v_sr = sf.read(str(vocals_path))
        inst, i_sr = sf.read(str(inst_path))

        # Mono-ify hvis nødvendig
        if len(vocals.shape) > 1:
            vocals = vocals.mean(axis=1)
        if len(inst.shape) > 1:
            inst = inst.mean(axis=1)

        # ── Andifisering med resampling (samme metode som Pi 4) ──
        # Resample til færre samples = høyere pitch når spilt på original sample rate
        # "Alvin og gjengen"-effekten — enkel og bra lydkvalitet
        DUCK_PITCH_OCTAVES = 0.5  # 0.5 oktav opp
        pitch_factor = 2.0 ** DUCK_PITCH_OCTAVES  # 1.414x

        # Normaliser amplitude først
        peak_before = np.max(np.abs(vocals))
        if peak_before > 0.01:
            vocals = vocals / peak_before * 0.90

        new_length = int(len(vocals) / pitch_factor)
        vocals = resample(vocals, new_length).astype(np.float32)

        # Sjekk for clipping etter resampling
        peak = np.max(np.abs(vocals))
        if peak > 0.95:
            vocals = vocals / peak * 0.95

        logger.info(f"  🦆 Andifisering: {DUCK_PITCH_OCTAVES} oktaver opp (resampling, {pitch_factor:.2f}x)")

        # ── Karaoke-klang (reverb) på vokalen ──
        reverb_delays = [
            (int(v_sr * 0.03), 0.3),   # 30ms tidlig refleksjon
            (int(v_sr * 0.06), 0.2),   # 60ms
            (int(v_sr * 0.12), 0.15),  # 120ms
            (int(v_sr * 0.20), 0.08),  # 200ms sen hall
            (int(v_sr * 0.35), 0.04),  # 350ms hale
        ]
        reverb = np.zeros(len(vocals) + int(v_sr * 0.4), dtype=np.float32)
        reverb[:len(vocals)] = vocals
        for delay_samples, gain in reverb_delays:
            reverb[delay_samples:delay_samples + len(vocals)] += vocals * gain
        vocals = reverb[:len(vocals)]

        # Normaliser etter reverb
        peak = np.max(np.abs(vocals))
        if peak > 0.95:
            vocals = vocals / peak * 0.95
        logger.info(f"  🎤 Karaoke-klang lagt til (5 refleksjoner)")

        # ── Synkroniser instrumental til andifisert vokal-lengde ──
        # VIKTIG: Vokalen er nå kortere pga pitch-shift. Vi tilpasser
        # instrumentalen til vokalen — ALDRI strekk vokalen tilbake,
        # for det reverserer pitch-shiften!
        vocal_dur = len(vocals) / v_sr
        inst_dur = len(inst) / i_sr
        logger.info(f"  ⏱️ Vokal: {vocal_dur:.1f}s (andifisert), Instrumental: {inst_dur:.1f}s")

        if inst_dur > vocal_dur * 1.5:
            # Instrumental MYE lengre → trim med god margin + fade out
            target_dur = vocal_dur + 3.0  # 3s outro
            target_len = int(target_dur * i_sr)
            inst = inst[:target_len]
            fade_samples = int(1.0 * i_sr)
            if len(inst) > fade_samples:
                fade = np.linspace(1.0, 0.0, fade_samples)
                inst[-fade_samples:] *= fade
            logger.info(f"  ✂️ Instrumental trimmet: {inst_dur:.1f}s → {target_dur:.1f}s")
        elif vocal_dur > inst_dur + 2.0:
            # Vokal lengre → stretch instrumentalen (ikke vokalen!)
            target_samples = int(len(inst) * vocal_dur / inst_dur)
            inst = np.interp(
                np.linspace(0, len(inst) - 1, target_samples),
                np.arange(len(inst)),
                inst
            )
            logger.info(f"  ⏱️ Instrumental strukket: {inst_dur:.1f}s → {vocal_dur:.1f}s")

        # Resample alt til target sample rate
        target_sr = SAMPLE_RATE  # 48kHz for HiFiBerry DAC
        if v_sr != target_sr:
            vocals = np.interp(
                np.linspace(0, len(vocals), int(len(vocals) * target_sr / v_sr)),
                np.arange(len(vocals)), vocals
            )
        if i_sr != target_sr:
            inst = np.interp(
                np.linspace(0, len(inst), int(len(inst) * target_sr / i_sr)),
                np.arange(len(inst)), inst
            )

        # Pad til lik lengde
        max_len = max(len(vocals), len(inst))
        if len(vocals) < max_len:
            vocals = np.pad(vocals, (0, max_len - len(vocals)))
        if len(inst) < max_len:
            inst = np.pad(inst, (0, max_len - len(inst)))

        # Mix: vokal tydelig foran instrumental
        mix_mono = vocals * 1.5 + inst * 0.35
        max_val = np.max(np.abs(mix_mono))
        if max_val > 0.99:
            mix_mono = mix_mono / max_val * 0.95

        # Stereo (begge kanaler like)
        mix_stereo = np.column_stack([mix_mono, mix_mono])
        vocals_stereo = np.column_stack([vocals, vocals])

        # Lagre som WAV
        mix_path = work_dir / "duck_mix.wav"
        vocals_final = work_dir / "vocals_duck.wav"

        sf.write(str(mix_path), mix_stereo, target_sr, subtype='PCM_16')
        sf.write(str(vocals_final), vocals_stereo, target_sr, subtype='PCM_16')

        logger.info(f"  🎚️ Mix: {len(mix_mono)/target_sr:.1f}s stereo @ {target_sr}Hz")
        return mix_path, vocals_final

    def _deliver_to_anda(self, mix_path: Path, vocals_path: Path,
                         folder_name: str) -> str:
        """SCP duck_mix.wav og vocals_duck.wav til Pi 4 musikk-mappe."""
        remote_dir = f"{ANDA_MUSIKK_DIR}/{folder_name}"

        if not ANDA_SSH_PASS:
            logger.warning("⚠️ ANDA_SSH_PASS ikke satt, kan ikke levere via SCP")
            logger.warning("  Filer ligger i: {mix_path.parent}")
            return str(mix_path.parent)

        try:
            # Opprett mappe på anda
            self._ssh_cmd(f"mkdir -p '{remote_dir}'")

            # SCP filene
            self._scp_file(mix_path, f"{remote_dir}/duck_mix.wav")
            self._scp_file(vocals_path, f"{remote_dir}/vocals_duck.wav")

            logger.info(f"  📦 Levert til {ANDA_HOST}:{remote_dir}")
            return remote_dir

        except Exception as e:
            logger.error(f"SCP feilet: {e}")
            raise

    def _ssh_cmd(self, cmd: str):
        """Kjør en kommando på anda via SSH."""
        subprocess.run(
            ["sshpass", "-p", ANDA_SSH_PASS, "ssh",
             "-o", "StrictHostKeyChecking=no",
             f"{ANDA_USER}@{ANDA_HOST}", cmd],
            check=True, timeout=10, capture_output=True
        )

    def _scp_file(self, local_path: Path, remote_path: str):
        """Kopier en fil til anda via SCP."""
        subprocess.run(
            ["sshpass", "-p", ANDA_SSH_PASS, "scp",
             "-o", "StrictHostKeyChecking=no",
             str(local_path),
             f"{ANDA_USER}@{ANDA_HOST}:{remote_path}"],
            check=True, timeout=60, capture_output=True
        )

    def _publish_status(self, status: str, message: str):
        """Publiser status-oppdatering."""
        payload = json.dumps({
            "status": status,
            "message": message,
            "timestamp": time.time()
        })
        self.client.publish("duck/singing/status", payload, qos=0)

    def _publish_complete(self, song_id: str, title: str,
                          remote_path: str, render_time: float):
        """Publiser ferdig-melding."""
        payload = json.dumps({
            "song_id": song_id,
            "title": title,
            "path": remote_path,
            "render_time": round(render_time, 1),
            "status": "complete"
        })
        self.client.publish("duck/singing/complete", payload, qos=1)
        logger.info(f"  📡 Publisert duck/singing/complete")


def main():
    """Start Song Service."""
    service = SongService()
    service.start()


if __name__ == "__main__":
    main()
