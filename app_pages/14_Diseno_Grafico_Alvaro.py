import base64
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import (
    DISENO_ARCHIVO_MAX_BYTES, DISENO_ARCHIVO_MAX_BYTES_STORAGE, DISENO_ARCHIVOS_MAX, ESTADOS_DISENO,
    ESTADOS_DISENO_INICIALES, LINEAS_VENTA,
)
from utils import (
    archivos_a_b64_lista, diseno_archivos_lista, diseno_pdf_bytes, diseno_resumen_html, download_excel_button,
    minutos_entre, minutos_legible, sidebar_user_box, vendedor_filter_selector,
)

_usa_storage = db.storage_disponible()
_diseno_max_bytes_archivo = DISENO_ARCHIVO_MAX_BYTES_STORAGE if _usa_storage else DISENO_ARCHIVO_MAX_BYTES


def _caption_limite_archivo():
    if _usa_storage:
        st.caption(f"Tamaño máximo por archivo: {_diseno_max_bytes_archivo // 1_000_000} MB.")
    else:
        st.caption(f"Tamaño máximo por archivo: {_diseno_max_bytes_archivo // 1000} KB.")


def _subir_archivos_diseno(archivos_subidos):
    """Sube los archivos adjuntos a Firebase Storage si está disponible;
    si no, cae al guardado anterior (base64 dentro del documento)."""
    if _usa_storage:
        return db.subir_archivos_storage_lista(
            "disenos_alvaro", archivos_subidos, _diseno_max_bytes_archivo, DISENO_ARCHIVOS_MAX,
        )
    return archivos_a_b64_lista(archivos_subidos, _diseno_max_bytes_archivo, DISENO_ARCHIVOS_MAX)

user = auth.current_user()
sidebar_user_box()

st.title("🎨 Diseño Gráfico — Álvaro")
st.caption(
    "Tablero de solicitudes de diseño, estilo Trello. El vendedor registra la solicitud (cae en la "
    "columna 'Lista de tareas' o 'Emergencias'); el diseñador la va moviendo por el tablero conforme avanza."
)

COLUMN_EMOJI = {
    "Lista de tareas": "📋", "Emergencias": "🚨", "En proceso": "🔧",
    "Cambios": "✏️", "Entregado": "✅",
}
# El semáforo (🟢/🔴) solo se muestra en estas columnas — no aplica a
# "Lista de tareas" ni "Emergencias", que todavía no están en producción.
COLUMNAS_CON_SEMAFORO = {"En proceso", "Cambios", "Entregado"}

puede_crear = user["rol"] in ("admin", "vendedor")
puede_mover = user["rol"] in ("admin", "disenador_alvaro")

tab_tablero, tab_nueva = st.tabs(["🗂️ Tablero", "➕ Nueva solicitud"])

