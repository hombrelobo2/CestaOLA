# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Genera las capturas de la guía con datos de ejemplo.

Necesita Playwright y Chrome/Chromium (solo para documentación):
    python3 docs/guia/capturas.py  [--chrome /ruta/a/chrome]
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)

from PIL import Image  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from cestaola import create_app  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--chrome", default=shutil.which("google-chrome") or shutil.which("chromium") or "")
args = ap.parse_args()

SAL = os.path.join(AQUI, "capturas")
os.makedirs(SAL, exist_ok=True)
DATOS = tempfile.mkdtemp(prefix="cestaola-guia-")
PUERTO = 8790
BASE = f"http://127.0.0.1:{PUERTO}"

app = create_app({"DATA_DIR": DATOS, "ADMIN_PASSWORD": "demo", "SECRET_KEY": "guia",
                  "SESSION_COOKIE_SECURE": False, "BASE_URL": "https://cesta.ejemplo.es"})
c = app.test_client()
tok = lambda h: re.search(r'name="_csrf" value="([^"]+)"', h).group(1)  # noqa: E731

# ------------------------------------------------------------------ datos de ejemplo
t = tok(c.get("/admin/login").text)
c.post("/admin/login", data={"_csrf": t, "clave": "demo"})
t = tok(c.get("/admin").text)
c.post("/admin/ajustes", data={
    "_csrf": t, "titulo": "Sorteo Navideño 2026", "precio": "2",
    "texto": "¡Participa en el sorteo de la cesta de este año! Cada papeleta va a la bolsa con tu nombre.",
    "fecha_sorteo": "Miércoles 23 de diciembre · 14:30 h", "prefijo": "OLA", "max_por_compra": "50",
    "bizum_nombre": ["Ana", "Pedro", ""], "bizum_tel": ["600 000 001", "600 000 002", ""],
    "mano_nombre": ["Luis", "Marta", ""]})

def foto(nombre):
    return (open(os.path.join(AQUI, "fotos-demo", nombre), "rb"), nombre)

LOTES = [
    ("La gran cesta", "Embutidos y quesos: paleta ibérica, lomo, chorizo y salchichón de bellota, queso curado.\n"
     "Bebidas: vino tinto reserva y blanco verdejo.\nDulces: turrón blando y duro, mantecados, polvorones y neulas.\n"
     "Conservas: paté ibérico y torta de oveja.", "85", "cesta.jpg"),
    ("Jamón y vinos", "Jamón de cebo con jamonero, dos botellas de tinto crianza y un queso manchego.", "120", "jamon.jpg"),
    ("Lote dulce y embutido", "Panettone artesano, bombones, dos chorizos de bellota y una caja regalo.", "35", "dulces.jpg"),
    ("Vale de cena para dos", "Menú degustación en un restaurante de la zona.", "60", None),
]
for nombre, desc, precio, f in LOTES:
    d = {"_csrf": t, "nombre": nombre, "descripcion": desc, "precio": precio}
    if f:
        d["foto"] = foto(f)
    c.post("/admin/premios/nuevo", data=d, content_type="multipart/form-data")

GENTE = [("Iratxe Gómez", 5, "bizum:0"), ("Jon Ugarte", 3, "mano:0"), ("Conchi Ruiz", 4, "bizum:1"),
         ("Iker Etxebarria", 2, "mano:1"), ("Lorena Sánchez", 6, "bizum:0"), ("Mikel Arana", 1, "mano:0")]
for nombre, n, pago in GENTE:
    u = app.test_client()
    tt = tok(u.get("/").text)
    u.post("/participar", data={"_csrf": tt, "nombre": nombre, "telefono": "600 000 0" + str(10 + len(nombre)),
                               "cantidad": str(n), "pago": pago})
for cid in (1, 2, 3, 4):
    c.post(f"/admin/compra/{cid}/confirmar", data={"_csrf": t})

srv = make_server("127.0.0.1", PUERTO, app)
threading.Thread(target=srv.serve_forever, daemon=True).start()


def guardar(png_bytes, nombre, ancho=780):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
    im.save(os.path.join(SAL, nombre + ".jpg"), "JPEG", quality=86, optimize=True)
    print("  ", nombre, im.size)


