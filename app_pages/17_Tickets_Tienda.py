import io

import pandas as pd
import qrcode
import streamlit as st

import auth
import database as db
from config import (
    APP_URL, ESTADOS_TICKET, INK_MUTED, ROLES_LABEL, STATUS, TICKET_SERVICIOS, TICKET_TIENDA_SLUG,
    TICKET_TIENDAS,
)
from utils import (
    download_excel_button, hora_legible, lineas_venta_display, minutos_entre, minutos_legible,
    sidebar_user_box,
)

user = auth.current_user()
sidebar_user_box()

st.title("🎫 Sistema de Tickets — Tiendas")
st.caption(
    "Fila de clientes nuevos que llegan a la tienda. El cliente escanea el código QR con su "
    "celular, se registra solo (nombre, teléfono y qué necesita) y aquí puedes ir avanzando su "
    "ticket por cada etapa mientras se mide el tiempo automáticamente."
)

puede_gestionar = auth.puede_gestionar_tickets_tienda()
puede_configurar_kpis = auth.puede_configurar_kpis_tienda()
tienda_usuario = auth.current_user_tienda()
es_rol_de_tienda = user["rol"] in (
    "anfitriona", "jefe_tienda", "subjefe_tienda", "asesor_ventas", "cajero",
)

if es_rol_de_tienda and not tienda_usuario:
    st.error(
        "Tu usuario todavía no tiene una tienda asignada. Pídele a un administrador que te "
        "asigne una tienda desde 'Administración de usuarios'."
    )
    st.stop()

ESTADO_EMOJI = {
    "En atención": "🕐",
    "En elaboración": "🛠️",
    "Facturado": "✅",
    "Abandono": "🚫",
}

# Títulos que ve el equipo en cada columna del tablero (el valor interno de
# "estado" que se guarda en la base de datos no cambia, solo cómo se muestra).
# Ya no existe la columna "Ingresado": el ticket entra directo a "En espera".
ESTADO_TITULO_COLUMNA = {
    "En atención": "En espera",
    "En elaboración": "En elaboración",
    "Facturado": "Facturado",
    "Abandono": "Abandono",
}

# "Facturado" ya no es una columna del tablero — los tickets facturados se
# muestran en una lista aparte (más compacta) para que no estorben junto a
# los tickets que todavía se están trabajando.
ESTADOS_TICKET_TABLERO = [e for e in ESTADOS_TICKET if e != "Facturado"]

def _render_abandono_form(ticket_id, abandonando_key):
    """Caja para capturar el motivo antes de marcar un ticket como Abandono —
    mismo patrón de 'Confirmar/Cancelar' que ya se usa en Llamadas para
    marcar un cliente como 'Perdido'."""
    motivo = st.text_area(
        "¿Por qué abandonó el cliente?", key=f"tt_motivo_ab_{ticket_id}", height=80,
    )
    cc1, cc2 = st.columns(2)
    if cc1.button("Confirmar", key=f"tt_confirmar_ab_{ticket_id}", use_container_width=True):
        db.abandonar_ticket_tienda(ticket_id, motivo)
        st.session_state.pop(abandonando_key, None)
        st.rerun()
    if cc2.button("Cancelar", key=f"tt_cancelar_ab_{ticket_id}", use_container_width=True):
        st.session_state.pop(abandonando_key, None)
        st.rerun()


