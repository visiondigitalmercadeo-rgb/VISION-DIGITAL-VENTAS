import base64

import pandas as pd
import streamlit as st

import auth
import database as db
from config import CAPACITACION_ARCHIVO_MAX_BYTES, CAPACITACION_ARCHIVOS_MAX, CAPACITACION_TIENDAS
from utils import archivos_a_b64_lista, diseno_archivos_lista, download_excel_button, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🎓 Capacitación")
st.caption(
    "Módulos y submódulos de capacitación por tienda, con material de apoyo y calificación "
    "del personal."
)

puede_editar = auth.puede_editar_capacitacion()

# ---------------------------------------------------------------------------
# Resumen numérico rápido
# ---------------------------------------------------------------------------
modulos_all = db.list_modulos()
submodulos_all = [sm for m in modulos_all for sm in db.list_submodulos(m["id"])]
personal_activo = db.list_personal_tiendas(solo_activos=True)
todas_calif = db.list_calificaciones()
promedio_general = (sum(c["calificacion"] for c in todas_calif) / len(todas_calif)) if todas_calif else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Módulos", len(modulos_all))
k2.metric("Submódulos", len(submodulos_all))
k3.metric("Personal activo", len(personal_activo))
k4.metric("Promedio de calificación", f"{promedio_general:.0f}" if todas_calif else "—")

st.divider()

tab_modulos, tab_personal, tab_calificaciones = st.tabs(
    ["📚 Módulos", "🏬 Personal por tienda", "📝 Calificaciones"]
)

