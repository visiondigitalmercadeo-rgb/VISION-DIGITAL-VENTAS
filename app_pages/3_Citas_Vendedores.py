from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar as st_calendar

import auth
import database as db
from config import ESTADOS_CITA, STATUS, TIPOS_CITA
from utils import download_excel_button, hora_24_a_12, selector_hora, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("📅 Calendario de citas y visitas de vendedores")
st.caption("Agenda de citas, visitas y llamadas de cada vendedor.")

TIPO_EMOJI = {"Cita": "🤝", "Visita": "🏬", "Llamada": "📞"}
ESTADO_COLOR = {
    "Programada": STATUS["warning"],
    "Realizada": STATUS["good"],
    "Cancelada": STATUS["critical"],
    "No asistió": STATUS["serious"],
}

tab_calendario, tab_lista, tab_nueva = st.tabs(["🗓️ Calendario", "📋 Lista / editar", "➕ Nueva cita"])

# --------------------------------------------------------------------------
# Calendario visual (mes / semana / lista)
# --------------------------------------------------------------------------
with tab_calendario:
    filtro_vendedor = vendedor_filter_selector(key="citas_filtro_vendedor_cal")

    citas_cal = db.list_citas(
        filtro_vendedor, desde=date.today() - timedelta(days=120), hasta=date.today() + timedelta(days=180)
    )
    vendedores = db.list_usuarios()

    eventos = []
    for c in citas_cal:
        hora = c["hora"] or "09:00"
        titulo = f"{TIPO_EMOJI.get(c['tipo'], '•')} {c['cliente_nombre']}"
        if user["rol"] != "vendedor":
            titulo += f" — {db.nombre_vendedor(c['vendedor_id'], vendedores)}"
        color = ESTADO_COLOR.get(c["estado"], "#898781")
        eventos.append({
            "id": str(c["id"]),
            "title": titulo,
            "start": f"{c['fecha']}T{hora}:00",
            "backgroundColor": color,
            "borderColor": color,
        })

    opciones_cal = {
        "locale": "es",
        "initialView": "dayGridMonth",
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,listMonth"},
        "height": 650,
        "firstDay": 1,
        "buttonText": {"today": "Hoy", "month": "Mes", "week": "Semana", "list": "Lista"},
    }

    estado_click = st_calendar(events=eventos, options=opciones_cal, key="citas_calendario_visual")

    st.caption(
        f"🟡 Programada · 🟢 Realizada · 🟠 No asistió · 🔴 Cancelada — "
        f"total en este rango: {len(eventos)} actividad(es)."
    )

    if estado_click and estado_click.get("eventClick"):
        cid = estado_click["eventClick"]["event"]["id"]
        cita_sel = next((c for c in citas_cal if str(c["id"]) == cid), None)
        if cita_sel:
            with st.container(border=True):
                st.markdown(f"**{cita_sel['tipo']} — {cita_sel['cliente_nombre']}**")
                st.write(
                    f"📅 {cita_sel['fecha']} {cita_sel['hora'] or ''} · 📍 {cita_sel['lugar'] or '—'} · "
                    f"Estado: {cita_sel['estado']}"
                )
                if user["rol"] != "vendedor":
                    st.caption(f"Vendedor: {db.nombre_vendedor(cita_sel['vendedor_id'], vendedores)}")
                if cita_sel["notas"]:
                    st.caption(f"Notas: {cita_sel['notas']}")
                st.caption("Para cambiar el estado o eliminarla, usa la pestaña 'Lista / editar'.")