def _render_asignar_form(ticket_id, tienda, asignando_key):
    """Caja para elegir quién de la tienda va a elaborar el pedido antes de
    pasar el ticket a 'En elaboración' — mismo patrón de 'Confirmar/Cancelar'
    que _render_abandono_form. La lista sale del personal de la tienda
    (colección "personal_tiendas"), no de los usuarios con acceso al
    sistema, porque la mayoría de quienes elaboran pedidos no tienen usuario."""
    personal = db.list_personal_tiendas(tienda=tienda, solo_activos=True)
    opciones_as = {a["nombre"]: a["id"] for a in personal}
    if personal:
        elegido_as = st.selectbox(
            "¿Quién va a elaborar este pedido?", ["—"] + list(opciones_as.keys()),
            key=f"tt_asesor_sel_{ticket_id}",
        )
    else:
        elegido_as = "—"
        st.caption(
            "No hay personal registrado para esta tienda todavía. Puedes continuar sin "
            "asignar a nadie, o pedirle a un administrador que lo agregue desde "
            "'Administración de usuarios' → 'Carga inicial de personal'."
        )
    cc1, cc2 = st.columns(2)
    if cc1.button("Confirmar", key=f"tt_confirmar_as_{ticket_id}", use_container_width=True):
        if personal and elegido_as == "—":
            st.error("Selecciona quién va a elaborar el pedido.")
        else:
            db.avanzar_ticket_tienda(ticket_id, "En elaboración", asesor_id=opciones_as.get(elegido_as))
            st.session_state.pop(asignando_key, None)
            st.rerun()
    if cc2.button("Cancelar", key=f"tt_cancelar_as_{ticket_id}", use_container_width=True):
        st.session_state.pop(asignando_key, None)
        st.rerun()


def _render_ticket_edit_form(tk, editando_key):
    """Formulario de edición en línea de un ticket — se abre con el lápiz ✏️
    de la tarjeta (o de la lista de facturados), mismo patrón que Prospectos
    y Logística. Permite corregir nombre, teléfono, servicio, estado y quién
    lo elabora, o eliminar el ticket por completo."""
    tid = tk["id"]
    with st.form(f"tt_editar_form_{tid}"):
        ge1, ge2 = st.columns(2)
        nombre_ed = ge1.text_input("Nombre", value=tk.get("nombre") or "")
        telefono_ed = ge2.text_input("Teléfono", value=tk.get("telefono") or "")
        servicio_ed = st.multiselect(
            "Servicio/producto",
            TICKET_SERVICIOS,
            default=[s for s in (tk.get("servicio") or []) if s in TICKET_SERVICIOS],
        )
        estado_ed = st.selectbox(
            "Estado", ESTADOS_TICKET,
            index=ESTADOS_TICKET.index(tk["estado"]) if tk.get("estado") in ESTADOS_TICKET else 0,
            format_func=lambda e: ESTADO_TITULO_COLUMNA.get(e, e),
        )
        personal_ed = db.list_personal_tiendas(tienda=tk.get("tienda"), solo_activos=True)
        opciones_as_ed = {"(sin asignar)": None}
        opciones_as_ed.update({a["nombre"]: a["id"] for a in personal_ed})
        nombre_as_actual = db.nombre_personal_tienda(tk.get("asesor_id"))
        valores_as_ed = list(opciones_as_ed.keys())
        if nombre_as_actual not in valores_as_ed and nombre_as_actual != "—":
            # La persona asignada ya no está activa/en esta tienda, pero la
            # dejamos como opción para no perder el dato al guardar.
            valores_as_ed.append(nombre_as_actual)
            opciones_as_ed[nombre_as_actual] = tk.get("asesor_id")
        asesor_ed = st.selectbox(
            "Asignado a (elaboración)", valores_as_ed,
            index=valores_as_ed.index(nombre_as_actual) if nombre_as_actual in valores_as_ed else 0,
        )
        motivo_ab_ed = st.text_input(
            "Motivo de abandono (solo aplica si el estado es Abandono)",
            value=tk.get("motivo_abandono") or "",
        )
        colg1, colg2 = st.columns(2)
        guardar = colg1.form_submit_button("💾 Guardar cambios", use_container_width=True)
        cancelar = colg2.form_submit_button("Cancelar", use_container_width=True)
        if guardar:
            if not nombre_ed.strip() or not servicio_ed:
                st.error("Nombre y servicio/producto son obligatorios.")
            else:
                if estado_ed != tk.get("estado"):
                    # avanzar_ticket_tienda registra también la hora de la
                    # nueva etapa (si aplica), igual que los botones del tablero.
                    db.avanzar_ticket_tienda(tid, estado_ed)
                db.update_ticket_tienda(
                    tid, nombre=nombre_ed.strip(), telefono=telefono_ed.strip(),
                    servicio=[s for s in servicio_ed if s],
                    motivo_abandono=motivo_ab_ed.strip() or None,
                    asesor_id=opciones_as_ed.get(asesor_ed),
                )
                st.session_state.pop(editando_key, None)
                st.success("Ticket actualizado.")
                st.rerun()
        if cancelar:
            st.session_state.pop(editando_key, None)
            st.rerun()

    with st.expander("🗑️ Eliminar este ticket"):
        st.caption(
            "El ticket deja de aparecer en el tablero y en el historial, pero queda guardado "
            "en el listado de 'Tickets eliminados' de más abajo, junto con el motivo y quién "
            "lo eliminó."
        )
        motivo_el = st.text_area(
            "¿Por qué se elimina este ticket?", key=f"tt_motivo_el_{tid}", height=80,
        )
        confirmar_borrar = st.checkbox(
            "Confirmo que quiero eliminar este ticket", key=f"tt_conf_del_{tid}",
        )
        if st.button("Eliminar ticket", key=f"tt_btn_del_{tid}", disabled=not confirmar_borrar):
            if not motivo_el.strip():
                st.error("Escribe el motivo antes de confirmar.")
            else:
                db.eliminar_ticket_tienda(tid, motivo_el, eliminado_por=user["nombre"])
                st.session_state.pop(editando_key, None)
                st.success("Ticket eliminado.")
                st.rerun()


