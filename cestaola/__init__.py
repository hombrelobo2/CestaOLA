# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""CestaOLA: web para el sorteo de la cesta de la empresa."""
import csv
import hmac
import io
import json
import os
import re
import secrets
import unicodedata
import uuid
from urllib.parse import quote
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, g, make_response, redirect,
                   render_template, request, send_from_directory, session, url_for)

from . import db as D
from . import pdfs
from . import telegram
from . import copias
from . import tickets as T

COOKIE = "cestaola_persona"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def version():
    """('1.0.0', '04241ac'). Lee VERSION y el commit desde .git sin ejecutar git
    (el servicio corre con otro usuario y git se negaría por 'dubious ownership')."""
    try:
        num = open(os.path.join(RAIZ, "VERSION")).read().strip()
    except OSError:
        num = "?"
    commit = ""
    try:
        git = os.path.join(RAIZ, ".git")
        head = open(os.path.join(git, "HEAD")).read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            ruta = os.path.join(git, ref)
            if os.path.exists(ruta):
                commit = open(ruta).read().strip()
            else:
                for linea in open(os.path.join(git, "packed-refs")):
                    if linea.strip().endswith(" " + ref):
                        commit = linea.split()[0]
        else:
            commit = head
    except OSError:
        pass
    return num, commit[:7]
FOTO_EXT = {"jpg", "jpeg", "png", "webp", "heic", "heif", "gif"}


def euros(cent):
    """1234 -> '12,34 €' (formato español)."""
    cent = int(cent or 0)
    signo = "-" if cent < 0 else ""
    cent = abs(cent)
    e, c = divmod(cent, 100)
    miles = f"{e:,}".replace(",", ".")
    return f"{signo}{miles},{c:02d} €"


def telefono_wa(tel):
    """'600 11 22 33' / '+34 600...' / '0034...' -> '34600112233' (formato de wa.me). '' si no vale."""
    d = re.sub(r"\D", "", tel or "")
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 9 and d[0] in "6789":      # número español sin prefijo
        d = "34" + d
    return d if 10 <= len(d) <= 15 else ""


def limpiar_telefono(tel):
    return " ".join((tel or "").split())[:20]


