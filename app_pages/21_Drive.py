import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import database as db
from config import (
    CATEGORICAL, DG_ANIOS_GRAFICA, DG_CATEGORIA_LABEL, DG_CATEGORIAS, DG_ENTIDAD_LABEL, DG_ENTIDADES,
    DG_MESES, KRISPY_ANIO_ASUMIDO, KRISPY_METRICA_LABEL, KRISPY_METRICAS, KRISPY_PRODUCTO_LABEL,
    KRISPY_PRODUCTOS, KRISPY_TIENDA_LABEL, KRISPY_TIENDAS,
)
from utils import base_layout, money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_drive()

st.title("📁 Drive")
st.caption(
    "Los números que antes se llevaban en un Google Sheet aparte, ahora directamente en la "
    "plataforma: **Datos generales** (ventas totales, por línea, flujo y ticket promedio) y "
    "**Krispy 2**. Esta pestaña es independiente de 'Ventas por mes' — no se calcula de ahí, "
    + ("se digita y se guarda aquí." if puede_editar else "la digita y actualiza el administrador.")
)

MESES_LABEL = {m: m.capitalize() for m in DG_MESES}


def _fila_total(valores: dict) -> float:
    return sum(float(v or 0) for v in valores.values())


tab_generales, tab_krispy = st.tabs(["📊 Datos generales", "🍩 Krispy 2"])

# =============================================================================
# Datos generales
# =============================================================================
with tab_generales:
    col_cat, col_ent = st.columns(2)
    categoria = col_cat.selectbox(
        "Categoría", DG_CATEGORIAS, format_func=lambda c: DG_CATEGORIA_LABEL.get(c, c), key="drive_dg_categoria",
    )
    entidades_disponibles = DG_ENTIDADES.get(categoria, [])
    if len(entidades_disponibles) > 1:
        entidad = col_ent.selectbox(
            "Tienda / línea", entidades_disponibles,
            format_func=lambda e: DG_ENTIDAD_LABEL.get(e, e), key="drive_dg_entidad",
        )
    else:
        entidad = entidades_disponibles[0] if entidades_disponibles else None
        col_ent.markdown("&nbsp;")
        col_ent.caption(f"({DG_ENTIDAD_LABEL.get(entidad, entidad)})")

    registros = db.get_dg_datos(categoria, entidad) if entidad else []
    es_dinero = categoria in ("ventas_totales", "por_linea", "ticket_promedio")

    st.markdown("###### Tabla")
    if not registros:
        st.info("Todavía no hay datos guardados para esta selección.")
    else:
        filas = []
        for r in registros:
            fila = {"Año": int(r["anio"]), "Tipo": "🎯 Meta" if r.get("meta") else "Real"}
            valores = r.get("valores") or {}
            for m in DG_MESES:
                v = valores.get(m)
                fila[MESES_LABEL[m]] = (money(v) if es_dinero else f"{float(v):,.0f}") if v is not None else "—"
            fila["Total"] = money(_fila_total(valores)) if es_dinero else f"{_fila_total(valores):,.0f}"
            filas.append(fila)
        df_tabla = pd.DataFrame(filas)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

    st.markdown("###### Gráfica (2024 – 2026)")
    registros_grafica = [r for r in registros if int(r["anio"]) in DG_ANIOS_GRAFICA]
    if not registros_grafica:
        st.info("No hay datos de 2024, 2025 o 2026 para mostrar en la gráfica.")
    else:
        color_por_anio = {anio: CATEGORICAL[i % len(CATEGORICAL)] for i, anio in enumerate(DG_ANIOS_GRAFICA)}
        fig = go.Figure()
        for r in registros_grafica:
            anio = int(r["anio"])
            valores = r.get("valores") or {}
            meses_presentes = [m for m in DG_MESES if valores.get(m) is not None]
            if not meses_presentes:
                continue
            es_meta = bool(r.get("meta"))
            fig.add_trace(go.Scatter(
                x=[MESES_LABEL[m] for m in meses_presentes],
                y=[valores[m] for m in meses_presentes],
                mode="lines+markers",
                name=f"{anio}" + (" (meta)" if es_meta else ""),
                line=dict(color=color_por_anio[anio], dash="dot" if es_meta else "solid"),
            ))
        st.plotly_chart(
            base_layout(fig, title=f"{DG_CATEGORIA_LABEL.get(categoria, categoria)} — {DG_ENTIDAD_LABEL.get(entidad, entidad)}", height=380),
            use_container_width=True,
        )

    if puede_editar and entidad:
        st.divider()
        st.markdown("###### ✏️ Agregar o corregir un año")
        col_anio, col_meta = st.columns(2)
        anio_edit = col_anio.number_input(
            "Año", min_value=2015, max_value=2035, value=2026, step=1, key="drive_dg_anio_edit",
        )
        meta_edit = col_meta.checkbox("Es meta (objetivo), no dato real", key="drive_dg_meta_edit")

        registro_actual = next(
            (r for r in registros if int(r["anio"]) == int(anio_edit) and bool(r.get("meta")) == meta_edit), None,
        )
        valores_actuales = (registro_actual or {}).get("valores") or {}

        with st.form("drive_dg_form"):
            nuevos_valores = {}
            cols = st.columns(4)
            for i, m in enumerate(DG_MESES):
                nuevos_valores[m] = cols[i % 4].number_input(
                    MESES_LABEL[m], min_value=0.0, step=100.0,
                    value=float(valores_actuales.get(m, 0) or 0),
                    key=f"drive_dg_input_{m}_{anio_edit}_{meta_edit}",
                )
            if st.form_submit_button("💾 Guardar", use_container_width=True):
                db.upsert_dg_dato(categoria, entidad, int(anio_edit), meta_edit, nuevos_valores)
                st.success(f"{DG_CATEGORIA_LABEL.get(categoria, categoria)} de {DG_ENTIDAD_LABEL.get(entidad, entidad)} — {int(anio_edit)} actualizado.")
                st.rerun()

