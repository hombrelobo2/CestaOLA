# SPDX-License-Identifier: GPL-3.0-or-later
# CestaOLA · Code por Hombrelobo
"""Maqueta la guía visual (docs/Guia-CestaOLA.pdf) a partir de las capturas.

    python3 docs/guia/capturas.py     # primero, si la app ha cambiado
    python3 docs/guia/generar.py
"""
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(os.path.dirname(AQUI), "Guia-CestaOLA.pdf")
CAP = "file://" + os.path.join(AQUI, "capturas")
GF = "/usr/share/fonts/truetype/google-fonts/"   # Lora y Poppins si están instaladas; si no, se usan otras


def movil(nombre, recorte=None, ancho="58mm"):
    estilo = f"width:{ancho};" + (f"height:{recorte};" if recorte else "")
    return (f'<div class="movil{" recortado" if recorte else ""}" style="{estilo}">'
            f'<img src="{CAP}/{nombre}.jpg"></div>')


def pieza(nombre, ancho="70mm", recorte=None, sombra=True):
    estilo = f"width:{ancho};" + (f"max-height:{recorte};" if recorte else "")
    return (f'<div class="pieza{" recortado" if recorte else ""}{" plana" if not sombra else ""}" style="{estilo}">'
            f'<img src="{CAP}/{nombre}.jpg"></div>')


def paso(n, titulo, texto):
    return f'<div class="paso"><b>{n}</b><div><h4>{titulo}</h4><p>{texto}</p></div></div>'


def cab(seccion, titulo, sub=""):
    return (f'<header class="cab"><div class="sec">{seccion}</div><h2>{titulo}</h2>'
            + (f'<p class="sub">{sub}</p>' if sub else "") + "</header>")


PAGINAS = []

# ------------------------------------------------------------------ portada
PAGINAS.append(f"""
<section class="pagina portada">
  <div class="puntos"></div><div class="aro a1"></div><div class="aro a2"></div>
  <div class="texto-portada">
    <div class="adorno">Guía visual</div>
    <h1>CestaOLA</h1>
    <p class="lema">La web para organizar el sorteo de la cesta:<br>papeletas, pagos por Bizum o en mano,<br>lotes con foto y cuentas claras.</p>
    <ul class="indice">
      <li><b>1</b> Cómo funciona</li>
      <li><b>2</b> Para participantes</li>
      <li><b>3</b> Para organizadores</li>
      <li><b>4</b> El día del sorteo</li>
      <li><b>5</b> Instalación y mantenimiento</li>
    </ul>
  </div>
  <div class="telefono-portada">{movil("p1-portada", ancho="74mm")}</div>
  <footer class="pie-portada">Code por Hombrelobo · Software libre GPL-3.0 · github.com/hombrelobo2/CestaOLA</footer>
</section>""")

