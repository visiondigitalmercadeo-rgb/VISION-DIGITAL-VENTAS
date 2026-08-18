import streamlit as st

import database as db
from config import EMPRESA_LEMA, EMPRESA_NOMBRE, LOGO_PATH


def do_login(username: str, password: str) -> bool:
    user = db.get_user_by_username(username.strip().lower())
    if not user or not user["activo"]:
        return False
    if not db.check_password(password, user["password_hash"]):
        return False
    st.session_state["user"] = {
        "id": user["id"],
        "nombre": user["nombre"],
        "username": user["username"],
        "rol": user["rol"],
    }
    return True


def do_logout():
    st.session_state.pop("user", None)


def current_user():
    return st.session_state.get("user")


def require_login():
    """Muestra el formulario de login si no hay sesión activa. Debe llamarse
    al inicio de app.py. Devuelve True si hay un usuario autenticado."""
    if current_user():
        return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_PATH, width=320)
        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.5rem;'>{EMPRESA_NOMBRE} · Plataforma Comercial</h3>"
            f"<p style='text-align:center;color:#52514e;'>{EMPRESA_LEMA} · "
            "Citas · CRM · Cotizaciones · Reclamos · Ventas · KPIs</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)
            if submitted:
                if do_login(username, password):
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos, o el usuario está inactivo.")
        with st.expander("Usuarios de demostración"):
            st.markdown(
                "- **admin** / admin123 — Administrador\n"
                "- **vista** / vista123 — Solo vista\n"
                "- **juan** / vendedor123 — Vendedor\n"
                "- **maria** / vendedor123 — Vendedor\n"
                "- **carlos** / vendedor123 — Vendedor"
            )
    return False


def is_admin():
    u = current_user()
    return u is not None and u["rol"] == "admin"


def is_vendedor():
    u = current_user()
    return u is not None and u["rol"] == "vendedor"


def is_vista():
    u = current_user()
    return u is not None and u["rol"] == "vista"


def can_edit():
    """Admin y vendedor pueden crear/editar; el rol 'vista' es solo lectura."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "vendedor")
