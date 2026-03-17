import json
import time
import requests
import re
import subprocess
import webbrowser
import os
import sys
import shlex
from pathlib import Path
from typing import Generator

# Assurer l'accès aux modules locaux
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
    GEMINI_API_KEY, OPENAI_API_KEY, OPENAI_MODEL,
    MAX_HISTORY_TURNS, SYSTEM_PROMPT, PERSONA_NAME,
    ALLOWED_COMMANDS, DANGEROUS_COMMANDS
)
from memory import memory

def _validate_command(command: str) -> tuple[bool, str]:
    """
    Validate a command for execution.
    Returns (is_valid, error_message).
    """
    if not command:
        return False, "Empty command"

    # Parse command safely (no shell expansion)
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"

    if not parts:
        return False, "No command parts parsed"

    cmd_name = Path(parts[0]).name.lower().strip()

    # Check against whitelist (from config)
    if cmd_name not in ALLOWED_COMMANDS:
        return False, f"Command '{cmd_name}' not authorized. Add to ALLOWED_COMMANDS in config to enable."

    # Check for shell metacharacters (shouldn't exist if using shlex, but double-check)
    dangerous_chars = [';', '|', '&', '>', '<', '`', '$', '(', ')', '{', '}', '[', ']']
    if any(char in command for char in dangerous_chars):
        return False, "Command contains shell metacharacters"

    # Check if requires confirmation (not implemented yet, block for now)
    if cmd_name in DANGEROUS_COMMANDS:
        return False, f"Command '{cmd_name}' is considered dangerous and requires user confirmation (not auto-executed)"

    return True, "OK"

def _execute_command_safely(command: str) -> tuple[bool, str]:
    """
    Execute a command after validation.
    Returns (success, output/error).
    """
    # Validate first
    is_valid, msg = _validate_command(command)
    if not is_valid:
        return False, f"[SECURITY] Command blocked: {msg}"

    try:
        # Use Popen with list, no shell=True
        parts = shlex.split(command)
        proc = subprocess.Popen(
            parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False  # CRITICAL: Never use shell=True
        )
        stdout, stderr = proc.communicate(timeout=10)

        if proc.returncode == 0:
            return True, stdout.strip() if stdout else "Command executed"
        else:
            return False, f"Command failed (code {proc.returncode}): {stderr.strip()}"
    except subprocess.TimeoutExpired:
        proc.kill()
        return False, "Command timed out after 10 seconds"
    except Exception as e:
        return False, f"Execution error: {e}"

# Historique conversationnel chargé depuis la mémoire
_conversation_history: list[dict] = []
_last_activity_time = time.time()

def _get_system_instructions(user_query: str = "", proactive=False):
    """Génère les instructions système avec le contexte de mémoire sémantique et les actions."""
    # Recherche sémantique de faits pertinents pour la requête actuelle
    query_for_facts = user_query if not proactive else "pensées intérieures"
    relevant_facts = memory.search_relevant_facts(query_for_facts, limit=3)
    facts_str = "\n- ".join(relevant_facts) if relevant_facts else "Analysant le flux de données..."
    
    # Récupérer le dernier résumé pour garder la trace des interactions passées
    last_summary = memory.get_last_summary()
    summary_context = f"\n[RÉSUMÉ DES ÉCHANGES PASSÉS]\n{last_summary}" if last_summary else ""
    
    # Stats (Dungeon Mode)
    stats = memory.get_stats()
    stats_str = f"[DONJON STATUS] Niveau: {stats.get('level', 1)} | XP: {stats.get('xp', 0)}"

    context = f"{stats_str}\n{summary_context}\n\n[MÉMOIRE SÉMANTIQUE (Faits pertinents)]\n- {facts_str}"
    
    actions = """
[SYSTEM ACTIONS]
- [ACTION:OPEN_URL|url] : Ouvre une adresse web.
- [ACTION:EXEC|commande] : Lance une application ou commande (ex: spotify, calc).
- [ACTION:VOL|+-N] : Ajuste le volume (ex: VOL|+10, VOL|-5).
- [ACTION:WEATHER|city] : Demande la météo (ex: WEATHER|Paris).
- [ACTION:SYS_INFO] : Récupère les ressources (CPU/RAM) de la machine.
- [SAVE_FACT:description] : Enregistre une information sur l'utilisateur.
- [EMOTION:type] : Change ton aura (angry, calm, power, thinking, happy).
"""
    return SYSTEM_PROMPT + context + actions

