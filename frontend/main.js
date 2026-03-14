/**
 * main.js – Orchestrateur principal Three.js
 * Assemble: scène 3D + personnage + VFX + lip-sync + WebSocket + UI
 */
import * as THREE from 'three';
import { Character, States } from './character.js';
import { LipSyncController, AudioLipSync } from './lipsync.js';
import { VFXManager } from './effects.js';
import { UIManager } from './ui.js';
import { sfx } from './sound.js';

// ─── Configuration ────────────────────────────────────────────────────────────
const WS_URL = 'ws://localhost:8765/ws';
const WS_RETRY_DELAY = 3000;

// ─── État global ──────────────────────────────────────────────────────────────
let scene, camera, renderer, clock;
let character, vfx, lipSync, audioLipSync, ui;
let ws = null;
let audioCtx = null;
let currentAudioSource = null;

// ─── État Balade sur le bureau ────────────────────────────────────────────────
let isWandering = false;
let wanderX = 50, wanderY = 100;
let wanderSpeedX = 2;

// ─── Initialisation de la scène Three.js ─────────────────────────────────────
function initScene() {
    scene = new THREE.Scene();
    scene.background = null; // Transparent !

    // Camera légèrement en dessous du niveau des yeux pour vue cinématique
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 0.4, 3.5);
    camera.lookAt(0, 0.4, 0);

    // Axes helper pour le debug
    const axes = new THREE.AxesHelper(3);
    scene.add(axes);

    renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,        // Fond transparent
        premultipliedAlpha: false,
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.setClearColor(0x000000, 0); // Transparent

    document.getElementById('canvas-container').appendChild(renderer.domElement);
    clock = new THREE.Clock();

    // Redimensionnement
    window.addEventListener('resize', onResize);

    // Suivi de la souris
    window.addEventListener('mousemove', onMouseMove);
}

function onMouseMove(e) {
    if (!character) return;
    // Normaliser les coordonnées (-1 à 1)
    const x = (e.clientX / window.innerWidth) * 2 - 1;
    const y = (e.clientY / window.innerHeight) * 2 - 1;
    character.lookAt(x, y);
}

function onResize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    vfx?.resize(w, h);
}

// ─── Boucle de rendu ─────────────────────────────────────────────────────────
function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();

    character?.update(delta);
    lipSync?.update(delta);

    if (audioLipSync && currentAudioSource) {
        audioLipSync.update(delta);
    } else {
        character?.resetMorphTargets?.();
    }

    vfx?.update(delta, character?.state ?? 'idle');
    vfx?.render() ?? renderer.render(scene, camera);
}

// ─── WebSocket – connexion et gestion messages ────────────────────────────────
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.addEventListener('open', () => {
        console.log('[WS] Connecté au serveur ✓');
    });

    ws.addEventListener('message', ({ data }) => {
        let msg;
        try { msg = JSON.parse(data); } catch { return; }
        handleServerMessage(msg);
    });

    ws.addEventListener('close', () => {
        console.warn('[WS] Déconnecté. Reconnexion dans', WS_RETRY_DELAY, 'ms...');
        setTimeout(connectWebSocket, WS_RETRY_DELAY);
    });

    ws.addEventListener('error', (e) => {
        console.error('[WS] Erreur:', e);
    });
}

function sendToServer(type, payload = {}) {
    if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type, ...payload }));
    }
}

// ─── Traitement des messages serveur ─────────────────────────────────────────
function handleServerMessage(msg) {
    switch (msg.type) {
        case 'status':
            handleStatus(msg.state, msg.text);
            break;

        case 'speech':
            ui?.setStatus('speaking');
            character?.setState(States.SPEAKING);
            vfx?.setThemeColor(msg.emotion || 'neutral');
            if (msg.xp !== undefined) updateDungeonStats(msg.level, msg.xp);
            handleSpeech(msg);
            break;

        case 'config':
            handleConfig(msg);
            break;

        case 'stats_sync':
            updateDungeonStats(msg.level, msg.xp);
            break;

        case 'error':
            console.error('[Server] Erreur:', msg.message);
            character?.setState(States.IDLE);
            ui?.setStatus('idle');
            break;

        case 'pong':
            break;
    }
}

function handleConfig({ emotion, scale }) {
    if (emotion) vfx?.setThemeColor(emotion);
    if (scale && character?.model) {
        character.model.scale.setScalar(scale);
    }
}