# --------------------------------------------------------------------------
# Tablero
# --------------------------------------------------------------------------
with tab_tablero:
    filtro_vendedor = vendedor_filter_selector(key="disA_filtro_vendedor")

    rows = db.list_disenos_alvaro(filtro_vendedor)  # ya vienen ordenadas: más nueva primero
    vendedores = db.list_usuarios()

    # ------------------------------------------------------------------
    # KPI: solicitudes por entregar hoy y mañana (para dar seguimiento
    # rápido al diseñador). No cuenta las que ya están en "Entregado".
    # ------------------------------------------------------------------
    hoy = date.today()
    manana = hoy + timedelta(days=1)
    pendientes_entrega = [
        r for r in rows
        if r.get("estado") != "Entregado" and r.get("fecha_necesaria") in (str(hoy), str(manana))
    ]
    entregar_hoy = [r for r in pendientes_entrega if r.get("fecha_necesaria") == str(hoy)]
    entregar_manana = [r for r in pendientes_entrega if r.get("fecha_necesaria") == str(manana)]

    # Tiempo promedio desde que ingresa la solicitud hasta que se entrega —
    # solo cuenta las que ya tienen 'fecha_entregado' guardada (se llena sola
    # la primera vez que una solicitud llega a 'Entregado', ver database.update_diseno_alvaro).
    entregadas_con_tiempo = [r for r in rows if r.get("fecha_entregado")]
    tiempos_entrega = [
        minutos_entre(r["creado_en"], r["fecha_entregado"]) for r in entregadas_con_tiempo
    ]
    tiempo_promedio_entrega = (sum(tiempos_entrega) / len(tiempos_entrega)) if tiempos_entrega else None

    kc1, kc2, kc3 = st.columns(3)
    kc1.metric("📦 Por entregar hoy", len(entregar_hoy))
    kc2.metric("📦 Por entregar mañana", len(entregar_manana))
    kc3.metric(
        "⏱️ Tiempo promedio: ingreso → entregado",
        minutos_legible(round(tiempo_promedio_entrega)) if tiempo_promedio_entrega is not None else "Sin datos",
        help=f"Calculado con {len(entregadas_con_tiempo)} solicitud(es) ya entregada(s) (con el filtro de vendedor de arriba).",
    )

    if pendientes_entrega:
        with st.expander(f"Ver detalle de las {len(pendientes_entrega)} solicitudes por entregar (hoy y mañana)"):
            st.dataframe(
                pd.DataFrame([{
                    "Cliente": r.get("cliente") or "—",
                    "Producto": r.get("producto") or "—",
                    "Fecha necesaria": r.get("fecha_necesaria"),
                    "Estado": r.get("estado"),
                    "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
                } for r in sorted(pendientes_entrega, key=lambda x: x.get("fecha_necesaria") or "")]),
                use_container_width=True, hide_index=True,
            )

    st.divider()

    busqueda = st.text_input("🔎 Buscar por cliente o producto (opcional)", key="disA_busqueda")
    if busqueda.strip():
        q = busqueda.strip().lower()
        rows = [
            r for r in rows
            if q in (r.get("cliente") or "").lower() or q in (r.get("producto") or "").lower()
        ]

    if rows:
        download_excel_button(
            pd.DataFrame([{
                "ID": r["id"], "Cliente": r.get("cliente"), "Producto": r.get("producto"),
                "Material": r.get("material"), "Acabado": r.get("acabado"), "Medida": r.get("medida"),
                "Fecha necesaria": r.get("fecha_necesaria"), "Estado": r.get("estado"),
                "Cambios necesarios": r.get("cambios_necesarios"),
                "Semáforo": (
                    ("Parado por emergencia" if r.get("detenido_emergencia") else "Sigue en proceso")
                    if r.get("estado") in COLUMNAS_CON_SEMAFORO else "—"
                ),
                "Archivos adjuntos": ", ".join(a["nombre"] for a in diseno_archivos_lista(r)) or "—",
                "Creado": r.get("creado_en"),
                "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
            } for r in rows]),
            "solicitudes_diseno_alvaro.xlsx", key="disA_descargar_excel",
        )

    # ------------------------------------------------------------------
    # Resumen de pendientes (vista de lista, estilo tablero tipo Asana)
    # — un resumen de las mismas columnas del tablero, antes de mostrarlas.
    # ------------------------------------------------------------------
    st.markdown("#### 📋 Resumen de pendientes")
    st.markdown(
        diseno_resumen_html(rows, ESTADOS_DISENO, COLUMN_EMOJI, COLUMNAS_CON_SEMAFORO, vendedores, hoy, manana),
        unsafe_allow_html=True,
    )

    st.divider()

    if not (puede_crear or puede_mover):
        st.caption("Tu rol es de solo vista para este tablero.")

    cols = st.columns(len(ESTADOS_DISENO))
    for col, estado in zip(cols, ESTADOS_DISENO):
        items = [r for r in rows if r.get("estado") == estado]
        with col:
            st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
            if not items:
                st.caption("Sin solicitudes.")
            for r in items:
                with st.container(border=True):
                    did = r["id"]
                    editando_key = f"disA_editando_{did}"
                    puede_editar_esta = puede_mover or (puede_crear and (user["rol"] == "admin" or r["vendedor_id"] == user["id"]))
                    puede_editar_este = puede_editar_esta or puede_mover

                    title_col, edit_col = st.columns([5, 1])
                    with title_col:
                        if estado in COLUMNAS_CON_SEMAFORO:
                            semaforo = "🔴" if r.get("detenido_emergencia") else "🟢"
                            st.markdown(f"{semaforo} **{r.get('cliente') or 'Sin cliente'}**")
                        else:
                            st.markdown(f"**{r.get('cliente') or 'Sin cliente'}**")
                    with edit_col:
                        if puede_editar_este:
                            if st.button("✏️", key=f"disA_editar_{did}", help="Editar esta solicitud"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()
                    st.caption(r.get("producto") or "—")
                    st.caption(f"Vendedor: {db.nombre_vendedor(r['vendedor_id'], vendedores)}")
                    if r.get("fecha_necesaria"):
                        st.caption(f"📅 Necesita: {r['fecha_necesaria']}")
                    if r.get("cambios_necesarios"):
                        st.caption(f"🔁 Cambios necesarios: {r['cambios_necesarios']}")
                    st.caption(f"🕒 {(r.get('creado_en') or '')[:16].replace('T', ' ')}")

                    pdf_bytes = diseno_pdf_bytes(r, db.nombre_vendedor(r["vendedor_id"], vendedores))
                    st.download_button(
                        "📄 PDF de la solicitud", data=pdf_bytes, file_name=f"solicitud_{r['id']}.pdf",
                        mime="application/pdf", use_container_width=True, key=f"disA_pdf_{r['id']}",
                    )
                    for i, arch in enumerate(diseno_archivos_lista(r)):
                        if arch.get("storage_path"):
                            url_archivo = db.url_descarga_archivo_storage(
                                arch["storage_path"], nombre_descarga=arch["nombre"],
                            )
                            if url_archivo:
                                st.link_button(
                                    f"📎 {arch['nombre']}", url_archivo,
                                    use_container_width=True, key=f"disA_file_{r['id']}_{i}",
                                )
                            else:
                                st.caption(f"📎 {arch['nombre']} (no se pudo generar el enlace de descarga)")
                        else:
                            st.download_button(
                                f"📎 {arch['nombre']}",
                                data=base64.b64decode(arch["b64"]),
                                file_name=arch["nombre"],
                                mime=arch.get("tipo") or "application/octet-stream",
                                use_container_width=True, key=f"disA_file_{r['id']}_{i}",
                            )

                    if puede_editar_este and st.session_state.get(editando_key):
                        # ----------------------------------------------------
                        # Edición en línea (se abrió con el lápiz ✏️)
                        # ----------------------------------------------------
                        with st.form(f"gestionar_disA_{did}"):
                            if puede_editar_esta:
                                cliente_ed = st.text_input("Nombre del cliente", value=r.get("cliente") or "")
                                c1, c2 = st.columns(2)
                                producto_ed = c1.selectbox(
                                    "¿Qué producto es?", LINEAS_VENTA,
                                    index=LINEAS_VENTA.index(r["producto"]) if r.get("producto") in LINEAS_VENTA else 0,
                                )
                                material_ed = c2.text_input("¿Qué material es?", value=r.get("material") or "")
                                c3, c4 = st.columns(2)
                                acabado_ed = c3.text_input("¿Qué acabado lleva?", value=r.get("acabado") or "")
                                medida_ed = c4.text_input("Medida del material", value=r.get("medida") or "")
                                fecha_necesaria_ed = st.date_input(
                                    "Fecha en que se necesita",
                                    value=date.fromisoformat(r["fecha_necesaria"]) if r.get("fecha_necesaria") else date.today(),
                                )
                                cambios_necesarios_ed = st.text_area(
                                    "Cambios necesarios",
                                    value=r.get("cambios_necesarios") or "",
                                    help="Qué hay que ajustar en el diseño (por ejemplo, después de la revisión del cliente).",
                                )
                                archivos_actuales = diseno_archivos_lista(r)
                                st.caption(
                                    f"Archivos actuales: {', '.join(a['nombre'] for a in archivos_actuales)}"
                                    if archivos_actuales else "Archivos actuales: ninguno."
                                )
                                nuevos_archivos = st.file_uploader(
                                    f"Reemplazar archivos adjuntos (opcional, máximo {DISENO_ARCHIVOS_MAX})",
                                    type=["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx", "psd", "ai"],
                                    accept_multiple_files=True,
                                    key=f"disA_archivo_ed_{did}",
                                    help="Si subes archivos aquí, reemplazan a TODOS los actuales. Déjalo vacío para no cambiarlos.",
                                )
                                _caption_limite_archivo()
                            else:
                                nuevos_archivos = None
                                st.caption(f"Cliente: **{r.get('cliente') or '—'}**")
                                st.caption(
                                    f"Producto: {r.get('producto') or '—'} · Material: {r.get('material') or '—'} · "
                                    f"Acabado: {r.get('acabado') or '—'}"
                                )
                                st.caption(
                                    f"Medida: {r.get('medida') or '—'} · Necesita para: {r.get('fecha_necesaria') or '—'}"
                                )
                                st.caption(f"Cambios necesarios: {r.get('cambios_necesarios') or '—'}")

                            if puede_mover:
                                estado_ed = st.selectbox(
                                    "Estado (columna del tablero)", ESTADOS_DISENO,
                                    index=ESTADOS_DISENO.index(r["estado"]) if r.get("estado") in ESTADOS_DISENO else 0,
                                )
                                opciones_semaforo = ["🟢 Sigue en proceso", "🔴 Parado por trabajo de emergencia"]
                                semaforo_ed = st.radio(
                                    "Semáforo (se muestra en las columnas En proceso, Cambios y Entregado)",
                                    opciones_semaforo,
                                    index=1 if r.get("detenido_emergencia") else 0,
                                    horizontal=True,
                                )
                            else:
                                estado_ed = r.get("estado")
                                st.caption(f"Estado actual: **{estado_ed}** — solo el diseñador o el administrador lo pueden mover.")
                                if r.get("estado") in COLUMNAS_CON_SEMAFORO:
                                    st.caption(
                                        "🔴 Parado por trabajo de emergencia" if r.get("detenido_emergencia")
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
                                archivos_a_reemplazar = None
                                if puede_mover:
                                    update_kwargs["detenido_emergencia"] = semaforo_ed.startswith("🔴")
                                if puede_editar_esta:
                                    if not cliente_ed.strip():
                                        error_msg = "El nombre del cliente es obligatorio."
                                    else:
                                        update_kwargs.update(
                                            cliente=cliente_ed.strip(), producto=producto_ed,
                                            material=material_ed.strip(), acabado=acabado_ed.strip(),
                                            medida=medida_ed.strip(), fecha_necesaria=str(fecha_necesaria_ed),
                                            cambios_necesarios=cambios_necesarios_ed.strip() or None,
                                        )
                                        if nuevos_archivos:
                                            try:
                                                update_kwargs["archivos"] = _subir_archivos_diseno(nuevos_archivos)
                                                # Los archivos actuales se borran de Storage recién
                                                # después de guardar el reemplazo con éxito (más abajo).
                                                archivos_a_reemplazar = archivos_actuales
                                            except ValueError as e:
                                                error_msg = str(e)
                                if error_msg:
                                    st.error(error_msg)
                                else:
                                    db.update_diseno_alvaro(did, **update_kwargs)
                                    if archivos_a_reemplazar:
                                        db.eliminar_archivos_storage(archivos_a_reemplazar)
                                    st.session_state.pop(editando_key, None)
                                    st.success("Solicitud actualizada.")
                                    st.rerun()
                            if eliminar:
                                db.delete_diseno_alvaro(did)
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
        st.info("Solo vendedores y administradores pueden crear solicitudes de diseño.")
    else:
        if user["rol"] == "admin":
            vendedores_activos = db.list_vendedores()
            opciones_v = {v["nombre"]: v["id"] for v in vendedores_activos}
            vendedor_nombre_sel = st.selectbox("Vendedor", list(opciones_v.keys()), key="disA_nuevo_vendedor")
            vendedor_id = opciones_v[vendedor_nombre_sel]
        else:
            vendedor_id = user["id"]
            st.caption(f"Vendedor: **{user['nombre']}**")

        with st.form("nueva_solicitud_diseno_alvaro", clear_on_submit=True):
            tipo_solicitud = st.radio(
                "Tipo de solicitud", ESTADOS_DISENO_INICIALES, horizontal=True,
                help="'Emergencias' aparece en su propia columna del tablero para que el diseñador la vea primero.",
            )
            cliente = st.text_input("Nombre del cliente")
            c1, c2 = st.columns(2)
            producto = c1.selectbox("¿Qué producto es?", LINEAS_VENTA)
            material = c2.text_input("¿Qué material es?")
            c3, c4 = st.columns(2)
            acabado = c3.text_input("¿Qué acabado lleva?")
            medida = c4.text_input("Medida del material (ej. 21x29.7 cm)")
            fecha_necesaria = st.date_input("Fecha en que se necesita", value=date.today())
            cambios_necesarios = st.text_area(
                "Cambios necesarios (opcional)",
                help="Déjalo en blanco si es una solicitud nueva; úsalo si ya hay una versión previa que ajustar.",
            )
            archivos = st.file_uploader(
                f"Adjuntar archivos de referencia (opcional, máximo {DISENO_ARCHIVOS_MAX}) — "
                "PDF, PNG, JPEG, Word, Excel, PSD o AI",
                type=["pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx", "psd", "ai"],
                accept_multiple_files=True,
            )
            _caption_limite_archivo()

            if st.form_submit_button("Enviar solicitud", use_container_width=True):
                if not cliente.strip():
                    st.error("El nombre del cliente es obligatorio.")
                else:
                    try:
                        archivos_lista = _subir_archivos_diseno(archivos)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        db.create_diseno_alvaro(
                            vendedor_id, cliente.strip(), producto, material.strip(), acabado.strip(),
                            medida.strip(), fecha_necesaria, tipo_solicitud,
                            archivos=archivos_lista,
                            cambios_necesarios=cambios_necesarios.strip() or None,
                        )
                        st.success(f"Solicitud enviada a la columna '{tipo_solicitud}'.")
                        st.rerun()
