#!/usr/bin/env bash
# Instalación de CestaOLA en un LXC Debian 12/13 limpio (como root).
#
#   apt update && apt install -y git
#   git clone https://github.com/hombrelobo2/CestaOLA /opt/cestaola
#   bash /opt/cestaola/deploy/install.sh
set -euo pipefail
# Evita avisos de "Setting locale failed" (el cliente SSH envía un idioma que el LXC no tiene)
export LC_ALL=C.UTF-8 LANG=C.UTF-8 LANGUAGE=

APP=/opt/cestaola
DATA=/var/lib/cestaola
ENVF=/etc/cestaola/cestaola.env
PUERTO="${PUERTO:-8000}"

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta como root"; exit 1; }
[ -f "$APP/wsgi.py" ] || { echo "No encuentro $APP/wsgi.py. Clona el repo en $APP primero."; exit 1; }

echo "==> Paquetes del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip ca-certificates tzdata >/dev/null
ln -sf /usr/share/zoneinfo/Europe/Madrid /etc/localtime

echo "==> Usuario y carpetas"
id cestaola >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin cestaola
mkdir -p "$DATA/fotos" /etc/cestaola
chown -R cestaola:cestaola "$DATA"
chmod 750 "$DATA"

echo "==> Entorno Python"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

if [ ! -f "$ENVF" ]; then
  echo "==> Configuración ($ENVF)"
  CLAVE=$(python3 -c "import secrets;print(secrets.token_urlsafe(9))")
  cat > "$ENVF" <<EOF
# Contraseña del panel de organizadores (/admin)
CESTAOLA_ADMIN_PASSWORD=$CLAVE
# Clave interna para firmar sesiones (no la compartas)
CESTAOLA_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
# Dirección pública, para los enlaces personales. Ej: https://cesta.midominio.es
CESTAOLA_BASE_URL=
# 1 = solo cookies por HTTPS (déjalo en 1 cuando esté detrás del proxy con HTTPS).
# Pon 0 SOLO para probar por http://IP:$PUERTO en la red local.
CESTAOLA_COOKIE_SECURE=0
CESTAOLA_DATA=$DATA
EOF
  chmod 640 "$ENVF"; chown root:cestaola "$ENVF"
  NUEVA=1
fi

echo "==> Servicio systemd"
sed "s/__PUERTO__/$PUERTO/" "$APP/deploy/cestaola.service" > /etc/systemd/system/cestaola.service
systemctl daemon-reload
systemctl enable --now cestaola >/dev/null
systemctl restart cestaola
sleep 2

IP=$(hostname -I | awk '{print $1}')
if curl -fsS -o /dev/null "http://127.0.0.1:$PUERTO/" 2>/dev/null || python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$PUERTO/')" 2>/dev/null; then
  echo
  echo "  ✅ CestaOLA funcionando en  http://$IP:$PUERTO"
  echo "     Panel:                   http://$IP:$PUERTO/admin"
  [ "${NUEVA:-0}" = 1 ] && echo "     Contraseña de admin:     $CLAVE   (cámbiala en $ENVF)"
  echo
  echo "  Siguiente paso: publícala con HTTPS (ver README) y pon CESTAOLA_BASE_URL y CESTAOLA_COOKIE_SECURE=1"
else
  echo "  ⚠ El servicio no responde. Mira:  journalctl -u cestaola -n 50"
  exit 1
fi
