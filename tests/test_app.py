# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Prueba de extremo a extremo:  python -m pytest -q   (o  python tests/test_app.py)"""
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from cestaola import create_app  # noqa: E402


def _csrf(html):
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


def _foto():
    b = io.BytesIO()
    Image.new("RGB", (1200, 900), (180, 40, 50)).save(b, "JPEG")
    b.seek(0)
    return b


def test_flujo_completo():
    tmp = tempfile.mkdtemp()
    app = create_app({"DATA_DIR": tmp, "ADMIN_PASSWORD": "secreta", "SECRET_KEY": "x",
                      "SESSION_COOKIE_SECURE": False, "TESTING": True})
    c = app.test_client()

    r = c.get("/")
    assert r.status_code == 200
    assert "Versión " + open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")).read().strip() in r.text
    tok = _csrf(r.text)

    # Telegram: se capturan los envíos en lugar de llamar a la API
    from cestaola import telegram as tg
    enviados = []
    tg.enviar_en_segundo_plano = lambda token, chats, texto: enviados.append((token, chats, texto))
    tg._llamar = lambda token, metodo, datos=None, timeout=8: (
        {"ok": True, "result": {"username": "cesta_bot"}} if metodo == "getMe" else
        {"ok": True, "result": [{"message": {"chat": {"id": 111, "type": "private", "first_name": "Ana"}}},
                                {"my_chat_member": {"chat": {"id": -222, "type": "group", "title": "Organizadores"}}}]}
        if metodo == "getUpdates" else {"ok": True})

    # sin CSRF -> 400
    assert c.post("/participar", data={"nombre": "X"}).status_code == 400

    # login admin
    assert c.post("/admin/login", data={"_csrf": tok, "clave": "mala"}).status_code == 200
    r = c.post("/admin/login", data={"_csrf": tok, "clave": "secreta"})
    assert r.status_code == 302
    tok = _csrf(c.get("/admin").text)

    # ajustes y lote con foto
    r = c.post("/admin/ajustes", data={"_csrf": tok, "precio": "2,50", "titulo": "Cesta OLA 2026",
                                        "texto": "Hola", "bizum_nombre": ["Ana", "Pedro", ""],
                                        "bizum_tel": ["600 111 222", "611 222 333", ""],
                                        "mano_nombre": ["Luis", "Marta", ""], "fecha_sorteo": "19 dic",
                                        "prefijo": "ola", "max_por_compra": "40"})
    assert r.status_code == 302
    r = c.post("/admin/premios/nuevo", data={"_csrf": tok, "nombre": "Cesta ibérica",
                                              "descripcion": "Jamón\nQueso", "precio": "85,90",
                                              "foto": (_foto(), "cesta.jpg")},
               content_type="multipart/form-data")
    assert r.status_code == 302
    c.post("/admin/premios/nuevo", data={"_csrf": tok, "nombre": "Vino", "precio": "20"})
    assert len(os.listdir(os.path.join(tmp, "fotos"))) == 1
    c.get("/admin/salir")

    # compra pública con Bizum
    pub = app.test_client()
    tok = _csrf(pub.get("/").text)
    c.post("/admin/login", data={"_csrf": _csrf(c.get('/admin/login').text), "clave": "secreta"})
    ta = _csrf(c.get("/admin/ajustes").text)
    c.post("/admin/ajustes", data={"_csrf": ta, "precio": "2,50", "titulo": "Cesta OLA 2026", "prefijo": "ola",
                                   "max_por_compra": "40", "bizum_nombre": ["Ana", "Pedro"],
                                   "bizum_tel": ["600 111 222", "611 222 333"], "mano_nombre": ["Luis", "Marta"]})
    r = c.post("/admin/ajustes", data={"_csrf": ta, "accion": "tg_detectar"}, follow_redirects=True)
    assert "Falta el token" in r.text
    # el token se escribe y se pulsa Detectar directamente (sin guardar antes)
    r = c.post("/admin/ajustes", data={"_csrf": ta, "accion": "tg_detectar", "telegram_token": "123:abc",
                                       "telegram_chats": ""}, follow_redirects=True)
    assert "Organizadores (group) → -222 (añadido)" in r.text and "Ana (private) → 111" in r.text
    assert 'value="111, -222"' in c.get("/admin/ajustes").text
    r = c.post("/admin/ajustes", data={"_csrf": ta, "accion": "tg_prueba", "telegram_chats": "111, -222"},
               follow_redirects=True)
    assert r.text.count("mensaje enviado") == 2
    # el formulario general no borra los datos de Telegram
    c.post("/admin/ajustes", data={"_csrf": ta, "precio": "2,50", "titulo": "Cesta OLA 2026", "prefijo": "ola",
                                   "max_por_compra": "40", "bizum_nombre": ["Ana", "Pedro"],
                                   "bizum_tel": ["600 111 222", "611 222 333"], "mano_nombre": ["Luis", "Marta"]})
    assert 'value="111, -222"' in c.get("/admin/ajustes").text
    c.get("/admin/salir")
    # sin teléfono no deja reservar
    r = pub.post("/participar", data={"_csrf": tok, "nombre": "Sin Movil", "cantidad": "1", "pago": "mano:0"},
                 follow_redirects=True)
    assert "Escribe tu teléfono" in r.text
    r = pub.post("/participar", data={"_csrf": tok, "nombre": "María José Fernández de la Vega", "telefono": "+34 611 22 33 44",
                                     "cantidad": "3", "pago": "bizum:1"})
    assert r.status_code == 302
    enlace = r.headers["Location"]
    assert len(enviados) == 1 and enviados[0][0] == "123:abc" and enviados[0][1] == "111, -222"
    assert "Nueva reserva OLA-0001" in enviados[0][2] and "a Pedro" in enviados[0][2] and "7,50 €" in enviados[0][2]
    assert "quien=bizum%7CPedro" in enviados[0][2]
    r = pub.get(enlace)
    assert "OLA-0001" in r.text and "7,50 €" in r.text and "611 222 333" in r.text and "a Pedro" in r.text
    token = re.search(r"/mi/([^?\"]+)", enlace).group(1)
    # vuelve con su enlace y compra más
    r = pub.post("/participar", data={"_csrf": tok, "token": token, "cantidad": "2", "pago": "mano:1"})
    assert "a <b>Marta</b>" in pub.get(enlace.split("?")[0]).text
    assert "/mi/" + token in r.headers["Location"]
    r = pub.get(f"/mi/{token}/resguardo/1")
    assert r.data[:4] == b"%PDF"
    assert "resguardo-Maria-Jose-Fernandez-de-la-Vega-OLA-0001.pdf" in r.headers["Content-Disposition"]
    assert "filename*=UTF-8''resguardo-Mar%C3%ADa-Jos%C3%A9-Fern%C3%A1ndez-de-la-Vega-OLA-0001.pdf" in r.headers["Content-Disposition"]
    open(os.path.join(tmp, "resguardo.pdf"), "wb").write(r.data)
    assert pub.get("/mi/otro/resguardo/1").status_code == 404
    # la portada lo reconoce por cookie
    assert "Hola, <b>María José" in pub.get("/").text

    otro = app.test_client()
    t2 = _csrf(otro.get("/").text)
    otro.post("/participar", data={"_csrf": t2, "nombre": "Luis", "telefono": "655443322", "cantidad": "1", "pago": "mano:0"})
    # cambia de forma de pago
    r = pub.post(f"/mi/{token}/cambiar-pago/1", data={"_csrf": tok, "pago": "bizum:0"})
    assert "600 111 222" in pub.get(enlace.split("?")[0]).text

    # admin confirma
    c.post("/admin/login", data={"_csrf": tok if False else _csrf(c.get('/admin/login').text), "clave": "secreta"})
    tok = _csrf(c.get("/admin").text)
    for cid in (1, 2, 3):
        c.post(f"/admin/compra/{cid}/confirmar", data={"_csrf": tok})
    # el móvil del organizador no "se convierte" en el participante al abrir su enlace
    c.get(f"/mi/{token}")
    assert "Hola, <b>" not in c.get("/").text
    # un participante que abre el enlace reenviado de otro sigue siendo él mismo
    otro_tok = re.search(r"/mi/([^/\"?]+)", otro.get("/").text).group(1)
    pub.get(f"/mi/{otro_tok}")
    assert "Hola, <b>María José" in pub.get("/").text
    # al salir del panel se olvida la persona recordada
    assert "cestaola_persona=;" in c.get("/admin/salir").headers.get("Set-Cookie", "")
    c.post("/admin/login", data={"_csrf": _csrf(c.get('/admin/login').text), "clave": "secreta"})
    tok = _csrf(c.get("/admin").text)

    # alta manual -> aviso con resguardo
    c.post("/admin/compra/nueva", data={"_csrf": tok, "nombre": "Josu Etxeberria", "cantidad": "4",
                                        "pago": "mano:0", "confirmada": "1"})
    r = c.get("/admin?estado=todas")
    assert "Descargar resguardo" in r.text and "Josu Etxeberria" in r.text
    m = re.search(r'href="(/mi/[^/]+/resguardo/(\d+))', r.text)
    assert c.get(m.group(1)).data[:4] == b"%PDF"
    assert "Descargar resguardo" not in c.get("/admin?estado=todas").text   # solo se muestra una vez
    r = pub.get(f"/mi/{token}/resguardo")          # resumen de varias reservas
    assert r.data[:4] == b"%PDF" and "Fern%C3%A1ndez-de-la-Vega-resumen.pdf" in r.headers["Content-Disposition"]
    open(os.path.join(tmp, "resguardo-total.pdf"), "wb").write(r.data)
    assert "Resguardo de todo" in pub.get(f"/mi/{token}").text
    assert c.get("/admin").text.count("🔗 Enlace") >= 3
    c.post(f"/admin/compra/{m.group(2)}/borrar", data={"_csrf": tok})
    r = c.get("/admin?estado=confirmado")
    assert r.text.count("Deshacer") == 3
    assert "15,00 €" in r.text  # 6 papeletas x 2,50
    # botón de WhatsApp con el chat de la persona y el enlace al resguardo
    from urllib.parse import unquote
    m = re.search(r'href="(https://wa\.me/34611223344\?text=[^"]+)"', r.text)
    assert m, "falta el botón de WhatsApp"
    texto = unquote(m.group(1).replace("&amp;", "&"))
    assert "Hola María" in texto and "/resguardo/" in texto and "pagado" in texto
    assert "https://wa.me/34655443322" in r.text
    assert "611 22 33 44" in c.get("/admin/exportar.csv").get_data(as_text=True)

    # PDFs
    r = c.get("/admin/papeletas.pdf")
    assert r.status_code == 200 and r.data[:4] == b"%PDF"
    open(os.path.join(tmp, "papeletas.pdf"), "wb").write(r.data)
    assert "no-store" in r.headers["Cache-Control"] and "papeletas-" in r.headers["Content-Disposition"]
    r = c.get("/admin/lotes.pdf")
    assert r.data[:4] == b"%PDF"
    open(os.path.join(tmp, "lotes.pdf"), "wb").write(r.data)
    r = c.get("/admin")
    assert "¿Quién tiene el dinero?" in r.text and "Marta" in r.text

    # sorteo y publicación
    c.post("/admin/sorteo", data={"_csrf": tok, "accion": "ganadores", "ganador_1": "1"})
    c.post("/admin/sorteo", data={"_csrf": tok, "accion": "azar", "premio_id": "2"})
    c.post("/admin/sorteo", data={"_csrf": tok, "accion": "publicar", "valor": "1"})
    assert "Enhorabuena" in pub.get(enlace).text
    assert "Ya tenemos premiados" in pub.get("/").text

    # copia de seguridad: exportar, cambiar algo, importar y comprobar que vuelve
    r = c.get("/admin/copia.zip")
    assert r.status_code == 200 and r.data[:2] == b"PK"
    import zipfile
    zf = zipfile.ZipFile(io.BytesIO(r.data))
    assert "cestaola.db" in zf.namelist() and any(n.startswith("fotos/") for n in zf.namelist())
    copia = r.data
    c.post("/admin/compra/1/borrar", data={"_csrf": tok})
    assert "OLA-0001" not in c.get("/admin?estado=todas").text
    r = c.post("/admin/importar", data={"_csrf": tok, "copia": (io.BytesIO(copia), "c.zip")},
               content_type="multipart/form-data", follow_redirects=True)
    assert "Marca la casilla" in r.text
    r = c.post("/admin/importar", data={"_csrf": tok, "confirmo": "1", "copia": (io.BytesIO(copia), "c.zip")},
               content_type="multipart/form-data", follow_redirects=True)
    assert "Copia importada" in r.text and "OLA-0001" in c.get("/admin?estado=todas").text
    assert len(os.listdir(os.path.join(tmp, "copias"))) == 1
    r = c.post("/admin/importar", data={"_csrf": tok, "confirmo": "1", "copia": (io.BytesIO(b"no es zip"), "x.zip")},
               content_type="multipart/form-data", follow_redirects=True)
    assert "no es un .zip" in r.text
    assert pub.get("/admin/copia.zip").status_code == 302

    # copia por Telegram (manual y nocturna)
    docs = []
    tg.enviar_documento = lambda token, chats, datos, nombre, texto="": (
        docs.append((nombre, datos[:2], texto)) or [(c_, True, "") for c_ in tg.chats_de(chats)])
    r = c.post("/admin/ajustes", data={"_csrf": tok, "accion": "tg_copia", "telegram_chats": "111, -222"},
               follow_redirects=True)
    assert r.text.count("copia enviada") == 2 and docs[-1][1] == b"PK" and "reservas" in docs[-1][2]
    from cestaola import nocturna
    with app.app_context():
        assert nocturna.enviar_copia(tmp)[1] == ["La copia nocturna está desactivada en Ajustes."]
    c.post("/admin/ajustes", data={"_csrf": tok, "accion": "tg_guardar", "telegram_chats": "111, -222",
                                   "telegram_copia": "1"})
    with app.app_context():
        assert nocturna.enviar_copia(tmp)[1] == ["Sin cambios desde la última copia: no se envía."]
    c.post("/admin/compra/2/nota", data={"_csrf": tok, "nota": "cambio"})
    with app.app_context():
        ok, msgs = nocturna.enviar_copia(tmp)
        assert ok and len(msgs) == 2, msgs

    # cierre
    c.post("/admin/ajustes", data={"_csrf": tok, "accion": "estado", "valor": "cerrada"})
    r = pub.post("/participar", data={"_csrf": tok, "token": token, "cantidad": "1", "pago": "mano:0"})
    assert "cerrada" in pub.get("/").text
    assert "csv" in c.get("/admin/exportar.csv").headers["Content-Type"]
    assert pub.get("/admin").status_code == 302
    assert pub.get("/admin/papeletas.pdf").status_code == 302
    print("OK", tmp)
    return tmp


if __name__ == "__main__":
    test_flujo_completo()
