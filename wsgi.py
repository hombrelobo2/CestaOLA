# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Punto de entrada para gunicorn:  gunicorn wsgi:app"""
from cestaola import create_app

app = create_app()

if __name__ == "__main__":
    # Modo prueba local:  python wsgi.py  ->  http://127.0.0.1:8000
    app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="127.0.0.1", port=8000, debug=True)
