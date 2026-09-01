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
        if comentarios:
            st.dataframe(pd.DataFrame(comentarios), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay comentarios en este período.")

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
