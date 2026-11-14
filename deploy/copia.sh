#!/usr/bin/env bash
# Copia de seguridad de la base de datos y las fotos en /root/cestaola-AAAAMMDD-HHMM.tar.gz
set -euo pipefail
F=/root/cestaola-$(date +%Y%m%d-%H%M).tar.gz
/opt/cestaola/.venv/bin/python - <<'EOF'
import sqlite3
src = sqlite3.connect("/var/lib/cestaola/cestaola.db")
dst = sqlite3.connect("/var/lib/cestaola/copia.db")
src.backup(dst); dst.close(); src.close()
EOF
tar -czf "$F" -C /var/lib/cestaola copia.db fotos
rm -f /var/lib/cestaola/copia.db
echo "✅ Copia guardada en $F"
