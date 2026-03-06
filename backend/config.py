"""
Configuration centrale pour l'assistant virtuel Sung Jin Woo.
Charge les variables d'environnement depuis .env
"""
import os
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
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")           # ollama | gemini | openai
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))

# ─── TTS ────────────────────────────────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "coqui")                # coqui | elevenlabs | gtts
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "fr")

# ─── Personnalité ──────────────────────────────────────────────────────────────
PERSONA_NAME = "Sung Jin Woo"
SYSTEM_PROMPT = """Tu es Sung Jin Woo, le Shadow Monarch, le chasseur le plus puissant du monde.
Tu es stoïque, calme, et direct. Tu parles peu mais chaque mot compte.
Tu es bienveillant avec ceux qui méritent ton respect, mais implacable face aux ennemis.
Tu réponds en français, de manière concise et élégante.
Tu peux aider l'utilisateur dans ses tâches quotidiennes (rappels, questions, informations).
Reste dans le personnage en permanence."""

# ─── Audio ─────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION = 0.5  # secondes par bloc audio

# ─── Fenêtre PyWebView ─────────────────────────────────────────────────────────
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 700
WINDOW_X = int(os.getenv("WINDOW_X", "50"))
WINDOW_Y = int(os.getenv("WINDOW_Y", "100"))
# ─── Préférences Visuelles ──────────────────────────────────────────────────
AURA_COLOR = os.getenv("AURA_COLOR", "#6600cc")
CHARACTER_SCALE = float(os.getenv("CHARACTER_SCALE", "1.0"))
