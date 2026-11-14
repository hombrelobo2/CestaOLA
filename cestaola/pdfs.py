# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Generación de PDFs: papeletas para la bolsa y cartel de lotes."""
import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from xml.sax.saxutils import escape


VINO = colors.HexColor("#7b1e2c")
ORO = colors.HexColor("#c49a45")
TINTA = colors.HexColor("#2a1c18")
CREMA = colors.HexColor("#fbf5ea")

# Tamaño de cada papeleta: 10 x 5 cm -> 2 columnas x 5 filas en A4 (10 por hoja)
PAP_W, PAP_H = 100 * mm, 50 * mm
COLS, FILAS = 2, 5


def _rombo(c, cx, cy, r):
    p = c.beginPath()
    p.moveTo(cx, cy + r); p.lineTo(cx + r * .6, cy); p.lineTo(cx, cy - r); p.lineTo(cx - r * .6, cy); p.close()
    c.drawPath(p, stroke=0, fill=1)


def _ajustar_fuente(texto, fuente, maximo, minimo, ancho):
    t = maximo
    while t > minimo and stringWidth(texto, fuente, t) > ancho:
        t -= 1
    return t


def _partir_nombre(nombre, fuente, tam, ancho):
    """Si no cabe en una línea, intenta partirlo en dos por un espacio."""
    if stringWidth(nombre, fuente, tam) <= ancho or " " not in nombre:
        return [nombre]
    palabras = nombre.split()
    mejor = None
    for i in range(1, len(palabras)):
        a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
        m = max(stringWidth(a, fuente, tam), stringWidth(b, fuente, tam))
        if mejor is None or m < mejor[0]:
            mejor = (m, [a, b])
    return mejor[1]


