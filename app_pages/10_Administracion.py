from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PROSPECTO
from utils import download_excel_button, sidebar_user_box

_MESES_ABREV_GEN = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
}


def _mes_label_gen(anio_mes):
    """'2026-09' -> 'Sep 2026'; vacío o formato raro -> 'Sin fecha'."""
    if not anio_mes or "-" not in anio_mes:
        return "Sin fecha"
    anio, mes = anio_mes.split("-")
    return f"{_MESES_ABREV_GEN.get(mes, mes)} {anio}"


user = auth.current_user()
sidebar_user_box()

st.title("🌐 Prospectos generales (todos los vendedores)")
st.caption("Vista de solo lectura: la lista completa de prospectos de todo el equipo, para visibilidad general.")

rows_todos = db.list_prospectos()

# ---------------------------------------------------------------------------
# KPIs mensuales: cada prospecto se cuenta en el mes en que se REGISTRÓ (no
# en el mes en que cambió de estado después) — mismo criterio que ya usa la
# pestaña 'KPIs' para "Clientes cerrados".
# ---------------------------------------------------------------------------
st.markdown("### 📊 KPIs mensuales")

if not rows_todos:
    st.info("Todavía no hay prospectos registrados para calcular KPIs.")
else:
    df_kpi = pd.DataFrame([{
        "estado": r["estado"],
        "Mes": (r.get("fecha_registro") or "")[:7] if len(r.get("fecha_registro") or "") >= 7 else "",
    } for r in rows_todos])

    mes_sel = st.date_input(
        "Mes a consultar (elige cualquier día de ese mes)", value=date.today(), key="prosp_gen_kpi_mes",
    )
    anio_mes_sel = mes_sel.strftime("%Y-%m")
    st.markdown(f"##### {_mes_label_gen(anio_mes_sel)}")

    df_mes_sel = df_kpi[df_kpi["Mes"] == anio_mes_sel]
    nuevos_mes = len(df_mes_sel)
    ganados_mes = int((df_mes_sel["estado"] == "Cliente (Ganado)").sum())
    perdidos_mes = int((df_mes_sel["estado"] == "Perdido").sum())
    tasa_mes = (ganados_mes / nuevos_mes * 100) if nuevos_mes else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🧾 Prospectos nuevos", nuevos_mes)
    k2.metric("✅ Convertidos a cliente", ganados_mes)
    k3.metric("❌ Perdidos", perdidos_mes)
    k4.metric("📈 Tasa de conversión", f"{tasa_mes:.0f}%" if tasa_mes is not None else "—")
    st.caption(
        "Los KPIs cuentan a cada prospecto en el mes en que se registró, sin importar cuándo cambió de "
        "estado después (mismo criterio que la pestaña 'KPIs')."
    )

    st.markdown("##### 📈 Tendencia mes a mes")
    tabla_tendencia = df_kpi.groupby("Mes")["estado"].value_counts().unstack(fill_value=0)
    for est in ESTADOS_PROSPECTO:
        if est not in tabla_tendencia.columns:
            tabla_tendencia[est] = 0
    tabla_tendencia = tabla_tendencia[ESTADOS_PROSPECTO]
    tabla_tendencia["Total"] = tabla_tendencia.sum(axis=1)
    tabla_tendencia["Tasa de conversión"] = tabla_tendencia.apply(
        lambda f: f"{(f['Cliente (Ganado)'] / f['Total'] * 100):.0f}%" if f["Total"] else "—", axis=1,
    )
    tabla_tendencia = tabla_tendencia.sort_index()
    tabla_tendencia.index = [_mes_label_gen(m) for m in tabla_tendencia.index]
    st.dataframe(tabla_tendencia.rename_axis("Mes").reset_index(), use_container_width=True, hide_index=True)

st.divider()

filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_PROSPECTO, default=[])

rows = rows_todos
if filtro_estado:
    rows = [r for r in rows if r["estado"] in filtro_estado]

if not rows:
    st.info(
        "No hay prospectos registrados todavía." if not rows_todos
        else "Ningún prospecto coincide con este filtro."
    )
else:
    vendedores = db.list_usuarios()
    df = pd.DataFrame([{
        "Cliente": r["nombre_cliente"],
        "NIT": r["nit"],
        "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
        "Estado": r["estado"],
        "Registrado": r["fecha_registro"],
        "Próximo seguimiento": r["fecha_seguimiento"],
    } for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)
    download_excel_button(df, "prospectos_generales.xlsx", key="generales_descargar_excel")

    st.markdown("##### Resumen por estado")
    resumen = df["Estado"].value_counts().reindex(ESTADOS_PROSPECTO).fillna(0).astype(int)
    st.dataframe(resumen.rename("Cantidad"), use_container_width=True)

st.caption("Esta pestaña es solo de visibilidad: para editar un prospecto, ve a 'Prospección (CRM)'.")
