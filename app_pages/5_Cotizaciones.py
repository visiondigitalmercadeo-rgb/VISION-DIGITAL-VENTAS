from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_COTIZACION
from utils import money, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("💰 Fecha de contacto, cotización y estado")
st.caption("Seguimiento de cotizaciones enviadas a prospectos y clientes.")

tab_lista, tab_nueva = st.tabs(["📋 Cotizaciones", "➕ Nueva cotización"])

with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="cot_filtro_vendedor")
    filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_COTIZACION, default=[])

    rows = db.list_cotizaciones(filtro_vendedor)
    if filtro_estado:
        rows = [r for r in rows if r["estado"] in filtro_estado]

    if not rows:
        st.info("No hay cotizaciones registradas con estos filtros.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"], "Cliente": r["nombre_cliente"] or "—", "NIT": r["nit"] or "—",
            "Nº cotización": r["numero_cotizacion"], "Fecha contacto": r["fecha_contacto"],
            "Fecha cotización": r["fecha_cotizacion"], "Monto": money(r["monto"]),
            "Estado": r["estado"], "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if auth.can_edit():
            st.markdown("#### ✏️ Actualizar estado de cotización")
            opciones = {f"{r['numero_cotizacion'] or r['id']} — {r['nombre_cliente'] or ''}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona", ["—"] + list(opciones.keys()), key="cot_editar")
            if elegido != "—":
                cid = opciones[elegido]
                cot = next(r for r in rows if r["id"] == cid)
                if user["rol"] == "vendedor" and cot["vendedor_id"] != user["id"]:
                    st.warning("Esta cotización pertenece a otro vendedor.")
                else:
                    with st.form(f"editar_cot_{cid}"):
                        estado = st.selectbox("Estado", ESTADOS_COTIZACION,
                                               index=ESTADOS_COTIZACION.index(cot["estado"]))
                        monto = st.number_input("Monto (Q)", value=float(cot["monto"] or 0), min_value=0.0, step=100.0)
                        notas = st.text_area("Notas", value=cot["notas"] or "")
                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("Guardar", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar cotización", use_container_width=True)
                        if guardar:
                            db.update_cotizacion(cid, estado=estado, monto=monto, notas=notas)
                            st.success("Cotización actualizada.")
                            st.rerun()
                        if eliminar:
                            db.delete_cotizacion(cid)
                            st.success("Cotización eliminada.")
                            st.rerun()
        else:
            st.caption("Tu rol es de solo vista: puedes consultar pero no editar cotizaciones.")

with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede registrar cotizaciones.")
    else:
        if user["rol"] == "admin":
            vendedores = db.list_vendedores()
            opciones_v = {v["nombre"]: v["id"] for v in vendedores}
            vendedor_nombre = st.selectbox("Vendedor", list(opciones_v.keys()), key="cot_nueva_vendedor")
            vendedor_id = opciones_v[vendedor_nombre]
        else:
            vendedor_id = user["id"]
            st.caption(f"Vendedor: **{user['nombre']}**")

        prospectos = db.list_prospectos(vendedor_id)
        if not prospectos:
            st.warning("Este vendedor no tiene prospectos registrados. Crea uno primero en 'Prospección (CRM)'.")
        else:
            with st.form("nueva_cot_form", clear_on_submit=True):
                opciones_p = {f"{p['nombre_cliente']} (NIT {p['nit']})": p["id"] for p in prospectos}
                prospecto_sel = st.selectbox("Prospecto/cliente", list(opciones_p.keys()))
                prospecto_id = opciones_p[prospecto_sel]

                c1, c2 = st.columns(2)
                fecha_contacto = c1.date_input("Fecha de contacto", value=date.today())
                fecha_cotizacion = c2.date_input("Fecha de envío de cotización", value=date.today())
                c3, c4 = st.columns(2)
                numero_cotizacion = c3.text_input("Número de cotización")
                monto = c4.number_input("Monto (Q)", min_value=0.0, step=100.0)
                estado = st.selectbox("Estado", ESTADOS_COTIZACION)
                notas = st.text_area("Notas")

                if st.form_submit_button("Guardar cotización", use_container_width=True):
                    db.create_cotizacion(prospecto_id, vendedor_id, fecha_contacto, fecha_cotizacion,
                                          numero_cotizacion, monto, estado, notas)
                    st.success("Cotización registrada.")
                    st.rerun()
