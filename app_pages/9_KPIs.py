from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import database as db
from config import CATEGORICAL, PLANTAS, STATUS, TIPOS_CITA
from utils import base_layout, money, sidebar_user_box

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

    fig = go.Figure()
    for i, tipo in enumerate(TIPOS_CITA):
        fig.add_trace(go.Bar(name=tipo, x=pivot.index, y=pivot[tipo], marker_color=CATEGORICAL[i]))
    fig.update_layout(barmode="group")
    st.plotly_chart(base_layout(fig, title="Actividades por vendedor y tipo"), use_container_width=True)

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
    top = df_cerrados["Vendedor"].value_counts().idxmax()
    m2.metric("Vendedor con más cierres", top)

    pivot2 = df_cerrados.pivot_table(index="Mes", columns="Vendedor", values="id", aggfunc="count", fill_value=0).sort_index()
    fig2 = go.Figure()
    for i, vend in enumerate(pivot2.columns):
        fig2.add_trace(go.Bar(name=vend, x=pivot2.index, y=pivot2[vend], marker_color=CATEGORICAL[i % len(CATEGORICAL)]))
    fig2.update_layout(barmode="stack")
    st.plotly_chart(base_layout(fig2, title="Clientes cerrados por mes y vendedor"), use_container_width=True)
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

ventas_rango = db.list_ventas(desde=desde, hasta=hasta)
df_v = pd.DataFrame(ventas_rango) if ventas_rango else pd.DataFrame(columns=["fecha", "planta", "monto", "vendedor_id"])
total_acumulado = df_v["monto"].sum() if not df_v.empty else 0

m1, m2, m3 = st.columns(3)
m1.metric("Venta de hoy", money(total_hoy))
m2.metric("Acumulado del periodo", money(total_acumulado))
m3.metric("Nº de transacciones", len(df_v))

if not df_v.empty:
    df_v["Fecha"] = pd.to_datetime(df_v["fecha"])
    diario = df_v.groupby("Fecha")["monto"].sum().sort_index()
    acumulado = diario.cumsum()

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=acumulado.index, y=acumulado.values, mode="lines",
                               line=dict(color=CATEGORICAL[0], width=2), fill="tozeroy", name="Acumulado"))
    st.plotly_chart(base_layout(fig3, title="Venta acumulada en el periodo"), use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        por_planta = df_v.groupby("planta")["monto"].sum().reindex(PLANTAS).fillna(0)
        fig4 = go.Figure(go.Bar(x=por_planta.index, y=por_planta.values,
                                 marker_color=CATEGORICAL[:len(PLANTAS)]))
        st.plotly_chart(base_layout(fig4, title="Venta por planta"), use_container_width=True)
    with col_b:
        df_v["Vendedor"] = df_v["vendedor_id"].map(vend_lookup).fillna("Sin asignar")
        por_vendedor = df_v.groupby("Vendedor")["monto"].sum().sort_values(ascending=True)
        fig5 = go.Figure(go.Bar(x=por_vendedor.values, y=por_vendedor.index, orientation="h",
                                 marker_color=CATEGORICAL[0]))
        st.plotly_chart(base_layout(fig5, title="Venta por vendedor"), use_container_width=True)
else:
    st.info("No hay ventas registradas en este rango.")

st.divider()

# ===========================================================================
# 5. Productos más vendidos (línea de venta)
# ===========================================================================
st.header("5 · Productos más vendidos")
st.caption("Basado en la 'Línea de venta' (producto) registrada en cada venta del periodo seleccionado.")

if df_v.empty:
    st.info("No hay ventas registradas en este rango para calcular productos más vendidos.")
else:
    por_producto = df_v.groupby("linea_venta").agg(
        Transacciones=("monto", "count"), Monto=("monto", "sum"),
    ).sort_values("Monto", ascending=False)

    m1, m2 = st.columns(2)
    m1.metric("Producto con más ingresos (Q)", por_producto.index[0])
    top_cantidad = por_producto.sort_values("Transacciones", ascending=False).index[0]
    m2.metric("Producto más vendido (Nº de ventas)", top_cantidad)

    top10 = por_producto.head(10).sort_values("Monto", ascending=True)
    fig6 = go.Figure(go.Bar(x=top10["Monto"], y=top10.index, orientation="h", marker_color=CATEGORICAL[2]))
    st.plotly_chart(
        base_layout(fig6, title="Top 10 productos por monto vendido (Q)", height=max(320, 32 * len(top10) + 120)),
        use_container_width=True,
    )

    tabla_productos = por_producto.copy()
    tabla_productos["Monto"] = tabla_productos["Monto"].apply(money)
    st.dataframe(
        tabla_productos.rename_axis("Producto").reset_index(),
        use_container_width=True, hide_index=True,
    )