# --------------------------------------------------------------------------
# Módulos y submódulos
# --------------------------------------------------------------------------
with tab_modulos:
    if puede_editar:
        with st.expander("➕ Crear nuevo módulo"):
            with st.form("nuevo_modulo_form", clear_on_submit=True):
                nombre_mod = st.text_input("Nombre del módulo (ej. 'Ventas')")
                desc_mod = st.text_area("Descripción (opcional)")
                if st.form_submit_button("Crear módulo", use_container_width=True):
                    if not nombre_mod.strip():
                        st.error("El nombre del módulo es obligatorio.")
                    else:
                        db.create_modulo(nombre_mod.strip(), desc_mod.strip() or None)
                        st.success(f"Módulo '{nombre_mod}' creado.")
                        st.rerun()

    if not modulos_all:
        st.info("Todavía no hay módulos de capacitación." + (" Crea el primero arriba." if puede_editar else ""))
    else:
        for m in modulos_all:
            submods = db.list_submodulos(m["id"])
            with st.expander(f"📁 {m['nombre']} ({len(submods)} submódulo{'s' if len(submods) != 1 else ''})"):
                if m.get("descripcion"):
                    st.caption(m["descripcion"])

                if not submods:
                    st.caption("Sin submódulos todavía.")
                else:
                    for sm in submods:
                        with st.container(border=True):
                            st.markdown(f"**📂 {sm['nombre']}**")
                            if sm.get("descripcion"):
                                st.caption(sm["descripcion"])
                            archivos = diseno_archivos_lista(sm)
                            if archivos:
                                for i, a in enumerate(archivos):
                                    st.download_button(
                                        f"📎 {a['nombre']}", data=base64.b64decode(a["b64"]),
                                        file_name=a["nombre"], mime=a.get("tipo") or "application/octet-stream",
                                        use_container_width=True, key=f"cap_file_{sm['id']}_{i}",
                                    )
                            else:
                                st.caption("Sin archivos adjuntos.")

                            if puede_editar:
                                editando_key = f"cap_editando_sm_{sm['id']}"
                                if st.button(
                                    "✏️ Editar / eliminar", key=f"cap_toggle_sm_{sm['id']}", use_container_width=True,
                                ):
                                    st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                    st.rerun()

                                if st.session_state.get(editando_key):
                                    with st.form(f"editar_submodulo_{sm['id']}"):
                                        nombre_sm_ed = st.text_input("Nombre del submódulo", value=sm["nombre"])
                                        desc_sm_ed = st.text_area("Descripción", value=sm.get("descripcion") or "")
                                        st.caption(
                                            f"Archivos actuales: {', '.join(a['nombre'] for a in archivos)}"
                                            if archivos else "Archivos actuales: ninguno."
                                        )
                                        nuevos_archivos = st.file_uploader(
                                            f"Reemplazar archivos (máximo {CAPACITACION_ARCHIVOS_MAX}) — "
                                            "déjalo vacío para no cambiarlos",
                                            accept_multiple_files=True, key=f"cap_reemplazar_{sm['id']}",
                                        )
                                        colf1, colf2 = st.columns(2)
                                        guardar_sm = colf1.form_submit_button("Guardar cambios", use_container_width=True)
                                        eliminar_sm = colf2.form_submit_button("Eliminar submódulo", use_container_width=True)
                                        if guardar_sm:
                                            if not nombre_sm_ed.strip():
                                                st.error("El nombre del submódulo es obligatorio.")
                                            else:
                                                update_kwargs = {
                                                    "nombre": nombre_sm_ed.strip(),
                                                    "descripcion": desc_sm_ed.strip() or None,
                                                }
                                                error_archivo = None
                                                if nuevos_archivos:
                                                    try:
                                                        update_kwargs["archivos"] = archivos_a_b64_lista(
                                                            nuevos_archivos, CAPACITACION_ARCHIVO_MAX_BYTES,
                                                            CAPACITACION_ARCHIVOS_MAX,
                                                        )
                                                    except ValueError as e:
                                                        error_archivo = str(e)
                                                if error_archivo:
                                                    st.error(error_archivo)
                                                else:
                                                    db.update_submodulo(sm["id"], **update_kwargs)
                                                    st.session_state.pop(editando_key, None)
                                                    st.success("Submódulo actualizado.")
                                                    st.rerun()
                                        if eliminar_sm:
                                            db.delete_submodulo(sm["id"])
                                            st.session_state.pop(editando_key, None)
                                            st.success("Submódulo eliminado.")
                                            st.rerun()

                if puede_editar:
                    st.markdown("###### ➕ Agregar submódulo")
                    with st.form(f"nuevo_submodulo_{m['id']}", clear_on_submit=True):
                        nombre_sm = st.text_input("Nombre del submódulo (ej. 'Selling up')")
                        desc_sm = st.text_area("Descripción (opcional)")
                        archivos_subidos = st.file_uploader(
                            f"Presentación, políticas o material de apoyo (máximo {CAPACITACION_ARCHIVOS_MAX} archivos)",
                            accept_multiple_files=True, key=f"cap_nuevo_archivo_{m['id']}",
                        )
                        if st.form_submit_button("Crear submódulo", use_container_width=True):
                            if not nombre_sm.strip():
                                st.error("El nombre del submódulo es obligatorio.")
                            else:
                                try:
                                    archivos_lista = archivos_a_b64_lista(
                                        archivos_subidos, CAPACITACION_ARCHIVO_MAX_BYTES, CAPACITACION_ARCHIVOS_MAX,
                                    )
                                except ValueError as e:
                                    st.error(str(e))
                                else:
                                    db.create_submodulo(m["id"], nombre_sm.strip(), desc_sm.strip() or None, archivos_lista)
                                    st.success(f"Submódulo '{nombre_sm}' creado.")
                                    st.rerun()

                    st.divider()
                    editando_mod_key = f"cap_editando_mod_{m['id']}"
                    if st.button("⚙️ Editar / eliminar este módulo", key=f"cap_toggle_mod_{m['id']}", use_container_width=True):
                        st.session_state[editando_mod_key] = not st.session_state.get(editando_mod_key, False)
                        st.rerun()

                    if st.session_state.get(editando_mod_key):
                        with st.form(f"editar_modulo_{m['id']}"):
                            nombre_mod_ed = st.text_input("Nombre del módulo", value=m["nombre"])
                            desc_mod_ed = st.text_area("Descripción", value=m.get("descripcion") or "")
                            if st.form_submit_button("Guardar cambios", use_container_width=True):
                                if not nombre_mod_ed.strip():
                                    st.error("El nombre del módulo es obligatorio.")
                                else:
                                    db.update_modulo(
                                        m["id"], nombre=nombre_mod_ed.strip(), descripcion=desc_mod_ed.strip() or None,
                                    )
                                    st.session_state.pop(editando_mod_key, None)
                                    st.success("Módulo actualizado.")
                                    st.rerun()

                        st.caption(
                            "⚠️ Eliminar el módulo también elimina todos sus submódulos, archivos y "
                            "calificaciones asociadas — no se puede deshacer."
                        )
                        confirmar_borrar_mod = st.checkbox(
                            "Confirmo que deseo eliminar este módulo por completo", key=f"cap_confirmar_del_mod_{m['id']}",
                        )
                        if st.button(
                            "🗑️ Eliminar módulo", key=f"cap_del_mod_{m['id']}", disabled=not confirmar_borrar_mod,
                        ):
                            db.delete_modulo(m["id"])
                            st.session_state.pop(editando_mod_key, None)
                            st.success("Módulo eliminado.")
                            st.rerun()

