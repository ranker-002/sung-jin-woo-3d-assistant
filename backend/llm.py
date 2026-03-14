import json
import requests
import re
import subprocess
import webbrowser
import os
import sys
from typing import Generator

# Assurer l'accès aux modules locaux
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
    GEMINI_API_KEY, OPENAI_API_KEY, OPENAI_MODEL,
    MAX_HISTORY_TURNS, SYSTEM_PROMPT, PERSONA_NAME
)
from memory import memory

# Historique conversationnel chargé depuis la mémoire
_conversation_history: list[dict] = []

def _get_system_instructions():
    """Génère les instructions système avec le contexte de mémoire et les actions."""
    facts = memory.get_all_facts()
    facts_str = "\n- ".join(facts) if facts else "Aucun fait marquant connu."
    
    context = f"\n\n[MÉMOIRE À LONG TERME]\nTu te souviens de ces faits sur l'utilisateur :\n- {facts_str}"
    
    actions = """
[SYSTEM ACTIONS]
Tu peux interagir avec l'ordinateur de l'utilisateur en ajoutant un tag à la fin de ton message :
- [ACTION:OPEN_URL|url] : Ouvre une adresse web.
- [ACTION:EXEC|commande] : Lance une application ou commande (ex: spotify, calc).
- [SAVE_FACT:description] : Enregistre une information importante sur l'utilisateur pour tes prochaines sessions.
Exemple: "Je m'en souviendrai. [SAVE_FACT: L'utilisateur s'appelle Thomas]"
"""
    return SYSTEM_PROMPT + context + actions

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
                    webbrowser.open(val)
                    print(f"[Action] Ouverture URL: {val}")
                elif cmd_type == "EXEC":
                    subprocess.Popen(val, shell=True)
                    print(f"[Action] Exécution commande: {val}")
            text = text.replace(f"[ACTION:{act}]", "")
        except Exception as e:
            print(f"[Action] Erreur lors de l'exécution de {act}: {e}")

    return text.strip(), emotion

def _call_ollama(prompt: str) -> str:
    """Appel au modèle Ollama local."""
    system_instr = _get_system_instructions()
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
                "options": {"temperature": 0.7, "num_predict": 300}
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
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=_get_system_instructions())
    
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
    
    system_instr = _get_system_instructions()
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
    global _conversation_history

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
    _trim_history()

    return final_text, emotion
