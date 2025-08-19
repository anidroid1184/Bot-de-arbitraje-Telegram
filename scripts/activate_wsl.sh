#!/usr/bin/env bash
set -euo pipefail

# Este script prepara y activa el entorno virtual en WSL
# Uso recomendado desde WSL:
#   source Bot-de-arbitraje-Telegram/scripts/activate_wsl.sh
# o si ya estás en la carpeta del proyecto:
#   source ./scripts/activate_wsl.sh

# Detectar la carpeta raíz del proyecto (dos niveles arriba de este script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJ_ROOT"

echo "[INFO] Proyecto: $PROJ_ROOT"

# Crear venv si no existe
if [[ ! -d .venv ]]; then
  echo "[INFO] Creando entorno virtual (.venv)"
  python3 -m venv .venv
fi

# Activar venv en el shell actual
# Nota: este script debe ejecutarse con 'source' para que la activación persista
# en tu sesión. Si lo ejecutas como './activate_wsl.sh', se activará en un subshell
# y se perderá al terminar el script.
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[INFO] Python: $(python --version)"
echo "[INFO] Pip:    $(pip --version)"

# Instalar dependencias si existe requirements.txt
if [[ -f requirements.txt ]]; then
  echo "[INFO] Instalando dependencias de requirements.txt (si faltan)"
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
else
  echo "[WARN] No se encontró requirements.txt; omitiendo instalación"
fi

echo "[OK] Entorno virtual activado. Estás en: $PROJ_ROOT"
echo "[TIP] Para desactivar: 'deactivate'"
