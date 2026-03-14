"""
Configuration centrale pour l'assistant virtuel Sung Jin Woo.
Charge les variables d'environnement depuis .env
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Serveur WebSocket ─────────────────────────────────────────────────────────
WS_HOST = os.getenv("WS_HOST", "localhost")
WS_PORT = int(os.getenv("WS_PORT", "8765"))

# ─── STT (faster-whisper) ──────────────────────────────────────────────────────
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")          # tiny/small/medium/large
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")          # cpu / cuda
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "fr")       # langue de transcription
SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.01"))
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "1.5"))  # secondes de silence

# ─── Wake Word (Picovoice) ──────────────────────────────────────────────────
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")
WAKE_WORD = os.getenv("WAKE_WORD", "porcupine")  # ex: 'porcupine', 'jarvis', ou chemin vers .ppn
WAKE_WORD_SENSITIVITY = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.5"))

# ─── LLM ───────────────────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")           # ollama | gemini | openai
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))

# ─── TTS ────────────────────────────────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "sovits")               # sovits | coqui | elevenlabs | gtts
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "fr")

# Configuration GPT-SoVITS
SOVITS_URL = os.getenv("SOVITS_URL", "http://127.0.0.1:9880/tts")
SOVITS_TEXT_LANG = os.getenv("SOVITS_TEXT_LANG", "fr")
SOVITS_PROMPT_LANG = os.getenv("SOVITS_PROMPT_LANG", "fr")
SOVITS_REF_AUDIO = os.getenv("SOVITS_REF_AUDIO", "")
SOVITS_PROMPT_TEXT = os.getenv("SOVITS_PROMPT_TEXT", "")

# ─── Personnalité (Chargé dynamiquement via YAML) ──────────────────────────────
PERSONA_NAME = "Sung Jin Woo"
SYSTEM_PROMPT = """Tu es Sung Jin Woo."""
CHARACTER_SCALE = 1.0
AURA_COLOR = "#6600cc"

_yaml_path = Path(__file__).parent.parent / "character.yaml"
if _yaml_path.exists():
    try:
        with open(_yaml_path, "r", encoding="utf-8") as f:
            _char_conf = yaml.safe_load(f)
            if _char_conf:
                PERSONA_NAME = _char_conf.get("name", PERSONA_NAME)
                SYSTEM_PROMPT = _char_conf.get("system_prompt", SYSTEM_PROMPT)
                AURA_COLOR = _char_conf.get("aura_color", AURA_COLOR)
                CHARACTER_SCALE = float(_char_conf.get("character_scale", CHARACTER_SCALE))
    except Exception as e:
        print(f"[Config] Erreur lecture character.yaml: {e}")

# Overrides .env fallback 
AURA_COLOR = os.getenv("AURA_COLOR", AURA_COLOR)
CHARACTER_SCALE = float(os.getenv("CHARACTER_SCALE", CHARACTER_SCALE))

# ─── Audio ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION = 0.5  # secondes par bloc audio

# ─── Fenêtre PyWebView ─────────────────────────────────────────────────────────
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 700
WINDOW_X = int(os.getenv("WINDOW_X", "50"))
WINDOW_Y = int(os.getenv("WINDOW_Y", "100"))
