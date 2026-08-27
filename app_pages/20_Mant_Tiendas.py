import base64

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_MANT_TIENDAS, ESTADOS_MANT_TIENDAS_INICIALES, MANT_TIENDAS_FOTO_MAX_BYTES, MANT_TIENDAS_FOTOS_MAX, TICKET_TIENDAS
from utils import archivos_a_b64_lista, download_excel_button, mant_tiendas_resumen_html, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🏬 Mantenimiento de Tiendas")
st.caption(
    "Tablero de solicitudes de mantenimiento de tiendas, estilo Trello — mismo concepto que Diseño "
    "Gráfico. El jefe de tienda (o admin) registra qué hay que arreglar (cae en 'Lista de tareas' o "
    "'Emergencias'); el Jefe de Mantenimiento la va moviendo por el tablero conforme avanza."
)

COLUMN_EMOJI = {
    "Lista de tareas": "📋", "Emergencias": "🚨", "En proceso": "🔧",
    "Requiere seguimiento": "⏳", "Resuelto": "✅",
}
# El semáforo (🟢/🔴) solo se muestra en estas columnas — no aplica a
# "Lista de tareas" ni "Emergencias", que todavía no están en curso.
COLUMNAS_CON_SEMAFORO = {"En proceso", "Requiere seguimiento", "Resuelto"}

puede_crear = auth.puede_crear_mant_tiendas()
puede_mover = auth.puede_mover_mant_tiendas()
tienda_usuario = auth.current_user_tienda()

tab_tablero, tab_nueva = st.tabs(["🗂️ Tablero", "➕ Nueva solicitud"])