# --------------------------------------------------------------------------
# Lista / editar
# --------------------------------------------------------------------------
with tab_lista:
    filtro_vendedor2 = vendedor_filter_selector(key="citas_filtro_vendedor_lista")
    c1, c2 = st.columns(2)
    desde = c1.date_input("Desde", value=date.today() - timedelta(days=7), key="citas_desde")
    hasta = c2.date_input("Hasta", value=date.today() + timedelta(days=14), key="citas_hasta")

    rows = db.list_citas(filtro_vendedor2, desde=desde, hasta=hasta)
    if not rows:
        st.info("No hay citas/visitas/llamadas en este rango.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"], "Fecha": r["fecha"], "Hora": r["hora"], "Tipo": r["tipo"],
            "Cliente": r["cliente_nombre"], "Lugar": r["lugar"], "Estado": r["estado"],
            "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "citas.xlsx", key="citas_descargar_excel")

        if auth.can_edit():
            st.markdown("#### ✏️ Actualizar estado de una cita")
            opciones = {f"{r['fecha']} {r['hora'] or ''} — {r['cliente_nombre']}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona", ["—"] + list(opciones.keys()), key="citas_editar_select")
            if elegido != "—":
                cid = opciones[elegido]
                cita = next(r for r in rows if r["id"] == cid)
                if user["rol"] == "vendedor" and cita["vendedor_id"] != user["id"]:
                    st.warning("Esta cita pertenece a otro vendedor.")
                else:
                    with st.form(f"editar_cita_{cid}"):
                        cliente_nombre_ed = st.text_input("Nombre del cliente", value=cita["cliente_nombre"] or "")
                        ce1, ce2 = st.columns(2)
                        tipo_ed = ce1.selectbox(
                            "Tipo", TIPOS_CITA,
                            index=TIPOS_CITA.index(cita["tipo"]) if cita["tipo"] in TIPOS_CITA else 0,
                        )
                        fecha_ed = ce2.date_input(
                            "Fecha",
                            value=date.fromisoformat(cita["fecha"]) if cita["fecha"] else date.today(),
                        )
                        hora12_ed, minuto_ed, ampm_ed = hora_24_a_12(cita["hora"] or "09:00")
                        hora_texto_ed = selector_hora(
                            "Hora", f"editar_cita_{cid}",
                            hora12=hora12_ed, minuto=minuto_ed, ampm=ampm_ed,
                        )
                        lugar_ed = st.text_input("Lugar", value=cita["lugar"] or "")
                        nuevo_estado = st.selectbox("Estado", ESTADOS_CITA, index=ESTADOS_CITA.index(cita["estado"]))
                        notas = st.text_area("Notas", value=cita["notas"] or "")
                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("Guardar", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar", use_container_width=True)
                        if guardar:
                            if not cliente_nombre_ed.strip():
                                st.error("El nombre del cliente es obligatorio.")
                            else:
                                db.update_cita(
                                    cid, cliente_nombre=cliente_nombre_ed.strip(), tipo=tipo_ed,
                                    fecha=str(fecha_ed), hora=hora_texto_ed,
                                    lugar=lugar_ed, estado=nuevo_estado, notas=notas,
                                )
                                st.success("Actualizado.")
                                st.rerun()
                        if eliminar:
                            db.delete_cita(cid)
                            st.success("Eliminada.")
                            st.rerun()

# --------------------------------------------------------------------------
# Nueva cita
# --------------------------------------------------------------------------
with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede agendar citas.")
    else:
        with st.form("nueva_cita_form", clear_on_submit=True):
            if user["rol"] == "admin":
                vendedores = db.list_vendedores()
                opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                vendedor_nombre = st.selectbox("Vendedor", list(opciones_v.keys()))
                vendedor_id = opciones_v[vendedor_nombre]
            else:
                vendedor_id = user["id"]
                st.caption(f"Vendedor: **{user['nombre']}**")

            prospectos = db.list_prospectos(vendedor_id if user["rol"] != "admin" else None)
            opciones_p = {"(cliente libre — escribir abajo)": None}
            opciones_p.update({f"{p['nombre_cliente']} (NIT {p['nit']})": p["id"] for p in prospectos})
            prospecto_sel = st.selectbox("Prospecto/cliente (opcional)", list(opciones_p.keys()))
            prospecto_id = opciones_p[prospecto_sel]
            cliente_nombre = st.text_input(
                "Nombre del cliente",
                value=prospecto_sel.split(" (NIT")[0] if prospecto_id else "",
            )

            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", TIPOS_CITA)
            fecha = c2.date_input("Fecha", value=date.today())
            hora12_now, minuto_now, ampm_now = hora_24_a_12(datetime.now().strftime("%H:%M"))
            hora_texto = selector_hora(
                "Hora", "nueva_cita",
                hora12=hora12_now, minuto=minuto_now, ampm=ampm_now,
            )
            lugar = st.text_input("Lugar")
            notas = st.text_area("Notas")

            if st.form_submit_button("Agendar", use_container_width=True):
                if not cliente_nombre.strip():
                    st.error("Ingresa el nombre del cliente.")
                else:
                    db.create_cita(vendedor_id, prospecto_id, cliente_nombre.strip(), tipo,
                                    fecha, hora_texto, lugar, "Programada", notas)
                    st.success("Cita agendada.")
                    st.rerun()
