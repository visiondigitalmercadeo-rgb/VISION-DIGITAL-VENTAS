import re
import unicodedata

import pandas as pd
import streamlit as st

import auth
import database as db
from config import (
    PAGINAS_ASIGNABLES_EXTRA, PAGINAS_REGISTRO, PERSONAL_TIENDA_INICIAL, ROLES, ROLES_DE_TIENDA, ROLES_LABEL,
    TICKET_TIENDA_SLUG, TICKET_TIENDAS,
)
from utils import download_excel_button, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

if not auth.is_admin():
    st.error("Esta sección es solo para administradores.")
    st.stop()

st.title("👥 Administración de usuarios")
st.caption("Crear vendedores y usuarios de solo vista, activar/desactivar accesos y restablecer contraseñas.")

tab_lista, tab_nueva, tab_carga = st.tabs(
    ["📋 Usuarios", "➕ Nuevo usuario", "📥 Carga inicial de personal"]
)

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

        st.markdown("#### 🔓 Acceso extra a otras pestañas")
        st.caption(
            "Además de las pestañas que ya le da su rol, puedes darle a este usuario acceso a otras "
            "pestañas específicas — por ejemplo, si necesita consultar o usar algo puntual sin tener "
            "que crear un rol nuevo o cambiarle el suyo. Dentro de cada pestaña extra, el usuario sigue "
            "viendo y pudiendo hacer solo lo que su rol normalmente permite ahí — esto únicamente le "
            "abre la puerta para entrar a verla. El usuario debe cerrar sesión y volver a entrar para "
            "que el cambio se vea reflejado."
        )
        etiquetas_paginas = {p["key"]: f"{p['icon']} {p['title']}" for p in PAGINAS_REGISTRO}
        paginas_extra_actuales = [k for k in (u.get("paginas_extra") or []) if k in PAGINAS_ASIGNABLES_EXTRA]
        with st.form(f"paginas_extra_{uid}"):
            seleccion_paginas_extra = st.multiselect(
                "Pestañas adicionales", PAGINAS_ASIGNABLES_EXTRA, default=paginas_extra_actuales,
                format_func=lambda k: etiquetas_paginas.get(k, k),
            )
            if st.form_submit_button("💾 Guardar acceso extra", use_container_width=True):
                db.update_usuario(uid, paginas_extra=seleccion_paginas_extra)
                st.success("Acceso extra actualizado.")
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
        etiquetas_paginas_nuevo = {p["key"]: f"{p['icon']} {p['title']}" for p in PAGINAS_REGISTRO}
        paginas_extra_nuevo = st.multiselect(
            "Acceso extra a otras pestañas (opcional, además de lo que ya da el rol elegido)",
            PAGINAS_ASIGNABLES_EXTRA, format_func=lambda k: etiquetas_paginas_nuevo.get(k, k),
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
                    paginas_extra=paginas_extra_nuevo,
                )
                st.success(f"Usuario '{username}' creado como {ROLES_LABEL.get(rol, rol)}.")
                st.rerun()


