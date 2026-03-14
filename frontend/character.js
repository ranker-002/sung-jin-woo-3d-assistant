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
        const loader = new GLTFLoader();

        try {
            const gltf = await loader.loadAsync(modelPath);
            this.model = gltf.scene;
            this.model.name = "SungJinWoo";

            // Configuration du modèle
            this.model.traverse(node => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = false;

                    // Amélioration matériaux
                    if (node.material) {
                        node.material.envMapIntensity = 1.2;
                        node.material.needsUpdate = true;
                    }

                    // Trouver les morph targets pour le lip sync
                    if (node.morphTargetDictionary && Object.keys(node.morphTargetDictionary).length > 0) {
                        if (!this.morphTargets) this.morphTargets = [];
                        this.morphTargets.push(node);
                    }
                }
            });

            // Centrer et positionner (pieds à 0,0,0)
            const box = new THREE.Box3().setFromObject(this.model);
            const size = box.getSize(new THREE.Vector3());
            
            // On veut qu'il fasse environ 1.8 - 2.0 unités de haut
            const targetHeight = 1.8;
            const scale = targetHeight / size.y;
            this.targetScale = scale;
            this.model.scale.setScalar(scale);
            
            // Repositionner pour que les pieds soient au sol (y=0) après scale
            const newBox = new THREE.Box3().setFromObject(this.model);
            const min = newBox.min;
            this.model.position.y -= min.y;
            this.model.position.x -= (newBox.max.x + newBox.min.x) / 2;
            this.model.position.z -= (newBox.max.z + newBox.min.z) / 2;

            this.scene.add(this.model);
            
            // Ombre au sol (plane transparent)
            const planeGeom = new THREE.PlaneGeometry(10, 10);
            const planeMat = new THREE.ShadowMaterial({ opacity: 0.3 });
            const ground = new THREE.Mesh(planeGeom, planeMat);
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = 0;
            ground.receiveShadow = true;
            this.scene.add(ground);


            // Mixer d'animations
            this.mixer = new THREE.AnimationMixer(this.model);

            // Charger animations intégrées GLTF
            if (gltf.animations?.length > 0) {
                gltf.animations.forEach(clip => {
                    this.clips[clip.name.toLowerCase()] = this.mixer.clipAction(clip);
                });
            }

            // Charger animations externes Mixamo (non-bloquant)
            this._loadMixamoAnimations();

            // Identifier les os pour le LookAt
            this._findBones();

            console.log('[Character] Modèle chargé avec succès ✓');

        } catch (err) {
            console.error('[Character] Échec chargement GLB:', err);
            this._createPlaceholder();
        }
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
        this.state = newState;

        switch (newState) {
            case States.IDLE:
                this._playClip('breathing') || this._playClip('idle');
                break;
            case States.LISTENING:
                this._playClip('listening') || this._playClip('idle');
                break;
            case States.THINKING:
                this._playClip('thinking') || this._playClip('idle');
                break;
            case States.SPEAKING:
                this._playClip('talking') || this._playClip('gesture1') || this._playClip('idle');
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

        // Respiration légère sur le scale Y
        if (this.model && this.state === States.IDLE) {
            const breathScale = 1.0 + Math.sin(this._breathTime) * 0.008;
            this.model.scale.y = breathScale;
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
