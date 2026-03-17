"""
Serveur WebSocket FastAPI – Orchestration principale.
Gère les connexions depuis le frontend Three.js.
"""
import asyncio
import json
import sys
import os
import threading
import time
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import (
    WS_HOST, WS_PORT, AURA_COLOR, CHARACTER_SCALE,
    TTS_ENGINE, LLM_PROVIDER, WHISPER_MODEL, WHISPER_DEVICE,
    ELEVENLABS_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY,
    SOVITS_URL, PIPER_MODEL, ALLOWED_COMMANDS, DANGEROUS_COMMANDS
)
from tts import synthesize, prewarm as tts_prewarm
from llm import generate_response, reset_history
from memory import memory

# Pool de connexions WebSocket actives
_active_connections: set[WebSocket] = set()
_stt_listener = None
_SERVER_START_TIME = time.time()
_server_instance = None  # For graceful shutdown


def validate_config():
    """
    Validate configuration values at startup.
    Logs warnings for invalid or missing settings.
    """
    errors = []
    warnings = []

    # Validate TTS engine
    valid_tts = {'sovits', 'coqui', 'elevenlabs', 'piper', 'gtts'}
    if TTS_ENGINE not in valid_tts:
        errors.append(f"TTS_ENGINE '{TTS_ENGINE}' invalide. Doit être un de: {valid_tts}")

    # Validate LLM provider
    valid_llm = {'ollama', 'openai', 'gemini'}
    if LLM_PROVIDER not in valid_llm:
        errors.append(f"LLM_PROVIDER '{LLM_PROVIDER}' invalide. Doit être un de: {valid_llm}")

    # Check API keys for cloud providers
    if LLM_PROVIDER == 'openai' and not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY manquante pour le provider OpenAI")
    if LLM_PROVIDER == 'gemini' and not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY manquante pour le provider Gemini")

    # Validate TTS-specific
    if TTS_ENGINE == 'elevenlabs' and not ELEVENLABS_API_KEY:
        warnings.append("ELEVENLABS_API_KEY manquante pour ElevenLabs TTS")

    if TTS_ENGINE == 'sovits' and not SOVITS_URL:
        warnings.append("SOVITS_URL non configuré pour GPT-SoVITS")

    if TTS_ENGINE == 'piper' and not PIPER_MODEL:
        warnings.append("PIPER_MODEL non configuré pour Piper TTS")

    # Validate Whisper
    valid_whisper = {'tiny', 'base', 'small', 'medium', 'large'}
    if WHISPER_MODEL not in valid_whisper:
        warnings.append(f"WHISPER_MODEL '{WHISPER_MODEL}' inconnu. Doit être un de: {valid_whisper}")

    valid_devices = {'cpu', 'cuda'}
    if WHISPER_DEVICE not in valid_devices:
        warnings.append(f"WHISPER_DEVICE '{WHISPER_DEVICE}' inconnu. Doit être 'cpu' ou 'cuda'")

    # Validate command whitelist
    if not isinstance(ALLOWED_COMMANDS, list) or len(ALLOWED_COMMANDS) == 0:
        warnings.append("ALLOWED_COMMANDS vide ou invalide - aucune commande EXEC autorisée")

    # Report
    if errors:
        print("\n" + "=" * 60)
        print("  ERREUR DE CONFIGURATION")
        print("=" * 60)
        for e in errors:
            print(f"  ✗ {e}")
        print("=" * 60)
        print("Corrigez le fichier .env ou character.yaml et redémarrez.")
        print("=" * 60 + "\n")
        raise ValueError(f"Configuration invalide: {len(errors)} erreur(s)")

    if warnings:
        print("\n" + "=" * 60)
        print("  AVERTISSEMENTS DE CONFIGURATION")
        print("=" * 60)
        for w in warnings:
            print(f"  ⚠ {w}")
        print("=" * 60 + "\n")

    print("[Config] Validation: OK ✓")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage et arrêt propre."""
    print("[Server] Démarrage du serveur Sung Jin Woo Assistant...")

    # Validate configuration before starting
    try:
        validate_config()
    except ValueError:
        # Re-raise to prevent server start with invalid config
        raise

    # Preload TTS engine to reduce first-call latency
    try:
        tts_prewarm()
    except Exception as e:
        print(f"[Server] Avertissement: pré-chargement TTS échoué: {e}")

    yield
    # Arrêt
    if _stt_listener:
        _stt_listener.stop()
    print("[Server] Arrêt propre.")


app = FastAPI(title="Sung Jin Woo Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def broadcast(message: dict):
    """Envoie un message JSON à tous les clients connectés."""
    global _active_connections
    disconnected = set()
    payload = json.dumps(message, ensure_ascii=False)
    for ws in _active_connections.copy():
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    _active_connections -= disconnected


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns server status, uptime, and component health.
    """
    uptime = time.time() - _SERVER_START_TIME

    # Check memory DB connectivity
    try:
        memory.get_stats()
        memory_db = "ok"
    except Exception as e:
        memory_db = f"error: {str(e)}"

    # Check if TTS is loadable (doesn't test inference)
    try:
        from tts import _get_coqui
        tts_status = "loaded" if _get_coqui() else "unavailable"
    except Exception:
        tts_status = "error"

    # Check STT model (not loaded until first use, so just check import)
    try:
        from stt import get_model
        stt_status = "ready"
    except Exception as e:
        stt_status = f"error: {str(e)}"

    # Check WebSocket connections
    ws_connections = len(_active_connections)

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": round(uptime, 2),
        "components": {
            "memory_db": memory_db,
            "tts": tts_status,
            "stt": stt_status,
            "websocket_connections": ws_connections
        },
        "version": "1.0.0"
    }


