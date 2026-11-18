# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Copia nocturna por Telegram.

La lanza cada noche el temporizador de systemd (deploy/cestaola-copia.timer):
    python -m cestaola.nocturna            # solo si hay cambios desde la última copia enviada
    python -m cestaola.nocturna --forzar   # siempre
"""
import sys
from datetime import datetime

from . import copias
from . import db as D
from . import telegram


def enviar_copia(data_dir, forzar=False):
    """Manda el .zip a los chats de Telegram. Devuelve (enviado, mensajes)."""
    aj = D.ajustes()
    if not aj["telegram_token"] or not telegram.chats_de(aj["telegram_chats"]):
        return False, ["Falta el token del bot o algún chat."]
    if not forzar and aj.get("telegram_copia") != "1":
        return False, ["La copia nocturna está desactivada en Ajustes."]
    h = copias.huella(data_dir)
    if not forzar and h == aj.get("telegram_copia_hash"):
        return False, ["Sin cambios desde la última copia: no se envía."]
    zip_ = copias.exportar(data_dir)
    n, p = copias.resumen(data_dir)
    ahora = datetime.now()
    texto = (f"💾 <b>Copia de {aj['titulo']}</b>\n{ahora.strftime('%d/%m/%Y %H:%M')} · {n} reservas · "
             f"{p} papeletas en la bolsa\nPara restaurarla: Ajustes → Copia de seguridad → Importar.")
    if len(zip_) > 49 * 1024 * 1024:
        return False, ["La copia pasa de 50 MB, el máximo de Telegram para bots. Descárgala desde el panel."]
    res = telegram.enviar_documento(aj["telegram_token"], aj["telegram_chats"], zip_,
                                    f"cestaola-copia-{ahora.strftime('%Y%m%d-%H%M')}.zip", texto)
    ok = any(r[1] for r in res)
    if ok:
        D.guardar_ajuste("telegram_copia_hash", h)
        D.get_db().commit()
    return ok, [f"Chat {c}: " + ("copia enviada ✓" if o else f"error: {d}") for c, o, d in res]


def main():
    from . import create_app
    app = create_app()
    with app.app_context():
        ok, msgs = enviar_copia(app.config["DATA_DIR"], forzar="--forzar" in sys.argv)
    for m in msgs:
        print(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
