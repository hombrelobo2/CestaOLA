"""CestaOLA: web para el sorteo de la cesta de la empresa."""
import csv
import hmac
import io
import os
import secrets
import uuid
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, g, make_response, redirect,
                   render_template, request, send_from_directory, session, url_for)

from . import db as D
from . import pdfs

COOKIE = "cestaola_persona"
FOTO_EXT = {"jpg", "jpeg", "png", "webp", "heic", "heif", "gif"}


def euros(cent):
    """1234 -> '12,34 €' (formato español)."""
    cent = int(cent or 0)
    signo = "-" if cent < 0 else ""
    cent = abs(cent)
    e, c = divmod(cent, 100)
    miles = f"{e:,}".replace(",", ".")
    return f"{signo}{miles},{c:02d} €"


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
        metodo = request.form.get("metodo")
        try:
            cantidad = int(request.form.get("cantidad", "0"))
        except ValueError:
            cantidad = 0
        destino = url_for("mi", token=persona["token"]) if persona else url_for("inicio")
        if not persona and len(nombre) < 2:
            flash("Escribe tu nombre (y apellido, para no confundirte con otro compañero).", "error")
            return redirect(destino + "#participar")
        if cantidad < 1 or cantidad > aj["max_por_compra"]:
            flash(f"Elige entre 1 y {aj['max_por_compra']} papeletas.", "error")
            return redirect(destino + "#participar")
        if metodo not in ("bizum", "mano"):
            flash("Elige cómo vas a pagar.", "error")
            return redirect(destino + "#participar")
        if metodo == "bizum" and not aj["bizum_telefono"]:
            metodo = "mano"
        db = D.get_db()
        if not persona:
            token = D.nuevo_token()
            cur = db.execute("INSERT INTO personas (nombre, token) VALUES (?, ?)", (nombre, token))
            persona_id = cur.lastrowid
        else:
            persona_id, token = persona["id"], persona["token"]
        cur = db.execute(
            "INSERT INTO compras (persona_id, cantidad, precio_cent, metodo) VALUES (?, ?, ?, ?)",
            (persona_id, cantidad, aj["precio_cent"], metodo))
        db.commit()
        resp = make_response(redirect(url_for("mi", token=token, nueva=cur.lastrowid)))
        resp.set_cookie(COOKIE, token, max_age=3600 * 24 * 400, httponly=True, samesite="Lax",
                        secure=app.config["SESSION_COOKIE_SECURE"])
        return resp

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
        resp.set_cookie(COOKIE, token, max_age=3600 * 24 * 400, httponly=True, samesite="Lax",
                        secure=app.config["SESSION_COOKIE_SECURE"])
        return resp

    @app.post("/mi/<token>/cambiar-pago/<int:cid>")
    def cambiar_pago(token, cid):
        persona = D.persona_por_token(token)
        if not persona:
            abort(404)
        metodo = request.form.get("metodo")
        if metodo in ("bizum", "mano"):
            D.get_db().execute(
                "UPDATE compras SET metodo=? WHERE id=? AND persona_id=? AND estado='pendiente'",
                (metodo, cid, persona["id"]))
            D.get_db().commit()
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

    @app.get("/premios.pdf")
    def premios_pdf():
        aj = D.ajustes()
        mostrar = aj["publicar_ganadores"] or session.get("admin")
        datos = pdfs.pdf_premios(aj, D.premios(), D.resumen(),
                                 os.path.join(app.config["DATA_DIR"], "fotos"), mostrar)
        return Response(datos, mimetype="application/pdf",
                        headers={"Content-Disposition": "inline; filename=premios.pdf"})

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
        return redirect(url_for("inicio"))

    @app.get("/admin")
    @solo_admin
    def admin():
        filtro = request.args.get("estado", "pendiente")
        sql = ("SELECT c.*, pe.nombre, pe.token FROM compras c JOIN personas pe ON pe.id=c.persona_id ")
        args = ()
        if filtro in ("pendiente", "confirmado", "rechazado"):
            sql += "WHERE c.estado=? "
            args = (filtro,)
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
        return render_template("admin/panel.html", compras=compras, filtro=filtro,
                               res=D.resumen(), personas=personas, repetidos=repetidos)

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
        metodo = request.form.get("metodo") if request.form.get("metodo") in ("bizum", "mano") else "mano"
        if cantidad < 1 or (not pid and len(nombre) < 2):
            flash("Indica nombre (o persona existente) y número de papeletas.", "error")
            return redirect(url_for("admin"))
        if not pid:
            pid = db.execute("INSERT INTO personas (nombre, token) VALUES (?, ?)",
                             (nombre, D.nuevo_token())).lastrowid
        estado = "confirmado" if request.form.get("confirmada") else "pendiente"
        db.execute("INSERT INTO compras (persona_id, cantidad, precio_cent, metodo, estado, confirmado, nota) "
                   "VALUES (?, ?, ?, ?, ?, ?, 'alta manual')",
                   (pid, cantidad, aj["precio_cent"], metodo, estado,
                    datetime.now().strftime("%Y-%m-%d %H:%M") if estado == "confirmado" else None))
        db.commit()
        flash("Participación añadida.", "ok")
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
        db.commit()
        return redirect(url_for("admin", estado=request.form.get("estado", "pendiente")) + "#personas")

    @app.get("/admin/premios")
    @solo_admin
    def admin_premios():
        return render_template("admin/premios.html", premios=D.premios(), res=D.resumen())

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
            if premio:
                db.execute("UPDATE premios SET nombre=?, descripcion=?, precio_cent=?, foto=?, orden=? WHERE id=?",
                           (nombre, descripcion, precio, foto, orden, pid))
            else:
                if not orden:
                    orden = (db.execute("SELECT COALESCE(MAX(orden),0) FROM premios").fetchone()[0]) + 1
                db.execute("INSERT INTO premios (nombre, descripcion, precio_cent, foto, orden) VALUES (?,?,?,?,?)",
                           (nombre, descripcion, precio, foto, orden))
            db.commit()
            flash("Lote guardado.", "ok")
            return redirect(url_for("admin_premios"))
        return render_template("admin/premio.html", premio=premio, form={})

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
            if request.form.get("accion") == "estado":
                D.guardar_ajuste("estado", "cerrada" if request.form.get("valor") == "cerrada" else "abierta")
                D.get_db().commit()
                flash("Estado de la venta actualizado.", "ok")
                return redirect(request.form.get("volver") or url_for("admin_ajustes"))
            precio = a_cent(request.form.get("precio"))
            if precio is None or precio <= 0:
                flash("Precio por papeleta no válido.", "error")
                return redirect(url_for("admin_ajustes"))
            D.guardar_ajuste("precio_cent", precio)
            for k, lim in (("titulo", 120), ("texto", 2000), ("bizum_telefono", 20),
                           ("bizum_titular", 80), ("fecha_sorteo", 80)):
                D.guardar_ajuste(k, (request.form.get(k) or "").strip()[:lim])
            prefijo = "".join(ch for ch in (request.form.get("prefijo") or "CESTA").upper() if ch.isalnum())[:10]
            D.guardar_ajuste("prefijo", prefijo or "CESTA")
            D.guardar_ajuste("max_por_compra", max(1, min(500, request.form.get("max_por_compra", type=int) or 50)))
            D.get_db().commit()
            flash("Ajustes guardados.", "ok")
            return redirect(url_for("admin_ajustes"))
        return render_template("admin/ajustes.html")

    @app.get("/admin/papeletas.pdf")
    @solo_admin
    def admin_papeletas():
        personas = [p for p in D.personas_con_totales() if p["confirmadas"] > 0]
        datos = pdfs.pdf_papeletas(D.ajustes(), personas)
        return Response(datos, mimetype="application/pdf",
                        headers={"Content-Disposition": "inline; filename=papeletas.pdf"})

    @app.get("/admin/exportar.csv")
    @solo_admin
    def admin_csv():
        rows = D.get_db().execute(
            "SELECT c.id, pe.nombre, c.cantidad, c.precio_cent, c.metodo, c.estado, c.creado, "
            "c.confirmado, c.nota FROM compras c JOIN personas pe ON pe.id=c.persona_id ORDER BY c.id").fetchall()
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["concepto", "nombre", "papeletas", "importe", "pago", "estado", "fecha", "confirmado", "nota"])
        for r in rows:
            w.writerow([concepto(r["id"]), r["nombre"], r["cantidad"],
                        f"{r['cantidad'] * r['precio_cent'] / 100:.2f}".replace(".", ","),
                        r["metodo"], r["estado"], r["creado"], r["confirmado"] or "", r["nota"]])
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