# --------------------------------------------------------------------------
# Tablero
# --------------------------------------------------------------------------
with tab_tablero:
    if tienda_usuario:
        filtro_tienda = tienda_usuario
        st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
    else:
        elegido_tienda = st.selectbox(
            "Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mt_filtro_tienda",
        )
        filtro_tienda = None if elegido_tienda == "Todas" else elegido_tienda

    rows = db.list_mant_tiendas(tienda=filtro_tienda)  # ya vienen ordenadas: más nueva primero

    busqueda = st.text_input("🔎 Buscar por tienda, quién solicita o descripción (opcional)", key="mt_busqueda")
    if busqueda.strip():
        q = busqueda.strip().lower()
        rows = [
            r for r in rows
            if q in (r.get("tienda") or "").lower()
            or q in (r.get("quien_solicita") or "").lower()
            or q in (r.get("descripcion") or "").lower()
        ]

    if rows:
        download_excel_button(
            pd.DataFrame([{
                "ID": r["id"], "Tienda": r.get("tienda"), "Quién solicita": r.get("quien_solicita"),
                "Descripción": r.get("descripcion"), "Estado": r.get("estado"),
                "Semáforo": (
                    ("Parado por emergencia" if r.get("detenido_emergencia") else "Sigue en proceso")
                    if r.get("estado") in COLUMNAS_CON_SEMAFORO else "—"
                ),
                "Fotos adjuntas": len(r.get("fotos") or []),
                "Creado": r.get("creado_en"),
            } for r in rows]),
            "solicitudes_mant_tiendas.xlsx", key="mt_descargar_excel",
        )

    # ------------------------------------------------------------------
    # Resumen de pendientes (vista de lista, estilo tablero tipo Asana)
    # — un resumen de las mismas columnas del tablero, antes de mostrarlas.
    # ------------------------------------------------------------------
    st.markdown("#### 📋 Resumen de pendientes")
    st.markdown(
        mant_tiendas_resumen_html(rows, ESTADOS_MANT_TIENDAS, COLUMN_EMOJI, COLUMNAS_CON_SEMAFORO),
        unsafe_allow_html=True,
    )

    st.divider()

    if not (puede_crear or puede_mover):
        st.caption("Tu rol es de solo vista para este tablero.")

    cols = st.columns(len(ESTADOS_MANT_TIENDAS))
    for col, estado in zip(cols, ESTADOS_MANT_TIENDAS):
        items = [r for r in rows if r.get("estado") == estado]
        with col:
            st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
            if not items:
                st.caption("Sin solicitudes.")
            for r in items:
                with st.container(border=True):
                    mid = r["id"]
                    editando_key = f"mt_editando_{mid}"
                    puede_editar_esta = puede_crear and (user["rol"] == "admin" or r.get("creado_por_id") == user["id"])
                    puede_editar_este = puede_editar_esta or puede_mover

                    title_col, edit_col = st.columns([5, 1])
                    with title_col:
                        if estado in COLUMNAS_CON_SEMAFORO:
                            semaforo = "🔴" if r.get("detenido_emergencia") else "🟢"
                            st.markdown(f"{semaforo} **{r.get('tienda') or 'Sin tienda'}**")
                        else:
                            st.markdown(f"**{r.get('tienda') or 'Sin tienda'}**")
                    with edit_col:
                        if puede_editar_este:
                            if st.button("✏️", key=f"mt_editar_{mid}", help="Editar esta solicitud"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()
                    st.caption(f"🙋 Solicita: {r.get('quien_solicita') or '—'}")
                    if r.get("descripcion"):
                        st.caption(f"📝 {r['descripcion']}")
                    st.caption(f"🕒 {(r.get('creado_en') or '')[:16].replace('T', ' ')}")

                    for i, foto in enumerate(r.get("fotos") or []):
                        st.download_button(
                            f"📷 {foto['nombre']}",
                            data=base64.b64decode(foto["b64"]),
                            file_name=foto["nombre"],
                            mime=foto.get("tipo") or "application/octet-stream",
                            use_container_width=True, key=f"mt_foto_{mid}_{i}",
                        )

                    if puede_editar_este and st.session_state.get(editando_key):
                        # ----------------------------------------------------
                        # Edición en línea (se abrió con el lápiz ✏️)
                        # ----------------------------------------------------
                        with st.form(f"gestionar_mt_{mid}"):
                            if puede_editar_esta:
                                if tienda_usuario:
                                    tienda_ed = tienda_usuario
                                    st.caption(f"Tienda: **{tienda_usuario}**")
                                else:
                                    tienda_ed = st.selectbox(
                                        "Tienda", TICKET_TIENDAS,
                                        index=TICKET_TIENDAS.index(r["tienda"]) if r.get("tienda") in TICKET_TIENDAS else 0,
                                    )
                                quien_ed = st.text_input("¿Quién solicita?", value=r.get("quien_solicita") or "")
                                descripcion_ed = st.text_area(
                                    "Descripción del problema", value=r.get("descripcion") or "",
                                )
                                fotos_actuales = r.get("fotos") or []
                                st.caption(
                                    f"Fotos actuales: {', '.join(f['nombre'] for f in fotos_actuales)}"
                                    if fotos_actuales else "Fotos actuales: ninguna."
                                )
                                nuevas_fotos = st.file_uploader(
                                    f"Reemplazar fotos (opcional, máximo {MANT_TIENDAS_FOTOS_MAX})",
                                    type=["png", "jpg", "jpeg"], accept_multiple_files=True,
                                    key=f"mt_foto_ed_{mid}",
                                    help="Si subes fotos aquí, reemplazan a TODAS las actuales. Déjalo vacío para no cambiarlas.",
                                )
                                st.caption(f"Tamaño máximo por foto: {MANT_TIENDAS_FOTO_MAX_BYTES // 1000} KB.")
                            else:
                                nuevas_fotos = None
                                st.caption(f"Tienda: **{r.get('tienda') or '—'}**")
                                st.caption(f"Quién solicita: {r.get('quien_solicita') or '—'}")
                                st.caption(f"Descripción: {r.get('descripcion') or '—'}")

                            if puede_mover:
                                estado_ed = st.selectbox(
                                    "Estado (columna del tablero)", ESTADOS_MANT_TIENDAS,
                                    index=ESTADOS_MANT_TIENDAS.index(r["estado"]) if r.get("estado") in ESTADOS_MANT_TIENDAS else 0,
                                )
                                opciones_semaforo = ["🟢 Sigue en proceso", "🔴 Parado por emergencia"]
                                semaforo_ed = st.radio(
                                    "Semáforo (se muestra en las columnas En proceso, Requiere seguimiento y Resuelto)",
                                    opciones_semaforo,
                                    index=1 if r.get("detenido_emergencia") else 0,
                                    horizontal=True,
                                )
                            else:
                                estado_ed = r.get("estado")
                                st.caption(
                                    f"Estado actual: **{estado_ed}** — solo el Jefe de Mantenimiento o el "
                                    "administrador lo pueden mover."
                                )
                                if r.get("estado") in COLUMNAS_CON_SEMAFORO:
                                    st.caption(
                                        "🔴 Parado por emergencia" if r.get("detenido_emergencia")
                                        else "🟢 Sigue en proceso"
                                    )

                            if puede_editar_esta:
                                colf1, colf2, colf3 = st.columns(3)
                                guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                                eliminar = colf2.form_submit_button("Eliminar", use_container_width=True)
                                cancelar = colf3.form_submit_button("Cancelar", use_container_width=True)
                            else:
                                colf1, colf2 = st.columns(2)
                                guardar = colf1.form_submit_button("Guardar estado", use_container_width=True)
                                eliminar = False
                                cancelar = colf2.form_submit_button("Cancelar", use_container_width=True)

                            if guardar:
                                error_msg = None
                                update_kwargs = {"estado": estado_ed}
                                if puede_mover:
                                    update_kwargs["detenido_emergencia"] = semaforo_ed.startswith("🔴")
                                if puede_editar_esta:
                                    if not quien_ed.strip() or not descripcion_ed.strip():
                                        error_msg = "¿Quién solicita? y la descripción son obligatorios."
                                    else:
                                        update_kwargs.update(
                                            tienda=tienda_ed, quien_solicita=quien_ed.strip(),
                                            descripcion=descripcion_ed.strip(),
                                        )
                                        if nuevas_fotos:
                                            try:
                                                update_kwargs["fotos"] = archivos_a_b64_lista(
                                                    nuevas_fotos, MANT_TIENDAS_FOTO_MAX_BYTES, MANT_TIENDAS_FOTOS_MAX,
                                                )
                                            except ValueError as e:
                                                error_msg = str(e)
                                if error_msg:
                                    st.error(error_msg)
                                else:
                                    db.update_mant_tienda(mid, **update_kwargs)
                                    st.session_state.pop(editando_key, None)
                                    st.success("Solicitud actualizada.")
                                    st.rerun()
                            if eliminar:
                                db.delete_mant_tienda(mid)
                                st.session_state.pop(editando_key, None)
                                st.success("Solicitud eliminada.")
                                st.rerun()
                            if cancelar:
                                st.session_state.pop(editando_key, None)
                                st.rerun()

# --------------------------------------------------------------------------
# Nueva solicitud
# --------------------------------------------------------------------------
with tab_nueva:
    if not puede_crear:
        st.info("Solo el jefe de tienda y los administradores pueden crear solicitudes de mantenimiento.")
    else:
        with st.form("nueva_solicitud_mant_tienda", clear_on_submit=True):
            tipo_solicitud = st.radio(
                "Tipo de solicitud", ESTADOS_MANT_TIENDAS_INICIALES, horizontal=True,
                help="'Emergencias' aparece en su propia columna del tablero para que se vea primero.",
            )
            if tienda_usuario:
                tienda = tienda_usuario
                st.caption(f"Tienda: **{tienda_usuario}**")
            else:
                tienda = st.selectbox("Tienda", TICKET_TIENDAS)
            quien_solicita = st.text_input("¿Quién solicita?")
            descripcion = st.text_area("Descripción del problema")
            fotos = st.file_uploader(
                f"Adjuntar fotos del problema (opcional, máximo {MANT_TIENDAS_FOTOS_MAX}) — PNG o JPEG",
                type=["png", "jpg", "jpeg"], accept_multiple_files=True,
            )
            st.caption(f"Tamaño máximo por foto: {MANT_TIENDAS_FOTO_MAX_BYTES // 1000} KB.")

            if st.form_submit_button("Enviar solicitud", use_container_width=True):
                if not quien_solicita.strip() or not descripcion.strip():
                    st.error("¿Quién solicita? y la descripción son obligatorios.")
                else:
                    try:
                        fotos_lista = archivos_a_b64_lista(fotos, MANT_TIENDAS_FOTO_MAX_BYTES, MANT_TIENDAS_FOTOS_MAX)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        db.create_mant_tienda(
                            user["id"], tienda, quien_solicita.strip(), descripcion.strip(),
                            tipo_solicitud, fotos=fotos_lista,
                        )
                        st.success(f"Solicitud enviada a la columna '{tipo_solicitud}'.")
                        st.rerun()
