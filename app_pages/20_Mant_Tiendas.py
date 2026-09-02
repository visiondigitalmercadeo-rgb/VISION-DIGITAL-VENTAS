import base64

import pandas as pd
import streamlit as st

import auth
import database as db
from config import (
    APP_URL, ESTADOS_MANT_TIENDAS, ESTADOS_MANT_TIENDAS_INICIALES, MANT_TIENDA_SIGUIENTE_ESTADO,
    MANT_TIENDAS_COTIZACION_MAX_ARCHIVOS, MANT_TIENDAS_COTIZACION_MAX_BYTES, MANT_TIENDAS_FOTO_MAX_BYTES,
    MANT_TIENDAS_FOTOS_MAX, TICKET_TIENDAS,
)
from utils import (
    archivos_a_b64_lista, download_excel_button, duracion_legible, mant_tienda_pdf_bytes,
    mant_tienda_segmentos_etapa, mant_tienda_tiempo_en_etapa, mant_tiendas_resumen_html, minutos_entre,
    sidebar_user_box,
)

user = auth.current_user()
sidebar_user_box()

st.title("🏬 Mantenimiento de Tiendas")
st.caption(
    "Tablero de solicitudes de mantenimiento de tiendas, estilo Trello — mismo concepto que Diseño "
    "Gráfico. Jefe de tienda, sub jefe de tienda, mercadeo, Jefe de Mantenimiento y administrador tienen "
    "acceso total (crear, editar, mover y eliminar) conforme la solicitud avanza: Lista de tareas/"
    "Emergencia → En cotización → En proceso → Finalizado."
)

COLUMN_EMOJI = {
    "Lista de tareas": "📋", "Emergencia": "🚨", "En cotización": "💰",
    "En proceso": "🔧", "Finalizado": "✅",
}
# El semáforo (🟢/🔴) solo se muestra en estas columnas — no aplica a
# "Lista de tareas" ni "Emergencia", que todavía no están en curso.
COLUMNAS_CON_SEMAFORO = {"En cotización", "En proceso", "Finalizado"}

# Etapas que se miden para los KPIs de tiempo de arriba: (etiqueta, nombre
# exacto de la columna). El promedio de cada una se calcula a partir del
# historial completo de cada solicitud (ver utils.mant_tienda_segmentos_etapa
# / database.avanzar_mant_tienda, que agrega una entrada al historial cada
# vez que la solicitud entra a una columna nueva) — así queda correcto
# incluso si una solicitud se movió hacia atrás y volvió a pasar por la
# misma columna más de una vez (se suman todos los tramos completados). Las
# solicitudes de antes de que existiera el historial se reconstruyen lo
# mejor posible a partir de los campos anteriores (ver
# utils.mant_tienda_historial_o_reconstruido).
_ETAPAS_KPI = [
    ("📋 Tiempo en Lista de tareas", "Lista de tareas"),
    ("🚨 Tiempo en Emergencia", "Emergencia"),
    ("💰 Tiempo en cotización", "En cotización"),
    ("🔧 Tiempo en proceso", "En proceso"),
]


def _promedio_minutos_etapa(rows, etapa):
    valores = [t for t in (mant_tienda_tiempo_en_etapa(r, etapa) for r in rows) if t is not None]
    return (sum(valores) / len(valores)) if valores else None


def _promedio_minutos_total(rows):
    valores = [
        minutos_entre(r.get("creado_en"), r.get("fecha_finalizado"))
        for r in rows if r.get("fecha_finalizado")
    ]
    return (sum(valores) / len(valores)) if valores else None


def _label_numero(numero_solicitud):
    return f"#{numero_solicitud:04d} · " if isinstance(numero_solicitud, int) else ""


puede_crear = auth.puede_crear_mant_tiendas()
puede_mover = auth.puede_mover_mant_tiendas()
tienda_usuario = auth.current_user_tienda()