# --------------------------------------------------------------------------
# Personal por tienda
# --------------------------------------------------------------------------
with tab_personal:
    if puede_editar:
        with st.expander("➕ Agregar personal"):
            with st.form("nuevo_personal_form", clear_on_submit=True):
                nombre_p = st.text_input("Nombre completo")
                c1, c2 = st.columns(2)
                tienda_p = c1.selectbox("Tienda", CAPACITACION_TIENDAS)
                puesto_p = c2.text_input("Puesto (opcional)")
                if st.form_submit_button("Agregar personal", use_container_width=True):
                    if not nombre_p.strip():
                        st.error("El nombre es obligatorio.")
                    else:
                        db.create_personal_tienda(nombre_p.strip(), tienda_p, puesto_p.strip() or None)
                        st.success(f"'{nombre_p}' agregado a {tienda_p}.")
                        st.rerun()

    st.divider()
    filtro_tienda = st.selectbox(
        "Filtrar por tienda", ["Todas"] + CAPACITACION_TIENDAS, key="cap_filtro_tienda_personal",
    )
    personal_lista = db.list_personal_tiendas(
        tienda=None if filtro_tienda == "Todas" else filtro_tienda, solo_activos=False,
    )
    if not personal_lista:
        st.info("No hay personal registrado con este filtro.")
    else:
        df_personal = pd.DataFrame([{
            "Nombre": p["nombre"], "Tienda": p["tienda"], "Puesto": p.get("puesto") or "—",
            "Activo": "Sí" if p.get("activo", True) else "No",
        } for p in personal_lista])
        st.dataframe(df_personal, use_container_width=True, hide_index=True)
        download_excel_button(df_personal, "personal_tiendas.xlsx", key="cap_descargar_personal")

        if puede_editar:
            st.markdown("#### ✏️ Editar / activar / eliminar")
            opciones_p_ed = {
                f"{p['nombre']} — {p['tienda']}" + ("" if p.get("activo", True) else " (inactivo)"): p["id"]
                for p in personal_lista
            }
            elegido_p = st.selectbox("Selecciona una persona", ["—"] + list(opciones_p_ed.keys()), key="cap_personal_editar")
            if elegido_p != "—":
                pid = opciones_p_ed[elegido_p]
                p_ed = db.get_personal_tienda(pid)
                with st.form(f"editar_personal_{pid}"):
                    nombre_p_ed = st.text_input("Nombre", value=p_ed["nombre"])
                    c1, c2 = st.columns(2)
                    tienda_p_ed = c1.selectbox(
                        "Tienda", CAPACITACION_TIENDAS,
                        index=CAPACITACION_TIENDAS.index(p_ed["tienda"]) if p_ed.get("tienda") in CAPACITACION_TIENDAS else 0,
                    )
                    puesto_p_ed = c2.text_input("Puesto", value=p_ed.get("puesto") or "")
                    activo_p_ed = st.checkbox("Activo", value=p_ed.get("activo", True))
                    colf1, colf2 = st.columns(2)
                    guardar_p = colf1.form_submit_button("Guardar cambios", use_container_width=True)
                    eliminar_p = colf2.form_submit_button("Eliminar de la lista", use_container_width=True)
                    if guardar_p:
                        if not nombre_p_ed.strip():
                            st.error("El nombre es obligatorio.")
                        else:
                            db.update_personal_tienda(
                                pid, nombre=nombre_p_ed.strip(), tienda=tienda_p_ed,
                                puesto=puesto_p_ed.strip() or None, activo=activo_p_ed,
                            )
                            st.success("Actualizado.")
                            st.rerun()
                    if eliminar_p:
                        db.delete_personal_tienda(pid)
                        st.success("Eliminado de la lista.")
                        st.rerun()