# ------------------------------------------------------------------ cómo funciona
PAGINAS.append(f"""
<section class="pagina">
  {cab("1 · Cómo funciona", "Del WhatsApp a la bolsa", "Se manda un enlace al grupo y cada uno se apunta desde el móvil. Los organizadores solo confirman pagos y, el día del sorteo, imprimen y sacan nombres.")}
  <div class="flujo">
    <div class="nodo"><span>📱</span><h4>Reserva</h4><p>Nombre, número de papeletas y a quién paga.</p></div>
    <div class="flecha">→</div>
    <div class="nodo"><span>💶</span><h4>Paga</h4><p>Bizum con concepto único o en mano a un organizador.</p></div>
    <div class="flecha">→</div>
    <div class="nodo"><span>✓</span><h4>Confirmamos</h4><p>El organizador marca «Cobrado» en el panel.</p></div>
    <div class="flecha">→</div>
    <div class="nodo"><span>🧺</span><h4>A la bolsa</h4><p>Una papeleta impresa por participación, con su nombre.</p></div>
    <div class="flecha">→</div>
    <div class="nodo"><span>🏆</span><h4>Sorteo</h4><p>Se sacan nombres y se publican los premiados.</p></div>
  </div>

  <div class="dos">
    <div class="caja">
      <h3>Lo que ve cada participante</h3>
      <ul class="lista">
        <li>Los <b>lotes</b> con foto, descripción y <b>precio real</b>.</li>
        <li>Las <b>cuentas claras</b>: lo recaudado frente a lo que cuestan los lotes.</li>
        <li>Su <b>página personal</b>: papeletas, estado del pago y botón para comprar más.</li>
        <li>Su <b>resguardo en PDF</b> con un código QR a esa página.</li>
      </ul>
    </div>
    <div class="caja">
      <h3>Lo que hacen los organizadores</h3>
      <ul class="lista">
        <li>Confirmar pagos y ver <b>quién tiene el dinero</b>.</li>
        <li>Dar de alta a quien paga sin usar la web y enviarle su resguardo.</li>
        <li>Subir los lotes desde el móvil, con foto.</li>
        <li>Imprimir <b>papeletas de 10 × 5 cm</b> y <b>fichas de lotes para sobres</b>.</li>
        <li>Apuntar y publicar los premiados.</li>
      </ul>
    </div>
  </div>

  <div class="nota"><b>Sobre Bizum:</b> un particular no puede cobrar Bizum dentro de una web (hace falta un TPV de empresa).
  Por eso la web da el teléfono, el importe y un concepto único como <code>OLA-0007</code> para copiar, y el organizador
  confirma cuando ve el Bizum en su banco. El concepto dice de quién es cada pago.</div>
</section>""")

# ------------------------------------------------------------------ participantes
PAGINAS.append(f"""
<section class="pagina">
  {cab("2 · Para participantes", "Entra y mira los lotes", "Todo se hace desde el enlace que llega por WhatsApp. No hace falta registrarse ni instalar nada.")}
  <div class="fila">
    {movil("p1-portada")}
    <div class="col">
      {paso(1, "La portada", "Título, precio de la papeleta, fecha del sorteo y el botón <b>Quiero mis papeletas</b>, que baja directamente al formulario.")}
      {paso(2, "Los lotes", "Cada lote con su foto, número y precio real. La descripción sale plegada en dos líneas: <b>Ver qué incluye</b> la despliega entera.")}
      <div class="fila apretada">{pieza("p2-lote-plegado", "40mm")}{pieza("p3-lote-desplegado", "40mm")}</div>
    </div>
  </div>
  <div class="fila centrada" style="margin-top:6mm">
    {pieza("p4-cuentas", "78mm")}
    <div class="col estrecha">{paso(3, "Cuentas claras", "Lo que han costado los lotes, lo recaudado con pagos confirmados y lo que falta o sobra. Se actualiza solo con cada pago.")}</div>
  </div>
</section>""")

PAGINAS.append(f"""
<section class="pagina">
  {cab("2 · Para participantes", "Reserva tus papeletas")}
  <div class="fila">
    {pieza("p5-formulario", "62mm")}
    <div class="col">
      {paso(1, "Nombre y papeletas", "El nombre es el que saldrá en cada papeleta de la bolsa: mejor con apellido. Con <b>−</b> y <b>+</b> se elige el número y el importe se calcula al momento.")}
      {paso(2, "Cómo y a quién pagas", "Bizum a uno de los organizadores o en mano a quien recoge el dinero. Se puede cambiar después mientras el pago esté pendiente.")}
      {paso(3, "Reservar", "Las papeletas quedan reservadas y entran en la bolsa cuando un organizador confirma el pago.")}
    </div>
  </div>
  <div class="fila" style="margin-top:6mm">
    {movil("p6-mis-papeletas", recorte="92mm", ancho="52mm")}
    {pieza("p7-bizum", "60mm")}
    <div class="col estrecha">
      {paso(4, "Tus datos de Bizum", "Teléfono, importe y <b>concepto</b> con botón de copiar. Abre la app de tu banco → Bizum → Enviar dinero y pega los tres datos.")}
    </div>
  </div>
</section>""")