def _avisar_nueva_solicitud_por_correo(row):
    """Manda un aviso a los correos configurados SOLO cuando se crea una
    solicitud nueva — a propósito NO se manda nada cuando una solicitud
    cambia de columna/etapa (pedido explícito de Steven, para no saturar de
    correos en cada movimiento del tablero). No hace nada (ni muestra
    error) si todavía no hay correos guardados o si el remitente no está
    configurado — ver database.correo_disponible."""
    correos = db.get_mant_tiendas_correos_aviso()
    if not correos:
        return
    numero_txt = f"#{row['numero_solicitud']:04d}" if isinstance(row.get("numero_solicitud"), int) else "—"
    asunto = f"🏬 Nueva solicitud de mantenimiento {numero_txt} — {row.get('tienda') or '—'}"
    cuerpo = (
        f"Se abrió una nueva solicitud de mantenimiento de tiendas.\n\n"
        f"N° de solicitud: {numero_txt}\n"
        f"Tienda: {row.get('tienda') or '—'}\n"
        f"Tipo: {row.get('estado') or '—'}\n"
        f"Quién solicita: {row.get('quien_solicita') or '—'}\n"
        f"Descripción: {row.get('descripcion') or '—'}\n\n"
        f"Ver en la plataforma: {APP_URL}"
    )
    db.enviar_correo_aviso(correos, asunto, cuerpo)


if puede_mover:
    with st.expander("✉️ Avisos por correo (solo al crear una solicitud nueva)"):
        if not db.correo_disponible():
            st.info(
                "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta "
                "de Gmail en la configuración de la plataforma) — mientras tanto, esta sección no manda "
                "nada, pero puedes ir guardando los correos de una vez."
            )
        correos_actuales_mt = db.get_mant_tiendas_correos_aviso()
        with st.form("mant_tiendas_correos_aviso"):
            correos_texto_mt = st.text_area(
                "Correos que reciben el aviso — uno por línea (o separados por coma)",
                value="\n".join(correos_actuales_mt),
                help=(
                    "Se les avisa automáticamente solo cuando se crea una solicitud NUEVA (tanto de 'Lista "
                    "de tareas' como de 'Emergencia'). NO se manda correo cuando una solicitud cambia de "
                    "columna/etapa en el tablero."
                ),
            )
            if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                nuevos_correos_mt = [c.strip() for c in correos_texto_mt.replace(",", "\n").split("\n") if c.strip()]
                db.set_mant_tiendas_correos_aviso(nuevos_correos_mt)
                st.success("Correos actualizados.")
                st.rerun()

if tienda_usuario:
    filtro_tienda = tienda_usuario
    st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
else:
    elegido_tienda = st.selectbox(
        "Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mt_filtro_tienda",
    )
    filtro_tienda = None if elegido_tienda == "Todas" else elegido_tienda

rows = db.list_mant_tiendas(tienda=filtro_tienda)  # ya vienen ordenadas: más nueva primero

# ------------------------------------------------------------------
# KPIs de tiempo, arriba de todo — cuánto se tarda cada etapa del
# proceso completo, en promedio (solo cuenta solicitudes que ya
# completaron esa etapa).
# ------------------------------------------------------------------
st.markdown("#### ⏱️ Tiempos promedio por etapa")
st.caption(
    "Promedio de todas las solicitudes que ya completaron cada etapa (con el filtro de tienda de arriba) "
    "— suma el tiempo de todas las veces que una solicitud pasó por esa columna, por si se movió hacia "
    "atrás y volvió a entrar."
)
kcols = st.columns(len(_ETAPAS_KPI) + 1)
for col, (etiqueta, etapa) in zip(kcols, _ETAPAS_KPI):
    promedio = _promedio_minutos_etapa(rows, etapa)
    col.metric(etiqueta, duracion_legible(round(promedio)) if promedio is not None else "Sin datos")
promedio_total = _promedio_minutos_total(rows)
kcols[-1].metric(
    "🏁 Total (solicitud → finalización)",
    duracion_legible(round(promedio_total)) if promedio_total is not None else "Sin datos",
)

st.divider()

tab_tablero, tab_nueva = st.tabs(["🗂️ Tablero", "➕ Nueva solicitud"])

