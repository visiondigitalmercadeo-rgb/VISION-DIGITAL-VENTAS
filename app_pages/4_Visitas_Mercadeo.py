from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_calendar import calendar as st_calendar

import auth
import database as db
from config import CHECKLIST_DEFAULT, ESTADOS_PENDIENTE_MERCADEO, ESTADOS_VISITA_MERCADEO, STATUS
from utils import base_layout, download_excel_button, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("🏪 Calendario de visitas de mercadeo a puntos de venta")
st.caption("Programa visitas a puntos de venta y completa el checklist de cada visita.")

ESTADO_COLOR_VISITA = {"Pendiente": STATUS["warning"], "Realizada": STATUS["good"]}

tab_calendario, tab_lista, tab_gantt, tab_nueva, tab_pendientes = st.tabs(
    ["🗓️ Calendario", "📋 Visitas registradas", "📊 Gantt de pendientes", "➕ Nueva visita", "📌 Pendientes"]
)

# --------------------------------------------------------------------------
# Calendario visual de visitas programadas
# --------------------------------------------------------------------------
with tab_calendario:
    filtro_vendedor_cal = vendedor_filter_selector(key="mkt_filtro_vendedor_cal")

    visitas_cal = db.list_visitas_mercadeo(filtro_vendedor_cal)
    vendedores_cal = db.list_usuarios()

    eventos_cal = []
    for v in visitas_cal:
        titulo = f"🏪 {v['punto_venta']}"
        if user["rol"] != "vendedor":
            titulo += f" — {db.nombre_vendedor(v['vendedor_id'], vendedores_cal)}"
        color = ESTADO_COLOR_VISITA.get(v["estado"], "#898781")
        eventos_cal.append({
            "id": str(v["id"]),
            "title": titulo,
            "start": v["fecha"],
            "allDay": True,
            "backgroundColor": color,
            "borderColor": color,
        })

    opciones_cal = {
        "locale": "es",
        "initialView": "dayGridMonth",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,listMonth"},
        "height": 650,
        "firstDay": 1,
        "buttonText": {"today": "Hoy", "month": "Mes", "week": "Semana", "list": "Lista"},
    }

    estado_click_cal = st_calendar(events=eventos_cal, options=opciones_cal, key="mkt_calendario_visual")

    st.caption(f"🟡 Pendiente · 🟢 Realizada — total programado: {len(eventos_cal)} visita(s).")

    if estado_click_cal and estado_click_cal.get("eventClick"):
        vid_cal = estado_click_cal["eventClick"]["event"]["id"]
        visita_sel = next((v for v in visitas_cal if str(v["id"]) == vid_cal), None)
        if visita_sel:
            with st.container(border=True):
                st.markdown(f"**{visita_sel['punto_venta']}**")
                ok_count = sum(1 for i in visita_sel["checklist_items"] if i.get("ok"))
                total_count = len(visita_sel["checklist_items"])
                st.write(
                    f"📅 {visita_sel['fecha']} · 📍 {visita_sel['direccion'] or '—'} · "
                    f"Estado: {visita_sel['estado']} · Checklist: {ok_count}/{total_count}"
                )
                if user["rol"] != "vendedor":
                    st.caption(f"Vendedor: {db.nombre_vendedor(visita_sel['vendedor_id'], vendedores_cal)}")
                if visita_sel["pendientes"]:
                    st.caption(f"Pendientes: {visita_sel['pendientes']}")
                if visita_sel["notas"]:
                    st.caption(f"Notas: {visita_sel['notas']}")
                st.caption("Para editar el checklist o eliminar la visita, usa la pestaña 'Visitas registradas'.")

