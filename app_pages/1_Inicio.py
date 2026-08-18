from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from utils import money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title(f"Hola, {user['nombre'].split()[0]} 👋")
st.caption(f"{date.today().strftime('%A %d de %B, %Y')} · Rol: {user['rol']}")

vendedor_id = user["id"] if user["rol"] == "vendedor" else None
hoy = date.today()

# --------------------------------------------------------------------------
# Tarjetas resumen
# --------------------------------------------------------------------------
citas_hoy = [c for c in db.list_citas(vendedor_id, desde=hoy, hasta=hoy) if c["estado"] == "Programada"]
seguimientos = db.prospectos_con_seguimiento_proximo(vendedor_id, dias=3)
ventas_hoy = db.list_ventas(vendedor_id, desde=hoy, hasta=hoy)
total_ventas_hoy = sum(v["monto"] or 0 for v in ventas_hoy)
reclamos_abiertos = [r for r in db.list_reclamos(vendedor_id) if r["estatus"] in ("Abierto", "En proceso")]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Citas/visitas de hoy", len(citas_hoy))
c2.metric("Seguimientos próximos (3 días)", len(seguimientos))
c3.metric("Venta registrada hoy", money(total_ventas_hoy))
c4.metric("Reclamos abiertos", len(reclamos_abiertos))

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("⏰ Recordatorios de seguimiento próximos")
    if not seguimientos:
        st.info("No hay seguimientos próximos en los siguientes 3 días.")
    else:
        vendedores = db.list_usuarios()
        rows = []
        for p in seguimientos:
            rows.append({
                "Cliente": p["nombre_cliente"],
                "NIT": p["nit"],
                "Fecha de seguimiento": p["fecha_seguimiento"],
                "Recordatorio": p["recordatorio"] or "—",
                **({"Vendedor": db.nombre_vendedor(p["vendedor_id"], vendedores)} if user["rol"] != "vendedor" else {}),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with col_b:
    st.subheader("📅 Agenda de hoy")
    citas_todas_hoy = db.list_citas(vendedor_id, desde=hoy, hasta=hoy)
    if not citas_todas_hoy:
        st.info("No hay citas, visitas o llamadas programadas para hoy.")
    else:
        vendedores = db.list_usuarios()
        rows = []
        for c in citas_todas_hoy:
            rows.append({
                "Hora": c["hora"] or "—",
                "Tipo": c["tipo"],
                "Cliente": c["cliente_nombre"],
                "Estado": c["estado"],
                **({"Vendedor": db.nombre_vendedor(c["vendedor_id"], vendedores)} if user["rol"] != "vendedor" else {}),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Usa el menú de la izquierda para navegar entre Prospección (CRM), Citas, Visitas de mercadeo, "
    "Cotizaciones, Reclamos, Venta del día y KPIs."
)
