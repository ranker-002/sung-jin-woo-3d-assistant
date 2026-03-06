/**
 * effects.js – Effets visuels style Solo Leveling / Shadow Monarch
 * Bloom violet, particules flottantes, aura magique, ombres dynamiques.
 */
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export class VFXManager {
    constructor(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;

        this.composer = null;
        this._particles = null;
        this._auraLight = null;
        this._rimLights = [];
        this._particleTime = 0;

        this._init();
    }

    _init() {
        this._setupPostProcessing();
        this._setupLighting();
        this._setupParticles();
        this._setupGroundFog();
    }

    // ── Post-processing ──────────────────────────────────────────────────────────
    _setupPostProcessing() {
        const size = new THREE.Vector2(
            this.renderer.domElement.width,
            this.renderer.domElement.height
        );

        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));

        // Bloom violet pour l'aura
        const bloom = new UnrealBloomPass(size, 1.2, 0.5, 0.0);
        bloom.threshold = 0.0;
        bloom.strength = 1.4;
        bloom.radius = 0.7;
        this.composer.addPass(bloom);
        this._bloomPass = bloom;

        this.composer.addPass(new OutputPass());
    }

    // ── Éclairage cinématique ────────────────────────────────────────────────────
    _setupLighting() {
        // Lumière ambiante sombre
        const ambient = new THREE.AmbientLight(0x0a0520, 0.6);
        this.scene.add(ambient);

        // Lumière principale (bleu-violet froid)
        const keyLight = new THREE.DirectionalLight(0x6020d0, 2.0);
        keyLight.position.set(2, 4, 3);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.set(1024, 1024);
        keyLight.shadow.camera.near = 0.1;
        keyLight.shadow.camera.far = 20;
        this.scene.add(keyLight);

        // Lumière de remplissage (violet chaud)
        const fillLight = new THREE.PointLight(0x9333ea, 1.5, 8);
        fillLight.position.set(-2, 1, 1);
        this.scene.add(fillLight);

        // Rim light bleu glacé (contour)
        const rimLight = new THREE.PointLight(0x1a88ff, 2.0, 6);
        rimLight.position.set(0, 2, -3);
        this.scene.add(rimLight);
        this._rimLights.push(rimLight);

        // Aura pulsante sous le personnage
        this._auraLight = new THREE.PointLight(0x6600cc, 1.0, 4);
        this._auraLight.position.set(0, -0.8, 0);
        this.scene.add(this._auraLight);
    }

    // ── Particules Shadow Monarch ────────────────────────────────────────────────
    _setupParticles() {
        const count = 200;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        const sizes = new Float32Array(count);
        const speeds = new Float32Array(count);
        const phases = new Float32Array(count);

        for (let i = 0; i < count; i++) {
            // Cylindre autour du personnage
            const angle = Math.random() * Math.PI * 2;
            const radius = 0.4 + Math.random() * 1.2;
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = (Math.random() - 0.3) * 3.0;
            positions[i * 3 + 2] = Math.sin(angle) * radius;

            // Couleurs violet/bleu/blanc
            const t = Math.random();
            if (t < 0.5) {
                colors[i * 3] = 0.5 + Math.random() * 0.4;  // R
                colors[i * 3 + 1] = 0.1;                     // G
                colors[i * 3 + 2] = 1.0;                     // B (bleu-violet)
            } else {
                colors[i * 3] = 0.9;   // blanc-violet
                colors[i * 3 + 1] = 0.8;
                colors[i * 3 + 2] = 1.0;
            }

            sizes[i] = 0.02 + Math.random() * 0.05;
            speeds[i] = 0.3 + Math.random() * 0.8;
            phases[i] = Math.random() * Math.PI * 2;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

        // Shader particules avec glow
        const material = new THREE.PointsMaterial({
            size: 0.06,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            sizeAttenuation: true,
        });

        this._particles = new THREE.Points(geometry, material);
        this._particleSpeeds = speeds;
        this._particlePhases = phases;
        this._particleInitY = new Float32Array(positions.filter((_, i) => i % 3 === 1));
        this.scene.add(this._particles);
    }

    // ── Brume au sol ─────────────────────────────────────────────────────────────
    _setupGroundFog() {
        this.scene.fog = new THREE.FogExp2(0x000000, 0.0);  // transparent, pas de fog global
    }

    // ── Boucle mise à jour ───────────────────────────────────────────────────────
    update(delta, characterState) {
        this._particleTime += delta;

        // Animation particules
        if (this._particles) {
            const pos = this._particles.geometry.attributes.position;
            const count = pos.count;
            for (let i = 0; i < count; i++) {
                const speed = this._particleSpeeds[i];
                const phase = this._particlePhases[i];
                const initY = this._particleInitY[i];

                // Montée douce avec boucle
                pos.setY(i, initY + (this._particleTime * speed * 0.3 + phase) % 3.5 - 0.5);
                // Léger mouvement orbital
                const angle = this._particleTime * speed * 0.1 + phase;
                const r = Math.sqrt(pos.getX(i) ** 2 + pos.getZ(i) ** 2);
                if (r > 0.01) {
                    const curAngle = Math.atan2(pos.getZ(i), pos.getX(i));
                    const na = curAngle + delta * speed * 0.15;
                    pos.setX(i, Math.cos(na) * r);
                    pos.setZ(i, Math.sin(na) * r);
                }
            }
            pos.needsUpdate = true;

            // Opacité selon état
            const targetOpacity = characterState === 'speaking' ? 0.95 : 0.6;
            this._particles.material.opacity += (targetOpacity - this._particles.material.opacity) * delta * 2;
        }

        // Pulsation aura
        if (this._auraLight) {
            const pulse = Math.sin(this._particleTime * 2.0) * 0.3 + 0.7;
            this._auraLight.intensity = (characterState === 'speaking' ? 2.0 : 0.8) * pulse;
        }

        // Rim light dynamique
        this._rimLights.forEach(light => {
            const osc = Math.sin(this._particleTime * 1.2) * 0.3 + 0.7;
            light.intensity = 1.5 + osc * 0.5;
        });

        // Bloom amplifié quand le personnage parle
        if (this._bloomPass) {
            const targetStrength = characterState === 'speaking' ? 2.0 : 1.2;
            this._bloomPass.strength += (targetStrength - this._bloomPass.strength) * delta * 2;
        }
    }

    /** Effet 'Arise' (Extraction d'ombre) - Apparition spectaculaire */
    arise() {
        if (this._bloomPass) {
            this._bloomPass.strength = 6.0; // Explosion de lumière
            const decrease = setInterval(() => {
                this._bloomPass.strength -= 0.1;
                if (this._bloomPass.strength <= 1.4) {
                    this._bloomPass.strength = 1.4;
                    clearInterval(decrease);
                }
            }, 30);
        }

        // Booster les particules temporairement
        if (this._particles) {
            const oldSpeeds = new Float32Array(this._particleSpeeds);
            for (let i = 0; i < this._particleSpeeds.length; i++) this._particleSpeeds[i] *= 10;
            setTimeout(() => {
                this._particleSpeeds.set(oldSpeeds);
            }, 1000);
        }
    }

    /** Permet de changer la couleur de l'aura/thème */
    setThemeColor(hex) {
        const color = new THREE.Color(hex);
        if (this._auraLight) this._auraLight.color.copy(color);
        if (this._particles) this._particles.material.color.copy(color);
        this._rimLights.forEach(l => l.color.copy(color).lerp(new THREE.Color(0xffffff), 0.3));
    }

    /** Rendu via EffectComposer (remplace renderer.render()). */
    render() {
        this.composer.render();
    }

    /** Adapter la résolution au redimensionnement. */
    resize(width, height) {
        this.composer.setSize(width, height);
        if (this._bloomPass) {
            this._bloomPass.resolution.set(width, height);
        }
    }
}