def generate_proactive_thought() -> tuple[str, str]:
    """Génère une intervention spontanée du Monarque."""
    prompt = "L'utilisateur est silencieux depuis un moment. Fais une remarque stoïque, pose une question courte ou rappelle-lui ses objectifs. Sois très bref."
    
    try:
        # On passe proactive=True pour ajuster les instructions système
        if LLM_PROVIDER == "ollama":
             system_instr = _get_system_instructions(proactive=True)
             resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json={
                 "model": OLLAMA_MODEL,
                 "messages": [{"role": "system", "content": system_instr}, {"role": "user", "content": prompt}],
                 "stream": False,
                 "options": {"temperature": 0.8, "num_predict": 100}
             }, timeout=30)
             response = resp.json()["message"]["content"].strip()
        else:
             response = "Le silence est parfois nécessaire pour aiguiser sa lame."
             
        final_text, emotion = _process_output_tags(response)
        return final_text, emotion
    except:
        return "", "thinking"

def _should_summarize():
    """Détermine si on doit générer un résumé (ex: tous les 15 messages)."""
    # Pour simplifier, on vérifie la longueur de l'historique
    return len(_conversation_history) >= 14

def _generate_summary():
    """Génère un résumé de la conversation actuelle et l'enregistre."""
    global _conversation_history
    print("[LLM] Génération d'un résumé de session...")
    
    prompt = "Résume brièvement les points clés, les décisions et les préférences de l'utilisateur dans cette conversation pour conserver une trace à long terme."
    
    # On utilise une version courte du prompt pour le résumé
    try:
        if LLM_PROVIDER == "ollama":
            summary = _call_ollama(prompt, is_summary_call=True)
        else:
            summary = _call_openai(prompt) # Fallback simple
            
        memory.add_summary(summary)
        print(f"[Memory] Résumé enregistré : {summary[:50]}...")
        # On peut vider l'historique de session maintenant qu'on a un résumé
        _conversation_history = _conversation_history[-4:] # Garder juste un peu de contexte immédiat
    except Exception as e:
        print(f"[LLM] Échec du résumé : {e}")

def _trim_history():
    """Garde seulement les N derniers tours."""
    global _conversation_history
    if len(_conversation_history) > MAX_HISTORY_TURNS * 2:
        _conversation_history = _conversation_history[-(MAX_HISTORY_TURNS * 2):]

def reset_history():
    """Réinitialise le contexte conversationnel et recharge depuis la mémoire."""
    global _conversation_history
    _conversation_history = memory.get_recent_history(MAX_HISTORY_TURNS)
    print(f"[LLM] Historique rechargé depuis la mémoire ({len(_conversation_history)} messages).")

def _process_output_tags(text: str) -> tuple[str, str]:
    """Analyse le texte pour extraire les faits, émotions et actions."""
    emotion = "neutral"
    
    # 0. Extraction de l'émotion
    emotions_found = re.findall(r'\[EMOTION:(.*?)\]', text, re.IGNORECASE)
    if emotions_found:
        emotion = emotions_found[-1].strip().lower() # Prendre la dernière émotion
        text = re.sub(r'\[EMOTION:.*?\]', '', text, flags=re.IGNORECASE)
    # 1. Enregistrement des faits
    facts = re.findall(r'\[SAVE_FACT:(.*?)\]', text)
    for f in facts:
        memory.add_fact(f.strip())
        text = text.replace(f"[SAVE_FACT:{f}]", "")
        print(f"[Memory] Nouveau fait enregistré: {f.strip()}")

    # 2. Exécution des actions système
    actions = re.findall(r'\[ACTION:(.*?)\]', text)
    for act in actions:
        try:
            if "|" in act:
                cmd_type, val = act.split("|", 1)
                val = val.strip()
                if cmd_type == "OPEN_URL":
                    # Validate URL (basic check)
                    if not val.startswith(('http://', 'https://')):
                        val = 'https://' + val
                    webbrowser.open(val)
                    print(f"[Action] Ouverture URL: {val}")
                elif cmd_type == "EXEC":
                    # SECURE: Use whitelist validation, no shell=True
                    success, output = _execute_command_safely(val)
                    if success:
                        print(f"[Action] EXEC OK: {val} → {output}")
                        if output:
                            text = text + f"\n[INFO SYSTEME: {output}]"
                    else:
                        print(f"[Action] EXEC BLOCKED: {val} → {output}")
                        text = text + f"\n[INFO SYSTEME: Action non autorisée: {output}]"
                elif cmd_type == "VOL":
                    # SECURITY: Validate volume format before executing
                    if re.match(r'^[+-]\d{1,3}%?$', val):
                        amount = val.rstrip('%')
                        # Cross-platform volume control attempt
                        try:
                            if sys.platform == 'linux':
                                # Try PulseAudio (pactl)
                                cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{amount}%"]
                            elif sys.platform == 'darwin':
                                # macOS
                                cmd = ["osascript", "-e", f"set volume output volume {amount}"]
                            elif sys.platform == 'win32':
                                # Windows (requires nircmd or similar)
                                print("[Action] VOL: Not implemented on Windows without nircmd")
                                cmd = None
                            else:
                                cmd = None

                            if cmd:
                                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                                if result.returncode == 0:
                                    print(f"[Action] Volume: {val}")
                                else:
                                    print(f"[Action] VOL error: {result.stderr}")
                        except Exception as e:
                            print(f"[Action] VOL failed: {e}")
                    else:
                        print(f"[Action] VOL format invalid: {val}")
                elif cmd_type == "WEATHER":
                    # Validate city name (alphanumeric, spaces, hyphens only)
                    if re.match(r'^[a-zA-Z0-9\s\-]+$', val) and len(val) <= 50:
                        try:
                            resp = requests.get(f"https://wttr.in/{val}?format=3", timeout=10)
                            if resp.status_code == 200:
                                weather_text = resp.text.strip()
                                text = text + f"\n[INFO SYSTEME: La météo à {val} est {weather_text}]"
                            else:
                                text = text + f"\n[INFO SYSTEME: Impossible d'obtenir la météo pour {val}]"
                        except requests.RequestException as e:
                            text = text + f"\n[INFO SYSTEME: Erreur réseau météo: {e}]"
                    else:
                        print(f"[Action] WEATHER invalid city: {val}")
                elif cmd_type == "SYS_INFO":
                    # Platform-agnostic system info (no shell)
                    try:
                        import psutil
                        cpu = psutil.cpu_percent(interval=0.5)
                        ram = psutil.virtual_memory()
                        info = f"CPU: {cpu}%, RAM: {ram.used/1e9:.1f}GB/{ram.total/1e9:.1f}GB, Charge: {psutil.getloadavg()[0]:.1f}"
                    except ImportError:
                        info = "System info non disponible (psutil requis)"
                    text = text + f"\n[INFO SYSTEME: {info}]"
            text = text.replace(f"[ACTION:{act}]", "")
        except Exception as e:
            print(f"[Action] Erreur lors de l'exécution de {act}: {e}")

    return text.strip(), emotion

