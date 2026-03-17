"""
app.py – Point d'entrée principal.
Lance le serveur backend Python + la fenêtre PyWebView transparente.
"""
import os
import sys
import threading
import time
import importlib.util
import signal
from pathlib import Path

# Assurer que le répertoire backend est dans le PATH
BASE_DIR    = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))

import webview
import subprocess
from backend.config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_X, WINDOW_Y, WS_PORT, WS_HOST
from backend.main   import run_server


def validate_dependencies():
    """
    Vérifie que toutes les dépendances critiques sont installées.
    Affiche des messages d'erreur clairs si Something is missing.
    Returns True if all critical deps are available.
    """
    missing = []
    warnings = []

    # Required dependencies (core functionality)
    required_deps = {
        'fastapi': 'FastAPI (serveur WebSocket)',
        'uvicorn': 'Uvicorn (serveur ASGI)',
        'websockets': 'WebSocket client library',
        'pywebview': 'PyWebView (interface graphique)',
        'pystray': 'Pystray (icône système)',
        'PIL': 'Pillow (traitement images)',
        'numpy': 'NumPy (calculs audio)',
        'requests': 'Requests (appels HTTP)',
        'yaml': 'PyYAML (configuration)',
    }

    # Optional dependencies (features)
    optional_deps = {
        'faster_whisper': 'Faster-Whisper (STT local)',
        'TTS': 'Coqui TTS (synthèse vocale)',
        'sounddevice': 'SoundDevice (entrée microphone)',
        'google.generativeai': 'Google Generative AI (Gemini)',
        'openai': 'OpenAI API',
        'piper': 'Piper TTS (synthèse rapide)',
        'psutil': 'PSUtil (informations système)',
        'scipy': 'SciPy (traitement signal)',
        'pvporcupine': 'Picovoice (wake word)',
    }

    # Check required
    for module, description in required_deps.items():
        spec = importlib.util.find_spec(module)
        if spec is None:
            missing.append(f"  - {description} (module: {module})")

    # Check optional
    for module, description in optional_deps.items():
        spec = importlib.util.find_spec(module)
        if spec is None:
            warnings.append(f"  - {description} (module: {module}) - Functionality limited")

    # Report
    if missing:
        print("\n" + "=" * 60)
        print("  ERREUR: Dépendances manquantes")
        print("=" * 60)
        for m in missing:
            print(m)
        print("\nPour installer:")
        print("  source .venv/bin/activate")
        print("  pip install -r backend/requirements.txt")
        print("=" * 60 + "\n")
        return False

    if warnings:
        print("\n" + "=" * 60)
        print("  AVERTISSEMENT: Dépendances optionnelles manquantes")
        print("=" * 60)
        for w in warnings:
            print(w)
        print("Certaines fonctionnalités peuvent ne pas être disponibles.")
        print("=" * 60 + "\n")

    print("[Dép] Vérification des dépendances: OK ✓")
    return True


class SungJinWooAPI:
    """API exposée au frontend via window.pywebview.api"""

    def __init__(self, window):
        self._window = window
        self._drag_x = 0
        self._drag_y = 0

    def start_drag(self):
        """Permet le déplacement de la fenêtre sans barre de titre."""
        pass  # PyWebView gère le drag nativement sur certaines plateformes

    def move_window(self, x, y):
        """Permet au JS de déplacer dynamiquement la fenêtre sur le bureau."""
        self._window.move(int(x), int(y))

    def hide(self):
        """Cache la fenêtre."""
        self._window.hide()

    def show(self):
        """Affiche la fenêtre."""
        self._window.show()

    def open_settings(self):
        """Lance l'interface de configuration."""
        subprocess.Popen([sys.executable, str(BASE_DIR / "setup.py")])

    def quit(self):
        """Quitte l'application."""
        webview.windows[0].destroy()

    def get_version(self):
        return "1.0.0"


def start_backend_thread(shutdown_event=None):
    """Lance le serveur FastAPI+WebSocket dans un thread daemon."""
    print("[App] Démarrage du serveur backend...")
    t = threading.Thread(
        target=run_server,
        kwargs={"start_mic": True, "shutdown_event": shutdown_event},
        daemon=True
    )
    t.start()
    # Attendre que le serveur soit prêt
    time.sleep(2.0)
    print(f"[App] Backend prêt sur ws://{WS_HOST}:{WS_PORT} ✓")


def main():
    print("=" * 50)
    print("  Shadow Monarch – Sung Jin Woo Assistant")
    print("=" * 50)

    # 1. Vérifier les dépendances
    if not validate_dependencies():
        print("\n[ERREUR] L'application ne peut pas démarrer sans les dépendances critiques.")
        print("Installez-les et redémarrez.")
        sys.exit(1)

    # 2. Créer un événement pour l'arrêt propre
    shutdown_event = threading.Event()

    # 3. Configurer les gestionnaires de signaux pour arrêt propre
    def signal_handler(signum, frame):
        print(f"\n[App] Signal {signum} reçu, arrêt en cours...")
        shutdown_event.set()
        # Donner une chance au backend de s'arrêter
        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. Démarrer le backend
    start_backend_thread(shutdown_event)

    # 2. Créer la fenêtre PyWebView
    frontend_url = str(FRONTEND_DIR / "index.html")

    window = webview.create_window(
        title         = "Sung Jin Woo",
        url           = frontend_url,
        width         = WINDOW_WIDTH,
        height        = WINDOW_HEIGHT,
        x             = WINDOW_X,
        y             = WINDOW_Y,
        resizable     = True,
        frameless     = True,         # Pas de barre de titre
        transparent   = True,         # Fond transparent
        on_top        = True,         # Always-on-top
        background_color = '#000000',  # Triplet hex side-by-side with transparent=True
        shadow        = False,
        easy_drag     = False,        # Désactivé pour éviter les crashs PyQt5 (MouseButtons error)
    )

    api = SungJinWooAPI(window)
    window.expose(
        api.start_drag, 
        api.move_window, 
        api.hide, 
        api.show, 
        api.open_settings,
        api.quit, 
        api.get_version
    )

    # 3. Lancer l'interface graphique (bloquant)
    webview.start(
        gui='qt',
        debug=os.getenv("DEBUG", "0") == "1",
        http_server=True,
    )


if __name__ == "__main__":
    main()
