/**
 * ui.js – Gestionnaire UI et WebSocket
 * Gère : statut, bulles de dialogue, saisie texte, microphone navigateur.
 */

export class UIManager {
    constructor(onUserInput) {
        this.onUserInput = onUserInput;
        this._state = 'idle';
        this._bubbleTimer = null;
        this._micActive = false;
        this._recognition = null;

        // Éléments DOM
        this.$dot = document.getElementById('status-dot');
        this.$text = document.getElementById('status-text');
        this.$bubble = document.getElementById('speech-bubble');
        this.$speech = document.getElementById('speech-text');
        this.$user = document.getElementById('user-text');
        this.$input = document.getElementById('text-input');
        this.$send = document.getElementById('send-btn');
        this.$mic = document.getElementById('mic-btn');
        this.$loader = document.getElementById('loader');

        this._bindEvents();
        this._setupSpeechRecognition();
    }

    _bindEvents() {
        // Envoi par bouton
        this.$send.addEventListener('click', () => this._submitInput());

        // Envoi par Entrée
        this.$input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._submitInput();
            }
        });

        // Microphone
        this.$mic.addEventListener('click', () => this._toggleMic());

        // Drag fenêtre (exposé via pywebview ou CSS)
        const handle = document.getElementById('drag-handle');
        if (handle) {
            handle.addEventListener('mousedown', () => {
                if (window.pywebview) {
                    window.pywebview.api.start_drag?.();
                }
            });
        }
    }

    _submitInput() {
        const text = this.$input.value.trim();
        if (!text) return;
        this.$input.value = '';
        this.$user.textContent = `Vous: ${text}`;
        this.onUserInput(text);
    }

    // ── Reconnaissance vocale navigateur (fallback si Backend STT absent) ────────
    _setupSpeechRecognition() {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            this.$mic.title = 'Micro non supporté';
            return;
        }

        this._recognition = new SR();
        this._recognition.lang = 'fr-FR';
        this._recognition.continuous = false;
        this._recognition.interimResults = false;

        this._recognition.onresult = (e) => {
            const text = e.results[0][0].transcript;
            if (text) {
                this.$user.textContent = `🎤 ${text}`;
                this.onUserInput(text);
            }
        };

        this._recognition.onend = () => {
            this._micActive = false;
            this.$mic.classList.remove('active');
            this.setStatus('idle');
        };

        this._recognition.onerror = (e) => {
            console.warn('[Mic] Erreur:', e.error);
            this._micActive = false;
            this.$mic.classList.remove('active');
        };
    }

    _toggleMic() {
        if (!this._recognition) return;
        if (this._micActive) {
            this._recognition.stop();
        } else {
            this._recognition.start();
            this._micActive = true;
            this.$mic.classList.add('active');
            this.setStatus('listening');
        }
    }

    // ── Statut ────────────────────────────────────────────────────────────────────
    setStatus(state) {
        this._state = state;
        this.$dot.className = `${state}`;

        const labels = {
            idle: 'En veille',
            listening: 'Écoute…',
            thinking: 'Réflexion…',
            speaking: 'Parle…',
        };
        this.$text.textContent = labels[state] ?? state;
    }

    // ── Bulles de dialogue ────────────────────────────────────────────────────────
    showSpeech(text, userText = '') {
        if (userText) this.$user.textContent = `Vous: ${userText}`;
        this.$speech.textContent = text;
        this.$bubble.classList.add('visible');

        // Auto-hide après durée proportionnelle
        clearTimeout(this._bubbleTimer);
        const duration = Math.max(4000, text.length * 60);
        this._bubbleTimer = setTimeout(() => this.hideBubble(), duration);
    }

    hideBubble() {
        this.$bubble.classList.remove('visible');
    }

    // ── Loader ────────────────────────────────────────────────────────────────────
    hideLoader() {
        this.$loader.classList.add('hidden');
        setTimeout(() => { this.$loader.style.display = 'none'; }, 1000);
    }
}
