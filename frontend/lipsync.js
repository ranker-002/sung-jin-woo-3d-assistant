/**
 * lipsync.js – Pilote le lip-sync à partir d'une séquence de visèmes.
 * Reçoit: [{ time: ms, viseme: id, weight: float }]
 * Applique les morph targets sur le Character en temps réel.
 */

export class LipSyncController {
    constructor(character) {
        this.character = character;
        this._sequence = [];    // Séquence de visèmes à rejouer
        this._startTime = 0;     // Timestamp de début de lecture (ms)
        this._active = false;
        this._curViseme = 0;
        this._curWeight = 0;
        this._nextIdx = 0;
    }

    /**
     * Démarre une séquence de lip-sync.
     * @param {Array} visemes - [{time, viseme, weight}, ...]
     */
    play(visemes) {
        if (!visemes?.length) return;
        this._sequence = visemes;
        this._startTime = performance.now();
        this._nextIdx = 0;
        this._active = true;
        console.log(`[LipSync] Lecture ${visemes.length} visèmes`);
    }

    /** Arrête le lip-sync et ferme la bouche. */
    stop() {
        this._active = false;
        this._sequence = [];
        this._nextIdx = 0;
        this.character.resetMorphTargets();
    }

    /** Appelez chaque frame depuis la boucle principale. */
    update(delta) {
        if (!this._active || !this._sequence.length) {
            if (this._curWeight > 0.01) {
                this.character.resetMorphTargets();
                this._curWeight = 0;
            }
            return;
        }

        const elapsed = performance.now() - this._startTime;

        // Avancer dans la séquence
        while (
            this._nextIdx < this._sequence.length &&
            this._sequence[this._nextIdx].time <= elapsed
        ) {
            const v = this._sequence[this._nextIdx];
            this._curViseme = v.viseme;
            this._curWeight = v.weight ?? 1.0;
            this._nextIdx++;
        }

        // Fin de séquence
        if (this._nextIdx >= this._sequence.length && elapsed > this._sequence.at(-1)?.time + 200) {
            this.stop();
            return;
        }

        // Appliquer visème courant
        this.character.applyViseme(this._curViseme, this._curWeight, delta);
    }

    get isPlaying() { return this._active; }
}


/**
 * AudioLipSync – Lip-sync basé sur l'analyse audio en temps réel (Web Audio API).
 * Utilisé en complément pour les moteurs TTS sans visèmes précis.
 */
export class AudioLipSync {
    constructor(character) {
        this.character = character;
        this._ctx = null;
        this._analyser = null;
        this._dataArray = null;
        this._active = false;
        this._source = null;
    }

    /**
     * Analyse l'amplitude de l'audio en temps réel pour animer la bouche.
     * @param {AudioNode} sourceNode - Source audio Web Audio API
     */
    attachToSource(sourceNode, audioContext) {
        this._ctx = audioContext;
        this._analyser = audioContext.createAnalyser();
        this._analyser.fftSize = 256;
        this._dataArray = new Uint8Array(this._analyser.frequencyBinCount);

        sourceNode.connect(this._analyser);
        this._source = sourceNode;
        this._active = true;
    }

    update(delta) {
        if (!this._active || !this._analyser) return;

        this._analyser.getByteFrequencyData(this._dataArray);

        // Amplitude moyenne dans la plage vocale (300–3000 Hz)
        const binCount = this._analyser.frequencyBinCount;
        const sampleRate = this._ctx.sampleRate;
        const lowBin = Math.floor(300 / (sampleRate / 2) * binCount);
        const highBin = Math.floor(3000 / (sampleRate / 2) * binCount);

        let sum = 0;
        for (let i = lowBin; i < highBin; i++) sum += this._dataArray[i];
        const avg = sum / (highBin - lowBin);

        // Normaliser [0, 255] → [0, 1] avec courbe exponentielle
        const weight = Math.pow(avg / 255, 0.6);

        // Choisir visème en fonction de l'intensité
        let visemeId = 0;
        if (weight > 0.7) visemeId = 10; // viseme_aa (grande ouverture)
        else if (weight > 0.4) visemeId = 11; // viseme_E
        else if (weight > 0.1) visemeId = 12; // viseme_I (petite ouverture)

        this.character.applyViseme(visemeId, weight, delta);
    }

    stop() {
        this._active = false;
        if (this._source) {
            try { this._source.disconnect(this._analyser); } catch { }
        }
        this.character.resetMorphTargets();
    }
}
