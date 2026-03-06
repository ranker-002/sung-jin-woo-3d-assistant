"""
setup.py – Assistant d'installation et de configuration 
Affiche une interface HUD pour configurer le projet.
"""
import os
import sys
import subprocess
import threading
import time
import webview
from pathlib import Path

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
ENV_FILE = BASE_DIR / ".env"

class SetupAPI:
    def __init__(self, window):
        self._window = window

    def close_wizard(self):
        self._window.destroy()

    def launch_app(self):
        subprocess.Popen([sys.executable, str(BASE_DIR / "app.py")])
        self._window.destroy()

    def start_installation(self, config):
        """Lance le processus d'installation dans un thread séparé."""
        threading.Thread(target=self._run_install_task, args=(config,), daemon=True).start()

    def _run_install_task(self, config):
        def log(msg, percent, type="info"):
            self._window.evaluate_js(f"window.updateProgress({percent}, '{msg}', '{type}')")

        try:
            log("Sauvegarde de la configuration API...", 10)
            self._update_env(config)
            time.sleep(0.5)

            log("Vérification de l'environnement Python...", 30)
            # Normalement le venv est déjà là si on tourne ce script avec,
            # mais on s'assure que les deps sont OK.
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"])
            
            log("Initialisation des modules audio...", 50)
            time.sleep(0.8)

            log("Vérification d'Ollama (AI Locale)...", 70, "warn" if config['llm'] == 'ollama' else "info")
            # Une petite vérification si Ollama tourne
            try:
                import requests
                requests.get("http://localhost:11434", timeout=1)
                log("Ollama détecté et opérationnel.", 80, "success")
            except:
                if config['llm'] == 'ollama':
                    log("ATTENTION: Ollama n'est pas lancé. Pensez à 'ollama serve' !", 80, "warn")
                else:
                    log("Ollama non détecté (Utilisation Cloud Gemini).", 80)

            log("Installation du Monarque terminée.", 100, "success")
            
        except Exception as e:
            log(f"ERREUR CRITIQUE: {str(e)}", 0, "error")

    def _update_env(self, config):
        """Met à jour le fichier .env avec les nouvelles clés."""
        lines = []
        if ENV_FILE.exists():
            with open(ENV_FILE, "r") as f:
                lines = f.readlines()
        
        new_lines = []
        keys_to_update = {
            "PICOVOICE_ACCESS_KEY": config['picovoice'],
            "GEMINI_API_KEY": config['gemini'],
            "LLM_PROVIDER": config['llm']
        }

        updated_keys = set()
        for line in lines:
            found = False
            for k, v in keys_to_update.items():
                if line.startswith(f"{k}="):
                    new_lines.append(f"{k}={v}\n")
                    updated_keys.add(k)
                    found = True
                    break
            if not found:
                new_lines.append(line)
        
        # Ajouter les clés manquantes
        for k, v in keys_to_update.items():
            if k not in updated_keys:
                new_lines.append(f"{k}={v}\n")

        with open(ENV_FILE, "w") as f:
            f.writelines(new_lines)

def main():
    window = webview.create_window(
        title="Sung Jin Woo - System Initialization",
        url=str(FRONTEND_DIR / "setup.html"),
        width=600,
        height=500,
        frameless=True,
        transparent=True,
        on_top=True
    )
    api = SetupAPI(window)
    window.expose(
        api.start_installation, 
        api.close_wizard, 
        api.launch_app
    )
    webview.start()

if __name__ == "__main__":
    main()
