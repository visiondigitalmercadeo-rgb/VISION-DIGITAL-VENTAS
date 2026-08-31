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
        MAGENTA_LEVE = "#fbe3f2"
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


tab_ventas, tab_utilidades = st.tabs(["💰 Ventas", "📈 Utilidades"])

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
