#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('\x1b[36m%s\x1b[0m', '🕴️ [SYSTEM] Initialisation de la Quête d\'Éveil...');

const targetDir = path.join(process.cwd(), 'sung-assistant');

// 1. Cloner le repo si on n'est pas déjà dedans
if (!fs.existsSync(path.join(process.cwd(), 'setup.py'))) {
    console.log('\x1b[34m%s\x1b[0m', '> Téléchargement des archives du Monarque (Git clone)...');
    try {
        execSync(`git clone https://github.com/ranker-002/sung-jin-woo-3d-assistant.git ${targetDir}`, { stdio: 'inherit' });
        process.chdir(targetDir);
    } catch (err) {
        console.error('\x1b[31m%s\x1b[0m', '[ERREUR] Git n\'est pas installé ou impossible de cloner.');
        process.exit(1);
    }
}

// 2. Vérifier Python
try {
    execSync('python3 --version', { stdio: 'ignore' });
} catch (err) {
    console.error('\x1b[31m%s\x1b[0m', '[ERREUR] Python 3 est requis pour faire tourner le système.');
    process.exit(1);
}

// 3. Préparer l'environnement
console.log('\x1b[35m%s\x1b[0m', '> Préparation de l\'espace de mana (Environnement Python)...');
try {
    if (!fs.existsSync('.venv')) {
        execSync('python3 -m venv .venv', { stdio: 'inherit' });
    }

    // Installer les outils de base pour le wizard
    const pip = process.platform === 'win32' ? 'venv\\Scripts\\pip' : '.venv/bin/pip';
    const python = process.platform === 'win32' ? 'venv\\Scripts\\python' : '.venv/bin/python';

    console.log('\x1b[34m%s\x1b[0m', '> Installation du Wizard HUD...');
    execSync(`${pip} install pywebview requests python-dotenv`, { stdio: 'inherit' });

    // 4. Lancer le setup.py (Le Wizard HUD)
    console.log('\x1b[32m%s\x1b[0m', '> Ouverture du Portail HUD !');
    execSync(`${python} setup.py`, { stdio: 'inherit' });

} catch (err) {
    console.error('\x1b[31m%s\x1b[0m', '[ERREUR] Échec du processus d\'installation.');
    process.exit(1);
}
