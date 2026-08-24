from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import PLANTAS
from utils import money, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("📅 Ventas por mes")
st.caption(
    "Monto acumulado en el mes, por vendedor y por planta (Offset, Digital, Valloy, Colorado). "
    "Es un dato que digita el administrador: cada vez que se guarda, **reemplaza** el número "
    "anterior — no se suma. Esta pestaña es independiente de 'Venta del día', que sigue "
    "funcionando exactamente igual que antes."
)

mes_sel = st.date_input(
    "Mes a consultar (elige cualquier día de ese mes)", value=date.today(), key="vpm_mes",
)
anio_mes = mes_sel.strftime("%Y-%m")
st.markdown(f"##### {mes_sel.strftime('%B %Y').capitalize()}")

registros = db.get_ventas_mensuales_planta(anio_mes)
todos_los_vendedores = db.list_vendedores(solo_activos=False)
columnas_planta = [f"Venta {p}" for p in PLANTAS]

if user["rol"] == "admin":
    vendedores_tabla = [v for v in todos_los_vendedores if v["activo"]]
else:
    vendedor_id_propio = vendedor_filter_selector(key="vpm_filtro_vendedor")
    vendedores_tabla = (
        [v for v in todos_los_vendedores if v["id"] == vendedor_id_propio]
        if vendedor_id_propio else todos_los_vendedores
    )

if not vendedores_tabla:
    st.info("No hay vendedores para mostrar.")
else:
    filas = []
    for v in vendedores_tabla:
        montos = registros.get(v["id"], {}).get("montos", {})
        fila = {"Vendedor": v["nombre"]}
        for p in PLANTAS:
            fila[f"Venta {p}"] = float(montos.get(p, 0) or 0)
        filas.append(fila)
    df_display = pd.DataFrame(filas)
    df_display["Total"] = df_display[columnas_planta].sum(axis=1)
    for c in columnas_planta + ["Total"]:
        df_display[c] = df_display[c].apply(money)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

st.markdown("##### Totales del mes por planta (todos los vendedores)")
cols_tot = st.columns(len(PLANTAS))
for col, p in zip(cols_tot, PLANTAS):
    total_planta = sum(float((r.get("montos") or {}).get(p, 0) or 0) for r in registros.values())
    col.metric(p, money(total_planta))

if user["rol"] == "admin":
    st.divider()
    st.markdown("#### ✏️ Ingresar / actualizar venta mensual de un vendedor")
    vendedores_activos = [v for v in todos_los_vendedores if v["activo"]]
    if not vendedores_activos:
        st.info("No hay vendedores activos.")
    else:
        opciones_v = {v["nombre"]: v["id"] for v in vendedores_activos}
        vendedor_nombre_sel = st.selectbox(
            "Vendedor", list(opciones_v.keys()), key="vpm_vendedor_sel",
        )
        vendedor_id_sel = opciones_v[vendedor_nombre_sel]
        montos_actuales = registros.get(vendedor_id_sel, {}).get("montos", {})

        with st.form("vpm_form"):
            cols_input = st.columns(len(PLANTAS))
            valores = {}
            for col, p in zip(cols_input, PLANTAS):
                # La key incluye vendedor y mes para que, al cambiar de
                # vendedor o de mes, el campo muestre el valor correcto
                # (y no el que quedó escrito para otro vendedor/mes).
                valores[p] = col.number_input(
                    f"Venta {p} (Q)", min_value=0.0, step=100.0,
                    value=float(montos_actuales.get(p, 0) or 0),
                    key=f"vpm_input_{p}_{vendedor_id_sel}_{anio_mes}",
                )
            if st.form_submit_button("💾 Guardar venta mensual", use_container_width=True):
                db.upsert_venta_mensual_planta(vendedor_id_sel, anio_mes, valores)
                st.success(
                    f"Venta mensual de {vendedor_nombre_sel} actualizada para "
                    f"{mes_sel.strftime('%B %Y').capitalize()}."
                )
                st.rerun()
