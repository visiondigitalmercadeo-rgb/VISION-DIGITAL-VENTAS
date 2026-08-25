import io

import pandas as pd
import qrcode
import streamlit as st

import auth
import database as db
from config import APP_URL, ESTADOS_TICKET, TICKET_SERVICIOS, TICKET_TIENDA_SLUG, TICKET_TIENDAS
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
tienda_usuario = auth.current_user_tienda()
es_rol_de_tienda = user["rol"] in ("anfitriona", "jefe_tienda", "asesor_ventas")

if es_rol_de_tienda and not tienda_usuario:
    st.error(
        "Tu usuario todavía no tiene una tienda asignada. Pídele a un administrador que te "
        "asigne una tienda desde 'Administración de usuarios'."
    )
    st.stop()

ESTADO_EMOJI = {
    "Esperando": "🕐",
    "En atención": "🗣️",
    "En elaboración": "🛠️",
    "Facturado": "✅",
    "Abandono": "🚫",
}

# Títulos que ve el equipo en cada columna del tablero (el valor interno de
# "estado" que se guarda en la base de datos no cambia, solo cómo se muestra).
ESTADO_TITULO_COLUMNA = {
    "Esperando": "Ingresado",
    "En atención": "En espera",
    "En elaboración": "En elaboración",
    "Facturado": "Facturado",
    "Abandono": "Abandono",
}

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