# --------------------------------------------------------------------------
# Calificaciones
# --------------------------------------------------------------------------
with tab_calificaciones:
    if not personal_activo:
        st.info("Primero agrega personal en la pestaña 'Personal por tienda'.")
    elif not modulos_all:
        st.info("Primero crea al menos un módulo en la pestaña 'Módulos'.")
    else:
        c1, c2 = st.columns(2)
        tienda_calif_sel = c1.selectbox("Tienda", ["Todas"] + CAPACITACION_TIENDAS, key="cap_calif_tienda")
        personal_filtrado = (
            personal_activo if tienda_calif_sel == "Todas"
            else [p for p in personal_activo if p["tienda"] == tienda_calif_sel]
        )
        if not personal_filtrado:
            st.info("No hay personal activo en esta tienda.")
        else:
            opciones_persona = {f"{p['nombre']} ({p['tienda']})": p["id"] for p in personal_filtrado}
            persona_nombre_sel = c2.selectbox("Persona", list(opciones_persona.keys()), key="cap_calif_persona")
            persona_id_sel = opciones_persona[persona_nombre_sel]

            opciones_modulo = {m["nombre"]: m["id"] for m in modulos_all}
            modulo_nombre_sel = st.selectbox("Módulo", list(opciones_modulo.keys()), key="cap_calif_modulo")
            modulo_id_sel = opciones_modulo[modulo_nombre_sel]

            submods_sel = db.list_submodulos(modulo_id_sel)

            if puede_editar:
                with st.form(f"calificar_form_{persona_id_sel}_{modulo_id_sel}"):
                    calif_general_actual = db.get_calificacion(persona_id_sel, modulo_id_sel, None)
                    calif_general = st.number_input(
                        f"Calificación general — {modulo_nombre_sel} (0-100)", min_value=0, max_value=100, step=5,
                        value=int(calif_general_actual["calificacion"]) if calif_general_actual else 0,
                        key=f"cap_calif_gen_{persona_id_sel}_{modulo_id_sel}",
                    )
                    valores_sub = {}
                    for sm in submods_sel:
                        calif_sm_actual = db.get_calificacion(persona_id_sel, modulo_id_sel, sm["id"])
                        valores_sub[sm["id"]] = st.number_input(
                            f"«{sm['nombre']}» (0-100)", min_value=0, max_value=100, step=5,
                            value=int(calif_sm_actual["calificacion"]) if calif_sm_actual else 0,
                            key=f"cap_calif_sm_{persona_id_sel}_{sm['id']}",
                        )
                    if st.form_submit_button("💾 Guardar calificaciones", use_container_width=True):
                        db.upsert_calificacion(persona_id_sel, modulo_id_sel, None, calif_general)
                        for sm_id, val in valores_sub.items():
                            db.upsert_calificacion(persona_id_sel, modulo_id_sel, sm_id, val)
                        st.success(
                            f"Calificaciones de {persona_nombre_sel} guardadas para el módulo '{modulo_nombre_sel}'.",
                        )
                        st.rerun()
            else:
                st.caption("Tu rol es de solo vista: puedes consultar pero no calificar.")

            st.divider()

        st.markdown("##### Resumen de calificaciones registradas")
        if not todas_calif:
            st.caption("Todavía no hay calificaciones registradas.")
        else:
            personal_lookup = {p["id"]: p for p in db.list_personal_tiendas(solo_activos=False)}
            modulos_lookup = {m["id"]: m for m in modulos_all}
            submods_lookup = {sm["id"]: sm for sm in submodulos_all}
            filas_calif = []
            for c in todas_calif:
                persona_c = personal_lookup.get(c.get("persona_id"))
                modulo_c = modulos_lookup.get(c.get("modulo_id"))
                submod_c = submods_lookup.get(c.get("submodulo_id")) if c.get("submodulo_id") else None
                filas_calif.append({
                    "Persona": persona_c["nombre"] if persona_c else "—",
                    "Tienda": persona_c["tienda"] if persona_c else "—",
                    "Módulo": modulo_c["nombre"] if modulo_c else "—",
                    "Submódulo": submod_c["nombre"] if submod_c else "General",
                    "Calificación": c.get("calificacion"),
                    "Actualizado": c.get("actualizado_en"),
                })
            df_calif = pd.DataFrame(filas_calif).sort_values(["Persona", "Módulo", "Submódulo"])
            st.dataframe(df_calif, use_container_width=True, hide_index=True)
            download_excel_button(df_calif, "calificaciones_capacitacion.xlsx", key="cap_descargar_calif")
