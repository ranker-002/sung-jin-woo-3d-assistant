/**
 * ui.js – Gestionnaire UI et WebSocket
 * Gère : statut, bulles de dialogue, saisie texte, microphone navigateur.
 */
import { sfx } from './sound.js';

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
        this.$loader = document.getElementById('loader');

        // Conteneur boutons (à gauche)
        const btnContainer = document.createElement('div');
        btnContainer.className = 'ui-btn-container';
        btnContainer.style.cssText = `
          position: absolute; bottom: 20px; left: 20px;
          display: flex; gap: 10px;
        `;

        // Bouton Micro
        this.micBtn = this._createBtn('🎤');
        this.micBtn.title = 'Activer l\'écoute';

        // Bouton Système (Settings)
        this.sysBtn = this._createBtn('⚙️');
        this.sysBtn.title = 'Système (Paramètres)';

        // Bouton Wander (Exploration)
        this.wanderBtn = this._createBtn('🚶');
        this.wanderBtn.id = 'wander-btn';
        this.wanderBtn.title = 'Mode Exploration';

        btnContainer.appendChild(this.micBtn);
        btnContainer.appendChild(this.wanderBtn);
        btnContainer.appendChild(this.sysBtn);
        document.body.appendChild(btnContainer);

        this._bindEvents();

        this._setupSpeechRecognition();
    }

    _bindEvents() {
        // Envoi par bouton
        this.$send.addEventListener('click', () => {
            sfx.play('click');
            this._submitInput();
        });

        // Envoi par Entrée
        this.$input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sfx.play('click');
                this._submitInput();
            }
        });

        // Microphone
        if (this.micBtn) {
            this.micBtn.onclick = () => {
                sfx.play('click');
                this._toggleMic();
            }
        }

        // Settings
        if (this.sysBtn) {
            this.sysBtn.onclick = () => {
                sfx.play('click');
                this.openSettings();
            }
        }

        // Add hover sounds
        [this.micBtn, this.sysBtn, this.$send, this.wanderBtn].forEach(btn => {
            if (btn) btn.addEventListener('mouseenter', () => sfx.play('hover', 0.2));
        });

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
            if (this.micBtn) this.micBtn.title = 'Micro non supporté';
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
            // After receiving a result, stop recognition and set status to idle
            this._micActive = false;
            if (this.micBtn) this.micBtn.classList.remove('active');
            this.setStatus('idle');
        };

        this._recognition.onend = () => {
            this._micActive = false;
            this.micBtn.classList.remove('active');
            this.setStatus('idle');
        };

        this._recognition.onerror = (e) => {
            console.warn('[Mic] Erreur:', e.error);
            this._micActive = false;
            this.micBtn.classList.remove('active'); // Update new button too
        };
    }

    _toggleMic() {
        // Le backend gère l'écoute automatique via Wake Word.
        // Ce bouton peut servir à forcer l'état ou simplement d'indicateur.
        this._micActive = !this._micActive;
        if (this.micBtn) this.micBtn.classList.toggle('active', this._micActive);
        
        if (this._micActive) {
            this.setStatus('listening');
            sfx.play('click', 0.4);
        } else {
            this.setStatus('idle');
        }
    }

    /** Affiche une bulle d'XP flottante */
    showFloatingXP(amount) {
        const div = document.createElement('div');
        div.className = 'xp-float';
        div.textContent = `+${amount} XP`;
        // Positionner un peu aléatoirement près de la barre d'XP
        div.style.right = '40px';
        div.style.top = '100px';
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 1500);
    }

    /** Affiche une notification d'erreur (toast) */
    showError(message, duration = 5000) {
        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(220, 38, 38, 0.9);
            color: white;
            padding: 12px 20px;
            border-radius: 12px;
            font-size: 13px;
            max-width: 300px;
            text-align: center;
            z-index: 2000;
            box-shadow: 0 4px 20px rgba(220, 38, 38, 0.4);
            backdrop-filter: blur(10px);
            animation: slide-in 0.3s ease-out;
        `;

        // Add animation keyframes if not already present
        if (!document.getElementById('error-toast-styles')) {
            const style = document.createElement('style');
            style.id = 'error-toast-styles';
            style.textContent = `
                @keyframes slide-in {
                    from { opacity: 0; transform: translate(-50%, -20px); }
                    to { opacity: 1; transform: translate(-50%, 0); }
                }
                @keyframes fade-out {
                    from { opacity: 1; }
                    to { opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);

        // Auto-remove after duration
        setTimeout(() => {
            toast.style.animation = 'fade-out 0.3s ease-out forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
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

    // ── Paramètres ────────────────────────────────────────────────────────────────
    openSettings() {
        console.log('[UI] Ouverture des paramètres système...');
        if (window.pywebview && window.pywebview.api.open_settings) {
            window.pywebview.api.open_settings();
        }
    }

    _createBtn(icon) {
        const btn = document.createElement('button');
        btn.innerHTML = icon;
        btn.style.cssText = `
            width: 44px; height: 44px;
            border-radius: 50%;
            background: rgba(139, 92, 246, 0.2);
            border: 1px solid rgba(139, 92, 246, 0.4);
            color: white;
            font-size: 20px;
            cursor: pointer;
            backdrop-filter: blur(5px);
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            display: flex; align-items: center; justify-content: center;
        `;
        btn.onmouseover = () => {
            btn.style.transform = 'scale(1.1)';
            btn.style.background = 'rgba(139, 92, 246, 0.4)';
            btn.style.boxShadow = '0 0 15px rgba(139, 92, 246, 0.3)';
        };
        btn.onmouseout = () => {
            btn.style.transform = 'scale(1)';
            btn.style.background = 'rgba(139, 92, 246, 0.2)';
            btn.style.boxShadow = 'none';
        };
        return btn;
    }
}
