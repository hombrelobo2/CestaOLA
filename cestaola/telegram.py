# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Avisos por Telegram (sin dependencias: solo la biblioteca estándar)."""
import html
import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger("cestaola.telegram")
API = "https://api.telegram.org/bot{token}/{metodo}"


def _llamar(token, metodo, datos=None, timeout=8):
    url = API.format(token=token, metodo=metodo)
    cuerpo = urllib.parse.urlencode(datos or {}).encode()
    req = urllib.request.Request(url, data=cuerpo if datos else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:  # sin red, DNS, timeout...
        return {"ok": False, "description": str(e)}


def chats_de(texto):
    return [c.strip() for c in (texto or "").replace(";", ",").split(",") if c.strip()]


def enviar(token, chats, texto):
    """Envía a todos los chats. Devuelve lista de (chat, ok, detalle)."""
    resultados = []
    for chat in chats_de(chats):
        r = _llamar(token, "sendMessage", {"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                           "disable_web_page_preview": "true"})
        resultados.append((chat, bool(r.get("ok")), r.get("description", "")))
        if not r.get("ok"):
            log.warning("Telegram: no se pudo enviar a %s: %s", chat, r.get("description"))
    return resultados


def enviar_en_segundo_plano(token, chats, texto):
    """No hace esperar al participante: el aviso sale en un hilo aparte."""
    if token and chats_de(chats):
        threading.Thread(target=enviar, args=(token, chats, texto), daemon=True).start()


def detectar_chats(token):
    """Chats que han escrito al bot (o grupos donde está). Devuelve (ok, lista o error)."""
    yo = _llamar(token, "getMe")
    if not yo.get("ok"):
        return False, "El token no es válido: " + (yo.get("description") or "error desconocido")
    r = _llamar(token, "getUpdates", {"timeout": "0", "allowed_updates": '["message","my_chat_member"]'})
    if not r.get("ok"):
        return False, r.get("description", "No se pudieron leer los mensajes del bot")
    vistos = {}
    for u in r.get("result", []):
        for clave in ("message", "my_chat_member", "channel_post"):
            chat = (u.get(clave) or {}).get("chat")
            if chat:
                nombre = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
                vistos[str(chat["id"])] = f"{nombre or chat.get('username', '')} ({chat.get('type')})"
    return True, {"bot": "@" + yo["result"].get("username", ""), "chats": vistos}


def mensaje_reserva(aj, nombre, cantidad, importe, concepto, pago, url_panel, nueva_persona):
    e = html.escape
    lineas = [
        f"🎟️ <b>Nueva reserva {e(concepto)}</b>",
        f"<b>{e(nombre)}</b>{' (nuevo participante)' if nueva_persona else ''}",
        f"{cantidad} papeleta{'s' if cantidad != 1 else ''} · <b>{e(importe)}</b>",
        f"{'📱 Bizum' if pago['metodo'] == 'bizum' else '💶 En mano'}{' a ' + e(pago['nombre']) if pago['nombre'] else ''}",
    ]
    if url_panel:
        lineas.append(f'\n<a href="{e(url_panel)}">Abrir pagos pendientes</a>')
    return "\n".join(lineas)
