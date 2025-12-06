#!/bin/bash
# Script d'installation pour Transcribe

set -e

echo "=== Installation de Transcribe ==="
echo ""

# Vérifier macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Erreur: Ce script est pour macOS uniquement"
    exit 1
fi

# Vérifier Homebrew
if ! command -v brew &>/dev/null; then
    echo "Erreur: Homebrew requis. Installez-le depuis https://brew.sh"
    exit 1
fi

# Installer BlackHole
echo "[1/4] Installation de BlackHole (driver audio virtuel)..."
if ! brew list blackhole-2ch &>/dev/null; then
    brew install blackhole-2ch
    echo "      BlackHole installé"
else
    echo "      BlackHole déjà installé"
fi

# Installer FFmpeg
echo "[2/4] Installation de FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    brew install ffmpeg
    echo "      FFmpeg installé"
else
    echo "      FFmpeg déjà installé"
fi

# Installer PortAudio
echo "[3/4] Installation de PortAudio..."
if ! brew list portaudio &>/dev/null; then
    brew install portaudio
    echo "      PortAudio installé"
else
    echo "      PortAudio déjà installé"
fi

# Créer environnement virtuel et installer deps Python
echo "[4/4] Configuration de l'environnement Python..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
echo "      Dépendances Python installées"

echo ""
echo "=== Installation terminée ==="
echo ""
echo "IMPORTANT: Configurez BlackHole manuellement :"
echo ""
echo "  1. Ouvrir 'Configuration audio et MIDI' (chercher dans Spotlight)"
echo "  2. Cliquer sur '+' en bas à gauche → 'Créer un appareil à sorties multiples'"
echo "  3. Cocher : 'BlackHole 2ch' ET 'Haut-parleurs intégrés' (ou votre casque)"
echo "  4. Clic droit sur cet appareil → 'Utiliser cet appareil pour la sortie audio'"
echo ""
echo "Pour démarrer :"
echo "  source venv/bin/activate"
echo "  transcribe start"
echo ""