# =============================================================================
# Krispy 2
# =============================================================================
with tab_krispy:
    st.caption(
        f"El archivo original no tenía columna de año — los datos cargados se guardaron asumiendo "
        f"que son de **{KRISPY_ANIO_ASUMIDO}**. Si no es correcto, se puede corregir abajo, mes por mes."
    )
    col_anio_k, col_tienda_k, col_metrica_k = st.columns(3)
    anios_existentes = sorted({int(r["anio"]) for r in db.get_krispy_datos()}) or [KRISPY_ANIO_ASUMIDO]
    if KRISPY_ANIO_ASUMIDO not in anios_existentes:
        anios_existentes = sorted(set(anios_existentes) | {KRISPY_ANIO_ASUMIDO})
    anio_k = col_anio_k.selectbox("Año", anios_existentes, index=anios_existentes.index(KRISPY_ANIO_ASUMIDO), key="drive_kr_anio")
    tienda_k = col_tienda_k.selectbox(
        "Tienda", KRISPY_TIENDAS, format_func=lambda t: KRISPY_TIENDA_LABEL.get(t, t), key="drive_kr_tienda",
    )
    metrica_k = col_metrica_k.selectbox(
        "Métrica", KRISPY_METRICAS, format_func=lambda m: KRISPY_METRICA_LABEL.get(m, m), key="drive_kr_metrica",
    )

    registros_k = db.get_krispy_datos(anio=anio_k, tienda=tienda_k)
    es_dinero_k = metrica_k in ("dinero", "utilidad")

    st.markdown("###### Tabla")
    if not registros_k:
        st.info("Todavía no hay datos guardados para esta tienda y año.")
    else:
        filas_k = []
        for r in registros_k:
            valores = r.get("valores") or {}
            v_bites = float(valores.get(f"{metrica_k}_bites", 0) or 0)
            v_mini = float(valores.get(f"{metrica_k}_mini", 0) or 0)
            fmt = money if es_dinero_k else (lambda v: f"{v:,.0f}")
            filas_k.append({
                "Mes": MESES_LABEL.get(r["mes"], r["mes"]),
                KRISPY_PRODUCTO_LABEL["bites"]: fmt(v_bites),
                KRISPY_PRODUCTO_LABEL["mini"]: fmt(v_mini),
                "Total": fmt(v_bites + v_mini),
            })
        st.dataframe(pd.DataFrame(filas_k), use_container_width=True, hide_index=True)

        st.markdown("###### Gráfica — Bites vs. Mini")
        meses_orden = [r["mes"] for r in registros_k]
        fig_k = go.Figure()
        for i, prod in enumerate(KRISPY_PRODUCTOS):
            y_vals = [float((r.get("valores") or {}).get(f"{metrica_k}_{prod}", 0) or 0) for r in registros_k]
            fig_k.add_trace(go.Bar(
                x=[MESES_LABEL.get(m, m) for m in meses_orden], y=y_vals,
                name=KRISPY_PRODUCTO_LABEL[prod], marker_color=CATEGORICAL[i % len(CATEGORICAL)],
            ))
        st.plotly_chart(
            base_layout(fig_k, title=f"{KRISPY_TIENDA_LABEL.get(tienda_k, tienda_k)} — {KRISPY_METRICA_LABEL.get(metrica_k, metrica_k)} ({anio_k})", height=380),
            use_container_width=True,
        )

    if puede_editar:
        st.divider()
        st.markdown("###### ✏️ Agregar o corregir un mes")
        col_t_edit, col_a_edit, col_m_edit = st.columns(3)
        tienda_edit = col_t_edit.selectbox(
            "Tienda", KRISPY_TIENDAS, format_func=lambda t: KRISPY_TIENDA_LABEL.get(t, t), key="drive_kr_tienda_edit",
        )
        anio_edit_k = col_a_edit.number_input(
            "Año", min_value=2015, max_value=2035, value=KRISPY_ANIO_ASUMIDO, step=1, key="drive_kr_anio_edit",
        )
        mes_edit = col_m_edit.selectbox("Mes", DG_MESES, format_func=lambda m: MESES_LABEL[m], key="drive_kr_mes_edit")

        registro_k_actual = next(
            (
                r for r in db.get_krispy_datos(anio=int(anio_edit_k), tienda=tienda_edit)
                if r["mes"] == mes_edit
            ),
            None,
        )
        valores_k_actuales = (registro_k_actual or {}).get("valores") or {}

        with st.form("drive_kr_form"):
            cols_k = st.columns(3)
            nuevos_valores_k = {}
            for i, metrica in enumerate(KRISPY_METRICAS):
                with cols_k[i]:
                    st.markdown(f"**{KRISPY_METRICA_LABEL[metrica]}**")
                    for prod in KRISPY_PRODUCTOS:
                        campo = f"{metrica}_{prod}"
                        nuevos_valores_k[campo] = st.number_input(
                            KRISPY_PRODUCTO_LABEL[prod], min_value=0.0, step=1.0,
                            value=float(valores_k_actuales.get(campo, 0) or 0),
                            key=f"drive_kr_input_{campo}_{tienda_edit}_{anio_edit_k}_{mes_edit}",
                        )
            if st.form_submit_button("💾 Guardar", use_container_width=True):
                db.upsert_krispy_dato(tienda_edit, int(anio_edit_k), mes_edit, nuevos_valores_k)
                st.success(f"Krispy 2 de {KRISPY_TIENDA_LABEL.get(tienda_edit, tienda_edit)} — {MESES_LABEL[mes_edit]} {int(anio_edit_k)} actualizado.")
                st.rerun()