def pdf_a_png(datos, nombre, pagina=1, dpi=110):
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "a.pdf"), "wb").write(datos)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(pagina), "-l", str(pagina),
                        os.path.join(d, "a.pdf"), os.path.join(d, "p")], check=True)
        png = [f for f in os.listdir(d) if f.endswith(".png")][0]
        guardar(open(os.path.join(d, png), "rb").read(), nombre, ancho=1000)


from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=args.chrome or None, args=["--no-sandbox"])
    movil = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

    # ---------------- participante
    m = b.new_page(**movil)
    m.goto(BASE + "/"); m.wait_for_timeout(300)
    guardar(m.screenshot(), "p1-portada")
    lote = m.locator(".lote").first
    guardar(lote.screenshot(), "p2-lote-plegado")
    lote.locator(".ver-mas").click(); m.wait_for_timeout(150)
    guardar(lote.screenshot(), "p3-lote-desplegado")
    guardar(m.locator(".cuentas").screenshot(), "p4-cuentas")
    m.fill("#nombre", "Ane Lasa")
    m.fill("#telefono", "600 000 099")
    m.locator("#participar [data-paso='1']").click(); m.locator("#participar [data-paso='1']").click()
    guardar(m.locator("#participar").screenshot(), "p5-formulario")
    m.locator("#participar button.grande").click(); m.wait_for_load_state(); m.wait_for_timeout(200)
    guardar(m.screenshot(), "p6-mis-papeletas")
    guardar(m.locator(".bizum").first.screenshot(), "p7-bizum")
    m.evaluate("window.scrollTo(0, document.body.scrollHeight)"); m.wait_for_timeout(100)
    guardar(m.locator(".lista-compras").locator("xpath=..").screenshot(), "p8-historial")
    token = re.search(r"/mi/([^?/]+)", m.url).group(1)
    pdf_a_png(c.get(f"/mi/{token}/resguardo/7").data, "p9-resguardo", dpi=160)

    # ---------------- organizadores
    a = b.new_page(**movil)
    a.goto(BASE + "/admin/login")
    guardar(a.screenshot(), "a0-login")
    a.fill("#clave", "demo"); a.click("button.grande"); a.wait_for_load_state()
    # La barra superior es fija: en las capturas de elementos se dejaría ver por encima
    a.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');"
                      "s.textContent='.barra{position:static!important}';document.head.appendChild(s)})")
    a.goto(BASE + "/admin"); a.wait_for_timeout(200)
    guardar(a.screenshot(), "a1-panel")
    guardar(a.locator("text=¿Quién tiene el dinero?").locator("xpath=..").screenshot(), "a2-quien-tiene")
    guardar(a.locator(".pestanas").locator("xpath=..").screenshot(), "a3-pendientes")
    # alta manual
    a.locator("summary").click()
    a.fill("#nombre-nuevo", "Nerea Uriarte"); a.fill("#cant-manual", "2")
    a.locator("form[action='/admin/compra/nueva'] button.btn").click(); a.wait_for_load_state()
    guardar(a.locator(".aviso.ok").first.screenshot(), "a4-alta-manual")
    guardar(a.locator("#personas").screenshot(), "a5-participantes")
    a.goto(BASE + "/admin/premios"); a.wait_for_timeout(300)
    guardar(a.screenshot(), "a6-lotes")
    a.goto(BASE + "/admin/premios/1"); a.wait_for_timeout(300)
    guardar(a.screenshot(full_page=True), "a7-editar-lote")
    a.goto(BASE + "/admin/ajustes"); a.wait_for_timeout(200)
    guardar(a.screenshot(full_page=True), "a8-ajustes")
    a.goto(BASE + "/admin/sorteo"); a.wait_for_timeout(300)
    a.locator("select[name='ganador_1']").select_option(label="Iratxe Gómez")
    a.locator("select[name='ganador_1']").evaluate("s => s.classList.add('asignado')")
    guardar(a.screenshot(full_page=True), "a9-sorteo")
    b.close()

pdf_a_png(c.get("/admin/papeletas.pdf").data, "d1-papeletas", dpi=90)
pdf_a_png(c.get("/admin/lotes.pdf").data, "d2-lotes-sobres", dpi=90)
srv.shutdown()
shutil.rmtree(DATOS, ignore_errors=True)
print("Capturas en", SAL)