with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="mkt_filtro_vendedor")
    filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_VISITA_MERCADEO, default=[])

    visitas = db.list_visitas_mercadeo(filtro_vendedor)
    if filtro_estado:
        visitas = [v for v in visitas if v["estado"] in filtro_estado]

    if not visitas:
        st.info("No hay visitas de mercadeo registradas con estos filtros.")
    else:
        vendedores = db.list_usuarios()
        resumen = pd.DataFrame([{
            "ID": v["id"], "Fecha": v["fecha"], "Punto de venta": v["punto_venta"],
            "Estado": v["estado"],
            "Checklist completado": f"{sum(1 for i in v['checklist_items'] if i.get('ok'))}/{len(v['checklist_items'])}",
            "Pendientes": v["pendientes"] or "—",
            "Vendedor": db.nombre_vendedor(v["vendedor_id"], vendedores),
        } for v in visitas])
        st.dataframe(resumen, use_container_width=True, hide_index=True)
        download_excel_button(resumen, "visitas_mercadeo.xlsx", key="mkt_descargar_excel")

        st.markdown("#### ✅ Completar / actualizar checklist de una visita")
        opciones = {f"{v['fecha']} — {v['punto_venta']}": v["id"] for v in visitas}
        elegido = st.selectbox("Selecciona una visita", ["—"] + list(opciones.keys()))
        if elegido != "—":
            vid = opciones[elegido]
            visita = next(v for v in visitas if v["id"] == vid)
            puede_editar = auth.can_edit() and (user["rol"] != "vendedor" or visita["vendedor_id"] == user["id"])
            if not puede_editar:
                st.caption("Solo el vendedor asignado (o un administrador) puede editar esta visita.")
            with st.form(f"editar_visita_{vid}"):
                punto_venta_ed = st.text_input("Nombre del punto de venta", value=visita["punto_venta"] or "",
                                                disabled=not puede_editar)
                direccion_ed = st.text_input("Dirección", value=visita["direccion"] or "",
                                              disabled=not puede_editar)
                fecha_ed = st.date_input(
                    "Fecha de la visita",
                    value=date.fromisoformat(visita["fecha"]) if visita["fecha"] else date.today(),
                    disabled=not puede_editar,
                )
                nuevos_items = []
                st.write("**Checklist de la visita**")
                for idx, item in enumerate(visita["checklist_items"]):
                    ok = st.checkbox(item["item"], value=item.get("ok", False),
                                      key=f"chk_{vid}_{idx}", disabled=not puede_editar)
                    nuevos_items.append({"item": item["item"], "ok": ok})
                pendientes = st.text_area("Pendientes por resolver", value=visita["pendientes"] or "",
                                           disabled=not puede_editar)
                estado = st.selectbox("Estado de la visita", ESTADOS_VISITA_MERCADEO,
                                       index=ESTADOS_VISITA_MERCADEO.index(visita["estado"]),
                                       disabled=not puede_editar)
                notas = st.text_area("Notas", value=visita["notas"] or "", disabled=not puede_editar)
                colf1, colf2 = st.columns(2)
                guardar_v = colf1.form_submit_button("Guardar", use_container_width=True, disabled=not puede_editar)
                eliminar_v = colf2.form_submit_button("Eliminar visita", use_container_width=True, disabled=not puede_editar)
                if guardar_v and puede_editar:
                    if not punto_venta_ed.strip():
                        st.error("El nombre del punto de venta es obligatorio.")
                    else:
                        db.update_visita_mercadeo(
                            vid, punto_venta=punto_venta_ed.strip(), direccion=direccion_ed,
                            fecha=str(fecha_ed), checklist_items=nuevos_items, pendientes=pendientes,
                            estado=estado, notas=notas,
                        )
                        st.success("Visita actualizada.")
                        st.rerun()
                if eliminar_v and puede_editar:
                    db.delete_visita_mercadeo(vid)
                    st.success("Visita eliminada.")
                    st.rerun()

