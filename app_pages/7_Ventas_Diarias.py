from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import PLANTAS
from utils import money, sidebar_user_box, vendedor_filter_selector

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
            "Planta": r["planta"], "Línea de venta": r["linea_venta"], "Monto": r["monto"], "Notas": r["notas"],
        } for r in rows])

        total = df["Monto"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total del periodo", money(total))
        c2.metric("Nº de ventas", len(df))
        c3.metric("Promedio por venta", money(total / len(df) if len(df) else 0))

        df_display = df.copy()
        df_display["Monto"] = df_display["Monto"].apply(money)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("##### Por planta")
        por_planta = df.groupby("Planta")["Monto"].sum().reindex(PLANTAS).fillna(0)
        st.dataframe(por_planta.apply(money).rename("Total"), use_container_width=True)

        if auth.is_admin() or auth.is_vendedor():
            st.markdown("#### 🗑️ Eliminar un registro (corrección de captura)")
            opciones = {f"{r['fecha']} — {r['planta']} — {money(r['monto'])} — {r['linea_venta']}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona", ["—"] + list(opciones.keys()), key="vta_eliminar")
            if elegido != "—":
                vid = opciones[elegido]
                venta = next(r for r in rows if r["id"] == vid)
                if user["rol"] == "vendedor" and venta["vendedor_id"] != user["id"]:
                    st.warning("Esta venta pertenece a otro vendedor.")
                elif st.button("Eliminar registro seleccionado"):
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
            linea_venta = st.text_input("Línea de venta (producto/servicio)", placeholder="Ej. Volantes, Revistas, Empaques...")
            monto = st.number_input("Monto de la venta (Q)", min_value=0.0, step=50.0)
            notas = st.text_area("Notas (opcional)")

            if st.form_submit_button("Registrar venta", use_container_width=True):
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                elif not linea_venta.strip():
                    st.error("Ingresa la línea de venta.")
                else:
                    db.create_venta(vendedor_id, fecha, planta, linea_venta.strip(), monto, notas)
                    st.success(f"Venta de {money(monto)} registrada en planta {planta}.")
                    st.rerun()