tab_tablero, tab_qr, tab_historial = st.tabs(
    ["🗂️ Tablero de hoy", "🔗 Código QR / Pantalla", "📋 Historial"]
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
        tickets_hoy = db.list_tickets_tienda(tienda=tienda_activa, fecha=hoy)
    else:
        tickets_hoy = [
            t for tda in TICKET_TIENDAS for t in db.list_tickets_tienda(tienda=tda, fecha=hoy)
        ]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Tickets hoy", len(tickets_hoy))
    k2.metric("Ingresado", sum(1 for t in tickets_hoy if t["estado"] == "Esperando"))
    k3.metric("En espera", sum(1 for t in tickets_hoy if t["estado"] == "En atención"))
    k4.metric("En elaboración", sum(1 for t in tickets_hoy if t["estado"] == "En elaboración"))
    k5.metric("Facturados", sum(1 for t in tickets_hoy if t["estado"] == "Facturado"))
    k6.metric("Abandono", sum(1 for t in tickets_hoy if t["estado"] == "Abandono"))

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

    cols = st.columns(len(ESTADOS_TICKET))
    for col, estado in zip(cols, ESTADOS_TICKET):
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
                    st.write(f"**#{t['numero_ticket']} — {t['nombre']}**")
                    if not tienda_activa:
                        st.caption(f"🏬 {t['tienda']}")
                    if t.get("telefono"):
                        st.caption(f"📱 {t['telefono']}")
                    st.caption(f"🧾 {lineas_venta_display(t.get('servicio'))}")
                    st.caption(f"Ingresó: {hora_legible(t.get('hora_ingreso'))}")

                    abandonando_key = f"tt_abandonando_{t['id']}"

                    if estado == "Esperando":
                        espera = minutos_entre(t.get("hora_ingreso"))
                        st.caption(f"⏱️ Esperando hace {minutos_legible(espera)}")
                        if puede_gestionar:
                            if st.session_state.get(abandonando_key):
                                _render_abandono_form(t["id"], abandonando_key)
                            else:
                                bc1, bc2 = st.columns(2)
                                if bc1.button(
                                    "➡️ Atender", key=f"tt_atender_{t['id']}", use_container_width=True,
                                ):
                                    db.avanzar_ticket_tienda(t["id"], "En atención")
                                    st.rerun()
                                if bc2.button(
                                    "🚫", key=f"tt_abandono_{t['id']}", use_container_width=True,
                                    help="Marcar como Abandono",
                                ):
                                    st.session_state[abandonando_key] = True
                                    st.rerun()
                    elif estado == "En atención":
                        espera = minutos_entre(t.get("hora_ingreso"), t.get("hora_inicio_atencion"))
                        en_atencion = minutos_entre(t.get("hora_inicio_atencion"))
                        st.caption(f"⏱️ Esperó {minutos_legible(espera)}")
                        st.caption(f"🗣️ En esta etapa hace {minutos_legible(en_atencion)}")
                        if puede_gestionar:
                            if st.session_state.get(abandonando_key):
                                _render_abandono_form(t["id"], abandonando_key)
                            else:
                                bc1, bc2 = st.columns(2)
                                if bc1.button(
                                    "➡️ Elaborar", key=f"tt_elabora_{t['id']}", use_container_width=True,
                                ):
                                    db.avanzar_ticket_tienda(t["id"], "En elaboración")
                                    st.rerun()
                                if bc2.button(
                                    "🚫", key=f"tt_abandono_{t['id']}", use_container_width=True,
                                    help="Marcar como Abandono",
                                ):
                                    st.session_state[abandonando_key] = True
                                    st.rerun()
                    elif estado == "En elaboración":
                        en_elaboracion = minutos_entre(t.get("hora_inicio_elaboracion"))
                        st.caption(f"🛠️ En elaboración hace {minutos_legible(en_elaboracion)}")
                        if puede_gestionar:
                            if st.session_state.get(abandonando_key):
                                _render_abandono_form(t["id"], abandonando_key)
                            else:
                                bc1, bc2 = st.columns(2)
                                if bc1.button(
                                    "➡️ Facturar", key=f"tt_facturar_{t['id']}", use_container_width=True,
                                ):
                                    db.avanzar_ticket_tienda(t["id"], "Facturado")
                                    st.rerun()
                                if bc2.button(
                                    "🚫", key=f"tt_abandono_{t['id']}", use_container_width=True,
                                    help="Marcar como Abandono",
                                ):
                                    st.session_state[abandonando_key] = True
                                    st.rerun()
                    elif estado == "Facturado":
                        total = minutos_entre(t.get("hora_ingreso"), t.get("hora_facturado"))
                        st.caption(f"✅ Facturado: {hora_legible(t.get('hora_facturado'))}")
                        st.caption(f"⏱️ Tiempo total: {minutos_legible(total)}")
                    elif estado == "Abandono":
                        total = minutos_entre(t.get("hora_ingreso"), t.get("hora_abandono"))
                        st.caption(f"🚫 Abandonó: {hora_legible(t.get('hora_abandono'))}")
                        st.caption(f"⏱️ Tiempo en el sistema: {minutos_legible(total)}")
                        if t.get("motivo_abandono"):
                            st.caption(f"📝 Motivo: {t['motivo_abandono']}")

    if puede_gestionar:
        st.divider()
        st.markdown("#### ✏️ Gestionar o eliminar un ticket")
        st.caption(
            "Corrige el nombre, teléfono, servicio o estado de un ticket, o elimínalo por "
            "completo — por ejemplo si un cliente lo registró dos veces por error."
        )
        if not tickets_hoy:
            st.caption("No hay tickets registrados hoy todavía.")
        else:
            opciones_tk = {
                f"#{t['numero_ticket']} — {t['nombre']} "
                f"({t['tienda']}, {ESTADO_TITULO_COLUMNA.get(t['estado'], t['estado'])})": t["id"]
                for t in sorted(tickets_hoy, key=lambda t: t.get("numero_ticket") or 0)
            }
            elegido_tk = st.selectbox(
                "Selecciona un ticket", ["—"] + list(opciones_tk.keys()), key="tt_gestionar_sel"
            )
            if elegido_tk != "—":
                tid = opciones_tk[elegido_tk]
                tk = db.get_ticket_tienda(tid)
                if tk:
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
                        motivo_ab_ed = st.text_input(
                            "Motivo de abandono (solo aplica si el estado es Abandono)",
                            value=tk.get("motivo_abandono") or "",
                        )
                        if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
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
                                )
                                st.success("Ticket actualizado.")
                                st.rerun()

                    st.markdown("###### 🗑️ Eliminar este ticket")
                    st.caption(
                        "El ticket deja de aparecer en el tablero y en el historial, pero queda "
                        "guardado en el listado de 'Tickets eliminados' de más abajo, junto con el "
                        "motivo y quién lo eliminó."
                    )
                    eliminando_key = f"tt_eliminando_{tid}"
                    if st.session_state.get(eliminando_key):
                        motivo_el = st.text_area(
                            "¿Por qué se elimina este ticket?", key=f"tt_motivo_el_{tid}", height=80,
                        )
                        dc1, dc2 = st.columns(2)
                        if dc1.button(
                            "Confirmar eliminación", key=f"tt_confirmar_el_{tid}", use_container_width=True,
                        ):
                            if not motivo_el.strip():
                                st.error("Escribe el motivo antes de confirmar.")
                            else:
                                db.eliminar_ticket_tienda(tid, motivo_el, eliminado_por=user["nombre"])
                                st.session_state.pop(eliminando_key, None)
                                st.success("Ticket eliminado.")
                                st.rerun()
                        if dc2.button("Cancelar", key=f"tt_cancelar_el_{tid}", use_container_width=True):
                            st.session_state.pop(eliminando_key, None)
                            st.rerun()
                    else:
                        if st.button(
                            "🗑️ Eliminar ticket", key=f"tt_del_ticket_{tid}", use_container_width=True,
                        ):
                            st.session_state[eliminando_key] = True
                            st.rerun()

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
        df = pd.DataFrame([{
            "N° ticket": t["numero_ticket"], "Tienda": t["tienda"], "Cliente": t["nombre"],
            "Teléfono": t.get("telefono") or "—", "Servicio/producto": lineas_venta_display(t.get("servicio")),
            "Estado": ESTADO_TITULO_COLUMNA.get(t["estado"], t["estado"]),
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
