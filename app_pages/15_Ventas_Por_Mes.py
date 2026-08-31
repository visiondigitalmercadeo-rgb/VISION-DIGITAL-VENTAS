from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import database as db
from config import CATEGORICAL, DG_MESES, HISTORIAL_CATEGORIA_LABEL, HISTORIAL_CATEGORIAS, PLANTAS
from utils import base_layout, money, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("📅 Ventas por mes")
st.caption(
    "Monto acumulado en el mes, por vendedor y por planta (Offset, Digital, Valloy, Colorado). "
    "Es un dato que digita el administrador: cada vez que se guarda, **reemplaza** el número "
    "anterior — no se suma. Esta pestaña es independiente de 'Venta del día', que sigue "
    "funcionando exactamente igual que antes."
)

# Resaltado en magenta leve — mismo color en todas las tablas de esta
# página (Ventas, Utilidades e Historial), para la columna/fila "Total".
MAGENTA_LEVE = "#fbe3f2"
MESES_LABEL = {m: m.capitalize() for m in DG_MESES}

mes_sel = st.date_input(
    "Mes a consultar (elige cualquier día de ese mes)", value=date.today(), key="vpm_mes",
)
anio_mes = mes_sel.strftime("%Y-%m")
st.markdown(f"##### {mes_sel.strftime('%B %Y').capitalize()}")

todos_los_vendedores = db.list_vendedores(solo_activos=False)


def _render_seccion(prefijo_columna, registros, key_prefix, upsert_fn, texto_boton, texto_exito):
    """Dibuja una sección completa (totales por planta, desglose por vendedor
    y formulario de captura para el admin) — misma estructura para Ventas y
    para Utilidades, solo cambia de dónde vienen y a dónde se guardan los
    datos. Se llama una vez por pestaña."""
    columnas_planta = [f"{prefijo_columna} {p}" for p in PLANTAS]

    st.markdown("###### Totales del mes por planta (todos los vendedores)")
    totales_planta = {
        p: sum(float((r.get("montos") or {}).get(p, 0) or 0) for r in registros.values())
        for p in PLANTAS
    }
    total_general = sum(totales_planta.values())

    # Dos líneas de KPIs (pedido explícito de Steven): arriba el total
    # general + Offset y Digital; abajo Valloy y Colorado. Asume el orden de
    # config.PLANTAS = ["Offset", "Digital", "Valloy", "Colorado"].
    fila1 = st.columns(3)
    fila1[0].metric(f"{prefijo_columna} total", money(total_general))
    fila1[1].metric(PLANTAS[0], money(totales_planta[PLANTAS[0]]))
    fila1[2].metric(PLANTAS[1], money(totales_planta[PLANTAS[1]]))

    fila2 = st.columns(2)
    fila2[0].metric(PLANTAS[2], money(totales_planta[PLANTAS[2]]))
    fila2[1].metric(PLANTAS[3], money(totales_planta[PLANTAS[3]]))

    st.divider()

    if user["rol"] == "admin":
        vendedores_tabla = [v for v in todos_los_vendedores if v["activo"]]
    else:
        vendedor_id_propio = vendedor_filter_selector(key=f"{key_prefix}_filtro_vendedor")
        vendedores_tabla = (
            [v for v in todos_los_vendedores if v["id"] == vendedor_id_propio]
            if vendedor_id_propio else todos_los_vendedores
        )

    if not vendedores_tabla:
        st.info("No hay vendedores para mostrar.")
    else:
        st.markdown("###### Desglose por vendedor")
        filas = []
        for v in vendedores_tabla:
            montos = registros.get(v["id"], {}).get("montos", {})
            fila = {"Vendedor": v["nombre"]}
            for p in PLANTAS:
                fila[f"{prefijo_columna} {p}"] = float(montos.get(p, 0) or 0)
            filas.append(fila)
        df_display = pd.DataFrame(filas)
        df_display["Total"] = df_display[columnas_planta].sum(axis=1)

        # Fila de totales por columna, al final de la tabla.
        fila_total = {"Vendedor": "Total"}
        for c in columnas_planta:
            fila_total[c] = df_display[c].sum()
        fila_total["Total"] = df_display["Total"].sum()
        df_display = pd.concat([df_display, pd.DataFrame([fila_total])], ignore_index=True)

        for c in columnas_planta + ["Total"]:
            df_display[c] = df_display[c].apply(money)

        # Resaltado en magenta leve: la columna "Total" (a la derecha, por
        # fila) y la fila "Total" (al final, por columna).
        styler = df_display.style.set_properties(subset=["Total"], **{"background-color": MAGENTA_LEVE})
        styler = styler.set_properties(
            subset=pd.IndexSlice[df_display.index[-1], :],
            **{"background-color": MAGENTA_LEVE, "font-weight": "bold"},
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)

    if user["rol"] == "admin":
        st.divider()
        st.markdown(f"###### ✏️ {texto_boton.replace('💾 ', '')}")
        vendedores_activos = [v for v in todos_los_vendedores if v["activo"]]
        if not vendedores_activos:
            st.info("No hay vendedores activos.")
        else:
            opciones_v = {v["nombre"]: v["id"] for v in vendedores_activos}
            vendedor_nombre_sel = st.selectbox(
                "Vendedor", list(opciones_v.keys()), key=f"{key_prefix}_vendedor_sel",
            )
            vendedor_id_sel = opciones_v[vendedor_nombre_sel]
            montos_actuales = registros.get(vendedor_id_sel, {}).get("montos", {})

            with st.form(f"{key_prefix}_form"):
                cols_input = st.columns(len(PLANTAS))
                valores = {}
                for col, p in zip(cols_input, PLANTAS):
                    # La key incluye vendedor y mes para que, al cambiar de
                    # vendedor o de mes, el campo muestre el valor correcto
                    # (y no el que quedó escrito para otro vendedor/mes).
                    valores[p] = col.number_input(
                        f"{prefijo_columna} {p} (Q)", min_value=0.0, step=100.0,
                        value=float(montos_actuales.get(p, 0) or 0),
                        key=f"{key_prefix}_input_{p}_{vendedor_id_sel}_{anio_mes}",
                    )
                if st.form_submit_button(texto_boton, use_container_width=True):
                    upsert_fn(vendedor_id_sel, anio_mes, valores)
                    st.success(f"{texto_exito} de {vendedor_nombre_sel} actualizada para "
                               f"{mes_sel.strftime('%B %Y').capitalize()}.")
                    st.rerun()


