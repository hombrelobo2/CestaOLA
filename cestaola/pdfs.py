"""Generación de PDFs: papeletas para la bolsa y cartel de lotes."""
import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from xml.sax.saxutils import escape


def _euros(cent):
    from . import euros
    return euros(cent)


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


def _fondo_premios(aj):
    """Banda de cabecera granate con título y pie con adorno, en cada página."""
    def pintar(c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(CREMA)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        if doc.page == 1:
            c.setFillColor(VINO)
            c.rect(0, h - 48 * mm, w, 48 * mm, stroke=0, fill=1)
            # festón
            c.setFillColor(CREMA)
            r = 4 * mm
            xx = 0
            while xx < w + r:
                c.circle(xx, h - 48 * mm, r, stroke=0, fill=1)
                xx += 2 * r
            c.setFillColor(ORO)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(15 * mm, h - 15 * mm, "L O T E S   D E L   S O R T E O")
            c.setFillColor(colors.HexColor("#fff6e6"))
            c.setFont("Times-Bold", 28)
            c.drawString(15 * mm, h - 28 * mm, aj["titulo"][:42])
            if aj.get("fecha_sorteo"):
                c.setFont("Helvetica", 10)
                c.setFillColor(colors.HexColor("#f1e2bd"))
                c.drawString(15 * mm, h - 36 * mm, "Sorteo: " + aj["fecha_sorteo"][:70])
        else:
            c.setFillColor(VINO)
            c.rect(0, h - 6 * mm, w, 6 * mm, stroke=0, fill=1)
        c.setStrokeColor(ORO)
        c.setLineWidth(0.6)
        c.line(15 * mm, 11 * mm, w - 15 * mm, 11 * mm)
        c.setFont("Times-Italic", 8.5)
        c.setFillColor(colors.HexColor("#7b675d"))
        c.drawString(15 * mm, 7 * mm, "Cuentas claras, amigos eternos")
        c.drawRightString(w - 15 * mm, 7 * mm, f"Página {doc.page}")
        c.restoreState()
    return pintar


def _sin_foto(w, h):
    t = Table([[Paragraph("sin foto", ParagraphStyle("x", fontName="Times-Italic", fontSize=12,
                                                      alignment=1, textColor=ORO))]],
              colWidths=[w], rowHeights=[h])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1e2bd")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def pdf_premios(aj, premios, res, carpeta_fotos, mostrar_ganadores):
    """Cartel/listado de lotes con foto, descripción, precio y (opcional) ganador."""
    buf = io.BytesIO()
    pintar = _fondo_premios(aj)
    doc = BaseDocTemplate(buf, pagesize=A4, title=f"Lotes - {aj['titulo']}")
    w, h = A4
    doc.addPageTemplates([
        PageTemplate(id="primera", onPage=pintar, autoNextPageTemplate="resto",
                     frames=[Frame(15 * mm, 16 * mm, w - 30 * mm, h - 16 * mm - 58 * mm, id="f1")]),
        PageTemplate(id="resto", onPage=pintar,
                     frames=[Frame(15 * mm, 16 * mm, w - 30 * mm, h - 16 * mm - 14 * mm, id="f2")]),
    ])
    st_nom = ParagraphStyle("n", fontName="Times-Bold", fontSize=15, leading=18, textColor=TINTA)
    st_desc = ParagraphStyle("d", fontName="Helvetica", fontSize=9.5, leading=13,
                             textColor=colors.HexColor("#5a4a42"))
    st_prec = ParagraphStyle("p", fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=2, textColor=VINO)
    st_gan = ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                            textColor=colors.HexColor("#2e5a4c"))
    st_h = ParagraphStyle("h", fontName="Times-Bold", fontSize=16, leading=20, textColor=VINO)
    st_pie = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11,
                            textColor=colors.HexColor("#7b675d"))

    ancho_util = A4[0] - 30 * mm
    foto_w, foto_h = 56 * mm, 42 * mm
    el = []

    def recorte(ruta):
        """Recorta la foto a 4:3 (como en la web) para que todas queden iguales."""
        from PIL import Image as PILImage
        im = PILImage.open(ruta)
        iw, ih = im.size
        objetivo = foto_w / foto_h
        if iw / ih > objetivo:
            nw = int(ih * objetivo); x0 = (iw - nw) // 2; im = im.crop((x0, 0, x0 + nw, ih))
        else:
            nh = int(iw / objetivo); y0 = (ih - nh) // 2; im = im.crop((0, y0, iw, y0 + nh))
        b = io.BytesIO()
        im.convert("RGB").save(b, "JPEG", quality=88)
        b.seek(0)
        return Image(b, width=foto_w, height=foto_h)

    for n, p in enumerate(premios, 1):
        img = _sin_foto(foto_w, foto_h)
        if p["foto"]:
            ruta = os.path.join(carpeta_fotos, os.path.basename(p["foto"]))
            if os.path.exists(ruta):
                try:
                    img = recorte(ruta)
                except Exception:
                    pass
        texto = [Paragraph(f"<font color='#c49a45'>{n}.</font> {escape(p['nombre'])}", st_nom)]
        if p["descripcion"]:
            texto.append(Spacer(1, 2 * mm))
            texto.append(Paragraph(escape(p["descripcion"]).replace("\n", "<br/>"), st_desc))
        if mostrar_ganadores and p["ganador_nombre"]:
            texto.append(Spacer(1, 3 * mm))
            texto.append(Paragraph(f"Premiado/a: {escape(p['ganador_nombre'])}", st_gan))
        t = Table([[img, texto, Paragraph(_euros(p["precio_cent"]), st_prec)]],
                  colWidths=[foto_w + 6 * mm, ancho_util - foto_w - 6 * mm - 30 * mm, 30 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e7d9c4")),
            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("LEFTPADDING", (1, 0), (1, 0), 2 * mm),
        ]))
        el += [KeepTogether(t), Spacer(1, 4 * mm)]

    if not premios:
        el.append(Paragraph("Todavía no hay lotes.", st_desc))

    # Cuentas claras
    balance = res["balance"]
    filas = [
        ["Valor real de los lotes", _euros(res["coste"])],
        [f"Recaudado ({res['papeletas']} papeletas confirmadas)", _euros(res["recaudado"])],
        ["Sobra" if balance >= 0 else "Falta para cubrir los lotes", _euros(abs(balance))],
    ]
    tc = Table(filas, colWidths=[ancho_util - 45 * mm, 45 * mm])
    tc.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (1, -1), (1, -1), colors.HexColor("#2e5a4c") if balance >= 0 else colors.HexColor("#b3261e")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, TINTA),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e7d9c4")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
    ]))
    el.append(KeepTogether([Spacer(1, 4 * mm), Paragraph("Cuentas claras", st_h), Spacer(1, 3 * mm), tc,
                            Spacer(1, 3 * mm),
                            Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}", st_pie)]))
    doc.build(el)
    return buf.getvalue()
