/**
 * sound.js – Gestionnaire d'effets sonores (SFX)
 * Gère le chargement et la lecture des sons style Solo Leveling.
 */
export class SoundManager {
    constructor() {
        this.sounds = {};
        this.enabled = true;
        this.initialized = false;
        this._init();
    }

    _init() {
        // Liste des sons à charger (prévoir les fichiers dans assets/audio/)
        const manifest = {
            'arise': 'arise_epic.mp3',
            'click': 'ui_click.mp3',
            'hover': 'ui_hover.mp3',
            'ghost_whoosh': 'ghost_move.mp3',
            'magic_spark': 'magic_spark.mp3',
            'notification': 'notif_ding.mp3'
        };

        for (const [name, file] of Object.entries(manifest)) {
            const audio = new Audio(`assets/audio/${file}`);
            audio.volume = 0.5;
            this.sounds[name] = audio;
        }
    }

    /** Initialisation via interaction utilisateur (requis par les navigateurs) */
    init() {
        if (this.initialized) return;
        this.initialized = true;
        console.log('[Sound] Système audio initialisé ✓');
    }

    play(name, volume = 0.5) {
        if (!this.enabled || !this.sounds[name]) return;
        
        try {
            const sound = this.sounds[name].cloneNode();
            sound.volume = volume;
            sound.play().catch(() => {
                // Silencieux si l'utilisateur n'a pas encore cliqué
            });
        } catch (e) {
            console.warn(`[Sound] Erreur lecture ${name}:`, e);
        }
    }

    toggle(state) {
        this.enabled = state !== undefined ? state : !this.enabled;
    }
}

export const sfx = new SoundManager();
