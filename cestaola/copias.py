# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Exportar e importar todos los datos (base de datos + fotos) en un .zip."""
import hashlib
import io
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime

TABLAS = {"ajustes", "personas", "compras", "premios"}


def exportar(data_dir):
    """Devuelve los bytes de un .zip con una copia coherente de la base de datos y las fotos."""
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        copia = os.path.join(tmp, "cestaola.db")
        src = sqlite3.connect(os.path.join(data_dir, "cestaola.db"))
        dst = sqlite3.connect(copia)
        src.backup(dst)               # copia en caliente, segura aunque haya gente usando la web
        dst.close(); src.close()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia, "cestaola.db")
            fotos = os.path.join(data_dir, "fotos")
            for f in sorted(os.listdir(fotos)):
                if os.path.isfile(os.path.join(fotos, f)):
                    z.write(os.path.join(fotos, f), f"fotos/{f}", compress_type=zipfile.ZIP_STORED)
            z.writestr("LEEME.txt", "Copia de CestaOLA del " + datetime.now().strftime("%d/%m/%Y %H:%M")
                       + ".\nPara restaurarla: panel de admin > Ajustes > Importar copia.\n")
    return buf.getvalue()


def importar(data_dir, fichero):
    """Sustituye todos los datos por los del .zip. Antes guarda una copia automática.
    Devuelve (ok, mensaje)."""
    try:
        z = zipfile.ZipFile(fichero)
    except zipfile.BadZipFile:
        return False, "El archivo no es un .zip válido."
    nombres = z.namelist()
    if "cestaola.db" not in nombres:
        return False, "El .zip no contiene cestaola.db. ¿Es una copia exportada desde CestaOLA?"

    with tempfile.TemporaryDirectory() as tmp:
        nueva = os.path.join(tmp, "nueva.db")
        with open(nueva, "wb") as f:
            f.write(z.read("cestaola.db"))
        try:
            con = sqlite3.connect(nueva)
            tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            integra = con.execute("PRAGMA integrity_check").fetchone()[0]
            n = con.execute("SELECT COUNT(*) FROM compras").fetchone()[0] if "compras" in tablas else 0
            con.close()
        except sqlite3.DatabaseError:
            return False, "cestaola.db está dañada o no es una base de datos."
        if not TABLAS <= tablas:
            return False, "La base de datos no es de CestaOLA (faltan tablas)."
        if integra != "ok":
            return False, "La base de datos está dañada (integrity_check)."

        # Copia automática de lo que hay ahora, por si acaso
        dir_copias = os.path.join(data_dir, "copias")
        os.makedirs(dir_copias, exist_ok=True)
        previa = os.path.join(dir_copias, f"antes-de-importar-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip")
        with open(previa, "wb") as f:
            f.write(exportar(data_dir))

        # Base de datos: se vuelca dentro de la actual (seguro con la web en marcha)
        src = sqlite3.connect(nueva)
        dst = sqlite3.connect(os.path.join(data_dir, "cestaola.db"))
        src.backup(dst)
        dst.close(); src.close()

    # Fotos: se sustituyen por las del .zip
    fotos = os.path.join(data_dir, "fotos")
    for f in os.listdir(fotos):
        if os.path.isfile(os.path.join(fotos, f)):
            os.remove(os.path.join(fotos, f))
    n_fotos = 0
    for nombre in nombres:
        if nombre.startswith("fotos/") and not nombre.endswith("/"):
            base = os.path.basename(nombre)
            if base and not base.startswith(".") and base.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                with open(os.path.join(fotos, base), "wb") as f:
                    f.write(z.read(nombre))
                n_fotos += 1
    return True, (f"Copia importada: {n} reservas y {n_fotos} fotos. "
                  f"Lo que había antes está guardado en el servidor en copias/{os.path.basename(previa)}.")


def resumen(data_dir):
    con = sqlite3.connect(os.path.join(data_dir, "cestaola.db"))
    n = con.execute("SELECT COUNT(*) FROM compras WHERE estado!='rechazado'").fetchone()[0]
    p = con.execute("SELECT COALESCE(SUM(cantidad),0) FROM compras WHERE estado='confirmado'").fetchone()[0]
    con.close()
    return n, p


def huella(data_dir):
    """Cambia si cambian los datos o las fotos (para no mandar copias repetidas)."""
    h = hashlib.sha256()
    con = sqlite3.connect(os.path.join(data_dir, "cestaola.db"))
    for linea in con.iterdump():
        if "telegram_" not in linea:      # la huella y los ajustes de Telegram no cuentan como cambios
            h.update(linea.encode())
    con.close()
    fotos = os.path.join(data_dir, "fotos")
    for f in sorted(os.listdir(fotos)):
        h.update(f.encode())
    return h.hexdigest()
