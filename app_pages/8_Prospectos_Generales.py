import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PROSPECTO
from utils import download_excel_button, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🌐 Prospectos generales (todos los vendedores)")
st.caption("Vista de solo lectura: la lista completa de prospectos de todo el equipo, para visibilidad general.")

filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_PROSPECTO, default=[])

rows = db.list_prospectos()
if filtro_estado:
    rows = [r for r in rows if r["estado"] in filtro_estado]

if not rows:
    st.info("No hay prospectos registrados todavía.")
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
