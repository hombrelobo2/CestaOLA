#!/usr/bin/env bash
# Instala o actualiza el temporizador de la copia nocturna por Telegram (03:00).
# Solo envía algo si está activado en Ajustes → Avisos por Telegram.
set -euo pipefail
install -m 644 /opt/cestaola/deploy/cestaola-copia.service /etc/systemd/system/cestaola-copia.service
install -m 644 /opt/cestaola/deploy/cestaola-copia.timer /etc/systemd/system/cestaola-copia.timer
systemctl daemon-reload
systemctl enable --now cestaola-copia.timer >/dev/null 2>&1
echo "   Copia nocturna: $(systemctl list-timers cestaola-copia.timer --no-legend 2>/dev/null | awk '{print $1, $2, $3}' || true)"
