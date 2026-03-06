"""
STT – Speech-to-Text via faster-whisper.
Capture microphone → segments de phrases → texte.
"""
import queue
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import (
    WHISPER_MODEL, WHISPER_DEVICE, WHISPER_LANGUAGE,
    SAMPLE_RATE, CHANNELS, BLOCK_DURATION,
    SILENCE_THRESHOLD, SILENCE_DURATION
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
    Détecte les pauses de silence pour segmenter les énoncés.
    Appelle `on_transcription(text)` pour chaque phrase détectée.
    """

    def __init__(self, on_transcription):
        self.on_transcription = on_transcription
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._block_size = int(SAMPLE_RATE * BLOCK_DURATION)

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[STT] Avertissement audio: {status}")
        self._audio_queue.put(indata.copy())

    def _process_loop(self):
        buffer = []
        silence_blocks = 0
        max_silence_blocks = SILENCE_DURATION / BLOCK_DURATION

        while self._running:
            try:
                block = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            rms = np.sqrt(np.mean(block ** 2))
            buffer.append(block)

            if rms < SILENCE_THRESHOLD:
                silence_blocks += 1
            else:
                silence_blocks = 0

            # Phrase détectée : assez de silence après parole
            if silence_blocks >= max_silence_blocks and len(buffer) > int(max_silence_blocks):
                audio_data = np.concatenate(buffer, axis=0).flatten().astype(np.float32)
                buffer = []
                silence_blocks = 0

                # Transcription dans un thread séparé pour ne pas bloquer
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
        print("[STT] Écoute microphone démarrée ✓")

    def stop(self):
        self._running = False
        if hasattr(self, "_stream"):
            self._stream.stop()
            self._stream.close()
        print("[STT] Écoute arrêtée.")