def _call_ollama(prompt: str, is_summary_call=False) -> str:
    """Appel au modèle Ollama local."""
    system_instr = _get_system_instructions(prompt if not is_summary_call else "")
    messages = [{"role": "system", "content": system_instr}]
    messages += _conversation_history
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 400 if not is_summary_call else 150}
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")

def _call_gemini(prompt: str) -> str:
    """Appel à l'API Gemini."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY manquante.")

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=_get_system_instructions(prompt))
    
    # Formatage de l'historique
    history = []
    for msg in _conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=history)
    response = chat.send_message(prompt)
    
    if hasattr(response, 'text') and response.text:
        return response.text.strip()
    return "... Les ombres gardent le silence."

def _call_openai(prompt: str) -> str:
    """Appel à l'API OpenAI (similaire à riko_project)."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY manquante.")
        
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    system_instr = _get_system_instructions(prompt)
    messages = [{"role": "system", "content": system_instr}]
    messages += _conversation_history
    messages.append({"role": "user", "content": prompt})
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=1.0,
        top_p=1.0,
        max_tokens=2048,
    )
    
    content = response.choices[0].message.content
    return content.strip() if content else "... Les ombres sont silencieuses."

def generate_response(user_input: str) -> tuple[str, str]:
    """Génère une réponse avec mémoire et actions système."""
    global _conversation_history, _last_activity_time

    _last_activity_time = time.time()
    # Initialiser l'historique si vide
    if not _conversation_history:
        reset_history()

    # Log user input
    memory.log_chat("user", user_input)

    response = ""
    providers = []
    if LLM_PROVIDER == "openai":
        providers = [("openai", _call_openai)]
    elif LLM_PROVIDER == "gemini":
        providers = [("gemini", _call_gemini)]
    else:
        providers = [("ollama", _call_ollama)]


    for name, fn in providers:
        try:
            response = fn(user_input)
            break
        except Exception as e:
            print(f"[LLM] {name} échoué: {e}")

    if not response:
        response = "... Les ombres sont troublées."

    # Traiter les tags [SAVE_FACT] et [ACTION] et [EMOTION]
    final_text, emotion = _process_output_tags(response)

    # Log assistant response
    memory.log_chat("assistant", final_text)
    
    # Mise à jour de l'historique de session
    _conversation_history.append({"role": "user", "content": user_input})
    _conversation_history.append({"role": "assistant", "content": final_text})
    
    # Gestion de la mémoire et résumé si nécessaire
    if _should_summarize():
        _generate_summary()
    else:
        _trim_history()

    # Gain d'XP pour le Monarque (Donjon Mode)
    xp, level, leveled_up = memory.add_xp(10) # 10 XP par message
    
    if leveled_up:
        final_text = f"Félicitations. Tu viens de monter au niveau {level}. Continue ton ascension. [EMOTION:happy]\n\n" + final_text

    return final_text, emotion, xp, level
