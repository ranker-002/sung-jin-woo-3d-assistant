/**
 * sound.js – Gestionnaire d'effets sonores (SFX)
 * Gère le chargement et la lecture des sons style Solo Leveling.
 */
export class SoundManager {
    constructor() {
        this.sounds = {};
        this.enabled = true;
        this.initialized = false;
        this._missingSounds = new Set();
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

        // Check which files exist, create silent fallbacks for missing ones
        for (const [name, file] of Object.entries(manifest)) {
            const path = `assets/audio/${file}`;

            // Create an Audio element but it may fail to load if file missing
            const audio = new Audio();
            audio.volume = 0.5;
            audio.preload = 'none';

            // Check if file exists by trying to load and catching error
            // We'll lazily check on first play
            audio.addEventListener('error', (e) => {
                if (!this._missingSounds.has(name)) {
                    console.warn(`[Sound] Fichier audio manquant: ${path}`);
                    this._missingSounds.add(name);
                }
            });

            // Set source but don't trigger load yet
            audio.src = path;

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
        if (!this.enabled) return;
        const original = this.sounds[name];
        if (!original) {
            // Only log once per missing sound
            if (!this._missingSounds?.has(name)) {
                console.warn(`[Sound] Son non configuré: ${name}`);
            }
            return;
        }

        // If we already know this sound is missing, skip
        if (this._missingSounds.has(name)) return;

        try {
            const sound = original.cloneNode();
            sound.volume = volume;
            sound.play().catch((err) => {
                // Log missing file only once
                if (!this._missingSounds.has(name)) {
                    console.warn(`[Sound] Impossible de lire '${name}': ${err.message}`);
                    this._missingSounds.add(name);
                }
            });
        } catch (e) {
            console.warn(`[Sound] Erreur lecture ${name}:`, e);
            this._missingSounds.add(name);
        }
    }

    toggle(state) {
        this.enabled = state !== undefined ? state : !this.enabled;
    }
}

export const sfx = new SoundManager();
