import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import qrcode
import streamlit as st

import auth
import database as db
from config import (
    APP_URL, CATEGORICAL, INK_PRIMARY, NPS_CARITAS, NPS_TIENDA_SLUG, NPS_TIENDAS, STATUS,
)
from utils import base_layout, sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_nps()

st.title("😊 NPS")
st.caption(
    "Encuesta de servicio al cliente, contestada desde el celular al escanear el código QR de "
    "cada tienda (pestaña 'Código QR'). Aquí se consultan los resultados (KPIs) y, solo el "
    "administrador, puede cambiar el texto de las preguntas ('Parametrización')."
)

CATEGORIA_POR_VALOR = {c["valor"]: c["categoria_nps"] for c in NPS_CARITAS}
COLOR_POR_CATEGORIA = {"detractor": STATUS["critical"], "neutro": STATUS["warning"], "promotor": STATUS["good"]}
TIPO_LABEL = {"carita": "🙂 caritas (Malo / Regular / Excelente)", "opcion": "Opción múltiple", "texto": "Texto libre"}

tab_kpis, tab_qr, tab_param = st.tabs(["📊 KPIs", "🔗 Código QR", "⚙️ Parametrización"])


def _breakdown_carita(respuestas, pregunta_id):
    conteo = {"detractor": 0, "neutro": 0, "promotor": 0}
    for r in respuestas:
        cat = CATEGORIA_POR_VALOR.get((r.get("respuestas") or {}).get(pregunta_id))
        if cat:
            conteo[cat] += 1
    return conteo, sum(conteo.values())


def _grafica_donut(conteo, score, titulo):
    fig = go.Figure(go.Pie(
        labels=["Detractores", "Neutros", "Promotores"],
        values=[conteo["detractor"], conteo["neutro"], conteo["promotor"]],
        hole=0.65, sort=False, textinfo="none",
        marker=dict(colors=[COLOR_POR_CATEGORIA["detractor"], COLOR_POR_CATEGORIA["neutro"], COLOR_POR_CATEGORIA["promotor"]]),
    ))
    fig.add_annotation(text=f"<b>{score}</b>", x=0.5, y=0.5, showarrow=False, font=dict(size=34, color=INK_PRIMARY))
    return base_layout(fig, title=titulo, height=280)


def _calificacion_tienda_promedio(tienda):
    """Promedio de la calificación de servicio (pregunta tipo carita
    'servicio': ¿Cómo estuvo el servicio?) de una tienda, sobre TODAS las
    respuestas guardadas (no cambia con los filtros de fecha/tienda de la
    tabla de abajo — es un resumen general). Se devuelve la carita de
    NPS_CARITAS más cercana al promedio (malo/regular/excelente), junto con
    el promedio numérico y cuántas respuestas se usaron. None si la tienda
    todavía no tiene ninguna respuesta a esa pregunta."""
    valores = {"malo": 1, "regular": 2, "excelente": 3}
    puntos = [
        valores[(r.get("respuestas") or {}).get("servicio")]
        for r in db.list_nps_respuestas(tienda=tienda)
        if (r.get("respuestas") or {}).get("servicio") in valores
    ]
    if not puntos:
        return None
    promedio = sum(puntos) / len(puntos)
    if promedio < (1 + 2 / 3):
        carita_valor = "malo"
    elif promedio < (1 + 4 / 3):
        carita_valor = "regular"
    else:
        carita_valor = "excelente"
    carita = next(c for c in NPS_CARITAS if c["valor"] == carita_valor)
    return {"promedio": promedio, "carita": carita, "total": len(puntos)}


