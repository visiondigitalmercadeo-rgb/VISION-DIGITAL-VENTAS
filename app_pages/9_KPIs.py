from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import PLANTAS, TIPOS_CITA
from utils import as_lineas_venta, money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("📊 KPIs")
st.caption("Indicadores clave: actividad comercial, cierres, visitas de mercadeo y ventas.")

c1, c2 = st.columns(2)
desde = c1.date_input("Desde", value=date.today().replace(day=1), key="kpi_desde")
hasta = c2.date_input("Hasta", value=date.today(), key="kpi_hasta")

vendedores_all = db.list_vendedores(solo_activos=False)
vend_lookup = {v["id"]: v["nombre"] for v in vendedores_all}

# ===========================================================================
# 1. Número de citas, visitas y llamadas — total y por vendedor
# ===========================================================================
st.header("1 · Citas, visitas y llamadas")

citas = [c for c in db.list_citas(desde=desde, hasta=hasta)]
df_citas = pd.DataFrame(citas) if citas else pd.DataFrame(columns=["tipo", "vendedor_id", "estado"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total actividades", len(df_citas))
for i, tipo in enumerate(TIPOS_CITA):
    [m2, m3, m4][i].metric(f"{tipo}s", int((df_citas["tipo"] == tipo).sum()) if not df_citas.empty else 0)

if df_citas.empty:
    st.info("No hay citas/visitas/llamadas registradas en este rango.")
else:
    df_citas["Vendedor"] = df_citas["vendedor_id"].map(vend_lookup).fillna("Sin asignar")
    pivot = df_citas.pivot_table(index="Vendedor", columns="tipo", values="id", aggfunc="count", fill_value=0)
    pivot = pivot.reindex(columns=TIPOS_CITA, fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False)
    st.markdown("##### Actividades por vendedor y tipo")
    st.dataframe(pivot.rename_axis("Vendedor").reset_index(), use_container_width=True, hide_index=True)

st.divider()

# ===========================================================================
# 2. Clientes cerrados — total y por vendedor por mes
# ===========================================================================
st.header("2 · Clientes cerrados (ganados)")
st.caption("Se calcula sobre prospectos con estado 'Cliente (Ganado)', agrupados por mes de registro.")

prospectos = db.list_prospectos()
df_p = pd.DataFrame(prospectos) if prospectos else pd.DataFrame(columns=["estado", "vendedor_id", "fecha_registro"])
df_cerrados = df_p[df_p["estado"] == "Cliente (Ganado)"].copy() if not df_p.empty else df_p

m1, m2 = st.columns(2)
m1.metric("Total clientes cerrados", len(df_cerrados))
if not df_cerrados.empty:
    df_cerrados["Vendedor"] = df_cerrados["vendedor_id"].map(vend_lookup).fillna("Sin asignar")
    df_cerrados["Mes"] = pd.to_datetime(df_cerrados["fecha_registro"]).dt.strftime("%Y-%m")
    ranking_cierres = (
        df_cerrados["Vendedor"].value_counts().rename_axis("Vendedor").reset_index(name="Nº de cierres")
    )
    m2.metric("Vendedor con más cierres", ranking_cierres.iloc[0]["Vendedor"])

    st.markdown("##### Cierres por vendedor")
    st.dataframe(ranking_cierres, use_container_width=True, hide_index=True)

    st.markdown("##### Cierres por mes y vendedor")
    pivot2 = df_cerrados.pivot_table(
        index="Mes", columns="Vendedor", values="id", aggfunc="count", fill_value=0
    ).sort_index()
    st.dataframe(pivot2.rename_axis("Mes").reset_index(), use_container_width=True, hide_index=True)
else:
    st.info("Todavía no hay clientes marcados como 'Cliente (Ganado)'.")

st.divider()

# ===========================================================================
# 3. Visitas de mercadeo — checklist y pendientes
# ===========================================================================
st.header("3 · Visitas de mercadeo")

visitas = db.list_visitas_mercadeo()
visitas_rango = [v for v in visitas if desde.isoformat() <= v["fecha"] <= hasta.isoformat()]

total_items = sum(len(v["checklist_items"]) for v in visitas_rango)
items_ok = sum(sum(1 for i in v["checklist_items"] if i.get("ok")) for v in visitas_rango)
pct = (items_ok / total_items * 100) if total_items else 0
realizadas = sum(1 for v in visitas_rango if v["estado"] == "Realizada")
pendientes_count = sum(1 for v in visitas_rango if v["estado"] == "Pendiente")

m1, m2, m3 = st.columns(3)
m1.metric("Visitas en el periodo", len(visitas_rango))
m2.metric("Realizadas / Pendientes", f"{realizadas} / {pendientes_count}")
m3.metric("Checklist completado", f"{pct:.0f}%")

pendientes_texto = [(v["fecha"], v["punto_venta"], v["pendientes"]) for v in visitas_rango if v["pendientes"]]
if pendientes_texto:
    st.markdown("**Pendientes reportados:**")
    st.dataframe(
        pd.DataFrame(pendientes_texto, columns=["Fecha", "Punto de venta", "Pendiente"]),
        use_container_width=True, hide_index=True,
    )
else:
    st.caption("Sin pendientes reportados en el periodo.")

st.divider()

# ===========================================================================
# 4. Venta del día y acumulado
# ===========================================================================
st.header("4 · Venta del día y acumulado")

ventas_hoy = db.list_ventas(desde=date.today(), hasta=date.today())
total_hoy = sum(v["monto"] or 0 for v in ventas_hoy)
ordenes_hoy = sum(v.get("numero_ordenes") or 0 for v in ventas_hoy)

ventas_rango = db.list_ventas(desde=desde, hasta=hasta)
df_v = pd.DataFrame(ventas_rango) if ventas_rango else pd.DataFrame(
    columns=["fecha", "planta", "monto", "vendedor_id", "cliente", "numero_ordenes"]
)
if not df_v.empty and "numero_ordenes" not in df_v.columns:
    df_v["numero_ordenes"] = 0
if not df_v.empty:
    df_v["numero_ordenes"] = df_v["numero_ordenes"].fillna(0)
total_acumulado = df_v["monto"].sum() if not df_v.empty else 0
total_ordenes_periodo = int(df_v["numero_ordenes"].sum()) if not df_v.empty else 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Venta de hoy", money(total_hoy))
m2.metric("Órdenes de hoy", int(ordenes_hoy))
m3.metric("Acumulado del periodo", money(total_acumulado))
m4.metric("Nº de transacciones", len(df_v))
m5.metric("Órdenes del periodo", total_ordenes_periodo)

if not df_v.empty:
    df_v["Fecha"] = pd.to_datetime(df_v["fecha"])

    st.markdown("##### Venta y acumulado por día")
    diario = df_v.groupby("Fecha").agg(Venta=("monto", "sum"), Ordenes=("numero_ordenes", "sum")).sort_index()
    diario["Acumulado"] = diario["Venta"].cumsum()
    tabla_diaria = diario.copy()
    tabla_diaria.index = tabla_diaria.index.strftime("%Y-%m-%d")
    tabla_diaria["Venta"] = tabla_diaria["Venta"].apply(money)
    tabla_diaria["Acumulado"] = tabla_diaria["Acumulado"].apply(money)
    tabla_diaria["Ordenes"] = tabla_diaria["Ordenes"].astype(int)
    tabla_diaria = tabla_diaria.rename(columns={"Ordenes": "Nº de órdenes"})
    st.dataframe(tabla_diaria.rename_axis("Fecha").reset_index(), use_container_width=True, hide_index=True)

    st.markdown("##### Venta por planta")
    por_planta = df_v.groupby("planta")["monto"].sum().reindex(PLANTAS).fillna(0)
    cols_planta = st.columns(len(PLANTAS))
    for col, p in zip(cols_planta, PLANTAS):
        col.metric(p, money(por_planta.get(p, 0)))

    st.markdown("##### Venta por vendedor")
    df_v["Vendedor"] = df_v["vendedor_id"].map(vend_lookup).fillna("Sin asignar")
    por_vendedor = df_v.groupby("Vendedor").agg(
        Monto=("monto", "sum"), Ordenes=("numero_ordenes", "sum"), Transacciones=("monto", "count"),
    ).sort_values("Monto", ascending=False)
    tabla_vend = por_vendedor.copy()
    tabla_vend["Monto"] = tabla_vend["Monto"].apply(money)
    tabla_vend["Ordenes"] = tabla_vend["Ordenes"].astype(int)
    tabla_vend = tabla_vend.rename(columns={"Ordenes": "Nº de órdenes", "Transacciones": "Nº de ventas"})
    st.dataframe(tabla_vend.rename_axis("Vendedor").reset_index(), use_container_width=True, hide_index=True)

    st.markdown("##### Órdenes por mes")
    df_v["Mes"] = df_v["Fecha"].dt.strftime("%Y-%m")
    ordenes_mes = df_v.groupby("Mes")["numero_ordenes"].sum().sort_index()
    st.dataframe(ordenes_mes.rename("Nº de órdenes").astype(int), use_container_width=True)
else:
    st.info("No hay ventas registradas en este rango.")

st.divider()

# ===========================================================================
# 5. Productos más vendidos (línea de venta)
# ===========================================================================
st.header("5 · Productos más vendidos")
st.caption(
    "Basado en la 'Línea de venta' (producto) registrada en cada venta del periodo seleccionado. "
    "Una venta puede incluir varios productos; en ese caso el monto se contabiliza en cada producto elegido."
)

if df_v.empty:
    st.info("No hay ventas registradas en este rango para calcular productos más vendidos.")
else:
    df_v_prod = df_v.copy()
    df_v_prod["linea_venta"] = df_v_prod["linea_venta"].apply(as_lineas_venta)
    df_v_prod = df_v_prod.explode("linea_venta")
    df_v_prod = df_v_prod[df_v_prod["linea_venta"].notna() & (df_v_prod["linea_venta"] != "")]

    if df_v_prod.empty:
        st.info("No hay líneas de venta registradas en este rango para calcular productos más vendidos.")
        st.stop()

    por_producto = df_v_prod.groupby("linea_venta").agg(
        Transacciones=("monto", "count"), Monto=("monto", "sum"),
    ).sort_values("Monto", ascending=False)

    m1, m2 = st.columns(2)
    m1.metric("Producto con más ingresos (Q)", por_producto.index[0])
    top_cantidad = por_producto.sort_values("Transacciones", ascending=False).index[0]
    m2.metric("Producto más vendido (Nº de ventas)", top_cantidad)

    st.markdown("##### Ranking de productos por monto vendido")
    tabla_productos = por_producto.copy()
    tabla_productos["Monto"] = tabla_productos["Monto"].apply(money)
    tabla_productos = tabla_productos.rename_axis("Producto").reset_index()
    tabla_productos.insert(0, "#", range(1, len(tabla_productos) + 1))
    st.dataframe(tabla_productos, use_container_width=True, hide_index=True)
