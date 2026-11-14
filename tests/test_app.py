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
    tok = _csrf(r.text)

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
    r = pub.post("/participar", data={"_csrf": tok, "nombre": "María José Fernández de la Vega",
                                     "cantidad": "3", "pago": "bizum:1"})
    assert r.status_code == 302
    enlace = r.headers["Location"]
    r = pub.get(enlace)
    assert "OLA-0001" in r.text and "7,50 €" in r.text and "611 222 333" in r.text and "a Pedro" in r.text
    token = re.search(r"/mi/([^?\"]+)", enlace).group(1)
    # vuelve con su enlace y compra más
    r = pub.post("/participar", data={"_csrf": tok, "token": token, "cantidad": "2", "pago": "mano:1"})
    assert "a <b>Marta</b>" in pub.get(enlace.split("?")[0]).text
    assert "/mi/" + token in r.headers["Location"]
    r = pub.get(f"/mi/{token}/resguardo/1")
    assert r.data[:4] == b"%PDF" and "resguardo-OLA-0001" in r.headers["Content-Disposition"]
    open(os.path.join(tmp, "resguardo.pdf"), "wb").write(r.data)
    assert pub.get("/mi/otro/resguardo/1").status_code == 404
    # la portada lo reconoce por cookie
    assert "Hola, <b>María José" in pub.get("/").text

    otro = app.test_client()
    t2 = _csrf(otro.get("/").text)
    otro.post("/participar", data={"_csrf": t2, "nombre": "Luis", "cantidad": "1", "pago": "mano:0"})
    # cambia de forma de pago
    r = pub.post(f"/mi/{token}/cambiar-pago/1", data={"_csrf": tok, "pago": "bizum:0"})
    assert "600 111 222" in pub.get(enlace.split("?")[0]).text

    # admin confirma
    c.post("/admin/login", data={"_csrf": tok if False else _csrf(c.get('/admin/login').text), "clave": "secreta"})
    tok = _csrf(c.get("/admin").text)
    for cid in (1, 2, 3):
        c.post(f"/admin/compra/{cid}/confirmar", data={"_csrf": tok})
    # alta manual -> aviso con resguardo
    c.post("/admin/compra/nueva", data={"_csrf": tok, "nombre": "Josu Etxeberria", "cantidad": "4",
                                        "pago": "mano:0", "confirmada": "1"})
    r = c.get("/admin?estado=todas")
    assert "Descargar resguardo" in r.text and "Josu Etxeberria" in r.text
    m = re.search(r'href="(/mi/[^/]+/resguardo/(\d+))', r.text)
    assert c.get(m.group(1)).data[:4] == b"%PDF"
    assert "Descargar resguardo" not in c.get("/admin?estado=todas").text   # solo se muestra una vez
    c.post(f"/admin/compra/{m.group(2)}/borrar", data={"_csrf": tok})
    r = c.get("/admin?estado=confirmado")
    assert r.text.count("Deshacer") == 3
    assert "15,00 €" in r.text  # 6 papeletas x 2,50

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
