"""Acceso a SQLite: esquema, ajustes y consultas comunes."""
import os
import secrets
import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    creado TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_cent INTEGER NOT NULL,
    metodo TEXT NOT NULL CHECK (metodo IN ('bizum','mano')),
    estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','confirmado','rechazado')),
    nota TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    confirmado TEXT
);

CREATE TABLE IF NOT EXISTS premios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    precio_cent INTEGER NOT NULL DEFAULT 0,
    foto TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    ganador_id INTEGER REFERENCES personas(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_compras_persona ON compras(persona_id);
"""

DEFAULTS = {
    "titulo": "Sorteo de la Cesta",
    "texto": "¡Participa en el sorteo de la cesta de este año! Cada papeleta va a la bolsa con tu nombre.",
    "precio_cent": "200",
    "bizum_telefono": "",
    "bizum_titular": "",
    "prefijo": "CESTA",
    "max_por_compra": "50",
    "fecha_sorteo": "",
    "estado": "abierta",          # abierta | cerrada
    "publicar_ganadores": "0",
}


def get_db():
    if "db" not in g:
        path = os.path.join(current_app.config["DATA_DIR"], "cestaola.db")
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.config["DATA_DIR"], "fotos"), exist_ok=True)
    con = sqlite3.connect(os.path.join(app.config["DATA_DIR"], "cestaola.db"))
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    for k, v in DEFAULTS.items():
        con.execute("INSERT OR IGNORE INTO ajustes (clave, valor) VALUES (?, ?)", (k, v))
    con.commit()
    con.close()


def ajustes():
    rows = get_db().execute("SELECT clave, valor FROM ajustes").fetchall()
    a = dict(DEFAULTS)
    a.update({r["clave"]: r["valor"] for r in rows})
    a["precio_cent"] = int(a["precio_cent"] or 0)
    a["max_por_compra"] = int(a["max_por_compra"] or 50)
    a["abierta"] = a["estado"] == "abierta"
    a["publicar_ganadores"] = a["publicar_ganadores"] == "1"
    return a


def guardar_ajuste(clave, valor):
    get_db().execute(
        "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, str(valor)),
    )


def nuevo_token():
    return secrets.token_urlsafe(16)


def persona_por_token(token):
    if not token:
        return None
    return get_db().execute("SELECT * FROM personas WHERE token = ?", (token,)).fetchone()


def premios():
    return get_db().execute(
        "SELECT p.*, pe.nombre AS ganador_nombre FROM premios p "
        "LEFT JOIN personas pe ON pe.id = p.ganador_id ORDER BY p.orden, p.id"
    ).fetchall()


def personas_con_totales():
    """Cada persona con sus papeletas confirmadas, pendientes y lo pagado."""
    return get_db().execute(
        """
        SELECT pe.*,
          COALESCE(SUM(CASE WHEN c.estado='confirmado' THEN c.cantidad END),0) AS confirmadas,
          COALESCE(SUM(CASE WHEN c.estado='pendiente' THEN c.cantidad END),0) AS pendientes,
          COALESCE(SUM(CASE WHEN c.estado='confirmado' THEN c.cantidad*c.precio_cent END),0) AS pagado_cent,
          COUNT(c.id) AS n_compras
        FROM personas pe LEFT JOIN compras c ON c.persona_id = pe.id
        GROUP BY pe.id ORDER BY pe.nombre COLLATE NOCASE
        """
    ).fetchall()


def resumen():
    db = get_db()
    r = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN estado='confirmado' THEN cantidad*precio_cent END),0) AS recaudado,
          COALESCE(SUM(CASE WHEN estado='pendiente' THEN cantidad*precio_cent END),0) AS pendiente,
          COALESCE(SUM(CASE WHEN estado='confirmado' THEN cantidad END),0) AS papeletas,
          COALESCE(SUM(CASE WHEN estado='pendiente' THEN cantidad END),0) AS papeletas_pend,
          COUNT(DISTINCT CASE WHEN estado='confirmado' THEN persona_id END) AS personas
        FROM compras
        """
    ).fetchone()
    coste = db.execute("SELECT COALESCE(SUM(precio_cent),0) FROM premios").fetchone()[0]
    d = dict(r)
    d["coste"] = coste
    d["balance"] = d["recaudado"] - coste
    return d
