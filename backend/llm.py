"""
LLM – Interface de langage naturel.
Priorité: Ollama (local) → Gemini → fallback message d'erreur.
"""
import json
import requests
from typing import Generator
from config import (
    LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
    GEMINI_API_KEY, OPENAI_API_KEY,
    MAX_HISTORY_TURNS, SYSTEM_PROMPT, PERSONA_NAME
)

# Historique conversationnel en mémoire
_conversation_history: list[dict] = []


def _trim_history():
    """Garde seulement les N derniers tours."""
    global _conversation_history
    if len(_conversation_history) > MAX_HISTORY_TURNS * 2:
        _conversation_history = _conversation_history[-(MAX_HISTORY_TURNS * 2):]


def reset_history():
    """Réinitialise le contexte conversationnel."""
    global _conversation_history
    _conversation_history = []
    print("[LLM] Historique réinitialisé.")


def _call_ollama(prompt: str) -> str:
    """Appel au modèle Ollama local (non-stream pour simplicité)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _conversation_history
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 300,
                }
            },
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Ollama non disponible – tentative fallback Gemini")
    except Exception as e:
        raise RuntimeError(f"Erreur Ollama: {e}")


def _call_gemini(prompt: str) -> str:
    """Appel à l'API Gemini en fallback."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY non configurée.")

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
    # Reconstruit l'historique au format Gemini
    history = []
    for msg in _conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=history)
    response = chat.send_message(prompt)
    return response.text.strip()


def generate_response(user_input: str) -> str:
    """
    Génère une réponse IA pour le texte utilisateur.
    Essaie Ollama d'abord, puis Gemini, puis message de secours.
    """
    global _conversation_history

    print(f"[LLM] Requête: {user_input[:80]}...")
    response = ""

    # Tentatives par ordre de priorité
    providers = []
    if LLM_PROVIDER == "ollama":
        providers = [("ollama", _call_ollama), ("gemini", _call_gemini)]
    elif LLM_PROVIDER == "gemini":
        providers = [("gemini", _call_gemini), ("ollama", _call_ollama)]
    else:
        providers = [("ollama", _call_ollama), ("gemini", _call_gemini)]

    for name, fn in providers:
        try:
            response = fn(user_input)
            print(f"[LLM] Réponse ({name}): {response[:80]}...")
            break
        except Exception as e:
            print(f"[LLM] {name} échoué: {e}")
            continue

    if not response:
        response = "... Les ombres restent silencieuses pour l'instant."

    # Mise à jour historique
    _conversation_history.append({"role": "user", "content": user_input})
    _conversation_history.append({"role": "assistant", "content": response})
    _trim_history()

    return response
