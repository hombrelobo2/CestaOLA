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
