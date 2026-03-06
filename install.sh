#!/bin/bash

# Assistant Virtuel Sung Jin Woo - One-Line Installer
# Style: Solo Leveling System Quest

echo -e "\e[1;36m[SYSTEM] Initialisation de la Quête d'Installation...\e[0m"

# 1. Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo -e "\e[1;31m[ERREUR] Python 3 n'est pas installé.\e[0m"
    exit 1
fi

# 2. Créer l'environnement
echo -e "\e[1;34m[SYSTEM] Création de l'Espace de Mana (Virtual Env)...\e[0m"
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer les dépendances minimales pour le Setup
echo -e "\e[1;34m[SYSTEM] Absorption des capacités (Pip install)...\e[0m"
pip install pywebview requests python-dotenv &> /dev/null

# 4. Lancer le Wizard HUD
echo -e "\e[1;35m[SYSTEM] Ouverture du portail...\e[0m"
python3 setup.py
