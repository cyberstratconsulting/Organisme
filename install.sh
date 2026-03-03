#!/bin/bash
echo "================================================"
echo "  Installation - MCP Organismes de Formation"
echo "================================================"
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "ERREUR : Python 3 n'est pas installé."
    echo "Installez-le : sudo apt install python3 python3-pip (Linux)"
    echo "               ou brew install python3 (Mac)"
    exit 1
fi

echo "[1/2] Installation des dépendances..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERREUR : L'installation des dépendances a échoué."
    exit 1
fi

echo ""
echo "[2/2] Création du dossier de données..."
mkdir -p data

echo ""
echo "================================================"
echo "  Installation terminée !"
echo "================================================"
echo ""
echo "Pour utiliser ce serveur MCP avec Claude :"
echo ""
echo "  Voir le fichier LISEZMOI.md pour les instructions."
echo ""
