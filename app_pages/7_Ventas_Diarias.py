from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import LINEAS_VENTA, PLANTAS
from utils import download_excel_button, money, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("🧮 Venta del día por vendedor")
st.caption("Registra la venta diaria por planta (Offset, Digital, Valloy, Colorado) y por línea de venta.")

tab_lista, tab_nueva = st.tabs(["📋 Ventas registradas", "➕ Registrar venta del día"])

with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="vta_filtro_vendedor")
    c1, c2 = st.columns(2)
    desde = c1.date_input("Desde", value=date.today() - timedelta(days=30), key="vta_desde")
    hasta = c2.date_input("Hasta", value=date.today(), key="vta_hasta")

    rows = db.list_ventas(filtro_vendedor, desde=desde, hasta=hasta)
    if not rows:
        st.info("No hay ventas registradas en este rango.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"], "Fecha": r["fecha"], "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
            "Planta": r["planta"], "Línea de venta": r["linea_venta"], "Cliente": r.get("cliente") or "—",
            "Nº de órdenes": r.get("numero_ordenes") or 0, "Monto": r["monto"], "Notas": r["notas"],
        } for r in rows])

        total = df["Monto"].sum()
        total_ordenes = int(df["Nº de órdenes"].sum())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total del periodo", money(total))
        c2.metric("Nº de ventas", len(df))
        c3.metric("Promedio por venta", money(total / len(df) if len(df) else 0))
        c4.metric("Nº de órdenes del periodo", total_ordenes)

        df_display = df.copy()
        df_display["Monto"] = df_display["Monto"].apply(money)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        download_excel_button(df, "ventas.xlsx", key="vta_descargar_excel")

        st.markdown("##### Por planta")
        por_planta = df.groupby("Planta").agg(
            Total=("Monto", "sum"), **{"Nº de órdenes": ("Nº de órdenes", "sum")}
        ).reindex(PLANTAS).fillna(0)
        por_planta_display = por_planta.copy()
        por_planta_display["Total"] = por_planta_display["Total"].apply(money)
        por_planta_display["Nº de órdenes"] = por_planta_display["Nº de órdenes"].astype(int)
        st.dataframe(por_planta_display, use_container_width=True)

        st.markdown("##### Órdenes por día")
        df["FechaDT"] = pd.to_datetime(df["Fecha"])
        ordenes_dia = df.groupby("FechaDT")["Nº de órdenes"].sum().sort_index()
        ordenes_dia.index = ordenes_dia.index.strftime("%Y-%m-%d")
        st.dataframe(ordenes_dia.rename("Nº de órdenes").astype(int), use_container_width=True)

        st.markdown("##### Órdenes por mes")
        df["Mes"] = df["FechaDT"].dt.strftime("%Y-%m")
        ordenes_mes = df.groupby("Mes")["Nº de órdenes"].sum().sort_index()
        st.dataframe(ordenes_mes.rename("Nº de órdenes").astype(int), use_container_width=True)

        if auth.is_admin() or auth.is_vendedor():
            st.markdown("#### ✏️ Editar o eliminar un registro (corrección de captura)")
            opciones = {f"{r['fecha']} — {r['planta']} — {money(r['monto'])} — {r['linea_venta']}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona", ["—"] + list(opciones.keys()), key="vta_editar")
            if elegido != "—":
                vid = opciones[elegido]
                venta = next(r for r in rows if r["id"] == vid)
                if user["rol"] == "vendedor" and venta["vendedor_id"] != user["id"]:
                    st.warning("Esta venta pertenece a otro vendedor.")
                else:
                    with st.form(f"editar_venta_{vid}"):
                        if user["rol"] == "admin":
                            opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                            nombre_actual = db.nombre_vendedor(venta["vendedor_id"], vendedores)
                            nombres_v = list(opciones_v.keys())
                            vendedor_nombre_ed = st.selectbox(
                                "Vendedor", nombres_v,
                                index=nombres_v.index(nombre_actual) if nombre_actual in nombres_v else 0,
                            )
                            vendedor_id_ed = opciones_v[vendedor_nombre_ed]
                        else:
                            vendedor_id_ed = venta["vendedor_id"]
                            st.caption(f"Vendedor: **{db.nombre_vendedor(venta['vendedor_id'], vendedores)}**")

                        ce1, ce2 = st.columns(2)
                        fecha_ed = ce1.date_input(
                            "Fecha de la venta",
                            value=date.fromisoformat(venta["fecha"]) if venta["fecha"] else date.today(),
                        )
                        planta_ed = ce2.selectbox(
                            "Planta", PLANTAS,
                            index=PLANTAS.index(venta["planta"]) if venta["planta"] in PLANTAS else 0,
                        )
                        linea_venta_ed = st.selectbox(
                            "Línea de venta (producto)", LINEAS_VENTA,
                            index=LINEAS_VENTA.index(venta["linea_venta"]) if venta["linea_venta"] in LINEAS_VENTA else 0,
                        )
                        ce3, ce4 = st.columns(2)
                        cliente_ed = ce3.text_input("Cliente", value=venta.get("cliente") or "")
                        numero_ordenes_ed = ce4.number_input(
                            "Nº de órdenes", value=int(venta.get("numero_ordenes") or 0), min_value=0, step=1,
                        )
                        monto_ed = st.number_input("Monto de la venta (Q)", value=float(venta["monto"] or 0),
                                                    min_value=0.0, step=50.0)
                        notas_ed = st.text_area("Notas (opcional)", value=venta["notas"] or "")

                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("Guardar", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar registro", use_container_width=True)
                        if guardar:
                            if monto_ed <= 0:
                                st.error("El monto debe ser mayor a 0.")
                            elif not linea_venta_ed.strip():
                                st.error("Ingresa la línea de venta.")
                            else:
                                db.update_venta(
                                    vid, vendedor_id=vendedor_id_ed, fecha=str(fecha_ed), planta=planta_ed,
                                    linea_venta=linea_venta_ed, monto=monto_ed, notas=notas_ed,
                                    cliente=cliente_ed.strip(), numero_ordenes=int(numero_ordenes_ed),
                                )
                                st.success("Venta actualizada.")
                                st.rerun()
                        if eliminar:
                            db.delete_venta(vid)
                            st.success("Registro eliminado.")
                            st.rerun()

with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede registrar ventas.")
    else:
        if user["rol"] == "admin":
            vendedores = db.list_vendedores()
            opciones_v = {v["nombre"]: v["id"] for v in vendedores}
            vendedor_nombre = st.selectbox("Vendedor", list(opciones_v.keys()), key="vta_nueva_vendedor")
            vendedor_id = opciones_v[vendedor_nombre]
        else:
            vendedor_id = user["id"]
            st.caption(f"Vendedor: **{user['nombre']}**")

        with st.form("nueva_venta_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha de la venta", value=date.today())
            planta = c2.selectbox("Planta", PLANTAS)
            linea_venta = st.selectbox("Línea de venta (producto)", LINEAS_VENTA)
            c3, c4 = st.columns(2)
            cliente = c3.text_input("Cliente")
            numero_ordenes = c4.number_input("Nº de órdenes", min_value=0, step=1, value=1)
            monto = st.number_input("Monto de la venta (Q)", min_value=0.0, step=50.0)
            notas = st.text_area("Notas (opcional)")

            if st.form_submit_button("Registrar venta", use_container_width=True):
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    db.create_venta(
                        vendedor_id, fecha, planta, linea_venta, monto, notas,
                        cliente=cliente.strip(), numero_ordenes=int(numero_ordenes),
                    )
                    st.success(f"Venta de {money(monto)} registrada en planta {planta}.")
                    st.rerun()