PAGINAS.append(f"""
<section class="pagina">
  {cab("2 · Para participantes", "Tu enlace y tu resguardo")}
  <div class="fila">
    <div class="col">
      {paso(1, "Tu página personal", "Después de reservar llegas a <b>Mis papeletas</b>: cuántas tienes en la bolsa, cuáles faltan por confirmar y el historial. El móvil la recuerda, y con <b>Guardármelo en WhatsApp</b> te mandas el enlace para volver desde cualquier sitio.")}
      {paso(2, "Comprar más", "Desde esa misma página, el formulario añade papeletas a tu nombre sin volver a escribirlo.")}
      {paso(3, "Resguardo en PDF", "Cada reserva tiene su resguardo con el estado (pendiente, pagado o anulado) y un <b>código QR</b> que lleva a tu página. <b>Resguardo de todo</b> junta todas tus reservas en uno.")}
    </div>
    {pieza("p8-historial", "72mm")}
  </div>
  <div class="centro" style="margin-top:7mm">{pieza("p9-resguardo", "150mm")}</div>
  <p class="pie-foto">Resguardo (tamaño A6). El sello cambia a «Pagado» cuando el organizador confirma el pago.</p>
</section>""")

# ------------------------------------------------------------------ organizadores
PAGINAS.append(f"""
<section class="pagina">
  {cab("3 · Para organizadores", "El panel", "Se entra por <b>/admin</b> (o el enlace «admin» al pie de la web) con la contraseña de organizadores.")}
  <div class="fila">
    {movil("a0-login", recorte="70mm", ancho="50mm")}
    {movil("a1-panel", ancho="58mm")}
    <div class="col">
      {paso(1, "Pestañas", "<b>Pagos</b>, <b>Lotes</b>, <b>Sorteo</b> y <b>Ajustes</b>. La barra se queda fija arriba al bajar.")}
      {paso(2, "Resumen", "Cobrado, pendiente, valor de los lotes y balance. Debajo, los PDF para imprimir y la exportación a CSV.")}
      {paso(3, "¿Quién tiene el dinero?", "Lo cobrado y lo que falta por cobrar de cada organizador. Tocando un nombre se ven solo sus pagos.")}
    </div>
  </div>
  <div class="centro" style="margin-top:6mm">{pieza("a2-quien-tiene", "100mm")}</div>
</section>""")

PAGINAS.append(f"""
<section class="pagina">
  {cab("3 · Para organizadores", "Confirmar pagos y altas a mano")}
  <div class="fila">
    {pieza("a3-pendientes", "62mm", recorte="128mm")}
    <div class="col">
      {paso(1, "Pendientes", "Cada reserva con su concepto, nombre, papeletas, importe y a quién se paga. Cuando veas el Bizum o te den el dinero, pulsa <b>✓ Cobrado</b>. <b>Deshacer</b> lo vuelve a dejar pendiente y <b>Anular</b> lo saca de la bolsa.")}
      {paso(2, "Resguardos", "<b>📄 Resguardo</b> lo descarga y <b>📤</b> lo envía como archivo por WhatsApp desde el móvil.")}
      {paso(3, "Alta a mano", "Para quien paga sin usar la web: <b>Añadir una participación a mano</b>. Al guardar aparece este aviso para mandarle el resguardo o su enlace.")}
      {pieza("a4-alta-manual", "72mm")}
    </div>
  </div>
  <div class="fila" style="margin-top:6mm">
    {pieza("a5-participantes", "62mm", recorte="70mm")}
    <div class="col">{paso(4, "Participantes", "Todas las personas con sus papeletas. El nombre se puede corregir (es el que se imprime). Si hay dos nombres iguales, avisa ⚠. Cada una tiene su resguardo y su enlace personal.")}</div>
  </div>
</section>""")