# Etapas que se miden para los KPIs de tiempo: (estado, clave de la meta en
# get_ticket_kpis/set_ticket_kpis, etiqueta, campo de hora de inicio, campo de
# hora de fin). El promedio de cada una se calcula solo con los tickets de
# hoy que ya completaron esa etapa (tienen ambas horas guardadas).
# Ya no se mide "Ingresado → Atendido" — esa etapa desapareció, el ticket
# entra directo a "En espera".
_ETAPAS_KPI = [
    ("En atención", "meta_atencion", "🕐 En espera → Elaboración", "hora_inicio_atencion", "hora_inicio_elaboracion"),
    ("En elaboración", "meta_elaboracion", "🛠️ En elaboración → Facturado", "hora_inicio_elaboracion", "hora_facturado"),
]


def _promedio_minutos(tickets, campo_ini, campo_fin):
    valores = [
        minutos_entre(t.get(campo_ini), t.get(campo_fin))
        for t in tickets if t.get(campo_ini) and t.get(campo_fin)
    ]
    return (sum(valores) / len(valores)) if valores else None


def _render_kpis_tienda(tienda_nombre, tickets_tienda_hoy):
    """Fila de tarjetas con el tiempo promedio de hoy en cada etapa para una
    tienda, comparado contra su tiempo meta — en rojo si lo supera."""
    metas = db.get_ticket_kpis(tienda_nombre)
    cols_kpi = st.columns(len(_ETAPAS_KPI))
    for col, (_estado, meta_key, etiqueta, campo_ini, campo_fin) in zip(cols_kpi, _ETAPAS_KPI):
        with col:
            st.caption(etiqueta)
            promedio = _promedio_minutos(tickets_tienda_hoy, campo_ini, campo_fin)
            meta = metas.get(meta_key)
            if promedio is None:
                st.markdown(f"<span style='color:{INK_MUTED};'>Sin datos hoy</span>", unsafe_allow_html=True)
            else:
                excede = meta is not None and promedio > meta
                color = STATUS["critical"] if excede else (STATUS["good"] if meta is not None else INK_MUTED)
                st.markdown(
                    f"<span style='font-size:1.3rem; font-weight:700; color:{color};'>"
                    f"{minutos_legible(round(promedio))}</span>",
                    unsafe_allow_html=True,
                )
                if meta is not None:
                    st.caption(f"{'⚠️ Meta' if excede else '✅ Meta'}: {minutos_legible(meta)}")
                else:
                    st.caption("Sin meta configurada")


