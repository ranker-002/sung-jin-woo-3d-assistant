"""
STT – Speech-to-Text via faster-whisper.
Capture microphone → segments de phrases → texte.
"""
import queue
import threading
import os
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import pvporcupine

from config import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_LANGUAGE,
    SAMPLE_RATE, CHANNELS, BLOCK_DURATION,
    SILENCE_THRESHOLD, SILENCE_DURATION,
    PICOVOICE_ACCESS_KEY, WAKE_WORD, WAKE_WORD_SENSITIVITY
)

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def get_model() -> WhisperModel:
    global _model
    with _model_lock:
        if _model is None:
            print(f"[STT] Chargement du modèle Whisper '{WHISPER_MODEL}'...")
            _model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type="int8" if WHISPER_DEVICE == "cpu" else "float16"
            )
            print("[STT] Modèle prêt ✓")
    return _model


def transcribe_audio(audio: np.ndarray) -> str:
    """Transcrit un tableau numpy audio (float32, 16kHz) en texte."""
    model = get_model()
    segments, _ = model.transcribe(
        audio,
        language=WHISPER_LANGUAGE,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500}
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


class MicrophoneListener:
    """
    Écoute le microphone en continu.
    Phases : 
    1. WAKE_WORD : attend le mot clé (si configuré)
    2. RECORDING : enregistre jusqu'au silence
    3. TRANSCRIPTION : envoie au LLM
    """

    def __init__(self, on_transcription, on_status_change=None):
        self.on_transcription = on_transcription
        self.on_status_change = on_status_change
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._block_size = int(SAMPLE_RATE * BLOCK_DURATION)
        
        # État Picovoice
        self._porcupine = None
        if PICOVOICE_ACCESS_KEY:
            try:
                keyword_path = [WAKE_WORD] if os.path.exists(WAKE_WORD) else None
                keywords = [WAKE_WORD] if not keyword_path else None
                self._porcupine = pvporcupine.create(
                    access_key=PICOVOICE_ACCESS_KEY,
                    keywords=keywords,
                    keyword_paths=keyword_path,
                    sensitivities=[WAKE_WORD_SENSITIVITY]
                )
                print(f"[STT] Wake Word '{WAKE_WORD}' activé ✓")
                self._is_waiting_for_wake = True
            except Exception as e:
                print(f"[STT] Erreur Picovoice (AccessKey valide ?): {e}")
                self._is_waiting_for_wake = False
        else:
            self._is_waiting_for_wake = False

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[STT] Avertissement audio: {status}")
        self._audio_queue.put(indata.copy())

    def _process_loop(self):
        buffer = []
        silence_blocks = 0
        max_silence_blocks = SILENCE_DURATION / BLOCK_DURATION
        
        # Taille de frame requise par Porcupine
        porcupine_frame_length = self._porcupine.frame_length if self._porcupine else 512
        audio_stream_buffer = np.array([], dtype=np.float32)

        while self._running:
            try:
                block = self._audio_queue.get(timeout=0.1)
                # Normalisation pour Porcupine (int16)
                audio_stream_buffer = np.append(audio_stream_buffer, block.flatten())
            except queue.Empty:
                continue

            # Phase 1: Attente Wake Word
            if self._is_waiting_for_wake and self._porcupine:
                while len(audio_stream_buffer) >= porcupine_frame_length:
                    frame = audio_stream_buffer[:porcupine_frame_length]
                    audio_stream_buffer = audio_stream_buffer[porcupine_frame_length:]
                    
                    # Conversion float32 -> int16 pour Porcupine
                    pcm = (frame * 32767).astype(np.int16)
                    keyword_index = self._porcupine.process(pcm)
                    
                    if keyword_index >= 0:
                        print("[STT] Wake word détecté !")
                        self._is_waiting_for_wake = False
                        if self.on_status_change:
                            self.on_status_change("listening")
                        # On vide le buffer pour commencer l'enregistrement frais
                        buffer = [] 
                        silence_blocks = 0
                        break
                continue

            # Phase 2: Enregistrement après Wake Word (ou si Wake Word désactivé)
            rms = np.sqrt(np.mean(block ** 2))
            buffer.append(block)

            if rms < SILENCE_THRESHOLD:
                silence_blocks += 1
            else:
                silence_blocks = 0

            # Détection fin de phrase
            if silence_blocks >= max_silence_blocks and len(buffer) > int(max_silence_blocks):
                audio_data = np.concatenate(buffer, axis=0).flatten().astype(np.float32)
                buffer = []
                silence_blocks = 0
                
                # Repasser en mode attente Wake Word si configuré
                if self._porcupine:
                    self._is_waiting_for_wake = True
                    if self.on_status_change:
                        self.on_status_change("idle")

                # Transcription
                audio_copy = audio_data.copy()
                threading.Thread(
                    target=self._transcribe_and_emit,
                    args=(audio_copy,),
                    daemon=True
                ).start()

    def _transcribe_and_emit(self, audio: np.ndarray):
        text = transcribe_audio(audio)
        if text:
            print(f"[STT] Transcription: {text}")
            self.on_transcription(text)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=self._block_size,
            callback=self._audio_callback
        )
        self._stream.start()
        status = "en attente de mot-clé" if self._is_waiting_for_wake else "en écoute continue"
        print(f"[STT] Écoute microphone démarrée ({status}) ✓")

    def stop(self):
        self._running = False
        if hasattr(self, "_stream"):
            self._stream.stop()
            self._stream.close()
        if self._porcupine:
            self._porcupine.delete()
        print("[STT] Écoute arrêtée.")