PAGINAS.append(f"""
<section class="pagina">
  {cab("3 · Para organizadores", "Lotes y ajustes")}
  <div class="fila">
    {movil("a6-lotes", recorte="96mm", ancho="54mm")}
    {movil("a7-editar-lote", recorte="118mm", ancho="54mm")}
    <div class="col">
      {paso(1, "Lotes", "Lista con foto, nombre y precio, y el botón <b>Editar</b> siempre a la vista. Abajo, el valor total.")}
      {paso(2, "Editar un lote", "<b>📷 Hacer o elegir foto</b> abre la cámara del móvil. La foto se reduce sola. Pon el <b>precio real</b> (es el que se suma en las cuentas) y el <b>orden</b> en que se sortea. Un salto de línea en la descripción separa bien las categorías.")}
    </div>
  </div>
  <div class="fila" style="margin-top:6mm">
    {movil("a8-ajustes", recorte="118mm", ancho="54mm")}
    <div class="col">
      {paso(3, "Ajustes", "Título, texto de bienvenida, precio por papeleta, máximo por compra, fecha del sorteo y prefijo del concepto (<code>OLA-0001</code>…).")}
      {paso(4, "Quién cobra", "<b>Bizum</b>: nombre y teléfono de cada organizador que recibe Bizum. <b>En mano</b>: solo el nombre de quien recoge. El participante elige a quién paga y cada uno confirma los suyos.")}
      <div class="nota peq">Cambiar el precio no afecta a las reservas ya hechas: cada una guarda el precio con el que se hizo.</div>
    </div>
  </div>
</section>""")

# ------------------------------------------------------------------ día del sorteo
PAGINAS.append(f"""
<section class="pagina">
  {cab("4 · El día del sorteo", "Imprimir, sacar nombres y publicar")}
  <div class="fila">
    <div class="col">
      {paso(1, "Cierra la venta", "En <b>Pagos → 🔒 Cerrar la venta</b>. Nadie puede reservar más (se puede reabrir). Revisa que no queden pagos pendientes que sí hayas cobrado.")}
      {paso(2, "Imprime las papeletas", "<b>Papeletas para la bolsa</b>: A4 con 10 papeletas de 10 × 5 cm, una por participación confirmada, con «2 de 5» para comprobar que están todas. Imprime a <b>tamaño real / 100 %</b> y recorta por la línea discontinua.")}
      {paso(3, "Fichas de lotes para sobres", "3 por A4: foto, nombre y descripción, sin precio. Recorta y mete cada una en su sobre.")}
    </div>
    <div class="col" style="flex:0 0 auto; gap:4mm">
      <div class="fila apretada">{pieza("d1-papeletas", "52mm", sombra=True)}{pieza("d2-lotes-sobres", "52mm", sombra=True)}</div>
    </div>
  </div>
  <div class="fila" style="margin-top:6mm">
    {movil("a9-sorteo", recorte="120mm", ancho="56mm")}
    <div class="col">
      {paso(4, "Apunta los premiados", "En <b>Sorteo</b>, saca un nombre de la bolsa y elígelo en su lote. Los asignados se ven en verde. <b>Guardar premiados</b>.")}
      {paso(5, "Publica", "<b>📣 Publicar en la web</b>: los premiados salen en los lotes y cada ganador ve «¡Enhorabuena!» en su página.")}
      {paso(6, "¿Sin bolsa?", "<b>Sorteo digital</b>: saca una papeleta al azar contando cada participación confirmada una vez, igual que en la bolsa.")}
    </div>
  </div>
</section>""")