/** Update Level & XP Bar */
function updateDungeonStats(level, xp) {
    const lvlEl = document.getElementById('lvl-val');
    const xpFill = document.getElementById('xp-fill');
    if (lvlEl) lvlEl.textContent = `LVL ${level}`;
    if (xpFill) {
        const progress = xp % 100; // Simplifié: 100 XP par niveau
        xpFill.style.width = `${progress}%`;
    }
}

/** Drag & Drop Handling */
function setupFileDrop() {
    const overlay = document.getElementById('drop-overlay');
    
    window.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (overlay) overlay.style.display = 'flex';
    });
    
    window.addEventListener('dragleave', (e) => {
        if (overlay) overlay.style.display = 'none';
    });
    
    window.addEventListener('drop', (e) => {
        e.preventDefault();
        if (overlay) overlay.style.display = 'none';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const fileName = files[0].name;
            const fileSize = (files[0].size / 1024).toFixed(1);
            
            // On envoie une requête spéciale d'analyse d'objet
            sendToServer('user_input', { 
                text: `[OBJET DÉPOSÉ] Analyse ce fichier : "${fileName}" (${fileSize} KB).` 
            });
            
            // Effet visuel
            vfx?.arise();
            sfx.play('arise', 0.5);
        }
    });
}

function handleStatus(state, text = '') {
    switch (state) {
        case 'idle':
            character?.setState(States.IDLE);
            ui?.setStatus('idle');
            break;
        case 'thinking':
            character?.setState(States.THINKING);
            ui?.setStatus('thinking');
            if (text) ui?.showSpeech?.('…', text);
            break;
        case 'speaking':
            character?.setState(States.SPEAKING);
            ui?.setStatus('speaking');
            break;
        case 'listening':
            character?.setState(States.LISTENING);
            ui?.setStatus('listening');
            break;
    }
}

async function handleSpeech({ text, audio, duration_ms, visemes, emotion }) {
    // Afficher le texte dans la bulle
    ui?.showSpeech(text);
    
    // Gérer l'émotion
    if (emotion) {
        let hexColor = '#6600cc'; // Default: neutral/power
        
        switch (emotion) {
            case 'angry':
                hexColor = '#ff1122'; // Rouge sang
                if (character) character._playClip('gesture1', false) || character._playClip('talking');
                break;
            case 'calm':
                hexColor = '#11aaff'; // Bleu glacial
                if (character) character._playClip('breathing', false);
                break;
            case 'power':
                hexColor = '#b829ff'; // Violet intense
                vfx?.arise(); // Déclencher l'effet arise !
                break;
        }
        
        vfx?.setThemeColor(hexColor);
    }

    // Lancer le lip-sync basé sur les visèmes du serveur
    if (visemes?.length > 0) {
        lipSync?.play(visemes);
    }

    // Lire l'audio
    if (audio) {
        await playAudio(audio, duration_ms);
    }
}

// ─── Lecture audio avec Web Audio API ────────────────────────────────────────
async function playAudio(base64Audio, durationMs) {
    try {
        // Initialiser le contexte audio si besoin (doit être déclenché par interaction)
        if (!audioCtx) {
            audioCtx = new AudioContext();
        }
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }

        // Décoder les données audio base64
        const binaryStr = atob(base64Audio);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);

        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);

        // Stopper l'audio précédent
        currentAudioSource?.stop();
        lipSync?.stop();

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);

        // Lip-sync amplitude en temps réel (fallback si pas de visèmes précis)
        if (!lipSync?.isPlaying) {
            audioLipSync?.attachToSource(source, audioCtx);
        }

        currentAudioSource = source;
        source.start(0);

        source.onended = () => {
            currentAudioSource = null;
            audioLipSync?.stop();
            character?.setState(States.IDLE);
            ui?.setStatus('idle');
        };

    } catch (err) {
        console.error('[Audio] Erreur lecture:', err);
        character?.setState(States.IDLE);
        ui?.setStatus('idle');
    }
}

