/* SPDX-License-Identifier: GPL-3.0-or-later · CestaOLA · Code por Hombrelobo */
// CestaOLA — pequeños detalles de interfaz (sin dependencias)
(function () {
  function euros(cent) {
    return (cent / 100).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
  }

  // Contador de papeletas con importe en vivo
  document.querySelectorAll('[data-contador]').forEach(function (caja) {
    var input = caja.querySelector('input');
    var precio = parseInt(caja.dataset.precio, 10) || 0;
    var max = parseInt(input.max, 10) || 50;
    var salida = document.querySelector(caja.dataset.importe);
    function pintar() {
      var v = Math.max(1, Math.min(max, parseInt(input.value, 10) || 1));
      if (salida) salida.textContent = euros(v * precio);
    }
    caja.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = (parseInt(input.value, 10) || 1) + parseInt(b.dataset.paso, 10);
        input.value = Math.max(1, Math.min(max, v));
        pintar();
      });
    });
    input.addEventListener('input', pintar);
    pintar();
  });

  // Copiar al portapapeles
  document.querySelectorAll('[data-copiar]').forEach(function (b) {
    b.addEventListener('click', function () {
      var texto = b.dataset.copiar, original = b.textContent;
      function ok() { b.textContent = '¡Copiado!'; setTimeout(function () { b.textContent = original; }, 1600); }
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(texto).then(ok, function () { window.prompt('Copia:', texto); });
      else window.prompt('Copia:', texto);
    });
  });

  // Compartir (menú nativo del móvil o WhatsApp)
  document.querySelectorAll('[data-compartir]').forEach(function (b) {
    b.addEventListener('click', function () {
      var url = b.dataset.compartir, texto = b.dataset.texto || '';
      if (navigator.share) { navigator.share({ title: document.title, text: texto, url: url }).catch(function () {}); }
      else window.open('https://wa.me/?text=' + encodeURIComponent(texto + ' ' + url), '_blank');
    });
  });

  // Compartir un PDF (resguardo) como archivo: WhatsApp, Telegram, correo... desde el móvil.
  // Si el navegador no permite compartir archivos, se abre el PDF y se copia el texto.
  document.querySelectorAll('[data-compartir-pdf]').forEach(function (b) {
    b.addEventListener('click', function () {
      var url = b.dataset.compartirPdf, nombre = b.dataset.nombre || 'resguardo.pdf', texto = b.dataset.texto || '';
      var original = b.textContent; b.textContent = '…';
      fetch(url + (url.indexOf('?') < 0 ? '?' : '&') + 't=' + Date.now(), { credentials: 'same-origin' })
        .then(function (r) {
          if (!r.ok) throw new Error(r.status);
          // El nombre del archivo lo decide el servidor (Content-Disposition), igual al descargar que al compartir
          var cd = r.headers.get('Content-Disposition') || '', m = cd.match(/filename\*=UTF-8''([^;]+)/i) || cd.match(/filename="?([^";]+)"?/i);
          if (m) { try { nombre = decodeURIComponent(m[1]); } catch (e) { nombre = m[1]; } }
          return r.blob();
        })
        .then(function (blob) {
          var f = new File([blob], nombre, { type: 'application/pdf' });
          if (navigator.canShare && navigator.canShare({ files: [f] })) {
            return navigator.share({ files: [f], text: texto, title: nombre });
          }
          window.open(URL.createObjectURL(blob), '_blank');
          if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(texto);
        })
        .catch(function (e) { if (e && e.name !== 'AbortError') window.open(url, '_blank'); })
        .then(function () { b.textContent = original; });
    });
  });

  // Descripciones de los lotes: plegadas a 2 líneas, se despliegan bajo demanda
  document.querySelectorAll('.ver-mas').forEach(function (b) {
    var p = document.getElementById(b.getAttribute('aria-controls'));
    if (!p) return;
    if (p.scrollHeight > p.clientHeight + 2) b.hidden = false;   // solo si de verdad hay más texto
    else p.classList.remove('plegada');
    b.addEventListener('click', function () {
      var abrir = p.classList.contains('plegada');
      p.classList.toggle('plegada', !abrir);
      b.setAttribute('aria-expanded', abrir ? 'true' : 'false');
      b.textContent = abrir ? 'Ver menos ▴' : 'Ver qué incluye ▾';
      if (!abrir) b.closest('.lote').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
  });

  // Nombre del archivo de copia elegido
  var copia = document.getElementById('copia');
  if (copia) copia.addEventListener('change', function () {
    var n = document.getElementById('copia-nombre');
    if (n && copia.files[0]) n.textContent = '✓ ' + copia.files[0].name;
  });

  // Nombres de los tickets elegidos
  var tk = document.getElementById('tickets-archivo');
  if (tk) tk.addEventListener('change', function () {
    var n = document.getElementById('tickets-nombres');
    if (n) n.textContent = tk.files.length ? '✓ ' + Array.prototype.map.call(tk.files, function (f) { return f.name; }).join(', ') : '';
  });

  // Confirmación para acciones peligrosas
  document.querySelectorAll('[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!window.confirm(f.dataset.confirmar)) e.preventDefault(); });
  });

  // Vista previa de la foto antes de subirla
  document.querySelectorAll('input[type=file][data-previa]').forEach(function (inp) {
    inp.addEventListener('change', function () {
      var img = document.querySelector(inp.dataset.previa);
      if (img && inp.files && inp.files[0]) { img.src = URL.createObjectURL(inp.files[0]); img.hidden = false; }
      var n = document.getElementById('foto-nombre');
      if (n && inp.files && inp.files[0]) n.textContent = '✓ ' + inp.files[0].name + ' (se guardará al pulsar Guardar lote)';
    });
  });
})();
