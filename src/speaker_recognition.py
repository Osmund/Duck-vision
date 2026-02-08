#!/usr/bin/env python3
"""
Duck-Vision Speaker Recognition Module
Passiv stemmegjenkjenning som supplement til ansiktsgjenkjenning.

Funksjonalitet:
- Kontinuerlig mikrofon-lytting i bakgrunnstråd
- VAD (Voice Activity Detection) med WebRTC VAD
- Speaker embedding med Resemblyzer (d-vector)
- Matching mot kjente stemmeprofiler
- Automatisk profilbygging når ansikt er kjent men stemme ikke er det

Arkitektur:
  Mikrofon (48kHz) → Resample (16kHz) → VAD → Speaker Embedding → Match
"""

import os
# Numba JIT fungerer ikke stabilt på ARM (Pi 5) - deaktiver før librosa importeres
os.environ['NUMBA_DISABLE_JIT'] = '1'

import time
import threading
import logging
import pickle
import struct
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


def _hz_to_mel(hz):
    """Konverter Hz til Mel-skala."""
    return 2595.0 * np.log10(1.0 + hz / 700.0)

def _mel_to_hz(mel):
    """Konverter Mel-skala til Hz."""
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

def _mel_filterbank(sr, n_fft, n_mels, fmin=0.0, fmax=None):
    """Lag mel-filterbank uten librosa (ren numpy)."""
    if fmax is None:
        fmax = sr / 2.0
    
    n_freqs = n_fft // 2 + 1
    fft_freqs = np.linspace(0, sr / 2.0, n_freqs)
    
    mel_min = _hz_to_mel(fmin)
    mel_max = _hz_to_mel(fmax)
    mels = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = _mel_to_hz(mels)
    
    filterbank = np.zeros((n_mels, n_freqs))
    for i in range(n_mels):
        lower = hz_points[i]
        center = hz_points[i + 1]
        upper = hz_points[i + 2]
        
        # Stigende flanke
        up_mask = (fft_freqs >= lower) & (fft_freqs <= center)
        if center > lower:
            filterbank[i, up_mask] = (fft_freqs[up_mask] - lower) / (center - lower)
        
        # Synkende flanke
        down_mask = (fft_freqs >= center) & (fft_freqs <= upper)
        if upper > center:
            filterbank[i, down_mask] = (upper - fft_freqs[down_mask]) / (upper - center)
    
    return filterbank

def _patch_resemblyzer_mel():
    """
    Monkey-patch resemblyzer til å bruke scipy i stedet for librosa
    for mel-spektrogram-beregning. Unngår numba/librosa-problemer på ARM.
    """
    try:
        from scipy.signal import stft as scipy_stft
        import resemblyzer.audio as raudio
        from resemblyzer.hparams import sampling_rate, mel_window_length, mel_window_step, mel_n_channels
        
        n_fft = int(sampling_rate * mel_window_length / 1000)
        hop_length = int(sampling_rate * mel_window_step / 1000)
        mel_basis = _mel_filterbank(sampling_rate, n_fft, mel_n_channels)
        
        def patched_wav_to_mel_spectrogram(wav):
            """Mel-spektrogram via scipy (erstatter librosa-versjonen)."""
            _, _, Zxx = scipy_stft(wav, fs=sampling_rate, nperseg=n_fft, 
                                    noverlap=n_fft - hop_length, window='hann')
            S = np.abs(Zxx) ** 2
            mel = mel_basis @ S
            return mel.astype(np.float32).T
        
        raudio.wav_to_mel_spectrogram = patched_wav_to_mel_spectrogram
        logger.info("✓ Resemblyzer patchet til å bruke scipy (unngår librosa/numba)")
    except Exception as e:
        logger.warning(f"Kunne ikke patche resemblyzer mel-spektrogram: {e}")