def _seccion_carita(respuestas, pregunta_id, titulo_seccion, titulo_score):
    conteo, total = _breakdown_carita(respuestas, pregunta_id)
    st.markdown(f"###### {titulo_seccion}")
    if not total:
        st.info("No hay respuestas todavía para este filtro.")
        return
    score = round((conteo["promotor"] - conteo["detractor"]) / total * 100)
    col_donut, col_desglose = st.columns([1, 1.2])
    with col_donut:
        st.plotly_chart(_grafica_donut(conteo, score, titulo_score), use_container_width=True)
    with col_desglose:
        st.metric("Total de respuestas", total)
        for etiqueta, cat in [("🔴 Detractores", "detractor"), ("🟡 Neutros", "neutro"), ("🟢 Promotores", "promotor")]:
            n = conteo[cat]
            pct = (n / total * 100) if total else 0
            st.write(f"{etiqueta}: **{n}** ({pct:.1f}%)")


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
with tab_kpis:
    st.markdown("###### 🏪 Calificación promedio por tienda")
    st.caption(
        "Promedio de todas las respuestas guardadas a '¿Cómo estuvo el servicio?' — no cambia con "
        "los filtros de abajo."
    )
    cols_resumen = st.columns(len(NPS_TIENDAS))
    for col_resumen, tienda_resumen in zip(cols_resumen, NPS_TIENDAS):
        with col_resumen:
            with st.container(border=True):
                st.markdown(f"**{tienda_resumen}**")
                info = _calificacion_tienda_promedio(tienda_resumen)
                if info is None:
                    st.markdown(
                        "<div style='text-align:center;font-size:2.4rem;'>—</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption("Sin respuestas todavía")
                else:
                    carita = info["carita"]
                    st.markdown(
                        f"<div style='text-align:center;font-size:2.6rem;line-height:1.1;'>{carita['emoji']}</div>"
                        f"<div style='text-align:center;font-weight:700;color:{carita['color']};'>{carita['label']}</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{info['promedio']:.1f} / 3.0 · {info['total']} respuesta(s)")
    st.divider()

    fcol1, fcol2, fcol3 = st.columns(3)
    tienda_sel = fcol1.selectbox("Tienda", ["Todas"] + NPS_TIENDAS, key="nps_kpi_tienda")
    desde = fcol2.date_input("Desde", value=date.today().replace(day=1), key="nps_kpi_desde")
    hasta = fcol3.date_input("Hasta", value=date.today(), key="nps_kpi_hasta")

    respuestas = db.list_nps_respuestas(
        tienda=None if tienda_sel == "Todas" else tienda_sel, desde=desde, hasta=hasta,
    )
    preguntas = db.get_nps_preguntas()
    preguntas_por_id = {p["id"]: p for p in preguntas}

    st.divider()
    if "recomendaria" in preguntas_por_id:
        _seccion_carita(
            respuestas, "recomendaria",
            f"🎯 NPS — {preguntas_por_id['recomendaria']['texto']}", "NPS",
        )
    st.divider()
    if "servicio" in preguntas_por_id:
        _seccion_carita(
            respuestas, "servicio",
            f"😊 Satisfacción del servicio — {preguntas_por_id['servicio']['texto']}", "Índice",
        )

    pregunta_opcion = next((p for p in preguntas if p["tipo"] == "opcion"), None)
    if pregunta_opcion:
        st.divider()
        st.markdown(f"###### 📣 {pregunta_opcion['texto']}")
        opciones = pregunta_opcion.get("opciones") or []
        conteo_opcion = {op: 0 for op in opciones}
        for r in respuestas:
            valor = (r.get("respuestas") or {}).get(pregunta_opcion["id"])
            if valor:
                conteo_opcion[valor] = conteo_opcion.get(valor, 0) + 1
        if not respuestas:
            st.info("No hay respuestas todavía para este filtro.")
        else:
            fig_opcion = go.Figure(go.Bar(
                x=list(conteo_opcion.keys()), y=list(conteo_opcion.values()), marker_color=CATEGORICAL[0],
            ))
            st.plotly_chart(base_layout(fig_opcion, height=320), use_container_width=True)

    pregunta_texto = next((p for p in preguntas if p["tipo"] == "texto"), None)
    if pregunta_texto:
        st.divider()
        st.markdown(f"###### 💬 Comentarios — {pregunta_texto['texto']}")
        comentarios = [
            {
                "Fecha": (r.get("creado_en") or "")[:16].replace("T", " "),
                "Tienda": r.get("tienda") or "—",
                "Comentario": (r.get("respuestas") or {}).get(pregunta_texto["id"]),
            }
            for r in respuestas if (r.get("respuestas") or {}).get(pregunta_texto["id"])
        ]
        if not comentarios:
            st.caption("No hay comentarios en este período.")
        else:
            # Divididos por tienda (una pestaña por cada una) para poder leerlos
            # de un vistazo sin tener que buscarlos mezclados en una sola tabla.
            # Si el filtro de 'Tienda' de arriba ya está en una tienda específica,
            # las demás pestañas simplemente salen vacías.
            otras_tiendas = sorted({c["Tienda"] for c in comentarios if c["Tienda"] not in NPS_TIENDAS})
            etiquetas_tab_tienda = [
                f"{t} ({sum(1 for c in comentarios if c['Tienda'] == t)})" for t in NPS_TIENDAS
            ]
            if otras_tiendas:
                etiquetas_tab_tienda.append(f"Otras ({sum(1 for c in comentarios if c['Tienda'] in otras_tiendas)})")
            tabs_comentarios = st.tabs(etiquetas_tab_tienda)
            for tab_tienda, tienda_t in zip(tabs_comentarios, list(NPS_TIENDAS) + (["__otras__"] if otras_tiendas else [])):
                with tab_tienda:
                    if tienda_t == "__otras__":
                        comentarios_tienda = [c for c in comentarios if c["Tienda"] in otras_tiendas]
                    else:
                        comentarios_tienda = [c for c in comentarios if c["Tienda"] == tienda_t]
                    if not comentarios_tienda:
                        st.caption("No hay comentarios de esta tienda en este período.")
                    else:
                        df_comentarios_tienda = pd.DataFrame(comentarios_tienda)[["Fecha", "Comentario"]]
                        st.dataframe(df_comentarios_tienda, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Código QR — uno por tienda, mismo concepto que Tickets — Tiendas.
# ---------------------------------------------------------------------------
with tab_qr:
    st.markdown("#### 🔗 Códigos QR de la encuesta")
    st.caption(
        "Imprime el código de cada tienda y pégalo donde el cliente lo pueda escanear (mostrador, "
        "recibo, mesa de espera). Al escanearlo, el cliente llena la encuesta desde su celular sin "
        "necesidad de iniciar sesión."
    )
    cols_qr = st.columns(2)
    for i, tienda_qr in enumerate(NPS_TIENDAS):
        slug = NPS_TIENDA_SLUG[tienda_qr]
        link_encuesta = f"{APP_URL}/?nps={slug}"
        qr_img = qrcode.make(link_encuesta, box_size=8, border=2)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        with cols_qr[i % 2]:
            with st.container(border=True):
                st.image(png_bytes, caption=f"QR de encuesta — {tienda_qr}", width=220)
                st.download_button(
                    "⬇️ Descargar QR (PNG)", data=png_bytes,
                    file_name=f"qr_nps_{slug}.png", mime="image/png",
                    use_container_width=True, key=f"nps_qr_descargar_{slug}",
                )
                st.code(link_encuesta)

# ---------------------------------------------------------------------------
# Parametrización — solo admin.
# ---------------------------------------------------------------------------
with tab_param:
    if not puede_editar:
        st.info("Esta sección es solo para el administrador.")
    else:
        st.markdown("#### ⚙️ Parametrización de las preguntas")
        st.caption(
            "Puedes cambiar el texto de cada pregunta y, en la de opción múltiple, sus opciones "
            "(una por línea). El TIPO de cada pregunta (caritas / opción múltiple / texto libre) no "
            "se puede cambiar desde aquí."
        )
        preguntas_actuales = db.get_nps_preguntas()
        with st.form("nps_parametrizacion_form"):
            nuevas_preguntas = []
            for p in preguntas_actuales:
                st.markdown(f"**{TIPO_LABEL.get(p['tipo'], p['tipo'])}**")
                texto_nuevo = st.text_input(
                    "Texto de la pregunta", value=p["texto"], key=f"nps_param_texto_{p['id']}",
                )
                nueva_p = dict(p)
                nueva_p["texto"] = texto_nuevo
                if p["tipo"] == "opcion":
                    opciones_texto = st.text_area(
                        "Opciones (una por línea)", value="\n".join(p.get("opciones") or []),
                        key=f"nps_param_opciones_{p['id']}",
                    )
                    nueva_p["opciones"] = [o.strip() for o in opciones_texto.replace(",", "\n").split("\n") if o.strip()]
                nuevas_preguntas.append(nueva_p)
                st.divider()

            if st.form_submit_button("💾 Guardar preguntas", use_container_width=True):
                error_msg = None
                for p in nuevas_preguntas:
                    if not p["texto"].strip():
                        error_msg = "Todas las preguntas necesitan un texto."
                        break
                    if p["tipo"] == "opcion" and len(p.get("opciones") or []) < 2:
                        error_msg = "La pregunta de opción múltiple necesita al menos 2 opciones."
                        break
                if error_msg:
                    st.error(error_msg)
                else:
                    for p in nuevas_preguntas:
                        p["texto"] = p["texto"].strip()
                    db.set_nps_preguntas(nuevas_preguntas)
                    st.success("Preguntas actualizadas.")
                    st.rerun()

        st.divider()
        st.markdown("#### 🗑️ Borrar respuestas")
        st.caption(
            "Úsalo para borrar respuestas de prueba. Puedes borrar solo las de una tienda y/o un "
            "rango de fechas, o borrar TODAS las respuestas guardadas. Esta acción no se puede "
            "deshacer."
        )
        total_actual = len(db.list_nps_respuestas())
        st.write(f"Respuestas guardadas actualmente: **{total_actual}**")

        modo_borrado = st.radio(
            "¿Qué quieres borrar?",
            ["Solo algunas (filtrar por tienda y/o fecha)", "TODAS las respuestas"],
            key="nps_borrar_modo",
        )

        if modo_borrado == "TODAS las respuestas":
            with st.expander("🗑️ Borrar TODAS las respuestas de NPS"):
                st.warning(
                    f"Esto va a borrar las **{total_actual}** respuestas guardadas hasta ahora, "
                    "de todas las tiendas. No se puede deshacer."
                )
                confirmar_todas = st.checkbox(
                    "Confirmo que quiero borrar TODAS las respuestas", key="nps_conf_borrar_todas",
                )
                if st.button(
                    "Borrar TODAS las respuestas", key="nps_btn_borrar_todas",
                    disabled=not confirmar_todas,
                ):
                    n = db.delete_nps_respuestas()
                    st.success(f"Se borraron {n} respuesta(s).")
                    st.rerun()
        else:
            with st.expander("🗑️ Borrar respuestas filtradas"):
                bcol1, bcol2, bcol3 = st.columns(3)
                tienda_borrar = bcol1.selectbox(
                    "Tienda", ["Todas"] + NPS_TIENDAS, key="nps_borrar_tienda",
                )
                desde_borrar = bcol2.date_input(
                    "Desde", value=None, key="nps_borrar_desde",
                )
                hasta_borrar = bcol3.date_input(
                    "Hasta", value=None, key="nps_borrar_hasta",
                )
                cuantas = len(db.list_nps_respuestas(
                    tienda=None if tienda_borrar == "Todas" else tienda_borrar,
                    desde=desde_borrar, hasta=hasta_borrar,
                ))
                st.warning(f"Con este filtro se van a borrar **{cuantas}** respuesta(s). No se puede deshacer.")
                confirmar_filtro = st.checkbox(
                    "Confirmo que quiero borrar estas respuestas", key="nps_conf_borrar_filtro",
                )
                if st.button(
                    "Borrar respuestas filtradas", key="nps_btn_borrar_filtro",
                    disabled=not confirmar_filtro or cuantas == 0,
                ):
                    n = db.delete_nps_respuestas(
                        tienda=None if tienda_borrar == "Todas" else tienda_borrar,
                        desde=desde_borrar, hasta=hasta_borrar,
                    )
                    st.success(f"Se borraron {n} respuesta(s).")
                    st.rerun()