def a_cent(texto):
    """'12,5' / '12.50' / '12' -> 1250. Devuelve None si no es válido."""
    t = (texto or "").strip().replace("€", "").replace(" ", "")
    if not t:
        return 0
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = round(float(t) * 100)
    except ValueError:
        return None
    return v if v >= 0 else None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATA_DIR=os.environ.get("CESTAOLA_DATA", os.path.join(os.getcwd(), "data")),
        SECRET_KEY=os.environ.get("CESTAOLA_SECRET_KEY") or secrets.token_hex(32),
        ADMIN_PASSWORD=os.environ.get("CESTAOLA_ADMIN_PASSWORD", ""),
        BASE_URL=os.environ.get("CESTAOLA_BASE_URL", "").rstrip("/"),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CESTAOLA_COOKIE_SECURE", "1") == "1",
    )
    if test_config:
        app.config.update(test_config)

    # Detrás de un proxy inverso (Nginx Proxy Manager, Cloudflare Tunnel, Caddy...)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    D.init_db(app)
    app.teardown_appcontext(D.close_db)
    app.jinja_env.filters["euros"] = euros
    app.config["VERSION"], app.config["COMMIT"] = version()
    app.jinja_env.globals["version"] = app.config["VERSION"]
    app.jinja_env.globals["commit"] = app.config["COMMIT"]

    # ---------------------------------------------------------------- utilidades
    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(24)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def comprobar_csrf():
        if request.method == "POST":
            enviado = request.form.get("_csrf", "")
            if not enviado or not hmac.compare_digest(enviado, session.get("_csrf", "")):
                abort(400, "La sesión ha caducado. Vuelve atrás, recarga la página e inténtalo de nuevo.")

    @app.context_processor
    def comunes():
        if "aj" not in g:
            g.aj = D.ajustes()
        return {"aj": g.aj, "es_admin": session.get("admin", False)}

    def url_externa(endpoint, **kw):
        if app.config["BASE_URL"]:
            return app.config["BASE_URL"] + url_for(endpoint, **kw)
        return url_for(endpoint, _external=True, **kw)

    def concepto(compra_id):
        if "aj" not in g:
            g.aj = D.ajustes()
        return f"{g.aj['prefijo']}-{compra_id:04d}"

    app.jinja_env.globals["concepto"] = concepto

    def whatsapp(nombre, telefono, token, compra=None, en_bolsa=None):
        """Enlace wa.me que abre el chat de esa persona con el mensaje y el enlace al resguardo ya escritos."""
        num = telefono_wa(telefono)
        if not num:
            return ""
        aj = g.aj if "aj" in g else D.ajustes()
        nombre_pila = (nombre or "").split()[0] if nombre else ""
        if compra is not None:
            estado = {"confirmado": "pagado ✅", "pendiente": "pendiente de pago", "rechazado": "anulado"}[compra["estado"]]
            n = compra["cantidad"]
            linea = (f"Tu resguardo del {aj['titulo']}: {concepto(compra['id'])}, {n} papeleta{'s' if n != 1 else ''}, "
                     f"{euros(n * compra['precio_cent'])} ({estado}).")
            pdf = url_externa("resguardo", token=token, cid=compra["id"])
        else:
            linea = f"Tu resguardo del {aj['titulo']}" + (f" ({en_bolsa} papeleta{'s' if en_bolsa != 1 else ''} en la bolsa)." if en_bolsa is not None else ".")
            pdf = url_externa("resguardo_total", token=token)
        texto = f"Hola {nombre_pila} 👋\n{linea}\n📄 {pdf}\n🎟️ Tus papeletas: {url_externa('mi', token=token)}"
        return f"https://wa.me/{num}?text={quote(texto)}"

    app.jinja_env.globals["whatsapp"] = whatsapp

    def nombre_resguardo(nombre, sufijo):
        """Siempre igual: resguardo-Nombre-Apellido-CESTA-0017 (o ...-resumen si junta varias reservas)."""
        base = "-".join(re.sub(r"[^\w]+", " ", nombre).split())[:50] or "participante"
        return f"resguardo-{base}-{sufijo}"
    app.jinja_env.globals["ahora"] = lambda: datetime.now().strftime("%H%M%S")

    def solo_admin(f):
        @wraps(f)
        def w(*a, **kw):
            if not session.get("admin"):
                return redirect(url_for("admin_login", siguiente=request.path))
            return f(*a, **kw)
        return w

    def guardar_foto(fichero):
        """Guarda la foto reducida a 1600 px en JPEG. Devuelve el nombre o None."""
        if not fichero or not fichero.filename:
            return None
        ext = fichero.filename.rsplit(".", 1)[-1].lower() if "." in fichero.filename else ""
        if ext not in FOTO_EXT:
            flash("Formato de foto no admitido (usa JPG, PNG o WEBP).", "error")
            return None
        from PIL import Image, ImageOps
        try:
            img = Image.open(fichero.stream)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((1600, 1600))
            if img.mode not in ("RGB", "L"):
                fondo = Image.new("RGB", img.size, (255, 255, 255))
                fondo.paste(img, mask=img.convert("RGBA").split()[-1])
                img = fondo
            nombre = f"{uuid.uuid4().hex}.jpg"
            img.convert("RGB").save(os.path.join(app.config["DATA_DIR"], "fotos", nombre),
                                    "JPEG", quality=85, optimize=True)
            return nombre
        except Exception:
            flash("No se pudo leer la foto. Prueba con otra en JPG o PNG.", "error")
            return None

    def borrar_foto(nombre):
        if nombre:
            ruta = os.path.join(app.config["DATA_DIR"], "fotos", os.path.basename(nombre))
            if os.path.exists(ruta):
                os.remove(ruta)

    # ---------------------------------------------------------------- público
    @app.get("/")
    def inicio():
        persona = D.persona_por_token(request.cookies.get(COOKIE))
        mis = None
        if persona:
            mis = D.get_db().execute(
                "SELECT COALESCE(SUM(CASE WHEN estado='confirmado' THEN cantidad END),0) c, "
                "COALESCE(SUM(CASE WHEN estado='pendiente' THEN cantidad END),0) p "
                "FROM compras WHERE persona_id=?", (persona["id"],)).fetchone()
        return render_template("inicio.html", premios=D.premios(), res=D.resumen(),
                               persona=persona, mis=mis)

    @app.post("/participar")
    def participar():
        aj = D.ajustes()
        if not aj["abierta"]:
            flash("La venta de papeletas está cerrada.", "error")
            return redirect(url_for("inicio"))
        if request.form.get("web"):          # trampa para bots
            return redirect(url_for("inicio"))
        token = request.form.get("token", "")
        persona = D.persona_por_token(token) if token else None
        nombre = " ".join((request.form.get("nombre") or "").split())[:60]
        pago = D.opcion_pago(aj, request.form.get("pago", ""))
        try:
            cantidad = int(request.form.get("cantidad", "0"))
        except ValueError:
            cantidad = 0
        destino = url_for("mi", token=persona["token"]) if persona else url_for("inicio")
        telefono = limpiar_telefono(request.form.get("telefono"))
        if not persona and len(nombre) < 2:
            flash("Escribe tu nombre (y apellido, para no confundirte con otro compañero).", "error")
            return redirect(destino + "#participar")
        if not persona and not telefono_wa(telefono):
            flash("Escribe tu teléfono móvil (para mandarte el resguardo por WhatsApp).", "error")
            return redirect(destino + "#participar")
        if cantidad < 1 or cantidad > aj["max_por_compra"]:
            flash(f"Elige entre 1 y {aj['max_por_compra']} papeletas.", "error")
            return redirect(destino + "#participar")
        if not pago:
            flash("Elige cómo y a quién vas a pagar.", "error")
            return redirect(destino + "#participar")
        db = D.get_db()
        if not persona:
            token = D.nuevo_token()
            cur = db.execute("INSERT INTO personas (nombre, token, telefono) VALUES (?, ?, ?)", (nombre, token, telefono))
            persona_id = cur.lastrowid
        else:
            persona_id, token = persona["id"], persona["token"]
        cur = db.execute(
            "INSERT INTO compras (persona_id, cantidad, precio_cent, metodo, receptor, receptor_tel) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (persona_id, cantidad, aj["precio_cent"], pago["metodo"], pago["nombre"], pago["tel"]))
        db.commit()
        importe = euros(cantidad * aj["precio_cent"])
        telegram.enviar_en_segundo_plano(
            aj["telegram_token"], aj["telegram_chats"],
            telegram.mensaje_reserva(aj, (persona["nombre"] if persona else nombre)
                                     + (f" · {persona['telefono'] if persona else telefono}" if (persona["telefono"] if persona else telefono) else ""),
                                     cantidad, importe,
                                     concepto(cur.lastrowid), pago,
                                     url_externa("admin", estado="pendiente", quien=f"{pago['metodo']}|{pago['nombre']}"),
                                     nueva_persona=not persona))
        resp = make_response(redirect(url_for("mi", token=token, nueva=cur.lastrowid)))
        recordar_persona(resp, token, sustituir=True)
        return resp

    def recordar_persona(resp, token, sustituir):
        """El móvil recuerda a quién pertenece para saludarle y sumar papeletas a su nombre.
        - Nunca en el móvil de un organizador con sesión abierta: abre enlaces de otros a diario.
        - Al abrir un enlace personal no se pisa a quien ya estaba recordado (enlaces reenviados).
        - Al reservar (sustituir=True) sí: quien reserva en ese móvil es esa persona."""
        if session.get("admin"):
            return
        if not sustituir and D.persona_por_token(request.cookies.get(COOKIE)):
            return
        resp.set_cookie(COOKIE, token, max_age=3600 * 24 * 400, httponly=True, samesite="Lax",
                        secure=app.config["SESSION_COOKIE_SECURE"])

    @app.get("/mi/<token>")
    def mi(token):
        persona = D.persona_por_token(token)
        if not persona:
            abort(404, "Este enlace no corresponde a ninguna participación.")
        compras = D.get_db().execute(
            "SELECT * FROM compras WHERE persona_id=? ORDER BY id DESC", (persona["id"],)).fetchall()
        confirmadas = sum(c["cantidad"] for c in compras if c["estado"] == "confirmado")
        pendientes = sum(c["cantidad"] for c in compras if c["estado"] == "pendiente")
        premiado = [p for p in D.premios() if p["ganador_id"] == persona["id"]]
        nueva = request.args.get("nueva", type=int)
        resp = make_response(render_template(
            "mi.html", persona=persona, compras=compras, confirmadas=confirmadas,
            pendientes=pendientes, enlace=url_externa("mi", token=token), nueva=nueva,
            premiado=premiado))
        recordar_persona(resp, token, sustituir=False)
        return resp

    @app.get("/mi/<token>/resguardo")
    def resguardo_total(token):
        """Resguardo con todas las reservas (no anuladas) de una persona."""
        persona = D.persona_por_token(token)
        if not persona:
            abort(404)
        compras = D.get_db().execute(
            "SELECT * FROM compras WHERE persona_id=? AND estado!='rechazado' ORDER BY id", (persona["id"],)).fetchall()
        if not compras:
            abort(404, "Esta persona no tiene reservas.")
        if len(compras) == 1:
            return resguardo(token, compras[0]["id"])
        conf = sum(c["cantidad"] for c in compras if c["estado"] == "confirmado")
        formas = {("Bizum" if c["metodo"] == "bizum" else "En mano") + (f" a {c['receptor']}" if c["receptor"] else "")
                  for c in compras}
        resumen = {
            "cantidad": sum(c["cantidad"] for c in compras),
            "importe_cent": sum(c["cantidad"] * c["precio_cent"] for c in compras),
            "pago_txt": formas.pop() if len(formas) == 1 else "Varias formas de pago",
            "reservas": " · ".join(concepto(c["id"]) for c in compras),
            "estado": "confirmado" if all(c["estado"] == "confirmado" for c in compras) else "pendiente",
            "creado": compras[-1]["creado"],
        }
        datos = pdfs.pdf_resguardo(D.ajustes(), persona, resumen, "RESUMEN",
                                   url_externa("mi", token=token), conf)
        return enviar_pdf(datos, nombre_resguardo(persona["nombre"], "resumen"), con_hora=False)

    @app.get("/mi/<token>/resguardo/<int:cid>")
    def resguardo(token, cid):
        persona = D.persona_por_token(token)
        if not persona:
            abort(404)
        db = D.get_db()
        compra = db.execute("SELECT * FROM compras WHERE id=? AND persona_id=?", (cid, persona["id"])).fetchone()
        if not compra:
            abort(404)
        total = db.execute("SELECT COALESCE(SUM(cantidad),0) FROM compras WHERE persona_id=? AND estado='confirmado'",
                           (persona["id"],)).fetchone()[0]
        datos = pdfs.pdf_resguardo(D.ajustes(), persona, compra, concepto(cid),
                                   url_externa("mi", token=token), total)
        return enviar_pdf(datos, nombre_resguardo(persona["nombre"], concepto(cid)), con_hora=False)

    @app.post("/mi/<token>/cambiar-pago/<int:cid>")
    def cambiar_pago(token, cid):
        persona = D.persona_por_token(token)
        if not persona:
            abort(404)
        pago = D.opcion_pago(D.ajustes(), request.form.get("pago", ""))
        if pago:
            D.get_db().execute(
                "UPDATE compras SET metodo=?, receptor=?, receptor_tel=? "
                "WHERE id=? AND persona_id=? AND estado='pendiente'",
                (pago["metodo"], pago["nombre"], pago["tel"], cid, persona["id"]))
            D.get_db().commit()
            flash("Forma de pago cambiada.", "ok")
        return redirect(url_for("mi", token=token))

    @app.get("/olvidar")
    def olvidar():
        resp = make_response(redirect(url_for("inicio")))
        resp.delete_cookie(COOKIE)
        return resp

    @app.get("/fotos/<path:nombre>")
    def foto(nombre):
        return send_from_directory(os.path.join(app.config["DATA_DIR"], "fotos"),
                                   os.path.basename(nombre), max_age=86400 * 30)


    # ---------------------------------------------------------------- admin
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            clave = app.config["ADMIN_PASSWORD"]
            dada = request.form.get("clave", "")
            if clave and hmac.compare_digest(dada.encode(), clave.encode()):
                session.clear()
                session["admin"] = True
                session.permanent = True
                sig = request.args.get("siguiente", "")
                return redirect(sig if sig.startswith("/admin") else url_for("admin"))
            flash("Contraseña incorrecta." if clave else
                  "No hay contraseña de administración configurada (CESTAOLA_ADMIN_PASSWORD).", "error")
        return render_template("admin/login.html")

    @app.get("/admin/salir")
    def admin_salir():
        session.clear()
        resp = make_response(redirect(url_for("inicio")))
        resp.delete_cookie(COOKIE)          # olvida también a quién «era» este móvil
        return resp

    @app.get("/admin")
    @solo_admin
    def admin():
        filtro = request.args.get("estado", "pendiente")
        quien = request.args.get("quien")   # "bizum|Ana" o "mano|Luis"
        sql = ("SELECT c.*, pe.nombre, pe.token, pe.telefono FROM compras c JOIN personas pe ON pe.id=c.persona_id WHERE 1=1 ")
        args = []
        if filtro in ("pendiente", "confirmado", "rechazado"):
            sql += "AND c.estado=? "
            args.append(filtro)
        if quien and "|" in quien:
            m, r = quien.split("|", 1)
            sql += "AND c.metodo=? AND c.receptor=? "
            args += [m, r]
        sql += "ORDER BY c.id DESC"
        compras = D.get_db().execute(sql, args).fetchall()
        personas = D.personas_con_totales()
        # Avisos de nombres repetidos (posibles duplicados)
        vistos, repetidos = {}, set()
        for p in personas:
            k = p["nombre"].casefold()
            if k in vistos:
                repetidos.add(k)
            vistos[k] = True
        ultima = None
        if session.get("ultima_alta"):
            ultima = D.get_db().execute(
                "SELECT c.*, pe.nombre, pe.token, pe.telefono FROM compras c JOIN personas pe ON pe.id=c.persona_id WHERE c.id=?",
                (session.pop("ultima_alta"),)).fetchone()
        return render_template("admin/panel.html", compras=compras, filtro=filtro, quien=quien, ultima=ultima,
                               url_mi=lambda t: url_externa("mi", token=t),
                               res=D.resumen(), personas=personas, repetidos=repetidos,
                               receptores=D.por_receptor())

    @app.post("/admin/compra/<int:cid>/<accion>")
    @solo_admin
    def admin_compra(cid, accion):
        db = D.get_db()
        if accion == "confirmar":
            db.execute("UPDATE compras SET estado='confirmado', confirmado=? WHERE id=?",
                       (datetime.now().strftime("%Y-%m-%d %H:%M"), cid))
        elif accion == "rechazar":
            db.execute("UPDATE compras SET estado='rechazado', confirmado=NULL WHERE id=?", (cid,))
        elif accion == "pendiente":
            db.execute("UPDATE compras SET estado='pendiente', confirmado=NULL WHERE id=?", (cid,))
        elif accion == "borrar":
            db.execute("DELETE FROM compras WHERE id=?", (cid,))
        elif accion == "nota":
            db.execute("UPDATE compras SET nota=? WHERE id=?",
                       ((request.form.get("nota") or "")[:200], cid))
        else:
            abort(404)
        db.commit()
        return redirect(request.form.get("volver") or url_for("admin"))

    @app.post("/admin/compra/nueva")
    @solo_admin
    def admin_compra_nueva():
        """Alta manual (alguien que te da el dinero en mano y no usa la web)."""
        aj = D.ajustes()
        db = D.get_db()
        try:
            cantidad = int(request.form.get("cantidad", "0"))
        except ValueError:
            cantidad = 0
        pid = request.form.get("persona_id", type=int)
        nombre = " ".join((request.form.get("nombre") or "").split())[:60]
        pago = D.opcion_pago(aj, request.form.get("pago", "")) or aj["opciones_pago"][-1]
        if cantidad < 1 or (not pid and len(nombre) < 2):
            flash("Indica nombre (o persona existente) y número de papeletas.", "error")
            return redirect(url_for("admin"))
        if not pid:
            pid = db.execute("INSERT INTO personas (nombre, token, telefono) VALUES (?, ?, ?)",
                             (nombre, D.nuevo_token(), limpiar_telefono(request.form.get("telefono")))).lastrowid
        elif request.form.get("telefono", "").strip():
            db.execute("UPDATE personas SET telefono=? WHERE id=?", (limpiar_telefono(request.form.get("telefono")), pid))
        estado = "confirmado" if request.form.get("confirmada") else "pendiente"
        cur = db.execute("INSERT INTO compras (persona_id, cantidad, precio_cent, metodo, receptor, receptor_tel, "
                   "estado, confirmado, nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'alta manual')",
                   (pid, cantidad, aj["precio_cent"], pago["metodo"], pago["nombre"], pago["tel"], estado,
                    datetime.now().strftime("%Y-%m-%d %H:%M") if estado == "confirmado" else None))
        db.commit()
        session["ultima_alta"] = cur.lastrowid
        return redirect(url_for("admin", estado="todas"))

    @app.post("/admin/persona/<int:pid>")
    @solo_admin
    def admin_persona(pid):
        db = D.get_db()
        if request.form.get("accion") == "borrar":
            db.execute("DELETE FROM personas WHERE id=?", (pid,))
            flash("Persona y sus compras borradas.", "ok")
        else:
            nombre = " ".join((request.form.get("nombre") or "").split())[:60]
            if len(nombre) >= 2:
                db.execute("UPDATE personas SET nombre=? WHERE id=?", (nombre, pid))
            if "telefono" in request.form:
                db.execute("UPDATE personas SET telefono=? WHERE id=?", (limpiar_telefono(request.form.get("telefono")), pid))
        db.commit()
        return redirect(url_for("admin", estado=request.form.get("estado", "pendiente")) + "#personas")

    @app.get("/admin/premios")
    @solo_admin
    def admin_premios():
        tks = D.tickets()
        return render_template("admin/premios.html", premios=D.premios(), res=D.resumen(), tickets=tks,
                               total_tickets=sum(t["importe_cent"] or 0 for t in tks))

    @app.route("/admin/premios/nuevo", methods=["GET", "POST"])
    @app.route("/admin/premios/<int:pid>", methods=["GET", "POST"])
    @solo_admin
    def admin_premio(pid=None):
        db = D.get_db()
        premio = db.execute("SELECT * FROM premios WHERE id=?", (pid,)).fetchone() if pid else None
        if pid and not premio:
            abort(404)
        if request.method == "POST":
            if request.form.get("accion") == "borrar" and premio:
                borrar_foto(premio["foto"])
                db.execute("DELETE FROM premios WHERE id=?", (pid,))
                db.commit()
                flash("Lote borrado.", "ok")
                return redirect(url_for("admin_premios"))
            nombre = (request.form.get("nombre") or "").strip()[:120]
            descripcion = (request.form.get("descripcion") or "").strip()[:4000]
            precio = a_cent(request.form.get("precio"))
            orden = request.form.get("orden", type=int) or 0
            if not nombre or precio is None:
                flash("Pon un nombre y un precio válido (por ejemplo 35,90).", "error")
                return render_template("admin/premio.html", premio=premio, form=request.form)
            foto = premio["foto"] if premio else None
            nueva = guardar_foto(request.files.get("foto"))
            if nueva:
                borrar_foto(foto)
                foto = nueva
            elif request.form.get("quitar_foto"):
                borrar_foto(foto)
                foto = None
            con_ticket = 1 if request.form.get("con_ticket") else 0
            if premio:
                db.execute("UPDATE premios SET nombre=?, descripcion=?, precio_cent=?, foto=?, orden=?, con_ticket=? WHERE id=?",
                           (nombre, descripcion, precio, foto, orden, con_ticket, pid))
            else:
                if not orden:
                    orden = (db.execute("SELECT COALESCE(MAX(orden),0) FROM premios").fetchone()[0]) + 1
                db.execute("INSERT INTO premios (nombre, descripcion, precio_cent, foto, orden, con_ticket) VALUES (?,?,?,?,?,?)",
                           (nombre, descripcion, precio, foto, orden, con_ticket))
            db.commit()
            flash("Lote guardado.", "ok")
            return redirect(url_for("admin_premios"))
        return render_template("admin/premio.html", premio=premio, form={})

    # ---------------------------------------------------------------- tickets de compra
    def carpeta_tickets():
        return os.path.join(app.config["DATA_DIR"], "tickets")

    @app.post("/admin/premios/<int:pid>/ticket")
    @solo_admin
    def admin_premio_ticket(pid):
        """Marca o desmarca a mano que el lote ya tiene su ticket."""
        D.get_db().execute("UPDATE premios SET con_ticket = 1 - con_ticket WHERE id=?", (pid,))
        D.get_db().commit()
        return redirect(url_for("admin_premios") + f"#lote-{pid}")

    @app.post("/admin/tickets")
    @solo_admin
    def admin_tickets_subir():
        ficheros = [f for f in request.files.getlist("tickets") if f and f.filename]
        if not ficheros:
            flash("Elige al menos un ticket (JPG, PNG o PDF).", "error")
            return redirect(url_for("admin_premios") + "#tickets")
        descripcion = (request.form.get("descripcion") or "").strip()[:200]
        importe = a_cent(request.form.get("importe")) if (request.form.get("importe") or "").strip() else None
        if importe is None and (request.form.get("importe") or "").strip():
            flash("Importe no válido (por ejemplo 35,90).", "error")
            return redirect(url_for("admin_premios") + "#tickets")
        premio_id = request.form.get("premio_id", type=int) or None
        db = D.get_db()
        subidos = 0
        for f in ficheros:
            archivo, tipo = T.guardar(f, carpeta_tickets())
            if not archivo:
                flash(tipo, "error")
                continue
            db.execute("INSERT INTO tickets (archivo, original, tipo, descripcion, importe_cent, premio_id) "
                       "VALUES (?, ?, ?, ?, ?, ?)",
                       (archivo, f.filename[:120], tipo, descripcion, importe if subidos == 0 else None, premio_id))
            subidos += 1
        if subidos and premio_id and request.form.get("marcar"):
            db.execute("UPDATE premios SET con_ticket=1 WHERE id=?", (premio_id,))
        db.commit()
        if subidos:
            flash(f"{subidos} ticket{'s' if subidos != 1 else ''} subido{'s' if subidos != 1 else ''}.", "ok")
        return redirect(url_for("admin_premios") + "#tickets")

    @app.get("/admin/tickets/<int:tid>")
    @solo_admin
    def admin_ticket(tid):
        t = D.get_db().execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
        if not t:
            abort(404)
        return send_from_directory(carpeta_tickets(), os.path.basename(t["archivo"]),
                                   mimetype="application/pdf" if t["tipo"] == "pdf" else "image/jpeg",
                                   download_name=f"ticket-{tid}.{t['tipo']}", max_age=0)

    @app.post("/admin/tickets/<int:tid>/borrar")
    @solo_admin
    def admin_ticket_borrar(tid):
        db = D.get_db()
        t = db.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
        if t:
            ruta = os.path.join(carpeta_tickets(), os.path.basename(t["archivo"]))
            if os.path.exists(ruta):
                os.remove(ruta)
            db.execute("DELETE FROM tickets WHERE id=?", (tid,))
            db.commit()
            flash("Ticket borrado.", "ok")
        return redirect(url_for("admin_premios") + "#tickets")

    @app.get("/admin/tickets.zip")
    @solo_admin
    def admin_tickets_zip():
        nombre = f"tickets-compra-{datetime.now().strftime('%Y%m%d')}.zip"
        datos = T.exportar(D.tickets(), carpeta_tickets(), D.ajustes()["titulo"], euros)
        return Response(datos, mimetype="application/zip", headers={
            "Content-Disposition": f"attachment; filename={nombre}", "Cache-Control": "no-store"})

    @app.route("/admin/sorteo", methods=["GET", "POST"])
    @solo_admin
    def admin_sorteo():
        db = D.get_db()
        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "ganadores":
                for p in D.premios():
                    v = request.form.get(f"ganador_{p['id']}", type=int)
                    db.execute("UPDATE premios SET ganador_id=? WHERE id=?", (v or None, p["id"]))
                flash("Ganadores guardados.", "ok")
            elif accion == "publicar":
                D.guardar_ajuste("publicar_ganadores", "1" if request.form.get("valor") == "1" else "0")
            elif accion == "azar":
                # Sorteo digital ponderado (por si no hay bolsa). Respeta los ya premiados.
                pid = request.form.get("premio_id", type=int)
                ya = {p["ganador_id"] for p in D.premios() if p["ganador_id"]}
                bolsa = []
                for pe in D.personas_con_totales():
                    if pe["id"] not in ya or request.form.get("repetir"):
                        bolsa += [pe["id"]] * pe["confirmadas"]
                if bolsa and pid:
                    db.execute("UPDATE premios SET ganador_id=? WHERE id=?",
                               (secrets.SystemRandom().choice(bolsa), pid))
                    flash("Papeleta sacada al azar.", "ok")
                else:
                    flash("No hay papeletas confirmadas disponibles.", "error")
            db.commit()
            return redirect(url_for("admin_sorteo"))
        personas = [p for p in D.personas_con_totales() if p["confirmadas"] > 0]
        return render_template("admin/sorteo.html", premios=D.premios(), personas=personas,
                               res=D.resumen())

    @app.route("/admin/ajustes", methods=["GET", "POST"])
    @solo_admin
    def admin_ajustes():
        if request.method == "POST":
            accion = request.form.get("accion") or ""
            if accion.startswith("tg_"):
                session["tg_msgs"] = acciones_telegram(accion)
                return redirect(url_for("admin_ajustes") + "#telegram")
            if accion == "estado":
                D.guardar_ajuste("estado", "cerrada" if request.form.get("valor") == "cerrada" else "abierta")
                D.get_db().commit()
                flash("Estado de la venta actualizado.", "ok")
                return redirect(request.form.get("volver") or url_for("admin_ajustes"))
            precio = a_cent(request.form.get("precio"))
            if precio is None or precio <= 0:
                flash("Precio por papeleta no válido.", "error")
                return redirect(url_for("admin_ajustes"))
            D.guardar_ajuste("precio_cent", precio)
            for k, lim in (("titulo", 120), ("texto", 2000), ("fecha_sorteo", 80)):
                D.guardar_ajuste(k, (request.form.get(k) or "").strip()[:lim])
            bizum = []
            for n, t in zip(request.form.getlist("bizum_nombre"), request.form.getlist("bizum_tel")):
                n, t = " ".join(n.split())[:40], " ".join(t.split())[:20]
                if n and t:
                    bizum.append({"nombre": n, "tel": t})
                elif n or t:
                    flash("Cada Bizum necesita nombre y teléfono; se ha ignorado una fila incompleta.", "error")
            mano = [{"nombre": " ".join(n.split())[:40]} for n in request.form.getlist("mano_nombre") if n.strip()]
            D.guardar_ajuste("bizum", json.dumps(bizum, ensure_ascii=False))
            D.guardar_ajuste("mano", json.dumps(mano, ensure_ascii=False))
            prefijo = "".join(ch for ch in (request.form.get("prefijo") or "CESTA").upper() if ch.isalnum())[:10]
            D.guardar_ajuste("prefijo", prefijo or "CESTA")
            D.guardar_ajuste("max_por_compra", max(1, min(500, request.form.get("max_por_compra", type=int) or 50)))
            D.get_db().commit()
            flash("Ajustes guardados.", "ok")
            return redirect(url_for("admin_ajustes"))
        return render_template("admin/ajustes.html", tg_msgs=session.pop("tg_msgs", []))

    def acciones_telegram(accion):
        """Guarda los datos de Telegram del formulario y hace la acción pedida.
        Devuelve mensajes [(tipo, texto)] para enseñarlos junto a los botones."""
        f = request.form
        nuevo = (f.get("telegram_token") or "").strip().replace(" ", "")
        if f.get("telegram_quitar"):
            D.guardar_ajuste("telegram_token", "")
        elif nuevo:
            D.guardar_ajuste("telegram_token", nuevo[:100])
        D.guardar_ajuste("telegram_chats", ", ".join(telegram.chats_de(f.get("telegram_chats")))[:300])
        D.guardar_ajuste("telegram_copia", "1" if f.get("telegram_copia") else "0")
        D.get_db().commit()
        aj = D.ajustes()
        msgs = []
        if accion == "tg_guardar":
            msgs.append(("ok", "Ajustes de Telegram guardados."))
        elif not aj["telegram_token"]:
            msgs.append(("error", "Falta el token del bot. Pégalo arriba (te lo da @BotFather)."))
        elif accion == "tg_detectar":
            ok, res = telegram.detectar_chats(aj["telegram_token"])
            if not ok:
                msgs.append(("error", res))
            elif not res["chats"]:
                msgs.append(("info", f"El bot {res['bot']} funciona, pero no le ha llegado ningún mensaje todavía. "
                                     f"En Telegram abre {res['bot']}, pulsa Iniciar (o escribe /start) y vuelve a pulsar "
                                     f"Detectar chats. En un grupo, escribe /start@{res['bot'][1:]}."))
            else:
                actuales = telegram.chats_de(aj["telegram_chats"])
                nuevos = [c for c in res["chats"] if c not in actuales]
                if nuevos:
                    D.guardar_ajuste("telegram_chats", ", ".join(actuales + nuevos))
                    D.get_db().commit()
                for cid, nombre in res["chats"].items():
                    msgs.append(("ok", f"{nombre} → {cid}" + (" (añadido)" if cid in nuevos else " (ya estaba)")))
                msgs.append(("info", "Ahora pulsa «Enviar prueba». Quita de la lista los chats que no quieras."))
        elif not telegram.chats_de(aj["telegram_chats"]):
            msgs.append(("error", "No hay ningún chat. Pulsa «Detectar chats» primero."))
        elif accion == "tg_prueba":
            for chat, ok, det in telegram.enviar(aj["telegram_token"], aj["telegram_chats"],
                                                 f"✅ <b>{aj['titulo']}</b>\nLos avisos de nuevas reservas llegarán a este chat."):
                msgs.append(("ok" if ok else "error", f"Chat {chat}: " + ("mensaje enviado ✓" if ok else f"error: {det}")))
        elif accion == "tg_copia":
            from .nocturna import enviar_copia
            _, res = enviar_copia(app.config["DATA_DIR"], forzar=True)
            msgs += [("ok" if "✓" in m else "error", m) for m in res]
        return msgs

    def enviar_pdf(datos, nombre, con_hora=True):
        """Sin caché. Los PDF de imprimir llevan la hora en el nombre: los visores del móvil
        reabren el archivo antiguo si se descarga dos veces con el mismo nombre."""
        fichero = (f"{nombre}-{datetime.now().strftime('%Y%m%d-%H%M%S')}" if con_hora else nombre) + ".pdf"
        ascii_ = unicodedata.normalize("NFKD", fichero).encode("ascii", "ignore").decode() or "documento.pdf"
        return Response(datos, mimetype="application/pdf", headers={
            "Content-Disposition": f"inline; filename=\"{ascii_}\"; filename*=UTF-8''{quote(fichero)}",
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        })

    @app.get("/admin/papeletas.pdf")
    @solo_admin
    def admin_papeletas():
        personas = [p for p in D.personas_con_totales() if p["confirmadas"] > 0]
        return enviar_pdf(pdfs.pdf_papeletas(D.ajustes(), personas), "papeletas")

    @app.get("/admin/lotes.pdf")
    @solo_admin
    def admin_lotes_pdf():
        return enviar_pdf(pdfs.pdf_lotes_sobres(D.ajustes(), D.premios(),
                                                os.path.join(app.config["DATA_DIR"], "fotos")), "lotes-sobres")

    @app.get("/admin/copia.zip")
    @solo_admin
    def admin_copia():
        nombre = f"cestaola-copia-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
        return Response(copias.exportar(app.config["DATA_DIR"]), mimetype="application/zip",
                        headers={"Content-Disposition": f"attachment; filename={nombre}",
                                 "Cache-Control": "no-store"})

    @app.post("/admin/importar")
    @solo_admin
    def admin_importar():
        f = request.files.get("copia")
        if not f or not f.filename:
            flash("Elige el archivo .zip de la copia.", "error")
        elif request.form.get("confirmo") != "1":
            flash("Marca la casilla para confirmar que quieres sustituir todos los datos.", "error")
        else:
            ok, msg = copias.importar(app.config["DATA_DIR"], f.stream)
            if ok:
                D.init_db(app)          # adapta copias de versiones anteriores
                g.pop("aj", None)
            flash(msg, "ok" if ok else "error")
        return redirect(url_for("admin_ajustes") + "#copias")

    @app.get("/admin/exportar.csv")
    @solo_admin
    def admin_csv():
        rows = D.get_db().execute(
            "SELECT c.id, pe.nombre, c.cantidad, c.precio_cent, c.metodo, c.estado, c.creado, "
            "c.confirmado, c.nota, c.receptor, pe.telefono FROM compras c JOIN personas pe ON pe.id=c.persona_id ORDER BY c.id").fetchall()
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["concepto", "nombre", "telefono", "papeletas", "importe", "pago", "a quien", "estado", "fecha", "confirmado", "nota"])
        for r in rows:
            w.writerow([concepto(r["id"]), r["nombre"], r["telefono"], r["cantidad"],
                        f"{r['cantidad'] * r['precio_cent'] / 100:.2f}".replace(".", ","),
                        r["metodo"], r["receptor"], r["estado"], r["creado"], r["confirmado"] or "", r["nota"]])
        return Response("﻿" + out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=cestaola.csv"})

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error(e):
        msg = getattr(e, "description", "") or "Algo ha ido mal."
        if e.code == 413:
            msg = "El archivo es demasiado grande (máximo 25 MB)."
        return render_template("error.html", codigo=e.code, mensaje=msg), e.code

    return app