tab_tablero, tab_qr, tab_historial, tab_personal = st.tabs(
    ["🗂️ Tablero de hoy", "🔗 Código QR / Pantalla", "📋 Historial", "👥 Personal de la tienda"]
)

# ---------------------------------------------------------------------------
# Tablero de hoy
# ---------------------------------------------------------------------------
with tab_tablero:
    if es_rol_de_tienda:
        tienda_activa = tienda_usuario
        st.caption(f"Tienda: **{tienda_activa}**")
    else:
        filtro_tienda = st.selectbox(
            "Tienda", ["Todas"] + TICKET_TIENDAS, key="tt_tablero_tienda"
        )
        tienda_activa = None if filtro_tienda == "Todas" else filtro_tienda

    hoy = str(db.hoy_guatemala())
    if tienda_activa:
        tickets_por_tienda = {tienda_activa: db.list_tickets_tienda(tienda=tienda_activa, fecha=hoy)}
    else:
        tickets_por_tienda = {tda: db.list_tickets_tienda(tienda=tda, fecha=hoy) for tda in TICKET_TIENDAS}
    tickets_hoy = [t for lista in tickets_por_tienda.values() for t in lista]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Tickets hoy", len(tickets_hoy))
    k2.metric("En espera", sum(1 for t in tickets_hoy if t["estado"] == "En atención"))
    k3.metric("En elaboración", sum(1 for t in tickets_hoy if t["estado"] == "En elaboración"))
    k4.metric("Facturados", sum(1 for t in tickets_hoy if t["estado"] == "Facturado"))
    k5.metric("Abandono", sum(1 for t in tickets_hoy if t["estado"] == "Abandono"))

    st.markdown("#### ⏱️ Tiempos promedio de hoy vs. meta")
    st.caption(
        "Promedio de hoy en cada etapa, por tienda. Se pone en rojo cuando supera el tiempo "
        "meta configurado para esa tienda."
    )
    if tienda_activa:
        _render_kpis_tienda(tienda_activa, tickets_por_tienda[tienda_activa])
    else:
        for tda in TICKET_TIENDAS:
            st.markdown(f"**🏬 {tda}**")
            _render_kpis_tienda(tda, tickets_por_tienda[tda])

    if puede_configurar_kpis:
        with st.expander("🎯 Configurar tiempos meta (KPIs) por tienda"):
            st.caption(
                "Tiempo meta, en minutos, para cada etapa — es lo que ven arriba en rojo "
                "el asesor, el cajero y el jefe de tienda cuando el promedio de hoy se pasa. "
                "Cada tienda tiene su propio tiempo meta."
            )
            tienda_kpi_ed = st.selectbox("Tienda", TICKET_TIENDAS, key="tt_kpi_tienda_sel")
            metas_ed = db.get_ticket_kpis(tienda_kpi_ed)
            with st.form(f"tt_kpi_form_{tienda_kpi_ed}"):
                mk2, mk3 = st.columns(2)
                meta_atencion_ed = mk2.number_input(
                    "Meta: En espera → Elaboración (min)", min_value=0, step=1,
                    value=int(metas_ed["meta_atencion"]) if metas_ed["meta_atencion"] is not None else 0,
                )
                meta_elaboracion_ed = mk3.number_input(
                    "Meta: En elaboración → Facturado (min)", min_value=0, step=1,
                    value=int(metas_ed["meta_elaboracion"]) if metas_ed["meta_elaboracion"] is not None else 0,
                )
                st.caption("Deja un campo en 0 si no quieres poner meta para esa etapa (no se marcará en rojo).")
                if st.form_submit_button("💾 Guardar tiempos meta", use_container_width=True):
                    db.set_ticket_kpis(
                        tienda_kpi_ed,
                        None, meta_atencion_ed or None, meta_elaboracion_ed or None,
                    )
                    st.success(f"Tiempos meta de {tienda_kpi_ed} actualizados.")
                    st.rerun()

    st.divider()

    if puede_gestionar:
        with st.expander("➕ Agregar ticket manualmente (si el cliente no puede usar el QR)"):
            with st.form("tt_manual_form", clear_on_submit=True):
                if es_rol_de_tienda:
                    tienda_manual = tienda_activa
                else:
                    tienda_manual = st.selectbox(
                        "Tienda", TICKET_TIENDAS, key="tt_manual_tienda"
                    )
                m1, m2 = st.columns(2)
                nombre_m = m1.text_input("Nombre del cliente")
                telefono_m = m2.text_input("Teléfono")
                servicio_m = st.multiselect(
                    "¿Qué servicio o producto necesita? (puedes elegir varios)", TICKET_SERVICIOS,
                )
                if st.form_submit_button("Registrar ticket", use_container_width=True):
                    if not nombre_m.strip() or not servicio_m:
                        st.error("Nombre y servicio/producto son obligatorios.")
                    else:
                        r = db.create_ticket_tienda(tienda_manual, nombre_m, telefono_m, servicio_m)
                        st.success(f"Ticket #{r['numero_ticket']} registrado.")
                        st.rerun()

    st.divider()

    personal_todos = db.list_personal_tiendas(solo_activos=False)

    cols = st.columns(len(ESTADOS_TICKET_TABLERO))
    for col, estado in zip(cols, ESTADOS_TICKET_TABLERO):
        with col:
            st.markdown(f"**{ESTADO_EMOJI.get(estado, '')} {ESTADO_TITULO_COLUMNA.get(estado, estado)}**")
            en_este_estado = sorted(
                [t for t in tickets_hoy if t["estado"] == estado],
                key=lambda t: t.get("numero_ticket") or 0,
            )
            if not en_este_estado:
                st.caption("Sin tickets.")
            for t in en_este_estado:
                with st.container(border=True):
                    tid = t["id"]
                    editando_key = f"tt_editando_{tid}"

                    title_col, edit_col = st.columns([5, 1])
                    with title_col:
                        st.write(f"**#{t['numero_ticket']} — {t['nombre']}**")
                    with edit_col:
                        if puede_gestionar:
                            if st.button("✏️", key=f"tt_editar_{tid}", help="Editar este ticket"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()

                    if not tienda_activa:
                        st.caption(f"🏬 {t['tienda']}")
                    if t.get("telefono"):
                        st.caption(f"📱 {t['telefono']}")
                    st.caption(f"🧾 {lineas_venta_display(t.get('servicio'))}")
                    st.caption(f"Ingresó: {hora_legible(t.get('hora_ingreso'))}")

                    abandonando_key = f"tt_abandonando_{tid}"

                    if estado == "En atención":
                        en_atencion = minutos_entre(t.get("hora_inicio_atencion"))
                        st.caption(f"⏱️ En espera hace {minutos_legible(en_atencion)}")
                    elif estado == "En elaboración":
                        en_elaboracion = minutos_entre(t.get("hora_inicio_elaboracion"))
                        st.caption(f"🛠️ En elaboración hace {minutos_legible(en_elaboracion)}")
                        st.caption(f"👤 Asignado a: {db.nombre_personal_tienda(t.get('asesor_id'), personal_todos)}")
                    elif estado == "Abandono":
                        total = minutos_entre(t.get("hora_ingreso"), t.get("hora_abandono"))
                        st.caption(f"🚫 Abandonó: {hora_legible(t.get('hora_abandono'))}")
                        st.caption(f"⏱️ Tiempo en el sistema: {minutos_legible(total)}")
                        if t.get("motivo_abandono"):
                            st.caption(f"📝 Motivo: {t['motivo_abandono']}")

                    if puede_gestionar and st.session_state.get(editando_key):
                        _render_ticket_edit_form(t, editando_key)
                    elif puede_gestionar and estado == "En atención":
                        asignando_key = f"tt_asignando_{tid}"
                        if st.session_state.get(abandonando_key):
                            _render_abandono_form(tid, abandonando_key)
                        elif st.session_state.get(asignando_key):
                            _render_asignar_form(tid, t["tienda"], asignando_key)
                        else:
                            bc1, bc2 = st.columns(2)
                            if bc1.button(
                                "➡️ Elaborar", key=f"tt_elabora_{tid}", use_container_width=True,
                            ):
                                st.session_state[asignando_key] = True
                                st.rerun()
                            if bc2.button(
                                "🚫", key=f"tt_abandono_{tid}", use_container_width=True,
                                help="Marcar como Abandono",
                            ):
                                st.session_state[abandonando_key] = True
                                st.rerun()
                    elif puede_gestionar and estado == "En elaboración":
                        if st.session_state.get(abandonando_key):
                            _render_abandono_form(tid, abandonando_key)
                        else:
                            bc1, bc2 = st.columns(2)
                            if bc1.button(
                                "➡️ Facturar", key=f"tt_facturar_{tid}", use_container_width=True,
                            ):
                                db.avanzar_ticket_tienda(tid, "Facturado")
                                st.rerun()
                            if bc2.button(
                                "🚫", key=f"tt_abandono_{tid}", use_container_width=True,
                                help="Marcar como Abandono",
                            ):
                                st.session_state[abandonando_key] = True
                                st.rerun()

    # ------------------------------------------------------------------
    # Facturados de hoy: lista compacta (no tarjetas) para que no estorbe
    # junto a los tickets que todavía se están trabajando. Cada uno también
    # tiene su lápiz ✏️ para corregir algo si hace falta.
    # ------------------------------------------------------------------
    st.divider()
    st.markdown("#### ✅ Facturados de hoy")
    facturados_hoy = sorted(
        [t for t in tickets_hoy if t["estado"] == "Facturado"],
        key=lambda t: t.get("numero_ticket") or 0,
    )
    if not facturados_hoy:
        st.caption("Todavía no hay tickets facturados hoy.")
    else:
        for t in facturados_hoy:
            tid = t["id"]
            editando_key = f"tt_editando_{tid}"
            total = minutos_entre(t.get("hora_ingreso"), t.get("hora_facturado"))
            elaborado_por = db.nombre_personal_tienda(t.get("asesor_id"), personal_todos) if t.get("asesor_id") else "—"
            with st.container(border=True):
                fc1, fc2 = st.columns([6, 1])
                with fc1:
                    st.markdown(
                        f"**#{t['numero_ticket']} — {t['nombre']}**"
                        + (f" · 🏬 {t['tienda']}" if not tienda_activa else "")
                        + f"  \n🧾 {lineas_venta_display(t.get('servicio'))}"
                        f" · ✅ Facturado: {hora_legible(t.get('hora_facturado'))}"
                        f" · ⏱️ Total: {minutos_legible(total)} · 👤 {elaborado_por}"
                    )
                with fc2:
                    if puede_gestionar:
                        if st.button("✏️", key=f"tt_editar_{tid}", help="Editar este ticket"):
                            st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                            st.rerun()
                if puede_gestionar and st.session_state.get(editando_key):
                    _render_ticket_edit_form(t, editando_key)

    # ------------------------------------------------------------------
    # Tickets eliminados (registro de auditoría)
    # ------------------------------------------------------------------
    if puede_gestionar:
        st.divider()
        st.markdown("#### 🗑️ Tickets eliminados")
        st.caption("Registro de todos los tickets que se han eliminado, con el motivo y quién lo hizo.")
        eliminados = db.list_tickets_eliminados(tienda=tienda_activa)
        if eliminados:
            df_el = pd.DataFrame([{
                **({} if tienda_activa else {"Tienda": t["tienda"]}),
                "N° ticket": t["numero_ticket"], "Cliente": t["nombre"],
                "Teléfono": t.get("telefono") or "—",
                "Servicio/producto": lineas_venta_display(t.get("servicio")),
                "Estado al eliminarlo": ESTADO_TITULO_COLUMNA.get(t["estado"], t["estado"]),
                "Motivo de eliminación": t.get("motivo_eliminacion") or "—",
                "Eliminado por": t.get("eliminado_por") or "—",
                "Eliminado el": (
                    f"{(t.get('eliminado_en') or '')[:10]} {hora_legible(t.get('eliminado_en'))}"
                    if t.get("eliminado_en") else "—"
                ),
            } for t in eliminados])
            st.dataframe(df_el, use_container_width=True, hide_index=True)
            download_excel_button(df_el, "tickets_tienda_eliminados.xlsx", key="tt_descargar_eliminados")
        else:
            st.caption("No hay tickets eliminados todavía.")

# ---------------------------------------------------------------------------
# Código QR / Pantalla pública
# ---------------------------------------------------------------------------
with tab_qr:
    st.markdown("#### 🔗 Código QR de check-in")
    st.caption(
        "Imprime este código y pégalo en la tienda. El cliente lo escanea con la cámara de su "
        "celular, llena el formulario (nombre, teléfono y qué necesita) y su ticket aparece "
        "automáticamente en el tablero de esta pestaña."
    )

    if es_rol_de_tienda:
        tienda_qr = tienda_usuario
        st.caption(f"Tienda: **{tienda_qr}**")
    else:
        tienda_qr = st.selectbox("Tienda", TICKET_TIENDAS, key="tt_qr_tienda")

    slug = TICKET_TIENDA_SLUG[tienda_qr]
    link_checkin = f"{APP_URL}/?ticket={slug}"

    qr_img = qrcode.make(link_checkin, box_size=8, border=2)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.image(png_bytes, caption=f"QR de check-in — {tienda_qr}", width=260)
        st.download_button(
            "⬇️ Descargar QR (PNG)", data=png_bytes,
            file_name=f"qr_checkin_{slug}.png", mime="image/png",
            use_container_width=True,
        )
    with c2:
        st.write("Enlace del formulario de check-in (por si prefieres compartirlo directo):")
        st.code(link_checkin)

    st.divider()
    st.markdown("#### 📺 Pantalla pública \"Ahora atendiendo\"")
    st.caption(
        "Abre este enlace en una tablet o TV dentro de la tienda para mostrar a los clientes qué "
        "ticket se está atendiendo y quiénes siguen en la fila. Se actualiza sola cada 15 segundos "
        "y no necesita iniciar sesión."
    )
    link_pantalla = f"{APP_URL}/?pantalla={slug}"
    st.code(link_pantalla)

# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------
with tab_historial:
    if es_rol_de_tienda:
        tienda_hist = tienda_usuario
        st.caption(f"Tienda: **{tienda_hist}**")
    else:
        filtro_tienda_hist = st.selectbox(
            "Tienda", ["Todas"] + TICKET_TIENDAS, key="tt_hist_tienda"
        )
        tienda_hist = None if filtro_tienda_hist == "Todas" else filtro_tienda_hist

    fecha_hist = st.date_input("Fecha", value=db.hoy_guatemala(), key="tt_hist_fecha")

    if tienda_hist:
        tickets_hist = db.list_tickets_tienda(tienda=tienda_hist, fecha=str(fecha_hist))
    else:
        tickets_hist = [
            t for tda in TICKET_TIENDAS
            for t in db.list_tickets_tienda(tienda=tda, fecha=str(fecha_hist))
        ]
    tickets_hist.sort(key=lambda t: t.get("numero_ticket") or 0)

    if tickets_hist:
        personal_hist = db.list_personal_tiendas(solo_activos=False)
        df = pd.DataFrame([{
            "N° ticket": t["numero_ticket"], "Tienda": t["tienda"], "Cliente": t["nombre"],
            "Teléfono": t.get("telefono") or "—", "Servicio/producto": lineas_venta_display(t.get("servicio")),
            "Estado": ESTADO_TITULO_COLUMNA.get(t["estado"], t["estado"]),
            "Asignado a": db.nombre_personal_tienda(t.get("asesor_id"), personal_hist),
            "Ingresó": hora_legible(t.get("hora_ingreso")),
            "Espera (min)": minutos_entre(t.get("hora_ingreso"), t.get("hora_inicio_atencion")),
            "Atención (min)": minutos_entre(t.get("hora_inicio_atencion"), t.get("hora_inicio_elaboracion")),
            "Elaboración (min)": minutos_entre(t.get("hora_inicio_elaboracion"), t.get("hora_facturado")),
            "Facturado": hora_legible(t.get("hora_facturado")),
            "Tiempo total (min)": minutos_entre(t.get("hora_ingreso"), t.get("hora_facturado") or t.get("hora_abandono")),
            "Motivo abandono": t.get("motivo_abandono") or "—",
        } for t in tickets_hist])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "tickets_tienda.xlsx", key="tt_descargar_historial")
    else:
        st.info("No hay tickets registrados con este filtro.")