# ------------------------------------------------------------------ instalación
PAGINAS.append("""
<section class="pagina">
  <header class="cab"><div class="sec">5 · Instalación y mantenimiento</div><h2>En un LXC de Proxmox</h2>
  <p class="sub">Debian 12 no privilegiado · 1 núcleo · 512 MB de RAM · 4 GB de disco · <i>nesting</i> activado.</p></header>
  <div class="dos">
    <div>
      <h3>Crear el contenedor <span class="peq muted">(en el Proxmox)</span></h3>
<pre>pveam update
T=$(pveam available --section system \\
  | awk '/debian-12-standard/{print $2}' | tail -1)
pveam download local $T
pct create 114 local:vztmpl/$T \\
  --hostname cestaola --cores 1 \\
  --memory 512 --swap 512 \\
  --rootfs local-lvm:4 \\
  --net0 name=eth0,bridge=vmbr0,\\
ip=192.168.1.14/24,gw=192.168.1.1 \\
  --unprivileged 1 --features nesting=1 \\
  --onboot 1 --password 'TuClave'
pct start 114 &amp;&amp; pct enter 114</pre>
      <h3>Instalar CestaOLA <span class="peq muted">(dentro del LXC)</span></h3>
<pre>apt update &amp;&amp; apt install -y git
git clone https://github.com/hombrelobo2/CestaOLA \\
  /opt/cestaola
bash /opt/cestaola/deploy/install.sh</pre>
      <p class="peq">Al terminar muestra la dirección <code>http://IP:8000</code> y la contraseña de admin.</p>
    </div>
    <div>
      <h3>Publicar con HTTPS</h3>
      <p class="peq">En Nginx Proxy Manager: host <code>cesta.tudominio</code> → <code>http://IP-del-LXC:8000</code>, certificado Let's Encrypt y <b>Force SSL</b>. En <i>Advanced</i>: <code>client_max_body_size 25m;</code> para las fotos.</p>
      <h3>Configuración</h3>
      <p class="peq">Archivo <code>/etc/cestaola/cestaola.env</code>; después, <code>systemctl restart cestaola</code>.</p>
      <table class="tabla-conf">
        <tr><td><code>CESTAOLA_ADMIN_PASSWORD</code></td><td>Contraseña de /admin (letras, números, guiones).</td></tr>
        <tr><td><code>CESTAOLA_BASE_URL</code></td><td>Dirección pública: enlaces y QR de los resguardos.</td></tr>
        <tr><td><code>CESTAOLA_COOKIE_SECURE</code></td><td><b>1</b> con HTTPS (entra siempre por el dominio). <b>0</b> solo para probar por IP.</td></tr>
      </table>
      <h3>Mantenimiento</h3>
<pre># actualizar a la última versión
bash /opt/cestaola/deploy/actualizar.sh
# copia de seguridad en /root
bash /opt/cestaola/deploy/copia.sh
# ver el registro
journalctl -u cestaola -f</pre>
      <h3>Empezar de cero (el año que viene)</h3>
<pre>bash /opt/cestaola/deploy/copia.sh
systemctl stop cestaola
rm -f /var/lib/cestaola/cestaola.db*
rm -f /var/lib/cestaola/fotos/*
systemctl start cestaola</pre>
    </div>
  </div>
  <footer class="pie-final">CestaOLA · Code por Hombrelobo · Software libre GPL-3.0 · github.com/hombrelobo2/CestaOLA</footer>
</section>""")


def fuente(nombre, archivo, peso, estilo="normal"):
    ruta = os.path.join(GF, archivo)
    if os.path.exists(ruta):
        return f"@font-face {{ font-family: {nombre}; src: url('file://{ruta}'); font-weight: {peso}; font-style: {estilo}; }}"
    return ""


