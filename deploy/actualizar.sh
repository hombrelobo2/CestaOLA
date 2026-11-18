#!/usr/bin/env bash
# Actualiza CestaOLA a la última versión de GitHub sin tocar los datos.
set -euo pipefail
cd /opt/cestaola
git pull --ff-only
# (las 5 primeras líneas no deben cambiar: este archivo se actualiza a sí mismo mientras se ejecuta)
.venv/bin/pip install -q -r requirements.txt
bash /opt/cestaola/deploy/instalar-servicios.sh
systemctl restart cestaola
echo "✅ Actualizado a la versión $(cat VERSION) ($(git log -1 --format='%h %s'))"