# --------------------------------------------------------------------------
# Tablero
# --------------------------------------------------------------------------
with tab_tablero:
    busqueda = st.text_input("🔎 Buscar por tienda, quién solicita o descripción (opcional)", key="mt_busqueda")
    rows_tablero = rows
    if busqueda.strip():
        q = busqueda.strip().lower()
        rows_tablero = [
            r for r in rows_tablero
            if q in (r.get("tienda") or "").lower()
            or q in (r.get("quien_solicita") or "").lower()
            or q in (r.get("descripcion") or "").lower()
        ]

    if rows_tablero:
        download_excel_button(
            pd.DataFrame([{
                "N° Solicitud": r.get("numero_solicitud"),
                "Tienda": r.get("tienda"), "Quién solicita": r.get("quien_solicita"),
                "Descripción": r.get("descripcion"), "Estado": r.get("estado"),
                "Semáforo": (
                    ("Parado por emergencia" if r.get("detenido_emergencia") else "Sigue en proceso")
                    if r.get("estado") in COLUMNAS_CON_SEMAFORO else "—"
                ),
                "Fotos adjuntas": len(r.get("fotos") or []),
                "Creado": r.get("creado_en"),
                "Tiempo en Lista de tareas (min)": mant_tienda_tiempo_en_etapa(r, "Lista de tareas") or "—",
                "Tiempo en Emergencia (min)": mant_tienda_tiempo_en_etapa(r, "Emergencia") or "—",
                "Tiempo en cotización (min)": mant_tienda_tiempo_en_etapa(r, "En cotización") or "—",
                "Tiempo en proceso (min)": mant_tienda_tiempo_en_etapa(r, "En proceso") or "—",
                "Tiempo total (min)": (
                    minutos_entre(r.get("creado_en"), r.get("fecha_finalizado"))
                    if r.get("fecha_finalizado") else "—"
                ),
            } for r in rows_tablero]),
            "solicitudes_mant_tiendas.xlsx", key="mt_descargar_excel",
        )

    # ------------------------------------------------------------------
    # Resumen de pendientes (vista de lista, estilo tablero tipo Asana)
    # — un resumen de las mismas columnas del tablero, antes de mostrarlas.
    # ------------------------------------------------------------------
    st.markdown("#### 📋 Resumen de pendientes")
    st.markdown(
        mant_tiendas_resumen_html(rows_tablero, ESTADOS_MANT_TIENDAS, COLUMN_EMOJI, COLUMNAS_CON_SEMAFORO),
        unsafe_allow_html=True,
    )

    st.divider()

    if not (puede_crear or puede_mover):
        st.caption("Tu rol es de solo vista para este tablero.")

    cols = st.columns(len(ESTADOS_MANT_TIENDAS))
    for col, estado in zip(cols, ESTADOS_MANT_TIENDAS):
        items = [r for r in rows_tablero if r.get("estado") == estado]
        with col:
            st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
            if not items:
                st.caption("Sin solicitudes.")
            for r in items:
                with st.container(border=True):
                    mid = r["id"]
                    editando_key = f"mt_editando_{mid}"
                    puede_editar_esta = puede_mover or (
                        puede_crear and (user["rol"] == "admin" or r.get("creado_por_id") == user["id"])
                    )
                    puede_editar_este = puede_editar_esta or puede_mover
                    numero_txt = _label_numero(r.get("numero_solicitud"))

                    title_col, edit_col = st.columns([5, 1])
                    with title_col:
                        if estado in COLUMNAS_CON_SEMAFORO:
                            semaforo = "🔴" if r.get("detenido_emergencia") else "🟢"
                            st.markdown(f"{semaforo} **{numero_txt}{r.get('tienda') or 'Sin tienda'}**")
                        else:
                            st.markdown(f"**{numero_txt}{r.get('tienda') or 'Sin tienda'}**")
                    with edit_col:
                        if puede_editar_este:
                            if st.button("✏️", key=f"mt_editar_{mid}", help="Editar esta solicitud"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()
                    st.caption(f"🙋 Solicita: {r.get('quien_solicita') or '—'}")
                    if r.get("descripcion"):
                        st.caption(f"📝 {r['descripcion']}")
                    st.caption(f"🕒 {(r.get('creado_en') or '')[:16].replace('T', ' ')}")

                    # ------------------------------------------------------------
                    # Cuánto tiempo lleva/estuvo esta solicitud en cada columna
                    # por la que ha pasado — a partir del historial completo (ver
                    # utils.mant_tienda_segmentos_etapa). La columna en la que
                    # está ahora mismo se marca "en curso" (todavía no terminó).
                    # ------------------------------------------------------------
                    segmentos_r = mant_tienda_segmentos_etapa(r)
                    if segmentos_r:
                        partes_tiempo = []
                        for estado_etapa, minutos_etapa, en_curso in segmentos_r:
                            emoji_etapa = COLUMN_EMOJI.get(estado_etapa, "")
                            texto_etapa = duracion_legible(minutos_etapa)
                            if en_curso:
                                texto_etapa += " y contando"
                            partes_tiempo.append(f"{emoji_etapa} {estado_etapa}: {texto_etapa}")
                        st.caption("⏱️ " + " · ".join(partes_tiempo))

                    st.download_button(
                        "📄 Orden de trabajo (PDF)", data=mant_tienda_pdf_bytes(r),
                        file_name=f"orden_trabajo_{r.get('numero_solicitud') or mid}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"mt_pdf_{mid}",
                    )

                    for i, foto in enumerate(r.get("fotos") or []):
                        st.download_button(
                            f"📷 {foto['nombre']}",
                            data=base64.b64decode(foto["b64"]),
                            file_name=foto["nombre"],
                            mime=foto.get("tipo") or "application/octet-stream",
                            use_container_width=True, key=f"mt_foto_{mid}_{i}",
                        )

                    # ------------------------------------------------------------
                    # Cotización: PDFs (máximo 3) + autorización — semáforo propio
                    # (🟢 autorizada / 🔴 pendiente), independiente del semáforo de
                    # emergencia de arriba. El jefe de planta (y quien ya tenga
                    # acceso total) sube los PDF mientras está en la columna 'En
                    # cotización'; solo el admin puede autorizarla.
                    # ------------------------------------------------------------
                    puede_subir_cot = auth.puede_subir_cotizacion_mant_tiendas()
                    puede_autorizar_cot = auth.puede_autorizar_cotizacion_mant_tiendas()
                    cotizacion_pdfs = r.get("cotizacion_pdfs") or []
                    mostrar_cotizacion = bool(cotizacion_pdfs) or (puede_subir_cot and estado == "En cotización")

                    if mostrar_cotizacion:
                        with st.container(border=True):
                            semaforo_cot = "🟢" if r.get("cotizacion_autorizada") else "🔴"
                            estado_cot_txt = "Autorizada" if r.get("cotizacion_autorizada") else "Pendiente de autorizar"
                            st.markdown(f"{semaforo_cot} **Cotización — {estado_cot_txt}**")
                            if r.get("cotizacion_autorizada") and r.get("cotizacion_autorizada_en"):
                                st.caption(
                                    f"Autorizada el {(r.get('cotizacion_autorizada_en') or '')[:16].replace('T', ' ')}"
                                )

                            for i, pdf_doc in enumerate(cotizacion_pdfs):
                                st.download_button(
                                    f"📄 {pdf_doc['nombre']}", data=base64.b64decode(pdf_doc["b64"]),
                                    file_name=pdf_doc["nombre"], mime="application/pdf",
                                    use_container_width=True, key=f"mt_cotpdf_{mid}_{i}",
                                )

                            if puede_subir_cot and estado == "En cotización":
                                with st.form(f"cotizacion_form_{mid}"):
                                    st.caption(
                                        f"Subir/reemplazar los PDF de cotización "
                                        f"(máximo {MANT_TIENDAS_COTIZACION_MAX_ARCHIVOS})."
                                    )
                                    nuevos_pdfs_cot = st.file_uploader(
                                        "Archivos PDF de cotización", type=["pdf"], accept_multiple_files=True,
                                        key=f"mt_cot_upload_{mid}",
                                        help=(
                                            "Si subes archivos aquí, reemplazan a TODOS los actuales. Si ya había "
                                            "una cotización autorizada, subir archivos nuevos le quita la "
                                            "autorización — hay que volver a autorizarla."
                                        ),
                                    )
                                    if st.form_submit_button("💾 Guardar cotización", use_container_width=True):
                                        if not nuevos_pdfs_cot:
                                            st.error("Selecciona al menos un archivo PDF.")
                                        else:
                                            try:
                                                pdfs_lista_cot = archivos_a_b64_lista(
                                                    nuevos_pdfs_cot, MANT_TIENDAS_COTIZACION_MAX_BYTES,
                                                    MANT_TIENDAS_COTIZACION_MAX_ARCHIVOS,
                                                )
                                            except ValueError as e:
                                                st.error(str(e))
                                            else:
                                                db.subir_cotizacion_mant_tienda(mid, pdfs_lista_cot)
                                                st.success("Cotización subida.")
                                                st.rerun()

                            if puede_autorizar_cot and cotizacion_pdfs:
                                if r.get("cotizacion_autorizada"):
                                    if st.button(
                                        "🔓 Quitar autorización", key=f"mt_cot_desaut_{mid}", use_container_width=True,
                                    ):
                                        db.desautorizar_cotizacion_mant_tienda(mid)
                                        st.rerun()
                                else:
                                    if st.button(
                                        "✅ Autorizar cotización", key=f"mt_cot_autorizar_{mid}",
                                        use_container_width=True,
                                    ):
                                        db.autorizar_cotizacion_mant_tienda(mid, user["id"])
                                        st.success("Cotización autorizada.")
                                        st.rerun()

                    siguiente = MANT_TIENDA_SIGUIENTE_ESTADO.get(r.get("estado"))
                    if puede_mover and siguiente:
                        bloqueado_por_cotizacion = siguiente == "En proceso" and not r.get("cotizacion_autorizada")
                        if st.button(
                            f"➡️ Mover a «{siguiente}»", key=f"mt_avanzar_{mid}", use_container_width=True,
                            disabled=bloqueado_por_cotizacion,
                        ):
                            try:
                                db.avanzar_mant_tienda(mid, siguiente)
                            except ValueError as e:
                                st.error(str(e))
                            else:
                                st.success(f"Solicitud movida a «{siguiente}».")
                                st.rerun()
                        if bloqueado_por_cotizacion:
                            st.caption("🔒 Un admin debe autorizar la cotización antes de pasar a «En proceso».")

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
                                if r.get("estado") != "En proceso" and not r.get("cotizacion_autorizada"):
                                    st.caption("🔒 No se puede pasar a «En proceso» sin autorizar la cotización primero.")
                                opciones_semaforo = ["🟢 Sigue en proceso", "🔴 Parado por emergencia"]
                                semaforo_ed = st.radio(
                                    "Semáforo (se muestra en las columnas En cotización, En proceso y Finalizado)",
                                    opciones_semaforo,
                                    index=1 if r.get("detenido_emergencia") else 0,
                                    horizontal=True,
                                )
                            else:
                                estado_ed = r.get("estado")
                                st.caption(
                                    f"Estado actual: **{estado_ed}** — tu rol no tiene permiso para mover "
                                    "esta solicitud por el tablero."
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
                                update_kwargs = {}
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
                                    try:
                                        db.avanzar_mant_tienda(mid, estado_ed, extra=update_kwargs)
                                    except ValueError as e:
                                        st.error(str(e))
                                    else:
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
        st.info(
            "Solo el jefe de tienda, sub jefe de tienda, mercadeo, el Jefe de Mantenimiento y los "
            "administradores pueden crear solicitudes de mantenimiento."
        )
    else:
        with st.form("nueva_solicitud_mant_tienda", clear_on_submit=True):
            tipo_solicitud = st.radio(
                "Tipo de solicitud", ESTADOS_MANT_TIENDAS_INICIALES, horizontal=True,
                help="'Emergencia' aparece en su propia columna del tablero para que se vea primero.",
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
                        nuevo_id_mt = db.create_mant_tienda(
                            user["id"], tienda, quien_solicita.strip(), descripcion.strip(),
                            tipo_solicitud, fotos=fotos_lista,
                        )
                        nueva_solicitud_mt = db.get_mant_tienda(nuevo_id_mt)
                        if nueva_solicitud_mt:
                            _avisar_nueva_solicitud_por_correo(nueva_solicitud_mt)
                        st.success(f"Solicitud enviada a la columna '{tipo_solicitud}'.")
                        st.rerun()