def pdf_papeletas(aj, personas):
    """Una papeleta por participación confirmada, ordenadas por nombre."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Papeletas - {aj['titulo']}")
    pw, ph = A4
    mx = (pw - COLS * PAP_W) / 2
    my = (ph - FILAS * PAP_H) / 2

    papeletas = []
    for p in personas:
        n = p["confirmadas"]
        for i in range(1, n + 1):
            papeletas.append((p["nombre"], i, n))

    if not papeletas:
        c.setFont("Helvetica", 14)
        c.drawCentredString(pw / 2, ph / 2, "No hay participaciones confirmadas todavía.")
        c.showPage()
        c.save()
        return buf.getvalue()

    por_hoja = COLS * FILAS
    total = len(papeletas)
    for idx, (nombre, i, n) in enumerate(papeletas):
        pos = idx % por_hoja
        if pos == 0 and idx:
            c.showPage()
        if pos == 0:
            # Pie de página con el recuento
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.grey)
            hoja = idx // por_hoja + 1
            c.drawCentredString(pw / 2, 8 * mm,
                                f"{aj['titulo']} · hoja {hoja} de {(total - 1) // por_hoja + 1} · "
                                f"{total} papeletas · recorta por la línea discontinua")
        col, fila = pos % COLS, pos // COLS
        x = mx + col * PAP_W
        y = ph - my - (fila + 1) * PAP_H

        # Línea de corte
        c.setStrokeColor(colors.Color(0.6, 0.6, 0.6))
        c.setLineWidth(0.4)
        c.setDash(3, 3)
        c.rect(x, y, PAP_W, PAP_H)
        c.setDash()

        # Marco interior elegante (vino) con adornos
        c.setStrokeColor(VINO)
        c.setLineWidth(0.9)
        c.roundRect(x + 3 * mm, y + 3 * mm, PAP_W - 6 * mm, PAP_H - 6 * mm, 3 * mm)
        c.setLineWidth(0.3)
        c.setStrokeColor(ORO)
        c.roundRect(x + 4.2 * mm, y + 4.2 * mm, PAP_W - 8.4 * mm, PAP_H - 8.4 * mm, 2.2 * mm)
        # Cabecera: título en cursiva con estrellas
        tit = aj["titulo"][:48]
        c.setFillColor(VINO)
        c.setFont("Times-Italic", 9.5)
        c.drawCentredString(x + PAP_W / 2, y + PAP_H - 10.5 * mm, tit)
        wt = stringWidth(tit, "Times-Italic", 9.5)
        c.setFillColor(ORO)
        for dx in (-(wt / 2 + 4 * mm), wt / 2 + 4 * mm):
            _rombo(c, x + PAP_W / 2 + dx, y + PAP_H - 9.6 * mm, 1.3 * mm)

        # Nombre en grande, centrado
        c.setFillColor(TINTA)
        ancho = PAP_W - 16 * mm
        fuente = "Helvetica-Bold"
        tam = _ajustar_fuente(nombre, fuente, 30, 18, ancho)
        lineas = _partir_nombre(nombre, fuente, tam, ancho)
        if len(lineas) > 1:   # nombre largo: dos líneas
            tam = min(_ajustar_fuente(l, fuente, 24, 8, ancho) for l in lineas)
        elif stringWidth(nombre, fuente, tam) > ancho:   # una palabra larguísima
            tam = _ajustar_fuente(nombre, fuente, 18, 6, ancho)
        c.setFont(fuente, tam)
        alto_txt = tam * 1.15 * len(lineas)
        base = y + PAP_H / 2 - 1.5 * mm + alto_txt / 2 - tam * 0.95
        for k, l in enumerate(lineas):
            c.drawCentredString(x + PAP_W / 2, base - k * tam * 1.15, l)

        # Número de papeleta
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.Color(0.45, 0.4, 0.38))
        c.drawRightString(x + PAP_W - 7.5 * mm, y + 7 * mm, f"{i} de {n}")
    c.showPage()
    c.save()
    return buf.getvalue()


def _foto_recortada(ruta, w, h):
    """Devuelve un ImageReader con la foto recortada a la proporción w:h (centrada)."""
    from PIL import Image as PILImage
    from reportlab.lib.utils import ImageReader
    im = PILImage.open(ruta)
    iw, ih = im.size
    objetivo = w / h
    if iw / ih > objetivo:
        nw = int(ih * objetivo); x0 = (iw - nw) // 2; im = im.crop((x0, 0, x0 + nw, ih))
    else:
        nh = int(iw / objetivo); y0 = (ih - nh) // 2; im = im.crop((0, y0, iw, y0 + nh))
    im.thumbnail((1400, 1400))
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=88)
    b.seek(0)
    return ImageReader(b)


def pdf_lotes_sobres(aj, premios, carpeta_fotos):
    """Una ficha por lote (foto + nombre + descripción), 3 por A4 vertical, para recortar
    y meter en sobres. Sin precios ni premiados."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Lotes para sobres - {aj['titulo']}")
    pw, ph = A4
    alto = ph / 3
    if not premios:
        c.setFont("Helvetica", 14)
        c.drawCentredString(pw / 2, ph / 2, "Todavía no hay lotes.")
        c.showPage(); c.save()
        return buf.getvalue()

    st_desc = ParagraphStyle("d", fontName="Helvetica", fontSize=11, leading=14.5, textColor=colors.HexColor("#4a3b34"))
    st_nom = ParagraphStyle("n", fontName="Times-Bold", fontSize=20, leading=23, textColor=TINTA)
    total = len(premios)
    for idx, p in enumerate(premios):
        pos = idx % 3
        if pos == 0 and idx:
            c.showPage()
        if pos == 0:
            # Líneas de corte entre fichas y pie
            c.setStrokeColor(colors.Color(0.6, 0.6, 0.6)); c.setLineWidth(0.4); c.setDash(3, 3)
            c.line(0, alto, pw, alto); c.line(0, 2 * alto, pw, 2 * alto)
            c.setDash()
            c.setFont("Helvetica", 6.5); c.setFillColor(colors.grey)
            c.drawCentredString(pw / 2, 2.5 * mm, f"{aj['titulo']} · lotes para sobres · hoja {idx // 3 + 1} de {(total - 1) // 3 + 1} · recorta por la línea discontinua")
        y0 = ph - (pos + 1) * alto
        m = 8 * mm
        # Marco
        c.setStrokeColor(VINO); c.setLineWidth(1)
        c.roundRect(m, y0 + m, pw - 2 * m, alto - 2 * m, 3.5 * mm)
        c.setStrokeColor(ORO); c.setLineWidth(0.35)
        c.roundRect(m + 1.4 * mm, y0 + m + 1.4 * mm, pw - 2 * m - 2.8 * mm, alto - 2 * m - 2.8 * mm, 2.6 * mm)

        # Foto (4:3) a la izquierda
        pad = 6 * mm
        fh = alto - 2 * m - 2 * pad
        fw = fh * 4 / 3
        fx, fy = m + pad, y0 + m + pad
        ruta = os.path.join(carpeta_fotos, os.path.basename(p["foto"])) if p["foto"] else ""
        if ruta and os.path.exists(ruta):
            try:
                c.drawImage(_foto_recortada(ruta, fw, fh), fx, fy, fw, fh)
            except Exception:
                ruta = ""
        if not (ruta and os.path.exists(ruta)):
            c.setFillColor(colors.HexColor("#f1e2bd")); c.rect(fx, fy, fw, fh, stroke=0, fill=1)
            c.setFillColor(ORO); c.setFont("Times-Italic", 14)
            c.drawCentredString(fx + fw / 2, fy + fh / 2 - 4, "sin foto")

        # Texto a la derecha
        tx = fx + fw + 7 * mm
        tw = pw - m - pad - tx
        ty = y0 + alto - m - pad
        c.setFillColor(ORO); c.setFont("Helvetica-Bold", 8.5)
        c.drawString(tx, ty - 8, f"L O T E   {idx + 1}")
        _rombo(c, tx + stringWidth(f"L O T E   {idx + 1}", "Helvetica-Bold", 8.5) + 3 * mm, ty - 5.2, 1.3 * mm)
        disponible = ty - 14 - (fy)
        nom = Paragraph(escape(p["nombre"]), st_nom)
        desc_txt = escape(p["descripcion"] or "").replace("\n", "<br/>")
        # Reduce la letra hasta que quepa todo
        for esc in (1, .92, .85, .78, .7, .62, .55):
            sn = ParagraphStyle("n2", parent=st_nom, fontSize=st_nom.fontSize * min(1, esc + .1), leading=st_nom.leading * min(1, esc + .1))
            sd = ParagraphStyle("d2", parent=st_desc, fontSize=st_desc.fontSize * esc, leading=st_desc.leading * esc)
            nom = Paragraph(escape(p["nombre"]), sn)
            _, hn = nom.wrap(tw, disponible)
            desc = Paragraph(desc_txt, sd) if desc_txt else None
            hd = desc.wrap(tw, disponible)[1] if desc else 0
            if hn + 3 * mm + hd <= disponible:
                break
        yy = ty - 14 - 2 * mm - hn
        nom.drawOn(c, tx, yy)
        if desc:
            yy -= 3 * mm + hd
            desc.drawOn(c, tx, yy)
    c.showPage()
    c.save()
    return buf.getvalue()


