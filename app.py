"""Seguimiento de trámites de aprovechamiento forestal ante las CAR — Unergy.

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import hmac

import streamlit as st

from config.constantes import SecretKey
from config.flujos import validar_flujos
from ui.componentes import aplicar_estilos
from ui.datos import leer_seccion

st.set_page_config(page_title="Seguimiento forestal · Unergy", page_icon="🌳", layout="wide")
aplicar_estilos()


def acceso_permitido() -> bool:
    """Si en Secrets existe [app] password, se pide antes de mostrar datos."""
    clave = str(leer_seccion(SecretKey.SECCION_APP).get(SecretKey.PASSWORD.value) or "")
    if not clave or st.session_state.get("_acceso_ok"):
        return True
    st.title("Seguimiento forestal")
    escrita = st.text_input("Contraseña", type="password")
    if escrita and hmac.compare_digest(escrita.encode(), clave.encode()):
        st.session_state["_acceso_ok"] = True
        st.rerun()
    elif escrita:
        st.error("Contraseña incorrecta.")
    return False


if not acceso_permitido():
    st.stop()

errores_config = validar_flujos()
if errores_config:
    st.error("Hay errores en config/flujos.py:\n\n" + "\n".join(f"- {e}" for e in errores_config))
    st.stop()

pagina = st.navigation(
    [
        st.Page("paginas/vista_general.py", title="Vista general", icon="🧭", default=True),
        st.Page("paginas/proyectos.py", title="Proyectos", icon="🌳"),
        st.Page("paginas/historico.py", title="Histórico y calidad de datos", icon="📚"),
        st.Page("paginas/explorar_api.py", title="Explorar API", icon="🔌"),
    ]
)
pagina.run()
