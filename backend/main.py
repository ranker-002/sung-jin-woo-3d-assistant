"""
Serveur WebSocket FastAPI – Orchestration principale.
Gère les connexions depuis le frontend Three.js.
"""
import asyncio
import json
import sys
import os
import threading
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import WS_HOST, WS_PORT, AURA_COLOR, CHARACTER_SCALE
from tts import synthesize
from llm import generate_response, reset_history

# Pool de connexions WebSocket actives
_active_connections: set[WebSocket] = set()
_stt_listener = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage et arrêt propre."""
    print("[Server] Démarrage du serveur Sung Jin Woo Assistant...")
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
    disconnected = set()
    payload = json.dumps(message, ensure_ascii=False)
    for ws in _active_connections.copy():
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    _active_connections -= disconnected


async def process_user_input(text: str):
    """
    Pipeline complet:
    texte utilisateur → LLM → TTS → broadcast vers frontend
    """
    if not text.strip():
        return

    # 1. Notifier le frontend que l'assistant réfléchit
    await broadcast({"type": "status", "state": "thinking", "text": text})

    try:
        # 2. Générer la réponse LLM (bloquant → thread pool)
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, generate_response, text)

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


def run_server(start_mic: bool = True):
    """Lance le serveur WebSocket avec ou sans écoute microphone."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if start_mic:
        # Lancer STT après démarrage du serveur
        threading.Timer(2.0, lambda: start_stt_listener(loop)).start()

    uvicorn.run(
        app,
        host=WS_HOST,
        port=WS_PORT,
        log_level="warning",
        loop="asyncio",
    )


if __name__ == "__main__":
    run_server()
