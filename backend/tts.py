"""
TTS – Text-to-Speech avec génération de visèmes pour le lip-sync.
Moteurs supportés: Coqui XTTS-v2 (local), ElevenLabs (API), gTTS (fallback gratuit).
"""
import io
import os
import base64
import tempfile
import threading
import sys
import numpy as np
from pathlib import Path

# Assurer l'accès aux modules locaux
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    TTS_ENGINE, TTS_LANGUAGE,
    SOVITS_URL, SOVITS_TEXT_LANG, SOVITS_PROMPT_LANG,
    SOVITS_REF_AUDIO, SOVITS_PROMPT_TEXT,
    PIPER_MODEL, PIPER_CONFIG, BASE_DIR
)

_piper_voice = None
_piper_lock = threading.Lock()

# ─── Table de mapping phonème → visème (standard 15 visèmes) ──────────────────
# Basé sur la spécification Microsoft Azure Viseme
PHONEME_TO_VISEME: dict[str, int] = {
    "sil": 0, "æ": 1, "ə": 1, "ʌ": 1,
    "ɑ": 2, "ɔ": 3,
    "ɛ": 4, "ʊ": 4,
    "ɝ": 5,
    "j": 6, "i": 6, "ɪ": 6,
    "w": 7, "u": 7,
    "o": 8,
    "aʊ": 9, "aɪ": 9,
    "ɔɪ": 10,
    "h": 11,
    "ɹ": 12, "r": 12,
    "l": 13,
    "s": 14, "z": 14,
    "ʃ": 15, "tʃ": 15, "dʒ": 15, "ʒ": 15,
    "θ": 16, "ð": 16,
    "f": 17, "v": 17,
    "d": 18, "t": 18, "n": 18,
    "k": 19, "g": 19, "ŋ": 19,
    "p": 20, "b": 20, "m": 20,
}

# Durée moyenne (ms) par caractère pour estimation grossière
MS_PER_CHAR = 65

_coqui_model = None
_coqui_lock = threading.Lock()


def _get_coqui():
    global _coqui_model
    with _coqui_lock:
        if _coqui_model is None:
            try:
                from TTS.api import TTS as CoquiTTS
                print("[TTS] Chargement Coqui XTTS-v2...")
                _coqui_model = CoquiTTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
                print("[TTS] Coqui prêt ✓")
            except Exception as e:
                print(f"[TTS] Coqui non disponible: {e}")
                _coqui_model = False
    return _coqui_model


def _simple_visemes_from_text(text: str, duration_ms: float) -> list[dict]:
    """
    Génère une séquence de visèmes approximative basée sur les caractères du texte.
    Utilisé quand aucun timing précis n'est disponible.
    """
    char_map = {
        'a': 2, 'à': 2, 'â': 2, 'e': 4, 'é': 4, 'è': 4, 'ê': 4,
        'i': 6, 'î': 6, 'o': 8, 'ô': 8, 'u': 7, 'û': 7,
        'b': 20, 'p': 20, 'm': 20,
        'f': 17, 'v': 17,
        's': 14, 'z': 14,
        'l': 13, 'n': 18, 'd': 18, 't': 18,
        'k': 19, 'g': 19,
        'r': 12,
    }
    visemes = []
    step = duration_ms / max(len(text), 1)
    for i, char in enumerate(text.lower()):
        vis_id = char_map.get(char, 0)
        visemes.append({
            "time": int(i * step),
            "viseme": vis_id,
            "weight": 1.0
        })
    # Toujours terminer à visème 0 (bouche fermée)
    visemes.append({"time": int(duration_ms), "viseme": 0, "weight": 0.0})
    return visemes


