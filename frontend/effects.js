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

        // Bloom subtil mais profond
        const bloom = new UnrealBloomPass(size, 1.0, 0.4, 0.15);
        bloom.threshold = 0.2; 
        bloom.strength = 1.0;
        bloom.radius = 0.8;
        this.composer.addPass(bloom);
        this._bloomPass = bloom;

        this.composer.addPass(new OutputPass());
    }

    // ── Éclairage cinématique ────────────────────────────────────────────────────
    _setupLighting() {
        // Ambiante neutre très faible
        const ambient = new THREE.AmbientLight(0x101015, 0.4);
        this.scene.add(ambient);

        // Rim Light Violette #1 (Contre-jour gauche)
        const rim1 = new THREE.PointLight(0x7c3aed, 3.0, 10);
        rim1.position.set(-3, 2, -2);
        this.scene.add(rim1);
        this._rimLights.push(rim1);

        // Rim Light Cyan/Bleue #2 (Contre-jour droite - pour le contraste)
        const rim2 = new THREE.PointLight(0x0ea5e9, 2.0, 10);
        rim2.position.set(3, 3, -2);
        this.scene.add(rim2);
        this._rimLights.push(rim2);

        // Aura pulsante douce (Source de lumière venant du sol)
        this._auraLight = new THREE.PointLight(0x8b5cf6, 2.0, 5);
        this._auraLight.position.set(0, -0.5, 0.5);
        this.scene.add(this._auraLight);
    }

    // ── Particules Shadow Monarch (Stylisées et fluides) ────────────────────────
    _setupParticles() {
        const count = 300;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        const sizes = new Float32Array(count);
        
        this._particleData = [];

        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const radius = 0.3 + Math.random() * 1.5;
            const x = Math.cos(angle) * radius;
            const z = Math.sin(angle) * radius;
            const y = (Math.random() - 0.2) * 4.0;

            positions[i * 3] = x;
            positions[i * 3 + 1] = y;
            positions[i * 3 + 2] = z;

            // Dégradé violet à bleu profond
            const color = new THREE.Color().setHSL(0.75 + Math.random() * 0.1, 0.8, 0.5);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;

            sizes[i] = Math.random();
            
            this._particleData.push({
                speed: 0.2 + Math.random() * 0.5,
                phase: Math.random() * Math.PI * 2,
                radius: radius,
                angle: angle,
                initY: y
            });
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

        // Créer une texture de particule douce (glow)
        const canvas = document.createElement('canvas');
        canvas.width = 64; canvas.height = 64;
        const ctx = canvas.getContext('2d');
        const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
        grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
        grad.addColorStop(0.2, 'rgba(200, 150, 255, 0.8)');
        grad.addColorStop(0.5, 'rgba(100, 0, 255, 0.3)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 64, 64);
        const texture = new THREE.CanvasTexture(canvas);

        const material = new THREE.PointsMaterial({
            size: 0.12,
            map: texture,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            sizeAttenuation: true
        });

        this._particles = new THREE.Points(geometry, material);
        this.scene.add(this._particles);
    }

    // ── Brume au sol ─────────────────────────────────────────────────────────────
    _setupGroundFog() {
        this.scene.fog = new THREE.FogExp2(0x0a0520, 0.05);  // Brouillard sombre au sol
    }

    // ── Boucle mise à jour ───────────────────────────────────────────────────────
    update(delta, characterState) {
        this._particleTime += delta;

        // Animation particules
        if (this._particles) {
            const pos = this._particles.geometry.attributes.position;
            const count = pos.count;
            for (let i = 0; i < count; i++) {
                const data = this._particleData[i];
                
                // Mouvement ascendant cyclique
                let y = pos.getY(i) + delta * data.speed * 0.4;
                if (y > 3.0) y = -1.0;
                pos.setY(i, y);

                // Oscillation horizontale douce
                data.angle += delta * data.speed * 0.2;
                const orbitR = data.radius + Math.sin(this._particleTime * 0.5 + data.phase) * 0.1;
                pos.setX(i, Math.cos(data.angle) * orbitR);
                pos.setZ(i, Math.sin(data.angle) * orbitR);
            }
            pos.needsUpdate = true;

            // Opacité
            const targetOpacity = characterState === 'idle' ? 0.4 : 0.8;
            this._particles.material.opacity += (targetOpacity - this._particles.material.opacity) * delta;
        }

        // Pulsation aura
        if (this._auraLight) {
            const pulse = Math.sin(this._particleTime * 2.0) * 0.3 + 0.7;
            const boost = (characterState === 'speaking' || characterState === 'thinking') ? 2.5 : 0.8;
            this._auraLight.intensity = boost * pulse;
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

    /** Permet de changer la couleur de l'aura/thème selon l'émotion */
    setThemeColor(emotion) {
        let hex = '#6600cc'; // par défaut : violet
        
        switch(emotion) {
            case 'angry': hex = '#ff0033'; break;
            case 'calm': hex = '#00ccff'; break;
            case 'power': hex = '#cc00ff'; break;
            case 'thinking': hex = '#00ffcc'; break;
            case 'happy': hex = '#ffcc00'; break;
        }

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
