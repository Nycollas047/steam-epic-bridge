#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==================================================="
echo "       Inicializando Steam Epic Bridge..."
echo "==================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python3 nao encontrado. Instale python3, python3-venv e python3-tk."
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "Criando ambiente virtual (.venv)..."
    python3 -m venv .venv
fi

echo "Verificando dependencias..."
.venv/bin/python -m pip install -r requirements.txt --quiet

echo "[OK] Iniciando a Interface Grafica..."
.venv/bin/python SteamEpicBridge.py gui &
exit 0
