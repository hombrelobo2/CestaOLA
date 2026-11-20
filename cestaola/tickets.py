# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Tickets de compra de los lotes: guardar, validar y exportar."""
import csv
import io
import os
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime


def detectar_tipo(cabecera):
    """Por el contenido, no por la extensión (que el móvil a veces cambia)."""
    if cabecera[:4] == b"%PDF":
        return "pdf"
    if cabecera[:3] == b"\xff\xd8\xff":
        return "jpg"
    if cabecera[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return None


def guardar(fichero, carpeta):
    """Guarda un ticket subido. Devuelve (archivo, tipo) o (None, error)."""
    datos = fichero.read()
    tipo = detectar_tipo(datos[:8])
    if not tipo:
        return None, f"«{fichero.filename}» no es JPG, PNG ni PDF."
    nombre = uuid.uuid4().hex
    if tipo == "pdf":
        archivo = nombre + ".pdf"
        with open(os.path.join(carpeta, archivo), "wb") as f:
            f.write(datos)
    else:
        # Fotos del móvil: se giran bien y se reducen (un ticket se lee de sobra a 2400 px)
        from PIL import Image, ImageOps
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(datos)))
            img.thumbnail((2400, 2400))
            archivo = nombre + ".jpg"
            img.convert("RGB").save(os.path.join(carpeta, archivo), "JPEG", quality=88, optimize=True)
            tipo = "jpg"
        except Exception:
            return None, f"No se pudo leer la imagen «{fichero.filename}»."
    return archivo, tipo


def _slug(texto, largo=40):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return "-".join(re.sub(r"[^\w]+", " ", t).split())[:largo] or "ticket"


def exportar(tickets, carpeta, titulo, euros):
    """Zip con todos los tickets numerados y un índice (CSV para Excel + texto)."""
    buf = io.BytesIO()
    total = 0
    filas = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, t in enumerate(tickets, 1):
            ruta = os.path.join(carpeta, os.path.basename(t["archivo"]))
            if not os.path.exists(ruta):
                continue
            nombre = f"{n:02d}-{_slug(t['descripcion'] or t['lote'] or t['original'])}.{t['tipo']}"
            z.write(ruta, f"tickets/{nombre}", compress_type=zipfile.ZIP_STORED)
            total += t["importe_cent"] or 0
            filas.append((n, nombre, t["descripcion"], t["lote"] or "", t["importe_cent"], t["subido"][:16]))
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["n", "archivo", "descripcion", "lote", "importe", "subido"])
        for n, nombre, desc, lote, imp, sub in filas:
            w.writerow([n, nombre, desc, lote, "" if imp is None else f"{imp / 100:.2f}".replace(".", ","), sub])
        w.writerow(["", "", "TOTAL", "", f"{total / 100:.2f}".replace(".", ","), ""])
        z.writestr("indice.csv", "﻿" + out.getvalue())
        txt = [f"Tickets de compra · {titulo}", f"Exportado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""]
        for n, nombre, desc, lote, imp, sub in filas:
            txt.append(f"{n:2d}. {desc or '(sin descripción)'}" + (f" · lote: {lote}" if lote else "")
                       + (f" · {euros(imp)}" if imp is not None else "") + f"  [{nombre}]")
        txt += ["", f"Total: {euros(total)} en {len(filas)} ticket{'s' if len(filas) != 1 else ''}."]
        z.writestr("LEEME.txt", "\n".join(txt) + "\n")
    return buf.getvalue()