def _fecha(iso):
    """'2026-11-14 12:46:03' -> '14/11/2026 12:46'"""
    try:
        f, h = iso.split(" ")
        a, m, d = f.split("-")
        return f"{d}/{m}/{a} {h[:5]}"
    except ValueError:
        return iso


def pdf_resguardo(aj, persona, compra, concepto, enlace, total_confirmadas):
    """Resguardo de una reserva, tamaño A6 apaisado, con QR al enlace personal."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from . import euros

    W, H = 148 * mm, 105 * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Resguardo {concepto} - {persona['nombre']}")
    talon = 46 * mm                    # ancho del talón con el QR
    xt = W - talon                     # línea de separación

    # Fondo
    c.setFillColor(CREMA); c.rect(0, 0, W, H, stroke=0, fill=1)
    # Cabecera granate (parte principal)
    c.setFillColor(VINO); c.rect(0, H - 26 * mm, xt, 26 * mm, stroke=0, fill=1)
    c.setFillColor(CREMA)
    r = 2.2 * mm; xx = r
    while xx < xt:
        c.circle(xx, H - 26 * mm, r, stroke=0, fill=1); xx += 2 * r
    c.setFillColor(ORO); c.setFont("Helvetica-Bold", 7.5)
    c.drawString(8 * mm, H - 9 * mm, "R E S G U A R D O")
    c.setFillColor(colors.HexColor("#fff6e6")); c.setFont("Times-Bold", 17)
    c.drawString(8 * mm, H - 17 * mm, aj["titulo"][:30])
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.HexColor("#f1e2bd"))
    c.drawRightString(xt - 7 * mm, H - 9 * mm, concepto)

    # Nombre
    c.setFillColor(TINTA)
    tam = _ajustar_fuente(persona["nombre"], "Times-Bold", 20, 10, xt - 16 * mm)
    c.setFont("Times-Bold", tam)
    c.drawString(8 * mm, H - 38 * mm, persona["nombre"])

    # Datos
    compra = dict(compra)
    if compra.get("pago_txt"):
        pago = compra["pago_txt"]
    else:
        pago = "Bizum" if compra["metodo"] == "bizum" else "En mano"
        if compra["receptor"]:
            pago += f" a {compra['receptor']}"
        if compra["metodo"] == "bizum" and compra["receptor_tel"]:
            pago += f" ({compra['receptor_tel']})"
    importe = compra.get("importe_cent", compra.get("cantidad", 0) * compra.get("precio_cent", 0))
    filas = [
        ("Papeletas", f"{compra['cantidad']}"),
        ("Importe", euros(importe)),
        ("Pago", pago),
    ]
    if compra.get("reservas"):
        filas.append(("Reservas", compra["reservas"]))
    else:
        filas.append(("Reservado", _fecha(compra["creado"])))
    if aj.get("fecha_sorteo"):
        filas.append(("Sorteo", aj["fecha_sorteo"][:40]))
    y = H - 47 * mm
    for k, v in filas:
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#7b675d"))
        c.drawString(8 * mm, y, k.upper())
        c.setFont("Helvetica-Bold", 9.5); c.setFillColor(TINTA)
        txt = v
        while stringWidth(txt, "Helvetica-Bold", 9.5) > xt - 36 * mm and len(txt) > 4:
            txt = txt[:-2]
        c.drawString(30 * mm, y, txt if txt == v else txt + "…")
        y -= 5.6 * mm

    # Estado (sello)
    estado = compra["estado"]
    texto, color = {"confirmado": ("PAGADO", colors.HexColor("#2e5a4c")),
                    "pendiente": ("PENDIENTE DE PAGO", colors.HexColor("#a67c1e")),
                    "rechazado": ("ANULADO", colors.HexColor("#b3261e"))}[estado]
    c.saveState()
    c.translate(xt - 24 * mm, 17 * mm)
    c.rotate(8)
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(1.4)
    tw = stringWidth(texto, "Helvetica-Bold", 9) + 8 * mm
    c.roundRect(-tw / 2, -4 * mm, tw, 8 * mm, 2 * mm)
    c.setFont("Helvetica-Bold", 9); c.drawCentredString(0, -1.2 * mm, texto)
    c.restoreState()

    c.setFont("Times-Italic", 7.5); c.setFillColor(colors.HexColor("#7b675d"))
    c.drawString(8 * mm, 6 * mm, "Cuentas claras, amigos eternos")

    # Separación troquelada
    c.setStrokeColor(colors.HexColor("#c8b9a6")); c.setLineWidth(0.7); c.setDash(2, 2.5)
    c.line(xt, 4 * mm, xt, H - 4 * mm); c.setDash()
    c.setFillColor(colors.white)
    c.circle(xt, H, 3 * mm, stroke=0, fill=1); c.circle(xt, 0, 3 * mm, stroke=0, fill=1)

    # Talón: QR al enlace personal
    cx = xt + talon / 2
    c.setFillColor(VINO); c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(cx, H - 10 * mm, "TUS PAPELETAS")
    lado = 34 * mm
    qr = QrCodeWidget(enlace, barLevel="M")
    b = qr.getBounds(); qw, qh = b[2] - b[0], b[3] - b[1]
    d = Drawing(lado, lado, transform=[lado / qw, 0, 0, lado / qh, 0, 0])
    qr.barFillColor = TINTA
    d.add(qr)
    c.setFillColor(colors.white)
    c.roundRect(cx - lado / 2 - 2 * mm, H - 14 * mm - lado - 2 * mm, lado + 4 * mm, lado + 4 * mm, 2 * mm, stroke=0, fill=1)
    renderPDF.draw(d, c, cx - lado / 2, H - 14 * mm - lado)
    c.setFont("Helvetica", 6.5); c.setFillColor(colors.HexColor("#5a4a42"))
    c.drawCentredString(cx, H - 55 * mm, "Escanéalo para ver tus")
    c.drawCentredString(cx, H - 58.5 * mm, "papeletas o comprar más")
    c.setFillColor(ORO); c.setFont("Times-Bold", 24)
    c.drawCentredString(cx, 20 * mm, str(total_confirmadas))
    c.setFont("Helvetica", 6.5); c.setFillColor(colors.HexColor("#5a4a42"))
    c.drawCentredString(cx, 15.5 * mm, "en la bolsa ahora mismo")
    # Enlace en texto (y clicable)
    c.setFont("Helvetica", 5); c.setFillColor(colors.HexColor("#7b675d"))
    corto = enlace.split("://", 1)[-1]
    mitad = len(corto) // 2
    c.drawCentredString(cx, 9 * mm, corto[:mitad])
    c.drawCentredString(cx, 6.5 * mm, corto[mitad:])
    c.linkURL(enlace, (xt, 0, W, H), relative=0)
    c.showPage()
    c.save()
    return buf.getvalue()
