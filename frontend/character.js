/**
 * character.js – Chargement et contrôle du personnage 3D Sung Jin Woo
 * State machine: IDLE → LISTENING → THINKING → SPEAKING → IDLE
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';

export const States = {
    IDLE: 'idle',
    LISTENING: 'listening',
    THINKING: 'thinking',
    SPEAKING: 'speaking',
};

export class Character {
    constructor(scene) {
        this.scene = scene;
        this.mixer = null;
        this.model = null;
        this.clips = {};        // { name: AnimationAction }
        this.current = null;
        this.state = States.IDLE;
        this.morphTargets = null;  // référence aux mesh avec morph targets (bouche)
        this._clock = new THREE.Clock();
        
        // Procedural
        this._breathTime = 0;
        this._idleSwayTime = 0;
        this._gestureTimer = 0;
        this._nextGestureTime = 5 + Math.random() * 10;
        this._headBone = null;
        this.targetScale = 1.0;

        // Poursuite du regard (LookAt)
        this.bones = { neck: null, head: null, spine: null };
        this._targetLook = new THREE.Vector2(0, 0);
        this._currentLook = new THREE.Vector2(0, 0);
    }

    /**
     * Charge le modèle GLB principal + animations FBX Mixamo.
     * Si aucun modèle n'est trouvé, crée un placeholder géométrique.
     */
    async load(modelPath = 'assets/models/sung_jin_woo.glb') {
        const gltfLoader = new GLTFLoader();
        const fbxLoader = new FBXLoader();

        try {
            let loadedObject;
            if (modelPath.endsWith('.glb')) {
                const gltf = await gltfLoader.loadAsync(modelPath);
                loadedObject = gltf.scene;
                // Check if it's rigged. If no SkinnedMesh, we might want to try fallback.
                let hasBones = false;
                loadedObject.traverse(n => { if (n.isSkinnedMesh) hasBones = true; });
                
                if (!hasBones && modelPath === 'assets/models/sung_jin_woo.glb') {
                    console.warn('[Character] GLB lacks bones, trying FBX fallback...');
                    throw new Error('No bones');
                }
            } else {
                loadedObject = await fbxLoader.loadAsync(modelPath);
            }

            this.model = loadedObject;
            this.model.name = "SungJinWoo";

            // Configuration du modèle
            this.model.traverse(node => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = false;

                    if (node.material) {
                        node.material.envMapIntensity = 1.2;
                        node.material.needsUpdate = true;
                    }

                    if (node.morphTargetDictionary && Object.keys(node.morphTargetDictionary).length > 0) {
                        if (!this.morphTargets) this.morphTargets = [];
                        this.morphTargets.push(node);
                    }
                }
            });

            // Positionnement & Échelle
            const box = new THREE.Box3().setFromObject(this.model);
            const size = box.getSize(new THREE.Vector3());
            const targetHeight = 1.8;
            this.targetScale = targetHeight / (size.y || 1);
            this.model.scale.setScalar(this.targetScale);
            
            const newBox = new THREE.Box3().setFromObject(this.model);
            this.model.position.y -= newBox.min.y;
            this.model.position.x -= (newBox.max.x + newBox.min.x) / 2;
            this.model.position.z -= (newBox.max.z + newBox.min.z) / 2;

            // Correction orientation (Mixamo FBX are often rotated)
            if (modelPath.endsWith('.fbx')) {
                // Mixamo often needs y=0 rotation but check if it's sideways
                this.model.rotation.y = 0; 
            }

            this.scene.add(this.model);
            
            // Ground for shadows
            this._addGround();

            // Mixer
            this.mixer = new THREE.AnimationMixer(this.model);

            // Mixer update loop test: expose to window for debug
            window.character = this;

            // Load animations
            this._loadMixamoAnimations();
            this._findBones();

            console.log('[Character] Modèle chargé avec succès ✓');

        } catch (err) {
            console.error('[Character] Échec chargement modèle principal:', err);
            // Fallback to the suggested FBX if we failed GLB
            if (modelPath.endsWith('.glb')) {
                console.log('[Character] Tentative de secours avec FBX...');
                return this.load('assets/animations/standing_idle.fbx');
            }
            this._createPlaceholder();
        }
    }

    _addGround() {
        if (this.scene.getObjectByName('ground-shadow')) return;
        const planeGeom = new THREE.PlaneGeometry(10, 10);
        const planeMat = new THREE.ShadowMaterial({ opacity: 0.3 });
        const ground = new THREE.Mesh(planeGeom, planeMat);
        ground.name = 'ground-shadow';
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = 0;
        ground.receiveShadow = true;
        this.scene.add(ground);
    }

    /**
     * Charge les animations Mixamo FBX depuis /assets/animations/
     */
    async _loadMixamoAnimations() {
        const animations = [
            { name: 'idle', file: 'standing_idle.fbx' },
            { name: 'breathing', file: 'standing_idle.fbx' }, // Fallback to standing_idle
            { name: 'talking', file: 'talking.fbx' },
            { name: 'thinking', file: 'thinking.fbx' },
            { name: 'nodding', file: 'nodding.fbx' },
            { name: 'gesture1', file: 'talking.fbx' },      // Fallback to talking
            { name: 'listening', file: 'standing_idle.fbx' }, // Fallback to idle
        ];

        const fbxLoader = new FBXLoader();

        // Pour chaque animation, on essaie de charger le fichier
        await Promise.all(animations.map(async ({ name, file }) => {
            try {
                const fbx = await fbxLoader.loadAsync(`assets/animations/${file}`);
                if (fbx.animations?.length > 0) {
                    const clip = fbx.animations[0];
                    clip.name = name;
                    
                    // RETARGETING: On nettoie les noms des tracks (ex: MixamoRig:Hips -> Hips)
                    // car notre modèle exporté peut avoir des noms différents des FBX Mixamo originaux.
                    clip.tracks.forEach(track => {
                        track.name = track.name.replace(/mixamorig[0-9]* ?: ?/gi, '');
                        track.name = track.name.replace(/[0-9a-z_]*:([a-z_])/gi, '$1'); // Plus générique
                    });

                    const action = this.mixer.clipAction(clip);
                    this.clips[name] = action;
                    console.log(`[Character] Animation '${name}' bindée et corrigée ✓`);
                    
                    if (name === 'idle' && !this.current) {
                        this._playClip('idle', true);
                    }
                }
            } catch (err) {
                console.warn(`[Character] Animation '${name}' ignorer/échec:`, err.message);
            }
        }));
    }

    /**
     * Placeholder géométrique stylisé quand le GL est absent.
     */
    _createPlaceholder() {
        const group = new THREE.Group();

        const mat = new THREE.MeshStandardMaterial({
            color: 0x1a0a3a,
            emissive: 0x3d1a7a,
            emissiveIntensity: 0.4,
            metalness: 0.8,
            roughness: 0.3,
        });

        // Corps stylisé
        const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 0.9, 8, 16), mat);
        const head = new THREE.Mesh(new THREE.SphereGeometry(0.18, 16, 16), mat);
        const lArm = new THREE.Mesh(new THREE.CapsuleGeometry(0.07, 0.55, 6, 8), mat);
        const rArm = new THREE.Mesh(new THREE.CapsuleGeometry(0.07, 0.55, 6, 8), mat);

        body.position.y = 0;
        head.position.y = 0.75;
        lArm.position.set(-0.42, 0.1, 0);
        rArm.position.set(0.42, 0.1, 0);
        lArm.rotation.z = 0.3;
        rArm.rotation.z = -0.3;

        // Yeux lumineux violets
        const eyeMat = new THREE.MeshStandardMaterial({ emissive: 0x9333ea, emissiveIntensity: 3 });
        const eyeL = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 8), eyeMat);
        const eyeR = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 8), eyeMat);
        eyeL.position.set(-0.06, 0.76, 0.16);
        eyeR.position.set(0.06, 0.76, 0.16);

        group.add(body, head, lArm, rArm, eyeL, eyeR);
        group.position.y = -0.5;

        this.model = group;
        this.scene.add(this.model);
        this.mixer = null;
        this._placeholderEyes = [eyeL, eyeR];
        this._headBone = head; // Simuler un os pour le placeholder
        console.log('[Character] Placeholder créé ✓');
    }

    /** Effet 'Arise' - Apparition avec mise à l'échelle */
    arise() {
        if (!this.model) return;
        console.log('[Character] Shadow Monarch Arise!');
        const initialS = 0.01;
        this.model.scale.setScalar(initialS);
        let s = initialS;
        const animateScale = () => {
            s += (this.targetScale / 50); // Plus fluide
            if (s >= this.targetScale) {
                s = this.targetScale;
                this.model.scale.setScalar(s);
                this.setState(States.IDLE);
                console.log('[Character] Personnage prêt ✓');
                return;
            }
            this.model.scale.setScalar(s);
            requestAnimationFrame(animateScale);
        };
        requestAnimationFrame(animateScale);
    }

    /** Joue un clip par nom avec cross-fade. */
    _playClip(name, loop = true) {
        const next = this.clips[name];
        if (!next || next === this.current) return;

        if (this.current) {
            next.reset().setEffectiveWeight(1).play();
            this.current.crossFadeTo(next, 0.4, true);
        } else {
            next.reset().play();
        }
        next.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce);
        next.clampWhenFinished = !loop;
        this.current = next;
    }

    /** Change l'état du personnage et joue l'animation correspondante. */
    setState(newState) {
        if (this.state === newState) return;
        const oldState = this.state;
        this.state = newState;

        console.log(`[Character] State Transition: ${oldState} -> ${newState}`);

        switch (newState) {
            case States.IDLE:
                this._playClip('breathing') || this._playClip('idle');
                this._gestureTimer = 0;
                this._nextGestureTime = 7 + Math.random() * 15;
                break;
            case States.LISTENING:
                this._playClip('listening', true, 0.2) || this._playClip('idle');
                break;
            case States.THINKING:
                this._playClip('thinking', true, 1.0) || this._playClip('idle');
                break;
            case States.SPEAKING:
                // Choisir un clip de parole aléatoire si dispo
                const talkClips = ['talking', 'gesture1'].filter(n => this.clips[n]);
                const clip = talkClips[Math.floor(Math.random() * talkClips.length)] || 'idle';
                this._playClip(clip, true, 0.3);
                break;
        }
    }


    /**
     * Applique un visème (0-20) comme morph target.
     * Interpolation douce vers le poids cible.
     */
    applyViseme(visemeId, weight, delta) {
        if (!this.morphTargets) return;

        // Map visème ID → nom de morph target (nommage commun Mixamo/Ready Player Me)
        const visemeNames = [
            'viseme_sil', 'viseme_PP', 'viseme_FF', 'viseme_TH', 'viseme_DD',
            'viseme_kk', 'viseme_CH', 'viseme_SS', 'viseme_nn', 'viseme_RR',
            'viseme_aa', 'viseme_E', 'viseme_I', 'viseme_O', 'viseme_U',
        ];

        const targetName = visemeNames[visemeId % visemeNames.length];

        this.morphTargets.forEach(mesh => {
            const dict = mesh.morphTargetDictionary;
            if (!dict) return;

            // Trouver l'index du visème (essaie le nom exact, puis pattern partiel)
            let idx = dict[targetName] ?? -1;
            if (idx === -1) {
                const key = Object.keys(dict).find(k => k.toLowerCase().includes(targetName.toLowerCase().replace('viseme_', '')));
                if (key) idx = dict[key];
            }
            if (idx === -1) return;

            const current = mesh.morphTargetInfluences[idx];
            // Interpolation exponentielle pour fluidité
            mesh.morphTargetInfluences[idx] = current + (weight - current) * Math.min(1, delta * 12);
        });
    }

    /** Réinitialise tous les morph targets (bouche fermée). */
    resetMorphTargets() {
        if (!this.morphTargets) return;
        this.morphTargets.forEach(mesh => {
            if (mesh.morphTargetInfluences) {
                for (let i = 0; i < mesh.morphTargetInfluences.length; i++) {
                    mesh.morphTargetInfluences[i] *= 0.8; // fondu progressif
                }
            }
        });
    }

    /** Boucle de mise à jour principale. */
    update(delta) {
        if (this.mixer) this.mixer.update(delta);
        this._updateLookAt(delta);
        this._updateProcedural(delta);
    }

    /** Oriente la tête et le cou vers une cible (ex: souris) */
    lookAt(targetX, targetY) {
        // Coordonnées normalisées -1 à 1
        this._targetLook.x = targetX;
        this._targetLook.y = targetY;
    }

    _updateLookAt(delta) {
        const neck = this.bones.neck || this._headBone; // Fallback sur l'ancien nom si besoin
        if (!neck) return;

        // Vitesse de suivi
        const lerpFactor = delta * 5;
        this._currentLook.x += (this._targetLook.x - this._currentLook.x) * lerpFactor;
        this._currentLook.y += (this._targetLook.y - this._currentLook.y) * lerpFactor;

        // Limites de rotation
        const limitX = 0.6;
        const limitY = 0.4;

        neck.rotation.y = THREE.MathUtils.lerp(neck.rotation.y, -this._currentLook.x * limitX, 0.1);
        neck.rotation.x = THREE.MathUtils.lerp(neck.rotation.x, -this._currentLook.y * limitY, 0.1);
    }

    _findBones() {
        if (!this.model) return;
        this.model.traverse(node => {
            if (node.isBone) {
                const name = node.name.toLowerCase();
                if (name.includes('neck')) this.bones.neck = node;
                if (name.includes('head')) this.bones.head = node;
                if (name.includes('spine')) this.bones.spine = node;
            }
        });
        // Si on a trouvé des os, on assigne à _headBone pour la compatibilité procedural
        this._headBone = this.bones.head || this.bones.neck;
    }

    /** Animations procédurales (respiration, balancement de tête). */
    _updateProcedural(delta) {
        this._breathTime += delta * 0.6;
        this._idleSwayTime += delta * 0.3;

        // Gestes aléatoires en IDLE pour donner vie
        if (this.state === States.IDLE && this.mixer) {
            this._gestureTimer += delta;
            if (this._gestureTimer > this._nextGestureTime) {
                const idleGestures = ['nodding', 'gesture1'].filter(n => this.clips[n]);
                if (idleGestures.length > 0) {
                    const g = idleGestures[Math.floor(Math.random() * idleGestures.length)];
                    const action = this.clips[g];
                    if (action) {
                        console.log(`[Character] Gesturing: ${g}`);
                        action.reset().setLoop(THREE.LoopOnce).fadeIn(0.5).play();
                        // On ne change pas l'état, on joue juste l'animation par dessus (additive/override)
                    }
                }
                this._gestureTimer = 0;
                this._nextGestureTime = 12 + Math.random() * 20;
            }
        }

        // Respiration et flottement (bobbing)
        if (this.model) {
            const breathScale = 1.0 + Math.sin(this._breathTime) * 0.008;
            
            if (this.state === States.IDLE) {
                this.model.scale.set(this.targetScale, this.targetScale * breathScale, this.targetScale);
            }
            
            // Appliquer le flottement vertical (vibration ombre)
            this.model.position.y += Math.sin(this._breathTime) * 0.0004; 
        }

        // Léger balancement tête
        if (this._headBone && this.state !== States.SPEAKING) {
            this._headBone.rotation.x = Math.sin(this._idleSwayTime * 0.7) * 0.015;
            this._headBone.rotation.z = Math.sin(this._idleSwayTime * 0.5) * 0.012;
        }

        // Animation placeholder (yeux pulsants)
        if (this._placeholderEyes) {
            const pulse = (Math.sin(Date.now() * 0.003) + 1) * 0.5;
            this._placeholderEyes.forEach(eye => {
                eye.material.emissiveIntensity = 2 + pulse * 2;
            });
        }
    }
}
