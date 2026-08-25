import pandas as pd
import streamlit as st

import auth
import database as db
from config import ROLES, ROLES_DE_TIENDA, ROLES_LABEL, TICKET_TIENDAS
from utils import sidebar_user_box

user = auth.current_user()
sidebar_user_box()

if not auth.is_admin():
    st.error("Esta sección es solo para administradores.")
    st.stop()

st.title("👥 Administración de usuarios")
st.caption("Crear vendedores y usuarios de solo vista, activar/desactivar accesos y restablecer contraseñas.")

tab_lista, tab_nueva = st.tabs(["📋 Usuarios", "➕ Nuevo usuario"])

with tab_lista:
    usuarios = db.list_usuarios()
    df = pd.DataFrame([{
        "ID": u["id"], "Nombre": u["nombre"], "Usuario": u["username"],
        "Rol": ROLES_LABEL.get(u["rol"], u["rol"]), "Tienda": u.get("tienda") or "—",
        "Activo": "Sí" if u["activo"] else "No",
    } for u in usuarios])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("#### ✏️ Gestionar usuario")
    opciones = {f"{u['nombre']} ({u['username']})": u["id"] for u in usuarios}
    elegido = st.selectbox("Selecciona un usuario", ["—"] + list(opciones.keys()))
    if elegido != "—":
        uid = opciones[elegido]
        u = next(x for x in usuarios if x["id"] == uid)

        col1, col2 = st.columns(2)
        with col1:
            nuevo_estado = st.toggle("Usuario activo", value=bool(u["activo"]), key=f"toggle_{uid}")
            if nuevo_estado != bool(u["activo"]):
                db.set_usuario_activo(uid, nuevo_estado)
                st.success("Estado actualizado.")
                st.rerun()
        with col2:
            with st.form(f"reset_pwd_{uid}"):
                nueva_pwd = st.text_input("Nueva contraseña", type="password")
                if st.form_submit_button("Restablecer contraseña"):
                    if len(nueva_pwd) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres.")
                    else:
                        db.reset_password(uid, nueva_pwd)
                        st.success("Contraseña actualizada.")

        st.markdown("#### ✏️ Editar usuario")
        with st.form(f"editar_usuario_{uid}"):
            nombre_ed = st.text_input("Nombre completo", value=u["nombre"] or "")
            username_ed = st.text_input("Usuario (para iniciar sesión)", value=u["username"] or "")
            es_unico_admin = u["rol"] == "admin" and sum(1 for x in usuarios if x["rol"] == "admin") <= 1
            if es_unico_admin:
                st.caption("Este es el único administrador, así que su rol no se puede cambiar aquí.")
                rol_ed = "admin"
            else:
                rol_ed = st.selectbox(
                    "Rol", ROLES, index=ROLES.index(u["rol"]) if u["rol"] in ROLES else 0,
                    format_func=lambda r: ROLES_LABEL.get(r, r),
                )
            tienda_ed = st.selectbox(
                "Tienda (solo aplica a Anfitriona, Jefe de tienda o Asesor de ventas)",
                ["—"] + TICKET_TIENDAS,
                index=(["—"] + TICKET_TIENDAS).index(u["tienda"]) if u.get("tienda") in TICKET_TIENDAS else 0,
            )
            if st.form_submit_button("Guardar cambios", use_container_width=True):
                username_norm = username_ed.strip().lower()
                if not nombre_ed.strip() or not username_norm:
                    st.error("Completa nombre y usuario.")
                elif rol_ed in ROLES_DE_TIENDA and tienda_ed == "—":
                    st.error("Este rol necesita una tienda asignada.")
                else:
                    existente = db.get_user_by_username(username_norm)
                    if existente and existente["id"] != uid:
                        st.error("Ese nombre de usuario ya lo usa otra persona.")
                    else:
                        db.update_usuario(
                            uid, nombre=nombre_ed.strip(), username=username_norm, rol=rol_ed,
                            tienda=None if tienda_ed == "—" else tienda_ed,
                        )
                        st.success("Usuario actualizado.")
                        st.rerun()

        st.markdown("#### 🗑️ Eliminar usuario")
        st.caption(
            "Esto borra el acceso de este usuario por completo (no se puede deshacer). Los prospectos, "
            "citas, cotizaciones, reclamos y ventas que ya haya registrado **no se eliminan**, solo dejan "
            "de tener un vendedor asignado. Si solo quieres quitarle el acceso temporalmente, mejor usa "
            "el interruptor de 'Usuario activo' de arriba."
        )
        if uid == user["id"]:
            st.info("No puedes eliminar tu propio usuario mientras tienes la sesión iniciada con él.")
        elif u["rol"] == "admin" and sum(1 for x in usuarios if x["rol"] == "admin") <= 1:
            st.info("Este es el único administrador de la plataforma, no se puede eliminar.")
        else:
            with st.form(f"eliminar_usuario_{uid}"):
                confirmar = st.text_input(
                    f"Escribe el usuario **{u['username']}** para confirmar que deseas eliminarlo"
                )
                if st.form_submit_button("Eliminar definitivamente", use_container_width=True):
                    if confirmar.strip() != u["username"]:
                        st.error("El texto no coincide con el nombre de usuario. No se eliminó nada.")
                    else:
                        db.delete_usuario(uid)
                        st.success(f"Usuario '{u['username']}' eliminado.")
                        st.rerun()

with tab_nueva:
    with st.form("nuevo_usuario_form", clear_on_submit=True):
        nombre = st.text_input("Nombre completo")
        username = st.text_input("Usuario (para iniciar sesión)")
        password = st.text_input("Contraseña", type="password")
        rol = st.selectbox("Rol", ROLES, format_func=lambda r: ROLES_LABEL.get(r, r))
        tienda_nueva = st.selectbox(
            "Tienda (solo aplica a Anfitriona, Jefe de tienda o Asesor de ventas)",
            ["—"] + TICKET_TIENDAS,
        )

        if st.form_submit_button("Crear usuario", use_container_width=True):
            if not nombre.strip() or not username.strip() or len(password) < 4:
                st.error("Completa nombre, usuario y una contraseña de al menos 4 caracteres.")
            elif db.get_user_by_username(username.strip().lower()):
                st.error("Ese nombre de usuario ya existe.")
            elif rol in ROLES_DE_TIENDA and tienda_nueva == "—":
                st.error("Este rol necesita una tienda asignada.")
            else:
                db.create_usuario(
                    nombre.strip(), username.strip().lower(), password, rol,
                    tienda=None if tienda_nueva == "—" else tienda_nueva,
                )
                st.success(f"Usuario '{username}' creado como {ROLES_LABEL.get(rol, rol)}.")
                st.rerun()