async def process_user_input(text: str, is_proactive: bool = False):
    """
    Pipeline complet:
    texte utilisateur → LLM → TTS → broadcast vers frontend
    """
    if not text.strip():
        return

    # Si c'est proactif, on ne simule pas l'écriture utilisateur
    if not is_proactive:
        await broadcast({"type": "status", "state": "thinking", "text": text})
    else:
        await broadcast({"type": "status", "state": "thinking"})

    try:
        # 2. Générer la réponse LLM (bloquant → thread pool)
        loop = asyncio.get_event_loop()
        response_text, emotion, xp, level = await loop.run_in_executor(None, generate_response, text)

        # 3. Synthèse vocale + visèmes
        await broadcast({"type": "status", "state": "speaking"})
        audio_b64, duration_ms, visemes = await loop.run_in_executor(
            None, synthesize, response_text
        )

        # 4. Envoyer tout au frontend
        await broadcast({
            "type": "speech",
            "text": response_text,
            "audio": audio_b64,
            "duration_ms": duration_ms,
            "visemes": visemes,
            "emotion": emotion,
            "xp": xp,
            "level": level
        })

    except Exception as e:
        print(f"[Server] Erreur pipeline: {e}")
        await broadcast({
            "type": "error",
            "message": str(e)
        })
    finally:
        await broadcast({"type": "status", "state": "idle"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_connections.add(websocket)
    print(f"[WS] Client connecté. Total: {len(_active_connections)}")

    # Envoi de la configuration visuelle
    await websocket.send_text(json.dumps({
        "type": "config",
        "aura_color": AURA_COLOR,
        "scale": CHARACTER_SCALE
    }))

    # Sync stats (Dungeon Mode)
    stats = memory.get_stats()
    await websocket.send_text(json.dumps({
        "type": "stats_sync",
        "level": stats.get('level', 1),
        "xp": stats.get('xp', 0)
    }))

    # Message d'accueil
    await broadcast({"type": "status", "state": "idle"})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "user_input":
                # Texte envoyé depuis le frontend (chat ou STT)
                asyncio.create_task(process_user_input(msg.get("text", "")))

            elif msg_type == "reset":
                reset_history()
                await broadcast({"type": "status", "state": "idle"})

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        _active_connections.discard(websocket)
        print(f"[WS] Client déconnecté. Total: {len(_active_connections)}")


def start_stt_listener(loop: asyncio.AbstractEventLoop):
    """Lance l'écoute microphone et envoie les transcriptions via WebSocket."""
    global _stt_listener
    try:
        from stt import MicrophoneListener

        def on_transcription(text: str):
            asyncio.run_coroutine_threadsafe(
                process_user_input(text), loop
            )

        def on_status_change(state: str):
            asyncio.run_coroutine_threadsafe(
                broadcast({"type": "status", "state": state}), loop
            )

        _stt_listener = MicrophoneListener(on_transcription, on_status_change)
        _stt_listener.start()
    except ImportError as e:
        print(f"[STT] Module non disponible (sounddevice?): {e}")
    except Exception as e:
        print(f"[STT] Erreur démarrage: {e}")

def proactive_heartbeat_loop(loop: asyncio.AbstractEventLoop):
    """Vérifie l'inactivité et déclenche une intervention de l'IA si besoin."""
    from llm import _last_activity_time, generate_proactive_thought
    import time as pytime
    
    PROACTIVITY_THRESHOLD = 300 # 5 minutes de silence
    
    while True:
        pytime.sleep(60) # Vérifie chaque minute
        idle_duration = pytime.time() - _last_activity_time
        
        if idle_duration > PROACTIVITY_THRESHOLD:
            print("[System] Proactivity Triggered!")
            # On génère une pensée sans gain d'XP (car c'est l'IA qui parle)
            text, emotion = generate_proactive_thought()
            if text:
                # Synthèse et broadcast
                asyncio.run_coroutine_threadsafe(process_user_input(text, is_proactive=True), loop)


def run_server(start_mic: bool = True, shutdown_event: threading.Event = None):
    """
    Lance le serveur WebSocket avec ou sans écoute microphone.
    Args:
        start_mic: Whether to start microphone listener
        shutdown_event: Threading event to trigger graceful shutdown
    """
    global _server_instance

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if start_mic:
        # Lancer STT après démarrage du serveur
        threading.Timer(2.0, lambda: start_stt_listener(loop)).start()

    # Lancer le moniteur de proactivité (Heartbeat)
    threading.Thread(target=proactive_heartbeat_loop, args=(loop,), daemon=True).start()

    # Configure and start server
    config = uvicorn.Config(
        app,
        host=WS_HOST,
        port=WS_PORT,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    _server_instance = server

    # If a shutdown event is provided, monitor it in a separate thread
    if shutdown_event:
        def monitor_shutdown():
            shutdown_event.wait()
            print("[Server] Signal d'arrêt reçu, arrêt en cours...")
            server.should_exit = True

        threading.Thread(target=monitor_shutdown, daemon=True).start()

    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        print("[Server] Interruption clavier détectée")
    finally:
        server.should_exit = True
        print("[Server] Serveur arrêté")


def shutdown_server():
    """Trigger graceful shutdown of the backend server."""
    global _server_instance
    if _server_instance:
        _server_instance.should_exit = True
        print("[Server] Signal d'arrêt envoyé")


if __name__ == "__main__":
    run_server()
