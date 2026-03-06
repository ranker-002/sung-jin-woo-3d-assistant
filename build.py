"""
build.py – Script de packaging pour créer un exécutable (.exe ou binaire Linux).
Utilise PyInstaller pour empaqueter le backend, PyWebView et les assets.
"""
import os
import sys
import subprocess
from pathlib import Path

def build():
    print("🕴️ [SYSTEM] Préparation du packaging du Monarque...")
    
    # Vérifier PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("> Installation de PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Arguments PyInstaller
    # --noconsole : Pas de fenêtre terminal
    # --onefile : Un seul fichier (optionnel, peut ralentir le démarrage)
    # --add-data : Inclure le dossier frontend
    separator = ";" if sys.platform == "win32" else ":"
    
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--name=SungJinWooAssistant",
        f"--add-data=frontend{separator}frontend",
        f"--add-data=backend{separator}backend",
        "--hidden-import=pywebview",
        "--hidden-import=pystray",
        "--hidden-import=PIL",
        "--icon=frontend/assets/icon.ico", # Si vous en avez un
        "app.py"
    ]

    print(f"> Exécution de la commande : {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("\n🕴️ [SYSTEM] Extraction terminée ! Votre exécutable est dans le dossier 'dist/'.")
    except Exception as e:
        print(f"\n[ERREUR] Échec du packaging : {e}")

if __name__ == "__main__":
    build()