def _slug_simple(texto):
    """Quita acentos/símbolos y deja solo minúsculas y números — para armar
    nombres de usuario a partir de un nombre completo."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _generar_username(nombre, reservados):
    """Genera un nombre de usuario nuevo que no esté en 'reservados': primero
    intenta solo el primer nombre; si ya está reservado, agrega la inicial
    del primer apellido; si sigue chocando, agrega un número. Reserva el
    resultado antes de devolverlo."""
    partes = (nombre or "").strip().split()
    base = _slug_simple(partes[0]) if partes else "usuario"
    candidato = base or "usuario"
    if candidato in reservados and len(partes) > 1:
        extra = _slug_simple(partes[1])[:1]
        if extra:
            candidato = base + extra
    original = candidato
    n = 1
    while candidato in reservados:
        n += 1
        candidato = f"{original}{n}"
    reservados.add(candidato)
    return candidato


# Roles de PERSONAL_TIENDA_INICIAL que además necesitan usuario/contraseña
# para iniciar sesión (el resto — asesor_ventas / "Diseñador", acabados,
# express — solo queda como nombre asignado a su tienda, sin acceso).
ROLES_CON_ACCESO = {"jefe_tienda", "subjefe_tienda", "anfitriona", "cajero"}


def _construir_plan_personal():
    """Arma, una sola vez por ejecución, el plan de carga: TODAS las personas
    de PERSONAL_TIENDA_INICIAL quedan como nombre asignado a su tienda (para
    poder elegirlas como quien elabora un pedido); además, solo las que
    tienen un rol de ROLES_CON_ACCESO reciben usuario/contraseña. Comparar
    por nombre + tienda (y no solo por el usuario generado) contra lo que ya
    existe en cada colección es lo que hace seguro volver a presionar el
    botón: a quien ya esté cargado no se le vuelve a crear ni se le cambia
    nada."""
    todos_usuarios = db.list_usuarios()
    reservados = {u["username"] for u in todos_usuarios}
    todo_personal = db.list_personal_tiendas(solo_activos=False)
    plan = []
    for p in PERSONAL_TIENDA_INICIAL:
        necesita_acceso = p["rol"] in ROLES_CON_ACCESO
        ya_en_roster = any(
            x.get("tienda") == p["tienda"]
            and (x.get("nombre") or "").strip().lower() == p["nombre"].strip().lower()
            for x in todo_personal
        )
        item = {**p, "ya_en_roster": ya_en_roster, "necesita_acceso": necesita_acceso}
        if necesita_acceso:
            existente_usuario = next(
                (u for u in todos_usuarios if u.get("tienda") == p["tienda"]
                 and (u.get("nombre") or "").strip().lower() == p["nombre"].strip().lower()),
                None,
            )
            if existente_usuario:
                item["username"] = existente_usuario["username"]
                item["ya_existe_usuario"] = True
            else:
                item["username"] = _generar_username(p["nombre"], reservados)
                item["ya_existe_usuario"] = False
        else:
            item["username"] = None
            item["ya_existe_usuario"] = False
        plan.append(item)
    return plan


with tab_carga:
    st.caption(
        "Personal de tienda que ya nos diste, para dejarlo asignado a su tienda y así poder "
        "elegir quién elabora cada pedido en el Sistema de Tickets — Tiendas. Nota: en tu lista "
        "original, el puesto 'Diseñador' corresponde al rol **Asesor de ventas** del sistema "
        "(no se confunde con los diseñadores del tablero de Diseño Gráfico, que son otra cosa "
        "aparte)."
    )
    st.caption(
        "Solo Anfitriona, Jefe de tienda, Sub jefe de tienda y Cajero reciben usuario y "
        "contraseña para iniciar sesión (la contraseña inicial es la misma para todos los de "
        "una misma tienda, y se puede cambiar después desde 'Gestionar usuario' en la pestaña "
        "'Usuarios'). El resto del personal (asesores de ventas / 'Diseñador', acabados, "
        "express) queda solo como nombre asignado a su tienda, sin usuario. Es seguro presionar "
        "el botón más de una vez: a quien ya esté cargado (se compara por nombre + tienda) no "
        "se le vuelve a cargar ni se le cambia nada."
    )

    plan_personal = _construir_plan_personal()
    filas_preview = [{
        "Tienda": p["tienda"], "Nombre": p["nombre"], "Puesto": p["puesto_original"],
        "Acceso al sistema": "Sí" if p["necesita_acceso"] else "No",
        "Usuario": p["username"] or "—",
        "Contraseña inicial": (
            f"{TICKET_TIENDA_SLUG.get(p['tienda'], p['tienda'].lower())}2026"
            if p["necesita_acceso"] else "—"
        ),
        "Estado": (
            "Ya está" if p["ya_en_roster"] and (not p["necesita_acceso"] or p["ya_existe_usuario"])
            else "Se creará"
        ),
    } for p in plan_personal]
    df_preview = pd.DataFrame(filas_preview)
    st.dataframe(df_preview, use_container_width=True, hide_index=True)
    pendientes = sum(1 for f in filas_preview if f["Estado"] == "Se creará")
    st.caption(f"{pendientes} persona(s) por cargar, de {len(plan_personal)} en total.")

    if pendientes > 0 and st.button("👥 Cargar el personal pendiente", use_container_width=True):
        creados_roster = 0
        creados_usuarios = 0
        for p in plan_personal:
            if not p["ya_en_roster"]:
                db.create_personal_tienda(p["nombre"], p["tienda"], p["puesto_original"])
                creados_roster += 1
            if p["necesita_acceso"] and not p["ya_existe_usuario"]:
                password_p = f"{TICKET_TIENDA_SLUG.get(p['tienda'], p['tienda'].lower())}2026"
                db.create_usuario(p["nombre"], p["username"], password_p, p["rol"], tienda=p["tienda"])
                creados_usuarios += 1
        st.success(
            f"Se agregaron {creados_roster} persona(s) a la lista de personal de tienda y se "
            f"crearon {creados_usuarios} usuario(s) nuevo(s) con acceso al sistema."
        )
        st.rerun()

    download_excel_button(
        df_preview, "personal_tiendas_credenciales.xlsx", key="admin_descargar_personal_credenciales",
    )

    # -----------------------------------------------------------------
    # Limpieza: si esta lista se cargó antes (con una versión anterior de
    # esta pestaña) creando usuario a TODOS, aquí se puede detectar y
    # quitarle el acceso a quienes ya no deberían tenerlo, sin perder su
    # nombre de la lista de personal.
    # -----------------------------------------------------------------
    nombres_sin_acceso = {
        (p["nombre"].strip().lower(), p["tienda"])
        for p in PERSONAL_TIENDA_INICIAL if p["rol"] not in ROLES_CON_ACCESO
    }
    usuarios_de_mas = [
        u for u in db.list_usuarios()
        if ((u.get("nombre") or "").strip().lower(), u.get("tienda")) in nombres_sin_acceso
    ]
    if usuarios_de_mas:
        with st.expander(
            f"🧹 Se encontraron {len(usuarios_de_mas)} usuario(s) que ya no deberían tener acceso"
        ):
            st.caption(
                "Estas personas se habían creado como usuario, pero según la lista más reciente "
                "solo necesitan quedar como nombre asignado a su tienda (sin iniciar sesión). "
                "Puedes quitarles el acceso aquí — su nombre sigue disponible para asignarles "
                "pedidos, solo se elimina su usuario y contraseña."
            )
            df_demas = pd.DataFrame([{
                "Tienda": u.get("tienda") or "—", "Nombre": u["nombre"], "Usuario": u["username"],
                "Rol actual": ROLES_LABEL.get(u["rol"], u["rol"]),
            } for u in usuarios_de_mas])
            st.dataframe(df_demas, use_container_width=True, hide_index=True)
            if st.button("🗑️ Quitar el acceso a estas personas", use_container_width=True):
                for u in usuarios_de_mas:
                    db.delete_usuario(u["id"])
                st.success(f"Se quitó el acceso de {len(usuarios_de_mas)} persona(s).")
                st.rerun()
