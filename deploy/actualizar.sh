#!/usr/bin/env bash
# Actualiza CestaOLA a la última versión de GitHub sin tocar los datos.
set -euo pipefail
cd /opt/cestaola
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl restart cestaola
echo "✅ Actualizado a $(git log -1 --format='%h %s')"