// ─── Animation Déplacement sur le Bureau (Wander) ─────────────────────────────
function toggleWander() {
    isWandering = !isWandering;
    const btn = document.getElementById('wander-btn');
    if (isWandering) {
        btn?.classList.add('active');
        wanderX = window.screenX || 50;
        wanderY = window.screenY || 100;
        wanderSpeedX = 1.5; // Vitesse de marche
        
        if (character) character._playClip('breathing', true); // Peut être remplacé par 'walking'
        sfx.play('ghost_whoosh', 0.4);
        wanderLoop();
    } else {
        btn?.classList.remove('active');
        sfx.play('click', 0.3);
        if (character) character.setState(States.IDLE);
    }
}

function wanderLoop() {
    if (!isWandering) return;
    
    wanderX += wanderSpeedX;
    
    const screenW = window.screen.availWidth || 1920;
    const winW = 400; // largeur de la fenêtre PyWebView
    
    if (wanderX <= 0) {
        wanderX = 0;
        wanderSpeedX *= -1;
        if(character && character.model) character.model.rotation.y = Math.PI; // Se retourne
    } else if (wanderX + winW >= screenW) {
        wanderX = screenW - winW;
        wanderSpeedX *= -1;
        if(character && character.model) character.model.rotation.y = 0; // Regarde devant
    }
    
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.move_window(wanderX, wanderY);
    }
    
    requestAnimationFrame(wanderLoop);
}

// ─── Point d'entrée principal ─────────────────────────────────────────────────
async function main() {
    initScene();

    // VFX (must be after renderer init)
    vfx = new VFXManager(renderer, scene, camera);

    // Personnage
    // Character
    character = new Character(scene);
    
    // UI
    ui = new UIManager((userText) => {
        sendToServer('user_input', { text: userText });
        // État de réflexion immédiat
        ui?.setStatus('thinking');
        character?.setState(States.THINKING);
        vfx?.setThemeColor('thinking');
    });

    // Masquer le loader IMMÉDIATEMENT
    ui.hideLoader();

    // On n'attend pas toutes les animations pour afficher l'interface (lazy loading)
    // Droit de glisser des fichiers sur le Monarque
    setupFileDrop();
    
    // Reste de l'init...
    character.load('assets/models/sung_jin_woo.glb').then(() => {
         // Effet 'Arise' au démarrage once loaded
         character.arise();
         vfx?.arise();
         sfx.play('arise', 0.8);
    });


    // Lip-sync
    lipSync = new LipSyncController(character);
    audioLipSync = new AudioLipSync(character);

    // Connexion WebSocket
    connectWebSocket();

    // Démarrer la boucle de rendu
    animate();

    // Démarrer le contexte audio au premier clic
    document.addEventListener('click', () => {
        if (!audioCtx) audioCtx = new AudioContext();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        sfx.init(); // Init SFX system
    }, { once: true });

    // Exposer send pour PyWebView
    window.sendToServer = sendToServer;

    // Bouton de balade
    const wanderBtn = document.getElementById('wander-btn');
    if (wanderBtn) wanderBtn.addEventListener('click', toggleWander);

    // Initialisation du déplacement manuel avec la souris
    setupCustomDrag();

    console.log('[Main] Sung Jin Woo Assistant initialisé ✓');
}

// ─── Custom Window Dragging ───────────────────────────────────────────────────
function setupCustomDrag() {
    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    const dragElements = [
        document.getElementById('drag-handle'),
        document.getElementById('status-bar')
    ];

    dragElements.forEach(el => {
        if (!el) return;
        el.style.cursor = 'grab';
        
        el.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return; // clique gauche seulement
            isDragging = true;
            el.style.cursor = 'grabbing';
            // Offset from the top-left of the window
            offsetX = e.clientX;
            offsetY = e.clientY;
        });
    });

    window.addEventListener('mousemove', (e) => {
        if (isDragging && window.pywebview && window.pywebview.api) {
            // Screen position of the mouse minus the original offsets within the window
            const newX = e.screenX - offsetX;
            const newY = e.screenY - offsetY;
            
            // Override auto-wandering state if the user manually drags
            if (isWandering) {
                isWandering = false;
                document.getElementById('wander-btn')?.classList.remove('active');
                if (character) character.setState(States.IDLE);
            }
            
            window.pywebview.api.move_window(newX, newY);
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            dragElements.forEach(el => { if(el) el.style.cursor = 'grab'; });
            // Save last pos to wanderX/Y variables so it resumes from there later
            wanderX = window.screenX;
            wanderY = window.screenY;
        }
    });
}

main().catch(console.error);
