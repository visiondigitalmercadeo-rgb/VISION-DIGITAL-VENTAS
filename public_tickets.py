"""Páginas públicas del Sistema de Tickets — Tiendas: el formulario de
check-in que el cliente llena desde su celular al escanear el código QR, y
la pantalla pública "Ahora atendiendo" para mostrar en una TV/tablet dentro
de la tienda. Ninguna de las dos requiere haber iniciado sesión — se llaman
desde app.py ANTES de auth.require_login()."""

import streamlit as st

import database as db
from config import EMPRESA_NOMBRE, LOGO_PATH, TICKET_SERVICIOS, TICKET_SLUG_TIENDA


def _tienda_desde_slug(slug):
    return TICKET_SLUG_TIENDA.get((slug or "").strip().lower())


def render_checkin(slug):
    """Formulario público de check-in. Devuelve True si atendió la solicitud
    (haya que hacer st.stop() después)."""
    tienda = _tienda_desde_slug(slug)

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        try:
            st.image(LOGO_PATH, width=280)
        except Exception:
            pass

        if not tienda:
            st.error(
                "Este enlace de check-in no es válido. Por favor pide ayuda a un colaborador "
                "de la tienda."
            )
            return True

        if st.session_state.get("tt_checkin_ok_tienda") == tienda:
            numero = st.session_state.get("tt_checkin_ok_numero")
            st.success(f"✅ ¡Listo! Tu número de turno en **{tienda}** es **#{numero}**.")
            st.info(
                "Te atenderemos en el orden en que llegaste. Por favor toma asiento — en cuanto "
                "sea tu turno, un colaborador te llamará por tu nombre."
            )
            if st.button("Registrar a otra persona", use_container_width=True):
                st.session_state.pop("tt_checkin_ok_tienda", None)
                st.session_state.pop("tt_checkin_ok_numero", None)
                st.rerun()
            return True

        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.5rem;'>Bienvenido a {EMPRESA_NOMBRE} · {tienda}</h3>"
            "<p style='text-align:center;color:#52514e;'>Regístrate para que te atendamos — "
            "toma menos de un minuto.</p>",
            unsafe_allow_html=True,
        )
        with st.form("tt_checkin_form"):
            nombre = st.text_input("Nombre completo")
            telefono = st.text_input("Número de teléfono")
            servicio = st.multiselect(
                "¿Qué servicio o producto necesitas? (puedes elegir varios)",
                TICKET_SERVICIOS,
            )
            enviado = st.form_submit_button("✅ Registrarme", use_container_width=True)
            if enviado:
                if not nombre.strip() or not servicio:
                    st.error("Por favor completa al menos tu nombre y qué necesitas.")
                else:
                    r = db.create_ticket_tienda(tienda, nombre, telefono, servicio)
                    st.session_state["tt_checkin_ok_tienda"] = tienda
                    st.session_state["tt_checkin_ok_numero"] = r["numero_ticket"]
                    st.rerun()
    return True


def render_pantalla(slug):
    """Pantalla pública 'Ahora atendiendo', pensada para dejar abierta en una
    TV/tablet dentro de la tienda. Se auto-refresca cada 15 segundos."""
    tienda = _tienda_desde_slug(slug)

    st.markdown('<meta http-equiv="refresh" content="15">', unsafe_allow_html=True)

    if not tienda:
        st.error("Enlace de pantalla no válido.")
        return True

    hoy = str(db.hoy_guatemala())
    tickets_hoy = db.list_tickets_tienda(tienda=tienda, fecha=hoy)

    en_curso = [t for t in tickets_hoy if t["estado"] in ("En atención", "En elaboración")]
    en_curso.sort(key=lambda t: t.get("numero_ticket") or 0)
    en_espera = [t for t in tickets_hoy if t["estado"] == "Esperando"]
    en_espera.sort(key=lambda t: t.get("numero_ticket") or 0)

    st.markdown(
        f"<h1 style='text-align:center;'>{tienda} — Ahora atendiendo</h1>",
        unsafe_allow_html=True,
    )

    if en_curso:
        cols = st.columns(len(en_curso))
        for c, t in zip(cols, en_curso):
            with c:
                st.markdown(
                    f"<div style='text-align:center;padding:1.5rem;border-radius:12px;"
                    f"background:#eaf4ec;'>"
                    f"<div style='font-size:3rem;font-weight:800;'>#{t['numero_ticket']}</div>"
                    f"<div style='font-size:1.3rem;'>{t['nombre']}</div>"
                    f"<div style='color:#52514e;'>{t['estado']}</div></div>",
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            "<p style='text-align:center;font-size:1.3rem;color:#898781;'>"
            "Ningún cliente en atención por el momento.</p>",
            unsafe_allow_html=True,
        )

    st.markdown("<h3 style='text-align:center;margin-top:2rem;'>Siguen en la fila</h3>", unsafe_allow_html=True)
    if en_espera:
        numeros = "  ·  ".join(f"#{t['numero_ticket']}" for t in en_espera)
        st.markdown(
            f"<p style='text-align:center;font-size:1.6rem;'>{numeros}</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<p style='text-align:center;color:#898781;'>No hay nadie esperando ahora mismo.</p>",
            unsafe_allow_html=True,
        )

    return True