def _synthesize_coqui(text: str) -> tuple[str, float, list[dict]]:
    """Synthèse avec Coqui XTTS-v2. Retourne (audio_b64, dur_ms, visemes)."""
    model = _get_coqui()
    if not model:
        return _synthesize_gtts(text)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        model.tts_to_file(
            text=text,
            language=TTS_LANGUAGE,
            file_path=tmp_path,
            speaker="Claribel Dervla"  # Voix grave disponible en XTTS-v2
        )
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        # Calcul durée approximative
        import wave
        with wave.open(tmp_path, 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration_s = frames / float(rate)

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        duration_ms = duration_s * 1000
        visemes = _simple_visemes_from_text(text, duration_ms)
        return audio_b64, duration_ms, visemes
    finally:
        os.unlink(tmp_path)


def _synthesize_elevenlabs(text: str) -> tuple[str, float, list[dict]]:
    """Synthèse avec ElevenLabs. Retourne (audio_b64, dur_ms, visemes)."""
    import requests as req
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    resp = req.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    audio_bytes = resp.content
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Estimation durée 
    duration_ms = len(text) * MS_PER_CHAR
    visemes = _simple_visemes_from_text(text, duration_ms)
    return audio_b64, duration_ms, visemes


def _synthesize_sovits(text: str) -> tuple[str, float, list[dict]]:
    """Synthèse avec GPT-SoVITS (API de type riko_project)."""
    import requests as req
    payload = {
        "text": text,
        "text_lang": SOVITS_TEXT_LANG,
        "ref_audio_path": SOVITS_REF_AUDIO,
        "prompt_text": SOVITS_PROMPT_TEXT,
        "prompt_lang": SOVITS_PROMPT_LANG
    }
    
    resp = req.post(SOVITS_URL, json=payload, timeout=60)
    resp.raise_for_status()
    
    audio_bytes = resp.content
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    
    duration_ms = len(text) * MS_PER_CHAR  # Fallback duration
    try:
        # Tenter d'estimer avec wave si possible
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        import wave
        with wave.open(tmp_path, 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration_ms = (frames / float(rate)) * 1000
        os.unlink(tmp_path)
    except Exception:
        pass
        
    visemes = _simple_visemes_from_text(text, duration_ms)
    return audio_b64, duration_ms, visemes


def _synthesize_piper(text: str) -> tuple[str, float, list[dict]]:
    """Synthèse avec Piper (ultra-rapide, local)."""
    global _piper_voice
    
    with _piper_lock:
        if _piper_voice is None:
            try:
                from piper.voice import PiperVoice
                model_path = BASE_DIR / "backend" / "models" / PIPER_MODEL
                config_path = BASE_DIR / "backend" / "models" / PIPER_CONFIG
                
                # Créer le dossier models s'il n'existe pas
                model_path.parent.mkdir(parents=True, exist_ok=True)
                
                if not model_path.exists():
                     print(f"[TTS] Modèle Piper manquant à {model_path}. Fallback gTTS.")
                     return _synthesize_gtts(text)

                _piper_voice = PiperVoice.load(str(model_path), config_path=str(config_path))
                print("[TTS] Piper prêt ✓")
            except Exception as e:
                print(f"[TTS] Erreur init Piper: {e}")
                return _synthesize_gtts(text)

    # Synthèse en mémoire
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        with open(tmp_path, "wb") as wav_file:
            _piper_voice.synthesize(text, wav_file)
        
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()

        import wave
        with wave.open(tmp_path, 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration_ms = (frames / float(rate)) * 1000

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        visemes = _simple_visemes_from_text(text, duration_ms)
        return audio_b64, duration_ms, visemes
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def _synthesize_gtts(text: str) -> tuple[str, float, list[dict]]:
    """Fallback gratuit avec gTTS (nécessite internet)."""
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        tts = gTTS(text=text, lang=TTS_LANGUAGE[:2], slow=False)
        tts.write_to_fp(buf)
        audio_bytes = buf.getvalue()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        duration_ms = len(text) * MS_PER_CHAR
        visemes = _simple_visemes_from_text(text, duration_ms)
        return audio_b64, duration_ms, visemes
    except Exception as e:
        print(f"[TTS] gTTS échoué: {e}")
        return "", 0, []


def synthesize(text: str) -> tuple[str, float, list[dict]]:
    """
    Point d'entrée principal TTS.
    Retourne (audio_base64, duration_ms, visemes_list)
    """
    display_text = str(text)[:60]
    print(f"[TTS] Synthèse ({TTS_ENGINE}): {display_text}...")
    try:
        if TTS_ENGINE == "sovits":
            try:
                return _synthesize_sovits(text)
            except Exception as e:
                print(f"[TTS] GPT-SoVITS échoué, fallback gTTS: {e}")
                return _synthesize_gtts(text)
        elif TTS_ENGINE == "elevenlabs" and ELEVENLABS_API_KEY:
            return _synthesize_elevenlabs(text)
        elif TTS_ENGINE == "coqui":
            try:
                return _synthesize_coqui(text)
            except Exception as e:
                print(f"[TTS] Coqui échoué, fallback gTTS: {e}")
                return _synthesize_gtts(text)
        elif TTS_ENGINE == "piper":
            return _synthesize_piper(text)
        else:
            return _synthesize_gtts(text)
    except Exception as e:
        print(f"[TTS] Erreur générale: {e}")
        return "", 0, []