with tab_gantt:
    st.caption("Vista Gantt de los pendientes reportados en los puntos de venta: cada barra va desde la "
               "fecha reportada hasta su fecha de finalización (o hasta hoy, si sigue abierto).")
    filtro_vendedor_g = vendedor_filter_selector(key="mkt_filtro_vendedor_gantt")
    c1, c2 = st.columns(2)
    desde_g = c1.date_input("Desde", value=date.today() - timedelta(days=30), key="mkt_gantt_desde")
    hasta_g = c2.date_input("Hasta", value=date.today() + timedelta(days=14), key="mkt_gantt_hasta")

    pendientes_g = db.list_pendientes_mercadeo(filtro_vendedor_g)
    pendientes_g = [
        p for p in pendientes_g
        if p["fecha_reportada"] and desde_g.isoformat() <= p["fecha_reportada"] <= hasta_g.isoformat()
    ]

    if not pendientes_g:
        st.info("No hay pendientes de mercadeo en este rango para mostrar en el Gantt.")
    else:
        vendedores_g = db.list_usuarios()
        filas = []
        for p in pendientes_g:
            inicio = date.fromisoformat(p["fecha_reportada"])
            if p["fecha_finalizacion"]:
                fin = date.fromisoformat(p["fecha_finalizacion"])
                if fin < inicio:
                    fin = inicio
            else:
                fin = max(inicio, date.today())
            filas.append({
                "Pendiente": f"{p['tienda']} — {(p['pendiente'] or '')[:40]}",
                "Inicio": pd.Timestamp(inicio),
                "Fin": pd.Timestamp(fin + timedelta(days=1)),
                "Estado": p["estado"],
                "Vendedor": db.nombre_vendedor(p["vendedor_id"], vendedores_g),
            })
        df_g = pd.DataFrame(filas)

        fig = px.timeline(
            df_g, x_start="Inicio", x_end="Fin", y="Pendiente", color="Estado",
            color_discrete_map={
                "Pendiente": STATUS["warning"], "En proceso": STATUS["serious"], "Resuelto": STATUS["good"],
            },
            hover_data={"Vendedor": True, "Inicio": False, "Fin": False},
        )
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_traces(marker_line_width=0, width=0.5)
        st.plotly_chart(
            base_layout(fig, title="Pendientes de mercadeo por punto de venta", height=max(320, 40 * len(df_g["Pendiente"].unique()) + 120)),
            use_container_width=True,
        )
        st.caption("🟡 Pendiente · 🟠 En proceso · 🟢 Resuelto — cada barra va desde que se reportó hasta su resolución.")

with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede programar visitas de mercadeo.")
    else:
        with st.form("nueva_visita_form", clear_on_submit=True):
            if user["rol"] == "admin":
                vendedores = db.list_vendedores()
                opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                vendedor_nombre = st.selectbox("Responsable", list(opciones_v.keys()))
                vendedor_id = opciones_v[vendedor_nombre]
            else:
                vendedor_id = user["id"]
                st.caption(f"Responsable: **{user['nombre']}**")

            punto_venta = st.text_input("Nombre del punto de venta")
            direccion = st.text_input("Dirección")
            fecha = st.date_input("Fecha de la visita", value=date.today())
            st.caption("El checklist estándar se agregará automáticamente; podrás marcarlo al completar la visita.")
            pendientes = st.text_area("Pendientes conocidos (opcional)")
            notas = st.text_area("Notas")

            if st.form_submit_button("Programar visita", use_container_width=True):
                if not punto_venta.strip():
                    st.error("Ingresa el nombre del punto de venta.")
                else:
                    checklist_items = [{"item": i, "ok": False} for i in CHECKLIST_DEFAULT]
                    db.create_visita_mercadeo(vendedor_id, punto_venta.strip(), direccion, fecha,
                                               checklist_items, pendientes, "Pendiente", notas)
                    st.success("Visita de mercadeo programada.")
                    st.rerun()

