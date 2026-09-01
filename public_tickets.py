"""Página pública de la encuesta NPS: el formulario que el cliente llena
desde su celular al escanear el código QR de su tienda. No requiere haber
iniciado sesión — se llama desde app.py ANTES de auth.require_login(), igual
que public_tickets.py."""

import streamlit as st

import database as db
from config import EMPRESA_NOMBRE, LOGO_PATH, NPS_CARITAS, NPS_SLUG_TIENDA


def _tienda_desde_slug(slug):
    return NPS_SLUG_TIENDA.get((slug or "").strip().lower())


def render_encuesta(slug):
    """Formulario público de la encuesta. Devuelve True si atendió la
    solicitud (haya que hacer st.stop() después)."""
    tienda = _tienda_desde_slug(slug)

    _, col, _ = st.columns([1, 1.3, 1])
    with col:
        try:
            st.image(LOGO_PATH, width=280)
        except Exception:
            pass

        if not tienda:
            st.error(
                "Este enlace de encuesta no es válido. Por favor pide ayuda a un colaborador "
                "de la tienda."
            )
            return True

        if st.session_state.get("nps_encuesta_enviada_tienda") == tienda:
            st.success("✅ ¡Gracias por tu opinión! Nos ayuda mucho a seguir mejorando.")
            if st.button("Responder otra encuesta", use_container_width=True):
                st.session_state.pop("nps_encuesta_enviada_tienda", None)
                st.rerun()
            return True

        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.5rem;'>{EMPRESA_NOMBRE} · {tienda}</h3>"
            "<p style='text-align:center;color:#52514e;'>Tu opinión nos ayuda a mejorar — "
            "toma menos de un minuto.</p>",
            unsafe_allow_html=True,
        )

        preguntas = db.get_nps_preguntas()
        opciones_carita = {f"{c['emoji']} {c['label']}": c["valor"] for c in NPS_CARITAS}

        with st.form("nps_encuesta_form"):
            respuestas = {}
            for p in preguntas:
                if p["tipo"] == "carita":
                    elegido = st.radio(
                        p["texto"], list(opciones_carita.keys()),
                        index=None, horizontal=True, key=f"nps_q_{p['id']}",
                    )
                    respuestas[p["id"]] = opciones_carita.get(elegido)
                elif p["tipo"] == "opcion":
                    respuestas[p["id"]] = st.radio(
                        p["texto"], p.get("opciones") or [],
                        index=None, key=f"nps_q_{p['id']}",
                    )
                elif p["tipo"] == "texto":
                    respuestas[p["id"]] = st.text_area(p["texto"], key=f"nps_q_{p['id']}")

            enviado = st.form_submit_button("✅ Enviar", use_container_width=True)
            if enviado:
                faltantes = [
                    p["texto"] for p in preguntas
                    if p["tipo"] in ("carita", "opcion") and not respuestas.get(p["id"])
                ]
                if faltantes:
                    st.error("Por favor responde todas las preguntas antes de enviar.")
                else:
                    respuestas_limpias = {
                        pid: (v.strip() if isinstance(v, str) else v) or None
                        for pid, v in respuestas.items()
                    }
                    db.create_nps_respuesta(tienda, respuestas_limpias)
                    st.session_state["nps_encuesta_enviada_tienda"] = tienda
                    st.rerun()
    return True
