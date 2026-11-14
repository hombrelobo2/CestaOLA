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

  // Confirmación para acciones peligrosas
  document.querySelectorAll('[data-confirmar]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!window.confirm(f.dataset.confirmar)) e.preventDefault(); });
  });

  // Vista previa de la foto antes de subirla
  document.querySelectorAll('input[type=file][data-previa]').forEach(function (inp) {
    inp.addEventListener('change', function () {
      var img = document.querySelector(inp.dataset.previa);
      if (img && inp.files && inp.files[0]) { img.src = URL.createObjectURL(inp.files[0]); img.hidden = false; }
    });
  });
})();
