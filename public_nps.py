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
            # Para las preguntas de opción múltiple que incluyan "Otro" entre
            # sus opciones, se pide especificar cuál — el campo se muestra
            # siempre (no solo al elegir "Otro") porque, dentro de un
            # st.form, los campos no se actualizan en vivo al cambiar otro
            # campo, solo hasta que se presiona "Enviar".
            detalles_otro = {}
            for p in preguntas:
                if p["tipo"] == "carita":
                    elegido = st.radio(
                        p["texto"], list(opciones_carita.keys()),
                        index=None, horizontal=True, key=f"nps_q_{p['id']}",
                    )
                    respuestas[p["id"]] = opciones_carita.get(elegido)
                elif p["tipo"] == "opcion":
                    opciones_p = p.get("opciones") or []
                    respuestas[p["id"]] = st.radio(
                        p["texto"], opciones_p, index=None, key=f"nps_q_{p['id']}",
                    )
                    if any((o or "").strip().lower() == "otro" for o in opciones_p):
                        detalles_otro[p["id"]] = st.text_input(
                            "Si elegiste 'Otro' arriba, especifica cuál (obligatorio en ese caso)",
                            key=f"nps_q_{p['id']}_otro",
                        )
                elif p["tipo"] == "texto":
                    respuestas[p["id"]] = st.text_area(p["texto"], key=f"nps_q_{p['id']}")

            st.divider()
            st.caption(
                "¿Tuviste algún problema o reclamo? Si quieres que te contactemos, déjanos tus "
                "datos abajo (completamente opcional, no es necesario para enviar la encuesta):"
            )
            col_nombre, col_telefono = st.columns(2)
            nombre_contacto = col_nombre.text_input("Nombre (opcional)", key="nps_contacto_nombre")
            telefono_contacto = col_telefono.text_input("Teléfono (opcional)", key="nps_contacto_telefono")

            enviado = st.form_submit_button("✅ Enviar", use_container_width=True)
            if enviado:
                faltantes = [
                    p["texto"] for p in preguntas
                    if p["tipo"] in ("carita", "opcion") and not respuestas.get(p["id"])
                ]
                falta_detalle_otro = any(
                    (respuestas.get(pid) or "").strip().lower() == "otro"
                    and not (detalles_otro.get(pid) or "").strip()
                    for pid in detalles_otro
                )
                if faltantes:
                    st.error("Por favor responde todas las preguntas antes de enviar.")
                elif falta_detalle_otro:
                    st.error("Elegiste 'Otro' — por favor especifica cuál antes de enviar.")
                else:
                    respuestas_limpias = {
                        pid: (v.strip() if isinstance(v, str) else v) or None
                        for pid, v in respuestas.items()
                    }
                    for pid, detalle in detalles_otro.items():
                        if (respuestas.get(pid) or "").strip().lower() == "otro" and (detalle or "").strip():
                            respuestas_limpias[f"{pid}_otro"] = detalle.strip()
                    db.create_nps_respuesta(
                        tienda, respuestas_limpias,
                        nombre_contacto=nombre_contacto, telefono_contacto=telefono_contacto,
                    )
                    st.session_state["nps_encuesta_enviada_tienda"] = tienda
                    st.rerun()
    return True