class SpeakerRecognition:
    """
    Passiv stemmegjenkjenning for Duck-Vision.
    
    Lytter kontinuerlig på mikrofon, detekterer tale via VAD,
    og matcher stemmer mot kjente profiler.
    
    Kan også bygge nye profiler automatisk når personen er identifisert
    via ansiktsgjenkjenning men mangler stemmeprofil.
    """
    
    def __init__(self, config: dict, event_callback: Optional[Callable] = None):
        """
        Args:
            config: VOICE_CONFIG fra config.py
            event_callback: Callback for events (speaker_recognized, voice_profile_created, etc.)
        """
        self.config = config
        self.event_callback = event_callback
        
        # State
        self.running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Kjente stemmeprofiler: {name: np.ndarray (256-dim embedding)}
        self.known_voices: Dict[str, np.ndarray] = {}
        
        # Muting: ignorér audio når Samantha snakker
        self._muted = False
        self._mute_lock = threading.Lock()
        
        # Samtale-modus: høykvalitets stemmegjenkjenning under aktiv samtale
        self._conversation_active = False
        self._conversation_lock = threading.Lock()
        self._conversation_audio: List[np.ndarray] = []  # Samlet tale fra samtalen
        self._conversation_matched = False  # Har vi allerede matchet i denne samtalen?
        self._conversation_match_sent = False  # Har vi sendt match-event?
        
        # Auto-enrollment state
        self._enrolling_name: Optional[str] = None  # Person vi samler stemme for
        self._enroll_audio_buffer: List[np.ndarray] = []  # Samlet tale-audio
        self._enroll_speech_seconds: float = 0.0  # Akkumulert tale-varighet
        self._enroll_start_time: float = 0.0  # Når vi startet innsamling
        self._enroll_lock = threading.Lock()
        
        # Lazy-loaded components
        self._vad = None
        self._encoder = None
        self._sd = None  # sounddevice
        
        # Last kjente profiler
        self._load_voice_profiles()
        
        logger.info(f"SpeakerRecognition initialisert med {len(self.known_voices)} kjente stemmer")
    
    # ─── Muting (når Samantha snakker) ───────────────────────────────
    
    def mute(self):
        """Mute mikrofon-prosessering (kalt når Samantha snakker)"""
        with self._mute_lock:
            if not self._muted:
                self._muted = True
                logger.info("🔇 Mikrofon mutet (Samantha snakker)")
    
    def unmute(self):
        """Unmute mikrofon-prosessering (kalt når Samantha er ferdig)"""
        with self._mute_lock:
            if self._muted:
                self._muted = False
                logger.info("🔊 Mikrofon unmutet")
    
    @property
    def is_muted(self) -> bool:
        with self._mute_lock:
            return self._muted
    
    # ─── Samtale-modus (conversation-aware) ───────────────────────────
    
    def start_conversation(self):
        """Signal at en samtale er aktiv (wake word aktivert).
        
        Under samtale:
        - Senker match-cooldown (raskere gjenkjenning)
        - Samler all tale for bedre identifisering
        - Sender match-event så fort stemmen er gjenkjent
        """
        with self._conversation_lock:
            if not self._conversation_active:
                self._conversation_active = True
                self._conversation_audio = []
                self._conversation_matched = False
                self._conversation_match_sent = False
                logger.info("💬 Samtale startet - prioriterer stemmegjenkjenning")
    
    def end_conversation(self):
        """Signal at samtalen er avsluttet.
        
        Hvis vi har samlet nok tale uten match, prøv en siste matching.
        Hvis vi har en kjent person uten stemmeprofil, bruk samtale-audio til enrollment.
        """
        with self._conversation_lock:
            if not self._conversation_active:
                return
            
            self._conversation_active = False
            audio_chunks = self._conversation_audio.copy()
            already_matched = self._conversation_matched
            self._conversation_audio = []
            
        logger.info("💬 Samtale avsluttet")
        
        # Hvis vi ikke matchet under samtalen, prøv med all samlet audio
        if not already_matched and audio_chunks and self.known_voices:
            total_audio = np.concatenate(audio_chunks)
            total_speech = len(total_audio) / 16000
            
            if total_speech >= 2.0:
                logger.info(f"💬 Prøver siste matching med {total_speech:.1f}s samlet tale")
                embedding = self._compute_embedding(total_audio)
                
                if embedding is not None:
                    name, confidence = self._match_speaker(embedding)
                    if name:
                        logger.info(f"💬 Stemme gjenkjent ved samtaleslutt: {name} ({confidence:.2%})")
                        if self.event_callback:
                            self.event_callback("speaker_recognized", {
                                "name": name,
                                "confidence": round(confidence, 3),
                                "speech_duration": round(total_speech, 1),
                                "source": "conversation_end",
                            })
        
        # Bruk samtale-audio til enrollment hvis aktuelt
        if audio_chunks:
            with self._enroll_lock:
                if self._enrolling_name and not already_matched:
                    for chunk in audio_chunks:
                        self._enroll_audio_buffer.append(chunk)
                        self._enroll_speech_seconds += len(chunk) / 16000
    
    @property
    def is_conversation_active(self) -> bool:
        with self._conversation_lock:
            return self._conversation_active
    
    # ─── Lazy Loading ───────────────────────────────────────────────
    
    def _get_vad(self):
        """Lazy-load WebRTC VAD"""
        if self._vad is None:
            import webrtcvad
            self._vad = webrtcvad.Vad(self.config["vad_aggressiveness"])
            logger.info(f"✓ WebRTC VAD lastet (aggressiveness={self.config['vad_aggressiveness']})")
        return self._vad
    
    def _get_encoder(self):
        """Lazy-load Resemblyzer voice encoder"""
        if self._encoder is None:
            _patch_resemblyzer_mel()  # Erstatt librosa med scipy før bruk
            from resemblyzer import VoiceEncoder
            self._encoder = VoiceEncoder("cpu")
            logger.info("✓ Resemblyzer VoiceEncoder lastet")
        return self._encoder
    
    def _get_sounddevice(self):
        """Lazy-load sounddevice"""
        if self._sd is None:
            import sounddevice as sd
            self._sd = sd
        return self._sd
    
    # ─── Profilhåndtering ───────────────────────────────────────────
    
    def _load_voice_profiles(self):
        """Last alle stemmeprofiler fra disk"""
        voice_dir = Path(self.config["data_dir"])
        self.known_voices = {}
        
        if not voice_dir.exists():
            voice_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for profile_file in voice_dir.glob("*.pkl"):
            try:
                with open(profile_file, "rb") as f:
                    data = pickle.load(f)
                name = data["name"]
                embedding = data["embedding"]
                self.known_voices[name] = embedding
                logger.info(f"  Lastet stemmeprofil: {name}")
            except Exception as e:
                logger.error(f"  Feil ved lasting av {profile_file}: {e}")
        
        if self.known_voices:
            logger.info(f"✓ Lastet {len(self.known_voices)} stemmeprofil(er)")
    
    def _save_voice_profile(self, name: str, embedding: np.ndarray) -> bool:
        """Lagre stemmeprofil til disk"""
        voice_dir = Path(self.config["data_dir"])
        voice_dir.mkdir(parents=True, exist_ok=True)
        
        profile_path = voice_dir / f"{name}.pkl"
        try:
            data = {
                "name": name,
                "embedding": embedding,
                "created_at": time.time(),
            }
            with open(profile_path, "wb") as f:
                pickle.dump(data, f)
            
            self.known_voices[name] = embedding
            logger.info(f"✓ Stemmeprofil lagret for {name}")
            return True
        except Exception as e:
            logger.error(f"❌ Feil ved lagring av stemmeprofil for {name}: {e}")
            return False
    
    def has_voice_profile(self, name: str) -> bool:
        """Sjekk om en person har stemmeprofil"""
        return name in self.known_voices
    
    def list_known_speakers(self) -> List[str]:
        """Returner liste over personer med stemmeprofil"""
        return list(self.known_voices.keys())
    
    def forget_speaker(self, name: str) -> bool:
        """Slett stemmeprofil for en person"""
        voice_dir = Path(self.config["data_dir"])
        profile_path = voice_dir / f"{name}.pkl"
        
        if name in self.known_voices:
            del self.known_voices[name]
        
        if profile_path.exists():
            profile_path.unlink()
            logger.info(f"✓ Stemmeprofil slettet for {name}")
            return True
        return False
    
    # ─── Audio-prosessering ─────────────────────────────────────────
    
    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio fra orig_sr til target_sr"""
        if orig_sr == target_sr:
            return audio
        import soxr
        return soxr.resample(audio, orig_sr, target_sr)
    
    def _audio_to_vad_frames(self, audio_16k: np.ndarray) -> List[Tuple[bool, np.ndarray]]:
        """
        Del opp 16kHz audio i frames og kjør VAD på hver.
        Returnerer liste av (is_speech, frame_audio) tupler.
        """
        vad = self._get_vad()
        frame_ms = self.config["vad_frame_ms"]
        frame_samples = int(16000 * frame_ms / 1000)
        
        # Konverter til int16 bytes for WebRTC VAD
        audio_int16 = (audio_16k * 32767).astype(np.int16)
        
        frames = []
        for i in range(0, len(audio_int16) - frame_samples, frame_samples):
            frame = audio_int16[i:i + frame_samples]
            frame_bytes = frame.tobytes()
            try:
                is_speech = vad.is_speech(frame_bytes, 16000)
            except Exception:
                is_speech = False
            frames.append((is_speech, audio_16k[i:i + frame_samples]))
        
        return frames
    
    def _extract_speech_segments(self, audio_16k: np.ndarray) -> List[np.ndarray]:
        """
        Ekstraher sammenhengende tale-segmenter fra audio.
        Bruker VAD for å filtrere ut stillhet.
        """
        frames = self._audio_to_vad_frames(audio_16k)
        
        segments = []
        current_segment = []
        silence_frames = 0
        max_silence = 10  # Antall stillhets-frames før vi bryter segmentet
        
        for is_speech, frame_audio in frames:
            if is_speech:
                current_segment.append(frame_audio)
                silence_frames = 0
            else:
                silence_frames += 1
                if current_segment:
                    if silence_frames <= max_silence:
                        # Kort pause, fortsett segmentet
                        current_segment.append(frame_audio)
                    else:
                        # Lang pause, avslutt segmentet
                        segment = np.concatenate(current_segment)
                        if len(segment) > 16000 * 0.5:  # Minst 0.5 sek
                            segments.append(segment)
                        current_segment = []
        
        # Siste segment
        if current_segment:
            segment = np.concatenate(current_segment)
            if len(segment) > 16000 * 0.5:
                segments.append(segment)
        
        return segments
    
    def _compute_embedding(self, audio_16k: np.ndarray) -> Optional[np.ndarray]:
        """
        Beregn speaker embedding fra 16kHz audio.
        Returnerer 256-dim d-vector eller None ved feil.
        """
        try:
            encoder = self._get_encoder()
            # Resemblyzer forventer float32 audio normalisert til [-1, 1]
            audio = audio_16k.astype(np.float32)
            if np.abs(audio).max() > 0:
                audio = audio / np.abs(audio).max()
            
            embedding = encoder.embed_utterance(audio)
            return embedding
        except Exception as e:
            logger.error(f"Feil ved embedding-beregning: {e}")
            return None
    
    def _match_speaker(self, embedding: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Match en embedding mot kjente profiler.
        Returnerer (name, confidence) eller (None, 0.0).
        """
        if not self.known_voices:
            return None, 0.0
        
        best_name = None
        best_score = 0.0
        
        for name, known_embedding in self.known_voices.items():
            # Cosine similarity
            similarity = np.dot(embedding, known_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(known_embedding)
            )
            if similarity > best_score:
                best_score = similarity
                best_name = name
        
        threshold = self.config["match_threshold"]
        if best_score >= threshold:
            return best_name, float(best_score)
        
        return None, float(best_score)
    
    # ─── Profil fra samtale-audio ────────────────────────────────
    
    def create_profile_from_conversation(self, name: str) -> bool:
        """Lag stemmeprofil fra audio samlet under samtale-modus.
        
        Bruker _conversation_audio-bufferen som er fylt under aktiv samtale.
        Krever at samtalen fortsatt er aktiv (end_conversation ikke kalt ennå).
        
        Args:
            name: Navnet på personen å knytte profilen til
            
        Returns:
            True hvis profil ble lagret OK
        """
        with self._conversation_lock:
            audio_chunks = self._conversation_audio.copy()
        
        if not audio_chunks:
            logger.warning(f"Ingen samtale-audio tilgjengelig for {name}")
            return False
        
        total_audio = np.concatenate(audio_chunks)
        total_seconds = len(total_audio) / 16000
        logger.info(f"🎤 Lager stemmeprofil for {name} fra {total_seconds:.1f}s samtale-audio")
        
        if total_seconds < 2.0:
            logger.warning(f"For lite tale ({total_seconds:.1f}s) for {name}")
            return False
        
        embedding = self._compute_embedding(total_audio)
        if embedding is None:
            logger.error(f"Kunne ikke generere embedding for {name}")
            return False
        
        success = self._save_voice_profile(name, embedding)
        if success:
            logger.info(f"✅ Stemmeprofil lagret for {name} ({total_seconds:.1f}s samtale-audio)")
        return success
    
    # ─── Auto-enrollment (passiv profilbygging) ─────────────────────
    
    def start_auto_enroll(self, name: str):
        """
        Start passiv innsamling av stemmedata for en person.
        Kalles typisk når face detection gjenkjenner noen uten stemmeprofil.
        
        Args:
            name: Navnet på personen (fra face recognition)
        """
        with self._enroll_lock:
            if self._enrolling_name == name:
                return  # Allerede i gang
            
            self._enrolling_name = name
            self._enroll_audio_buffer = []
            self._enroll_speech_seconds = 0.0
            self._enroll_start_time = time.time()
            
            logger.info(f"🎤 Starter passiv stemmeinnsamling for {name}")
    
    def stop_auto_enroll(self):
        """Avbryt pågående auto-enrollment"""
        with self._enroll_lock:
            if self._enrolling_name:
                logger.info(f"🎤 Avbrøt stemmeinnsamling for {self._enrolling_name}")
            self._enrolling_name = None
            self._enroll_audio_buffer = []
            self._enroll_speech_seconds = 0.0
    
    def _process_enrollment_audio(self, speech_segments: List[np.ndarray]):
        """
        Legg til tale-segmenter til pågående enrollment.
        Hvis vi har nok data, generer og lagre profil.
        """
        with self._enroll_lock:
            if not self._enrolling_name:
                return
            
            name = self._enrolling_name
            min_duration = self.config["min_speech_duration"]
            max_duration = self.config["max_collect_duration"]
            
            # Legg til segmenter
            for segment in speech_segments:
                self._enroll_audio_buffer.append(segment)
                self._enroll_speech_seconds += len(segment) / 16000
            
            elapsed = time.time() - self._enroll_start_time
            
            logger.debug(
                f"🎤 {name}: {self._enroll_speech_seconds:.1f}s tale "
                f"({elapsed:.0f}s elapsed, trenger {min_duration}s)"
            )
            
            # Sjekk om vi har nok tale
            if self._enroll_speech_seconds >= min_duration:
                # Generer profil
                all_audio = np.concatenate(self._enroll_audio_buffer)
                embedding = self._compute_embedding(all_audio)
                
                if embedding is not None:
                    success = self._save_voice_profile(name, embedding)
                    if success and self.event_callback:
                        self.event_callback("voice_profile_created", {
                            "name": name,
                            "speech_duration": round(self._enroll_speech_seconds, 1),
                            "success": True,
                        })
                    logger.info(
                        f"✅ Stemmeprofil laget for {name} "
                        f"({self._enroll_speech_seconds:.1f}s tale)"
                    )
                else:
                    logger.error(f"❌ Kunne ikke generere embedding for {name}")
                    if self.event_callback:
                        self.event_callback("voice_profile_created", {
                            "name": name,
                            "success": False,
                            "error": "embedding_failed",
                        })
                
                # Reset enrollment
                self._enrolling_name = None
                self._enroll_audio_buffer = []
                self._enroll_speech_seconds = 0.0
                return
            
            # Timeout-sjekk
            if elapsed > max_duration:
                logger.warning(
                    f"⏱️ Timeout for {name}: kun {self._enroll_speech_seconds:.1f}s tale "
                    f"på {elapsed:.0f}s. Avbryter."
                )
                self._enrolling_name = None
                self._enroll_audio_buffer = []
                self._enroll_speech_seconds = 0.0
    
    # ─── Hovedløkke (bakgrunnstråd) ─────────────────────────────────
    
    def start(self):
        """Start passiv lytting i bakgrunnstråd"""
        if self.running:
            logger.warning("SpeakerRecognition kjører allerede")
            return
        
        if not self.config.get("enabled", True):
            logger.info("Speaker recognition er deaktivert i config")
            return
        
        self.running = True
        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="speaker-recognition",
            daemon=True,
        )
        self._listen_thread.start()
        logger.info("🎤 Speaker recognition startet (passiv lytting)")
    
    def stop(self):
        """Stopp passiv lytting"""
        self.running = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=3.0)
        logger.info("🎤 Speaker recognition stoppet")
    
    def _listen_loop(self):
        """
        Hovedløkke som kjører i bakgrunnstråd.
        Tar opp audio-chunks, kjører VAD, og matcher/enrollerer stemmer.
        """
        sd = self._get_sounddevice()
        mic_sr = self.config["mic_sample_rate"]
        target_sr = self.config["target_sample_rate"]
        chunk_duration = 3.0  # Prosesser 3 sekunder om gangen
        chunk_samples = int(mic_sr * chunk_duration)
        
        # Cooldown: ikke match samme person for ofte
        last_match_time: Dict[str, float] = {}
        match_cooldown = 15.0  # Sekunder mellom duplikat-events
        
        logger.info(f"🎤 Lytter på mikrofon ({mic_sr}Hz, {chunk_duration}s chunks)")
        
        while self.running:
            try:
                # Ta opp audio-chunk
                audio = sd.rec(
                    chunk_samples,
                    samplerate=mic_sr,
                    channels=1,
                    dtype="float32",
                    device=None,  # Default input device
                )
                sd.wait()
                
                if not self.running:
                    break
                
                # Sjekk mute-status (Samantha snakker)
                if self.is_muted:
                    logger.debug("🔇 Audio forkastet (mutet)")
                    continue
                
                # Flatten til 1D
                audio = audio.flatten()
                
                # Resample til 16kHz for VAD og embedding
                audio_16k = self._resample(audio, mic_sr, target_sr)
                
                # Ekstraher tale-segmenter via VAD
                speech_segments = self._extract_speech_segments(audio_16k)
                
                if not speech_segments:
                    continue  # Ingen tale detektert
                
                total_speech = sum(len(s) for s in speech_segments) / target_sr
                logger.debug(f"🎤 {total_speech:.1f}s tale detektert")
                
                # Sjekk om vi er i enrollment-modus
                with self._enroll_lock:
                    is_enrolling = self._enrolling_name is not None
                
                if is_enrolling:
                    self._process_enrollment_audio(speech_segments)
                
                # Samtale-modus: samle tale og matche raskere
                in_conversation = self.is_conversation_active
                if in_conversation:
                    with self._conversation_lock:
                        for seg in speech_segments:
                            self._conversation_audio.append(seg)
                
                # Velg cooldown basert på modus
                active_cooldown = 5.0 if in_conversation else match_cooldown
                
                # Prøv å matche mot kjente stemmer (selv under enrollment)
                if self.known_voices and total_speech >= 1.0:
                    # I samtale-modus: hopp over hvis allerede matchet
                    with self._conversation_lock:
                        skip_match = in_conversation and self._conversation_match_sent
                    
                    if not skip_match:
                        # Bruk den lengste segmenten for best embedding
                        best_segment = max(speech_segments, key=len)
                        
                        if len(best_segment) >= 16000:  # Minst 1 sek
                            embedding = self._compute_embedding(best_segment)
                            
                            if embedding is not None:
                                name, confidence = self._match_speaker(embedding)
                                
                                if name:
                                    now = time.time()
                                    last_time = last_match_time.get(name, 0)
                                    
                                    if now - last_time > active_cooldown:
                                        last_match_time[name] = now
                                        
                                        source = "conversation" if in_conversation else "passive"
                                        logger.info(
                                            f"🔊 Stemme gjenkjent: {name} "
                                            f"(confidence: {confidence:.2%}, {source})"
                                        )
                                        
                                        if in_conversation:
                                            with self._conversation_lock:
                                                self._conversation_matched = True
                                                self._conversation_match_sent = True
                                        
                                        if self.event_callback:
                                            self.event_callback("speaker_recognized", {
                                                "name": name,
                                                "confidence": round(confidence, 3),
                                                "speech_duration": round(total_speech, 1),
                                                "source": source,
                                            })
                
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Feil i lytteløkke: {e}")
                    time.sleep(1.0)  # Unngå tight loop ved feil
    
    # ─── Manuell enrollment ─────────────────────────────────────────
    
    def learn_voice(self, name: str, duration: float = 10.0) -> bool:
        """
        Manuell stemmelæring: ta opp `duration` sekunder og lag profil.
        Blokkerer til opptaket er ferdig.
        
        Args:
            name: Navn på personen
            duration: Opptakslengde i sekunder
            
        Returns:
            True hvis profil ble lagret OK
        """
        sd = self._get_sounddevice()
        mic_sr = self.config["mic_sample_rate"]
        target_sr = self.config["target_sample_rate"]
        
        logger.info(f"🎤 Tar opp {duration}s stemme for {name}...")
        
        try:
            audio = sd.rec(
                int(mic_sr * duration),
                samplerate=mic_sr,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            audio = audio.flatten()
            
            # Resample
            audio_16k = self._resample(audio, mic_sr, target_sr)
            
            # Ekstraher tale
            speech_segments = self._extract_speech_segments(audio_16k)
            
            if not speech_segments:
                logger.error(f"❌ Ingen tale detektert i opptaket for {name}")
                return False
            
            total_speech = sum(len(s) for s in speech_segments) / target_sr
            logger.info(f"  {total_speech:.1f}s tale ekstrahert")
            
            if total_speech < 2.0:
                logger.error(f"❌ For lite tale ({total_speech:.1f}s) for {name}")
                return False
            
            # Generer embedding fra all tale
            all_speech = np.concatenate(speech_segments)
            embedding = self._compute_embedding(all_speech)
            
            if embedding is None:
                return False
            
            return self._save_voice_profile(name, embedding)
            
        except Exception as e:
            logger.error(f"❌ Feil ved stemmelæring for {name}: {e}")
            return False


# ─── Standalone test ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from config import VOICE_CONFIG
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def on_event(event_type, data):
        print(f"\n📢 EVENT: {event_type} → {data}\n")
    
    sr = SpeakerRecognition(VOICE_CONFIG, event_callback=on_event)
    
    print("\n" + "=" * 50)
    print("🎤 Speaker Recognition Test")
    print("=" * 50)
    print(f"Kjente stemmer: {sr.list_known_speakers()}")
    print(f"Config: mic={VOICE_CONFIG['mic_sample_rate']}Hz, "
          f"threshold={VOICE_CONFIG['match_threshold']}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "learn":
        # Lær en ny stemme: python speaker_recognition.py learn "Åsmund"
        name = sys.argv[2] if len(sys.argv) > 2 else "TestPerson"
        print(f"\n🎤 Snakk i 10 sekunder for å lære stemmen til {name}...")
        time.sleep(1)
        success = sr.learn_voice(name, duration=10.0)
        print(f"Resultat: {'✅ OK' if success else '❌ Feilet'}")
    else:
        # Passiv lytting
        print("\nStarter passiv lytting... (Ctrl+C for å stoppe)")
        sr.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopper...")
            sr.stop()