# ---------------------------------------------------------------------------
# Personal de la tienda: todo el equipo asignado a cada tienda (jefe, sub
# jefe, anfitriona, cajero, asesores de ventas / "Diseñador", acabados,
# express), venga de la colección "personal_tiendas" (solo nombre, sin
# acceso al sistema) o de "usuarios" (con usuario/contraseña — solo
# anfitriona, jefe de tienda, sub jefe de tienda y cajero).
# ---------------------------------------------------------------------------
with tab_personal:
    if es_rol_de_tienda:
        tienda_personal = tienda_usuario
        st.caption(f"Tienda: **{tienda_personal}**")
    else:
        filtro_tienda_personal = st.selectbox(
            "Tienda", ["Todas"] + TICKET_TIENDAS, key="tt_personal_tienda"
        )
        tienda_personal = None if filtro_tienda_personal == "Todas" else filtro_tienda_personal

    personal_lista = db.list_personal_tiendas(tienda=tienda_personal, solo_activos=False)
    usuarios_tienda = [
        u for u in db.list_usuarios()
        if u.get("tienda") and (not tienda_personal or u["tienda"] == tienda_personal)
    ]
    # Se cruzan las dos listas por (nombre, tienda) para saber quién de la
    # lista de personal además tiene usuario con acceso al sistema.
    acceso_por_persona = {
        ((u.get("nombre") or "").strip().lower(), u.get("tienda")): u for u in usuarios_tienda
    }

    if not personal_lista and not usuarios_tienda:
        st.info("No hay personal de tienda registrado todavía con este filtro.")
    else:
        filas = []
        vistos = set()
        for p in personal_lista:
            clave = ((p.get("nombre") or "").strip().lower(), p.get("tienda"))
            vistos.add(clave)
            u_match = acceso_por_persona.get(clave)
            filas.append({
                "Tienda": p["tienda"], "Nombre": p["nombre"], "Puesto": p.get("puesto") or "—",
                "Acceso al sistema": "Sí" if u_match else "No",
                "Usuario": u_match["username"] if u_match else "—",
                "Activo": "Sí" if p.get("activo", True) else "No",
            })
        # Por si algún usuario se creó a mano y todavía no tiene su
        # contraparte en la lista de personal, también se muestra.
        for u in usuarios_tienda:
            clave = ((u.get("nombre") or "").strip().lower(), u.get("tienda"))
            if clave in vistos:
                continue
            filas.append({
                "Tienda": u["tienda"], "Nombre": u["nombre"], "Puesto": ROLES_LABEL.get(u["rol"], u["rol"]),
                "Acceso al sistema": "Sí", "Usuario": u["username"],
                "Activo": "Sí" if u.get("activo", True) else "No",
            })

        df_personal = pd.DataFrame(filas).sort_values(["Tienda", "Nombre"])
        st.dataframe(df_personal, use_container_width=True, hide_index=True)
        download_excel_button(df_personal, "personal_tiendas.xlsx", key="tt_descargar_personal")
        n_con_acceso = sum(1 for f in filas if f["Acceso al sistema"] == "Sí")
        st.caption(f"👤 {len(filas)} persona(s) en este filtro — {n_con_acceso} con acceso al sistema.")
        if not es_rol_de_tienda:
            st.caption(
                "Para agregar o corregir personal, ve a 'Administración de usuarios' → "
                "'Carga inicial de personal' o 'Nuevo usuario'."
            )
