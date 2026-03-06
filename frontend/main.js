/**
 * main.js – Orchestrateur principal Three.js
 * Assemble: scène 3D + personnage + VFX + lip-sync + WebSocket + UI
 */
import * as THREE from 'three';
import { Character, States } from './character.js';
import { LipSyncController, AudioLipSync } from './lipsync.js';
import { VFXManager } from './effects.js';
import { UIManager } from './ui.js';

// ─── Configuration ────────────────────────────────────────────────────────────
const WS_URL = 'ws://localhost:8765/ws';
const WS_RETRY_DELAY = 3000;

// ─── État global ──────────────────────────────────────────────────────────────
let scene, camera, renderer, clock;
let character, vfx, lipSync, audioLipSync, ui;
let ws = null;
let audioCtx = null;
let currentAudioSource = null;

// ─── Initialisation de la scène Three.js ─────────────────────────────────────
function initScene() {
    scene = new THREE.Scene();
    scene.background = null; // Transparent !

    // Camera légèrement en dessous du niveau des yeux pour vue cinématique
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 0.2, 3.2);
    camera.lookAt(0, 0.5, 0);

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
            handleSpeech(msg);
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

async function handleSpeech({ text, audio, duration_ms, visemes }) {
    // Afficher le texte dans la bulle
    ui?.showSpeech(text);

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

// ─── Point d'entrée principal ─────────────────────────────────────────────────
async function main() {
    initScene();

    // VFX (must be after renderer init)
    vfx = new VFXManager(renderer, scene, camera);

    // Personnage
    character = new Character(scene);
    await character.load('assets/models/sung_jin_woo.glb');

    // Lip-sync
    lipSync = new LipSyncController(character);
    audioLipSync = new AudioLipSync(character);

    // UI
    ui = new UIManager((userText) => {
        sendToServer('user_input', { text: userText });
    });

    // Masquer le loader
    ui.hideLoader();

    // Connexion WebSocket
    connectWebSocket();

    // Démarrer la boucle de rendu
    animate();

    // Démarrer le contexte audio au premier clic
    document.addEventListener('click', () => {
        if (!audioCtx) audioCtx = new AudioContext();
        if (audioCtx.state === 'suspended') audioCtx.resume();
    }, { once: true });

    // Exposer send pour PyWebView
    window.sendToServer = sendToServer;

    console.log('[Main] Sung Jin Woo Assistant initialisé ✓');
}

main().catch(console.error);
