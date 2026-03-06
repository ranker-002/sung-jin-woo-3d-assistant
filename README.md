# 🗡️ Sung Jin Woo – Shadow Monarch Assistant Virtuel 3D

Un assistant virtuel 3D réaliste inspiré de **Sung Jin Woo** (Solo Leveling) qui vit sur votre bureau. Il parle, écoute et interagit avec des animations Mixamo et du lip-sync temps-réel.

---

## ✨ Fonctionnalités

- 🎭 **Personnage 3D** avec animations Mixamo (idle, parler, écoute, réflexion)
- 👄 **Lip-sync** via visèmes → morph targets (bouche synchronisée)
- 🎤 **Écoute microphone** (faster-whisper, offline)
- 🧠 **IA conversationnelle** (Ollama local + fallback Gemini)
- 🎙️ **Synthèse vocale** (Coqui XTTS-v2 ou ElevenLabs)
- ✨ **Effets visuels** : bloom violet, particules shadow, aura magique
- 🪟 **Fenêtre transparente** toujours au premier plan (PyWebView)
- 🔲 **Icône barre systeme** (afficher/masquer/quitter)

---

## 🛠️ Installation

### 1. Prérequis
```bash
python >= 3.11
pip
Ollama (optionnel, recommandé)
```

### 2. Installer les dépendances Python
```bash
cd /home/ranker/DEV/sung
pip install -r backend/requirements.txt
# Pour gTTS (fallback TTS gratuit)
pip install gTTS
```

### 3. Installer Ollama (LLM local)
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
```

### 4. Configurer (optionnel)
```bash
cp .env .env.local
# Éditer .env avec vos clés API (Gemini, ElevenLabs...)
```

---

## 🎮 Lancer l'application

```bash
cd /home/ranker/DEV/sung
python app.py
```

Ou en mode debug (DevTools visible) :
```bash
DEBUG=1 python app.py
```

### Tester le backend seul
```bash
cd /home/ranker/DEV/sung/backend
python main.py
```

---

## 🧩 Ajouter le modèle 3D Sung Jin Woo

1. Télécharger un modèle FBX depuis :
   - [RigModels.com](https://rigmodels.com) → chercher "Sung Jin Woo"
   - [DeviantArt](https://www.deviantart.com) → "Sung Jinwoo FBX NekoPixil"

2. Ouvrir dans **Blender** :
   - Importer FBX → vérifier le rig
   - Ajouter morph targets pour la bouche (15 visèmes standard)

3. Télécharger les animations depuis **[Mixamo](https://www.mixamo.com)** :
   - Standing Idle → `assets/animations/standing_idle.fbx`
   - Breathing Idle → `assets/animations/breathing_idle.fbx`
   - Talking → `assets/animations/talking.fbx`
   - Thinking → `assets/animations/thinking.fbx`
   - Head Nod → `assets/animations/nodding.fbx`
   - Standing W Gesture → `assets/animations/gesture_talking.fbx`

4. Exporter depuis Blender en **GLB** → `assets/models/sung_jin_woo.glb`

> **Note**: Sans modèle GLB, l'assistant utilise un **placeholder géométrique** violet animé qui fonctionne aussi !

---

## 📁 Structure du projet

```
sung/
├── app.py                  # Lanceur principal (PyWebView)
├── tray.py                 # Icône système
├── .env                    # Configuration
├── backend/
│   ├── main.py             # Serveur WebSocket FastAPI
│   ├── stt.py              # Speech-to-Text (faster-whisper)
│   ├── llm.py              # LLM (Ollama + Gemini)
│   ├── tts.py              # TTS + visèmes
│   ├── config.py           # Configuration centralisée
│   └── requirements.txt
└── frontend/
    ├── index.html          # Interface & UI
    ├── main.js             # Orchestrateur Three.js
    ├── character.js        # Chargement modèle + animations
    ├── lipsync.js          # Système lip-sync
    ├── effects.js          # VFX bloom + particules
    ├── ui.js               # UI (status, bulles, input)
    └── assets/
        ├── models/         # sung_jin_woo.glb
        └── animations/     # FBX Mixamo
```

---

## 🔧 Configuration avancée

| Variable | Defaut | Description |
|----------|--------|-------------|
| `WHISPER_MODEL` | `small` | `tiny` (rapide) / `medium` (précis) |
| `LLM_PROVIDER` | `ollama` | `ollama`, `gemini`, `openai` |
| `TTS_ENGINE` | `coqui` | `coqui`, `elevenlabs`, `gtts` |
| `WINDOW_X` / `Y` | `50`/`100` | Position fenêtre sur le bureau |

---

## 📜 Licence
Usage personnel uniquement. Le character design Sung Jin Woo appartient à D&C Media / Chugong.
