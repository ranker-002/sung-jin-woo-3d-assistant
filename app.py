"""
app.py – Point d'entrée principal.
Lance le serveur backend Python + la fenêtre PyWebView transparente.
"""
import os
import sys
import threading
import time
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


def start_backend_thread():
    """Lance le serveur FastAPI+WebSocket dans un thread daemon."""
    print("[App] Démarrage du serveur backend...")
    t = threading.Thread(
        target=run_server,
        kwargs={"start_mic": True},
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

    # 1. Démarrer le backend
    start_backend_thread()

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
        debug=os.getenv("DEBUG", "0") == "1",
        http_server=True,
    )


if __name__ == "__main__":
    main()