CSS = "\n".join([
    fuente("Lora", "Lora-Variable.ttf", "400 700"), fuente("Poppins", "Poppins-Regular.ttf", 400),
    fuente("Poppins", "Poppins-Medium.ttf", 500), fuente("Poppins", "Poppins-SemiBold.ttf", 600),
    fuente("Poppins", "Poppins-Bold.ttf", 700),
]) + """
@page { size: A4; margin: 0; }
:root { --vino:#7b1e2c; --vino2:#4e111b; --oro:#c49a45; --oro2:#e8cf8f; --crema:#f8f1e6; --papel:#fffaf2; --tinta:#2a1c18; --suave:#6f5d54; --linea:#e7d9c4; --abeto:#2e5a4c; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Poppins, "Helvetica Neue", Arial, sans-serif; color: var(--tinta); font-size: 9.6pt; line-height: 1.45; }
h1, h2, h3, h4 { font-family: Lora, Georgia, serif; line-height: 1.15; }
code { font-family: "DejaVu Sans Mono", Menlo, monospace; font-size: .86em; background: #f1e6d4; padding: .2mm 1.2mm; border-radius: 1mm; }
.pagina { width: 210mm; height: 297mm; padding: 16mm 15mm 14mm; position: relative; overflow: hidden; page-break-after: always;
  background: radial-gradient(circle at 100% 0, rgba(196,154,69,.10), transparent 40%), var(--crema); }
.pagina:last-child { page-break-after: auto; }
.cab { margin-bottom: 7mm; }
.cab .sec { font-size: 8pt; letter-spacing: 1mm; text-transform: uppercase; font-weight: 600; color: var(--oro); }
.cab h2 { font-size: 24pt; color: var(--vino); margin-top: 1mm; }
.cab h2::after { content: ""; display: block; width: 16mm; height: .9mm; background: var(--oro); border-radius: 1mm; margin-top: 2.5mm; }
.cab .sub { margin-top: 3mm; color: var(--suave); font-size: 10pt; max-width: 165mm; }
h3 { font-size: 12.5pt; color: var(--vino); margin: 4mm 0 2mm; }
.fila { display: flex; gap: 7mm; align-items: flex-start; }
.fila.centrada { align-items: center; }
.fila.apretada { gap: 3mm; }
.col { flex: 1; display: flex; flex-direction: column; gap: 4.5mm; min-width: 0; }
.col.estrecha { flex: 0 1 70mm; }
.centro { display: flex; justify-content: center; }
.dos { display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; }
.movil { flex: none; border: 2.2mm solid #1d1412; border-radius: 7mm; overflow: hidden; background: #1d1412;
  box-shadow: 0 2mm 6mm rgba(60,30,20,.25); position: relative; }
.movil img { width: 100%; display: block; border-radius: 4.8mm; }
.recortado { overflow: hidden; }
.movil.recortado::after, .pieza.recortado::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 14mm;
  background: linear-gradient(transparent, rgba(248,241,230,.95)); }
.movil.recortado::after { background: linear-gradient(transparent, rgba(29,20,18,.85)); }
.pieza { flex: none; position: relative; border-radius: 3mm; overflow: hidden; box-shadow: 0 1.5mm 5mm rgba(60,30,20,.18); background: #fff; }
.pieza.plana { box-shadow: none; }
.pieza img { width: 100%; display: block; }
.paso { display: flex; gap: 3.5mm; align-items: flex-start; }
.paso > b { flex: none; width: 8mm; height: 8mm; border-radius: 50%; background: var(--vino); color: #fff;
  display: grid; place-items: center; font-family: Lora, Georgia, serif; font-size: 11pt; }
.paso h4 { font-size: 11.5pt; margin-bottom: .8mm; }
.paso p { color: #4a3b34; }
.nota { margin-top: 7mm; background: #fff4dc; border: .3mm solid #e6cf98; border-radius: 3mm; padding: 4mm 5mm; color: #5d4512; }
.nota.peq { margin-top: 0; font-size: 8.6pt; padding: 3mm 4mm; }
.peq { font-size: 8.6pt; } .muted { color: var(--suave); font-weight: 400; }
.pie-foto { text-align: center; color: var(--suave); font-size: 8.4pt; margin-top: 3mm; }
.caja { background: var(--papel); border: .3mm solid var(--linea); border-radius: 4mm; padding: 5mm 6mm; }
.caja h3 { margin-top: 0; }
.lista { list-style: none; display: flex; flex-direction: column; gap: 2.2mm; }
.lista li { padding-left: 5mm; position: relative; }
.lista li::before { content: "✦"; position: absolute; left: 0; color: var(--oro); font-size: 8pt; top: .4mm; }
.flujo { display: flex; align-items: stretch; gap: 2mm; margin: 4mm 0 9mm; }
.flujo .nodo { flex: 1; background: var(--papel); border: .3mm solid var(--linea); border-radius: 4mm; padding: 4mm 3mm; text-align: center; }
.flujo .nodo span { display: grid; place-items: center; width: 11mm; height: 11mm; margin: 0 auto 2mm; border-radius: 50%;
  background: var(--vino); color: #fff; font-size: 13pt; }
.flujo .nodo h4 { font-size: 11pt; color: var(--vino); }
.flujo .nodo p { font-size: 8.2pt; color: var(--suave); margin-top: 1mm; }
.flujo .flecha { align-self: center; color: var(--oro); font-size: 16pt; font-weight: 700; }
pre { background: #2a1c18; color: #f6ead6; border-radius: 3mm; padding: 3.5mm 4mm; font-family: "DejaVu Sans Mono", Menlo, monospace;
  font-size: 7.6pt; line-height: 1.5; white-space: pre; margin-bottom: 2mm; }
.tabla-conf { width: 100%; border-collapse: collapse; font-size: 8.2pt; margin: 1mm 0 2mm; }
.tabla-conf td { padding: 1.6mm 1.5mm; border-bottom: .3mm solid var(--linea); vertical-align: top; }
.tabla-conf td:first-child { white-space: nowrap; }
.pie-final { position: absolute; left: 15mm; right: 15mm; bottom: 8mm; text-align: center; color: var(--suave); font-size: 8pt;
  border-top: .3mm solid var(--linea); padding-top: 2.5mm; }

/* portada */
.portada { background: radial-gradient(120% 80% at 90% 0%, #9a2a3b 0%, var(--vino) 45%, var(--vino2) 100%); color: #fff6e6; padding: 0; }
.portada .puntos { position: absolute; inset: 0; background-image: radial-gradient(rgba(255,255,255,.08) .4mm, transparent .5mm); background-size: 5mm 5mm; }
.portada .aro { position: absolute; border-radius: 50%; border: .7mm solid rgba(196,154,69,.45); }
.portada .a1 { width: 170mm; height: 170mm; right: -70mm; top: -60mm; }
.portada .a2 { width: 90mm; height: 90mm; left: -40mm; bottom: -30mm; }
.texto-portada { position: absolute; left: 18mm; top: 34mm; width: 95mm; }
.adorno { color: var(--oro2); letter-spacing: 1.4mm; text-transform: uppercase; font-weight: 600; font-size: 10pt; }
.portada h1 { font-size: 50pt; color: #fff8ec; margin: 3mm 0 6mm; letter-spacing: -.5mm; }
.portada .lema { font-size: 12pt; line-height: 1.55; color: rgba(255,246,230,.92); }
.indice { list-style: none; margin-top: 16mm; display: flex; flex-direction: column; gap: 3.5mm; font-size: 11.5pt; font-weight: 500; }
.indice b { display: inline-grid; place-items: center; width: 8mm; height: 8mm; border-radius: 50%; background: var(--oro); color: var(--vino2);
  margin-right: 3mm; font-family: Lora, Georgia, serif; }
.telefono-portada { position: absolute; right: 18mm; top: 52mm; transform: rotate(4deg); }
.telefono-portada .movil { border-color: #120c0b; box-shadow: 0 6mm 16mm rgba(0,0,0,.45); }
.pie-portada { position: absolute; left: 0; right: 0; bottom: 12mm; text-align: center; font-size: 8.5pt; color: rgba(255,246,230,.75); }
"""

html = f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>CestaOLA · Guía visual</title><style>{CSS}</style></head><body>{''.join(PAGINAS)}</body></html>"
ruta_html = os.path.join(AQUI, "guia.html")
open(ruta_html, "w").write(html)

from playwright.sync_api import sync_playwright  # noqa: E402

chrome = shutil.which("google-chrome") or shutil.which("chromium")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox", "--allow-file-access-from-files"])
    pg = b.new_page()
    pg.goto("file://" + ruta_html)
    pg.wait_for_timeout(600)
    pg.pdf(path=SALIDA, format="A4", print_background=True, prefer_css_page_size=True)
    b.close()
print("Guía generada:", SALIDA, f"({len(PAGINAS)} páginas)")
if "--html" not in sys.argv:
    os.remove(ruta_html)
