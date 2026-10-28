"""Ícono y nombre para la pantalla de inicio del celular (favicon, apple-touch-icon y manifest)."""
import base64
from pathlib import Path

import streamlit as st

NOMBRE, COLOR = "Magoia", "#FFFFFF"

JS = """<script>
(function () {
  var ICON = "__ICON__", NOMBRE = "__NOMBRE__", COLOR = "__COLOR__";
  function aplicar(doc, loc) {
    var quitar = function (sel) { doc.querySelectorAll(sel).forEach(function (n) { n.remove(); }); };
    var link = function (rel, attrs) {
      var l = doc.createElement("link"); l.setAttribute("rel", rel);
      Object.keys(attrs).forEach(function (k) { l.setAttribute(k, attrs[k]); });
      doc.head.appendChild(l);
    };
    var meta = function (n, c) {
      quitar('meta[name="' + n + '"]');
      var m = doc.createElement("meta"); m.setAttribute("name", n); m.setAttribute("content", c);
      doc.head.appendChild(m);
    };
    var iconos = doc.querySelectorAll('link[rel~="icon"]');
    if (iconos.length) { iconos.forEach(function (n) { n.setAttribute("href", ICON); n.setAttribute("type", "image/png"); }); }
    else { link("icon", {type: "image/png", href: ICON}); }
    quitar('link[rel="apple-touch-icon"]');
    link("apple-touch-icon", {href: ICON});
    var man = {name: "Consultora Agrofinanzas Magoia", short_name: NOMBRE, display: "standalone", background_color: COLOR,
               theme_color: COLOR, start_url: loc.href, scope: loc.origin + "/",
               icons: [{src: ICON, sizes: "512x512", type: "image/png", purpose: "any"}]};
    var href = "data:application/manifest+json," + encodeURIComponent(JSON.stringify(man));
    var existente = doc.querySelector('link[rel="manifest"]');
    if (existente) { existente.setAttribute("href", href); } else { link("manifest", {href: href}); }
    meta("apple-mobile-web-app-title", NOMBRE);
    meta("apple-mobile-web-app-capable", "yes");
    meta("mobile-web-app-capable", "yes");
    meta("theme-color", COLOR);
  }
  [window.parent, window.top].forEach(function (w) { try { aplicar(w.document, w.location); } catch (e) {} });
})();
</script>"""


def _incrustar(html):
    """Ejecuta el script en un iframe invisible (st.iframe; components.html en versiones viejas)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=0)


def icono_movil():
    """Pone el ícono propio (icono.png junto a app.py) en la pestaña y en 'Agregar a pantalla de inicio'."""
    f = Path(__file__).with_name("icono.png")
    if not f.exists():
        return
    try:
        uri = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode()
        _incrustar(JS.replace("__ICON__", uri).replace("__NOMBRE__", NOMBRE).replace("__COLOR__", COLOR))
    except Exception:
        pass  # el ícono es opcional: si algo falla, la app sigue normal

# FIN icono_movil.py