with tab_pendientes:
    st.caption("Checklist de pendientes reportados en los puntos de venta: fecha reportada, tienda, "
               "pendiente, fecha de finalización y estado.")
    sub_lista, sub_nuevo = st.tabs(["📋 Lista de pendientes", "➕ Nuevo pendiente"])

    with sub_lista:
        filtro_vendedor_p = vendedor_filter_selector(key="mkt_pend_filtro_vendedor")
        filtro_estado_p = st.multiselect("Filtrar por estado", ESTADOS_PENDIENTE_MERCADEO, default=[],
                                          key="mkt_pend_filtro_estado")

        pendientes_rows = db.list_pendientes_mercadeo(filtro_vendedor_p)
        if filtro_estado_p:
            pendientes_rows = [p for p in pendientes_rows if p["estado"] in filtro_estado_p]

        if not pendientes_rows:
            st.info("No hay pendientes registrados con estos filtros.")
        else:
            vendedores_p = db.list_usuarios()
            df_p = pd.DataFrame([{
                "ID": p["id"], "Fecha reportada": p["fecha_reportada"], "Tienda": p["tienda"],
                "Pendiente": p["pendiente"], "Fecha finalización": p["fecha_finalizacion"] or "—",
                "Estado": p["estado"], "Vendedor": db.nombre_vendedor(p["vendedor_id"], vendedores_p),
            } for p in pendientes_rows])
            st.dataframe(df_p, use_container_width=True, hide_index=True)
            download_excel_button(df_p, "pendientes_mercadeo.xlsx", key="mkt_pend_descargar_excel")

            if auth.can_edit():
                st.markdown("#### ✏️ Actualizar pendiente")
                opciones_p = {
                    f"{p['fecha_reportada']} — {p['tienda']} — {(p['pendiente'] or '')[:40]}": p["id"]
                    for p in pendientes_rows
                }
                elegido_p = st.selectbox("Selecciona un pendiente", ["—"] + list(opciones_p.keys()),
                                          key="mkt_pend_editar")
                if elegido_p != "—":
                    pid = opciones_p[elegido_p]
                    pend = next(p for p in pendientes_rows if p["id"] == pid)
                    if user["rol"] == "vendedor" and pend["vendedor_id"] != user["id"]:
                        st.warning("Este pendiente pertenece a otro vendedor.")
                    else:
                        with st.form(f"editar_pend_{pid}"):
                            tienda_ed = st.text_input("Tienda / punto de venta", value=pend["tienda"] or "")
                            fecha_reportada_ed = st.date_input(
                                "Fecha reportada",
                                value=date.fromisoformat(pend["fecha_reportada"]) if pend["fecha_reportada"] else date.today(),
                            )
                            pendiente_ed = st.text_area("Pendiente", value=pend["pendiente"] or "")
                            estado_ed = st.selectbox("Estado", ESTADOS_PENDIENTE_MERCADEO,
                                                      index=ESTADOS_PENDIENTE_MERCADEO.index(pend["estado"]))
                            tiene_fin = estado_ed == "Resuelto"
                            fecha_fin_ed = st.date_input(
                                "Fecha de finalización",
                                value=date.fromisoformat(pend["fecha_finalizacion"]) if pend["fecha_finalizacion"] else date.today(),
                                disabled=not tiene_fin,
                            )
                            colf1, colf2 = st.columns(2)
                            guardar_p = colf1.form_submit_button("Guardar", use_container_width=True)
                            eliminar_p = colf2.form_submit_button("Eliminar pendiente", use_container_width=True)
                            if guardar_p:
                                if not tienda_ed.strip() or not pendiente_ed.strip():
                                    st.error("Tienda y descripción del pendiente son obligatorios.")
                                else:
                                    db.update_pendiente_mercadeo(
                                        pid, tienda=tienda_ed.strip(), fecha_reportada=str(fecha_reportada_ed),
                                        pendiente=pendiente_ed.strip(), estado=estado_ed,
                                        fecha_finalizacion=str(fecha_fin_ed) if tiene_fin else None,
                                    )
                                    st.success("Pendiente actualizado.")
                                    st.rerun()
                            if eliminar_p:
                                db.delete_pendiente_mercadeo(pid)
                                st.success("Pendiente eliminado.")
                                st.rerun()
            else:
                st.caption("Tu rol es de solo vista: puedes consultar pero no editar pendientes.")

    with sub_nuevo:
        if not auth.can_edit():
            st.info("Tu rol es de solo vista y no puede registrar pendientes.")
        else:
            with st.form("nuevo_pend_form", clear_on_submit=True):
                if user["rol"] == "admin":
                    vendedores_np = db.list_vendedores()
                    opciones_vnp = {v["nombre"]: v["id"] for v in vendedores_np}
                    vendedor_nombre_np = st.selectbox("Responsable", list(opciones_vnp.keys()),
                                                        key="mkt_pend_nuevo_vendedor")
                    vendedor_id_np = opciones_vnp[vendedor_nombre_np]
                else:
                    vendedor_id_np = user["id"]
                    st.caption(f"Responsable: **{user['nombre']}**")

                tienda_np = st.text_input("Tienda / punto de venta")
                fecha_reportada_np = st.date_input("Fecha reportada", value=date.today())
                pendiente_np = st.text_area("Descripción del pendiente")

                if st.form_submit_button("Registrar pendiente", use_container_width=True):
                    if not tienda_np.strip() or not pendiente_np.strip():
                        st.error("Tienda y descripción del pendiente son obligatorios.")
                    else:
                        db.create_pendiente_mercadeo(vendedor_id_np, tienda_np.strip(), fecha_reportada_np,
                                                      pendiente_np.strip(), "Pendiente")
                        st.success("Pendiente registrado.")
                        st.rerun()
