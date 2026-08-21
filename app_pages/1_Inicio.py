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

inicio_mes = hoy.replace(day=1)
ventas_mes = db.list_ventas(vendedor_id, desde=inicio_mes, hasta=hoy)
total_ventas_mes = sum(v["monto"] or 0 for v in ventas_mes)
ordenes_mes = sum(v.get("numero_ordenes") or 0 for v in ventas_mes)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Citas/visitas de hoy", len(citas_hoy))
c2.metric("Seguimientos próximos (3 días)", len(seguimientos))
c3.metric("Venta registrada hoy", money(total_ventas_hoy))
c4.metric("Reclamos abiertos", len(reclamos_abiertos))
c5.metric(f"Venta del mes en curso ({hoy.strftime('%B')})", money(total_ventas_mes),
          help=f"{ordenes_mes} órdenes registradas en {hoy.strftime('%B')}.")

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

# --------------------------------------------------------------------------
# Diseño Gráfico — entregas próximas (para dar seguimiento rápido al
# diseñador). Cada vendedor ve solo lo suyo; admin y vista ven todo.
# --------------------------------------------------------------------------
st.subheader("🎨 Diseño Gráfico — entregas próximas")
manana = hoy + timedelta(days=1)
disenos_scope = db.list_disenos(vendedor_id)
disenos_pendientes = [
    d for d in disenos_scope
    if d.get("estado") != "Entregado" and d.get("fecha_necesaria") in (str(hoy), str(manana))
]
entregar_hoy = [d for d in disenos_pendientes if d.get("fecha_necesaria") == str(hoy)]
entregar_manana = [d for d in disenos_pendientes if d.get("fecha_necesaria") == str(manana)]

cd1, cd2 = st.columns(2)
cd1.metric("📦 Por entregar hoy", len(entregar_hoy))
cd2.metric("📦 Por entregar mañana", len(entregar_manana))

if not disenos_pendientes:
    st.info("No hay diseños por entregar hoy ni mañana.")
else:
    vendedores_d = db.list_usuarios()
    filas_d = []
    for d in sorted(disenos_pendientes, key=lambda x: x.get("fecha_necesaria") or ""):
        filas_d.append({
            "Cliente": d.get("cliente") or "—",
            "Producto": d.get("producto") or "—",
            "Fecha necesaria": d.get("fecha_necesaria"),
            "Estado": d.get("estado"),
            **({"Vendedor": db.nombre_vendedor(d["vendedor_id"], vendedores_d)} if user["rol"] != "vendedor" else {}),
        })
    st.dataframe(pd.DataFrame(filas_d), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Usa el menú de la izquierda para navegar entre Prospección (CRM), Citas, Visitas de mercadeo, "
    "Cotizaciones, Reclamos, Venta del día y KPIs."
)