def _render_historial():
    """Pestaña 'Historial': serie histórica año por año, mes por mes, de la
    Venta total o la Utilidad total de la empresa (viene del Excel aparte
    que llevaba Steven) — tabla numérica con el mismo formato de totales en
    magenta que Ventas/Utilidades, gráfica abajo, y editable por el admin."""
    st.caption(
        "Serie histórica de Venta y Utilidad totales de la empresa, año por año — el dato que antes "
        "se llevaba en un Excel aparte. Es independiente de las pestañas 'Ventas' y 'Utilidades' de "
        "arriba (esas son el detalle del mes elegido por vendedor/planta; esto es el histórico "
        "mensual completo, mes a mes y año a año)."
    )

    # Corrección puntual (una sola vez por sesión, no borra nada si ya está
    # bien): la meta solo aplica a 2026 — los años anteriores no deben tener
    # fila de meta propia.
    if user["rol"] == "admin" and not st.session_state.get("_vpm_hist_limpieza_meta_hecha"):
        _borrados_meta = db.limpiar_historial_metas_fuera_de_2026()
        st.session_state["_vpm_hist_limpieza_meta_hecha"] = True
        if _borrados_meta:
            st.success(f"🧹 Se quitaron {_borrados_meta} fila(s) de meta que no correspondían (solo 2026 lleva meta).")

    categoria_hist = st.selectbox(
        "Categoría", HISTORIAL_CATEGORIAS, format_func=lambda c: HISTORIAL_CATEGORIA_LABEL.get(c, c),
        key="vpm_hist_categoria",
    )
    registros = db.get_historial_datos(categoria_hist)
    anios_disponibles = sorted({int(r["anio"]) for r in registros})

    st.markdown("###### Tabla")
    if not registros:
        st.info("Todavía no hay datos de historial guardados para esta categoría.")
    else:
        filas = []
        for r in sorted(registros, key=lambda r: (int(r["anio"]), bool(r.get("meta")))):
            valores = r.get("valores") or {}
            # "Año" como texto (no número) para que la columna no mezcle
            # tipos con la fila "Total" de más abajo (evita una advertencia
            # de Streamlit al convertir la tabla).
            fila = {"Año": str(int(r["anio"])), "Tipo": "🎯 Meta" if r.get("meta") else "Real"}
            for m in DG_MESES:
                v = valores.get(m)
                fila[MESES_LABEL[m]] = money(v) if v is not None else "—"
            fila["Total"] = money(sum(float(v or 0) for v in valores.values()))
            filas.append(fila)
        df_hist = pd.DataFrame(filas)

        # Fila de totales al final, sumando solo los años "Real" (no mezcla
        # las filas de meta) — mismo formato que Ventas/Utilidades arriba.
        suma_meses = {m: 0.0 for m in DG_MESES}
        for r in registros:
            if r.get("meta"):
                continue
            valores = r.get("valores") or {}
            for m in DG_MESES:
                suma_meses[m] += float(valores.get(m, 0) or 0)
        fila_total = {"Año": "Total", "Tipo": ""}
        for m in DG_MESES:
            fila_total[MESES_LABEL[m]] = money(suma_meses[m])
        fila_total["Total"] = money(sum(suma_meses.values()))
        df_hist = pd.concat([df_hist, pd.DataFrame([fila_total])], ignore_index=True)

        styler = df_hist.style.set_properties(subset=["Total"], **{"background-color": MAGENTA_LEVE})
        styler = styler.set_properties(
            subset=pd.IndexSlice[df_hist.index[-1], :],
            **{"background-color": MAGENTA_LEVE, "font-weight": "bold"},
        )
        st.dataframe(styler, use_container_width=True, hide_index=True)

    st.markdown("###### Gráfica")
    registros_grafica = [r for r in registros if (r.get("valores") or {})]
    if not registros_grafica:
        st.info("No hay datos para mostrar en la gráfica todavía.")
    else:
        anios_orden = sorted(anios_disponibles)
        color_por_anio = {a: CATEGORICAL[i % len(CATEGORICAL)] for i, a in enumerate(anios_orden)}
        fig = go.Figure()
        for r in sorted(registros_grafica, key=lambda r: (int(r["anio"]), bool(r.get("meta")))):
            anio = int(r["anio"])
            valores = r.get("valores") or {}
            meses_presentes = [m for m in DG_MESES if valores.get(m) is not None]
            if not meses_presentes:
                continue
            es_meta = bool(r.get("meta"))
            nombre = f"{anio}" + (" (meta)" if es_meta else "")
            fig.add_trace(go.Scatter(
                x=[MESES_LABEL[m] for m in meses_presentes],
                y=[valores[m] for m in meses_presentes],
                mode="lines+markers",
                name=nombre,
                line=dict(color=color_por_anio.get(anio, CATEGORICAL[0]), dash="dot" if es_meta else "solid"),
            ))
        st.plotly_chart(
            base_layout(fig, title=f"{HISTORIAL_CATEGORIA_LABEL.get(categoria_hist, categoria_hist)} histórica — por año", height=380),
            use_container_width=True,
        )

    if user["rol"] == "admin":
        st.divider()
        st.markdown("###### ✏️ Agregar o corregir un año")
        col_anio, col_meta = st.columns(2)
        anio_edit = col_anio.number_input(
            "Año", min_value=2015, max_value=2035,
            value=anios_disponibles[-1] if anios_disponibles else date.today().year,
            step=1, key="vpm_hist_anio_edit",
        )
        meta_edit = col_meta.checkbox("Es meta (objetivo), no dato real", key="vpm_hist_meta_edit")

        registro_actual = next(
            (
                r for r in registros
                if int(r["anio"]) == int(anio_edit) and bool(r.get("meta")) == meta_edit
            ),
            None,
        )
        valores_actuales = (registro_actual or {}).get("valores") or {}

        with st.form("vpm_hist_form"):
            nuevos_valores = {}
            cols = st.columns(4)
            for i, m in enumerate(DG_MESES):
                nuevos_valores[m] = cols[i % 4].number_input(
                    MESES_LABEL[m], min_value=0.0, step=100.0,
                    value=float(valores_actuales.get(m, 0) or 0),
                    key=f"vpm_hist_input_{m}_{categoria_hist}_{anio_edit}_{meta_edit}",
                )
            colf1, colf2 = st.columns(2)
            guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
            eliminar = colf2.form_submit_button(
                "🗑️ Eliminar esta fila", use_container_width=True,
                disabled=registro_actual is None,
                help=None if registro_actual else "No hay nada guardado para este año/tipo todavía.",
            )
            if guardar:
                db.upsert_historial_dato(categoria_hist, int(anio_edit), meta_edit, nuevos_valores)
                st.success(
                    f"{HISTORIAL_CATEGORIA_LABEL.get(categoria_hist, categoria_hist)} "
                    f"{'meta' if meta_edit else 'real'} de {int(anio_edit)} actualizada."
                )
                st.rerun()
            if eliminar:
                db.delete_historial_dato(categoria_hist, int(anio_edit), meta_edit)
                st.success(
                    f"Se eliminó la fila {'meta' if meta_edit else 'real'} de "
                    f"{HISTORIAL_CATEGORIA_LABEL.get(categoria_hist, categoria_hist).lower()} — {int(anio_edit)}."
                )
                st.rerun()
    else:
        st.caption("Tu rol es de solo vista para el historial.")


tab_ventas, tab_utilidades, tab_historial = st.tabs(["💰 Ventas", "📈 Utilidades", "📜 Historial"])

with tab_ventas:
    registros_ventas = db.get_ventas_mensuales_planta(anio_mes)
    _render_seccion(
        "Venta", registros_ventas, "vpm",
        db.upsert_venta_mensual_planta, "💾 Guardar venta mensual", "Venta mensual",
    )

with tab_utilidades:
    registros_utilidades = db.get_utilidades_mensuales_planta(anio_mes)
    _render_seccion(
        "Utilidad", registros_utilidades, "upm",
        db.upsert_utilidad_mensual_planta, "💾 Guardar utilidad mensual", "Utilidad mensual",
    )

with tab_historial:
    _render_historial()
