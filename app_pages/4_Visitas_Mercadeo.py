from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

import auth
import database as db
from config import CHECKLIST_DEFAULT, ESTADOS_VISITA_MERCADEO, STATUS
from utils import base_layout, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("🏪 Calendario de visitas de mercadeo a puntos de venta")
st.caption("Programa visitas a puntos de venta y completa el checklist de cada visita.")

tab_lista, tab_gantt, tab_nueva = st.tabs(["📋 Visitas registradas", "📊 Vista Gantt", "➕ Nueva visita"])

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
    filtro_vendedor_g = vendedor_filter_selector(key="mkt_filtro_vendedor_gantt")
    c1, c2 = st.columns(2)
    desde_g = c1.date_input("Desde", value=date.today() - timedelta(days=14), key="mkt_gantt_desde")
    hasta_g = c2.date_input("Hasta", value=date.today() + timedelta(days=14), key="mkt_gantt_hasta")

    visitas_g = db.list_visitas_mercadeo(filtro_vendedor_g)
    visitas_g = [v for v in visitas_g if desde_g.isoformat() <= v["fecha"] <= hasta_g.isoformat()]

    if not visitas_g:
        st.info("No hay visitas de mercadeo en este rango para mostrar en el Gantt.")
    else:
        vendedores_g = db.list_usuarios()
        filas = []
        for v in visitas_g:
            inicio = date.fromisoformat(v["fecha"])
            total = len(v["checklist_items"])
            ok = sum(1 for i in v["checklist_items"] if i.get("ok"))
            filas.append({
                "Punto de venta": v["punto_venta"],
                "Inicio": pd.Timestamp(inicio),
                "Fin": pd.Timestamp(inicio + timedelta(days=1)),
                "Estado": v["estado"],
                "Vendedor": db.nombre_vendedor(v["vendedor_id"], vendedores_g),
                "Checklist": f"{ok}/{total} completado",
            })
        df_g = pd.DataFrame(filas)

        fig = px.timeline(
            df_g, x_start="Inicio", x_end="Fin", y="Punto de venta", color="Estado",
            color_discrete_map={"Pendiente": STATUS["warning"], "Realizada": STATUS["good"]},
            hover_data={"Vendedor": True, "Checklist": True, "Inicio": False, "Fin": False},
        )
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_traces(marker_line_width=0, width=0.5)
        st.plotly_chart(
            base_layout(fig, title="Visitas de mercadeo por punto de venta", height=max(320, 40 * len(df_g["Punto de venta"].unique()) + 120)),
            use_container_width=True,
        )
        st.caption("🟡 Pendiente · 🟢 Realizada — cada barra marca el día programado de la visita.")

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
