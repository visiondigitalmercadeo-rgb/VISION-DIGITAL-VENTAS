from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PENDIENTE_MINUTA, TICKET_TIENDAS
from utils import download_excel_button, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("📝 Minutas de Tienda")
st.caption(
    "El jefe (o sub jefe) de tienda deja constancia de su reunión: un checklist de los temas que se "
    "tocaron y los pendientes que quedaron abiertos. El jefe de línea (y los administradores) le dan "
    "seguimiento a cada pendiente hasta que queda resuelto."
)

ESCRIBIR_RESPONSABLE_NUEVO = "✍️ Escribir otro nombre"

puede_crear = auth.puede_crear_minuta_tienda()
puede_seguimiento = auth.puede_gestionar_pendientes_minuta()
tienda_usuario = auth.current_user_tienda()


def _opciones_responsable(tienda):
    personal = db.list_personal_tiendas(tienda=tienda) if tienda else []
    nombres = [p["nombre"] for p in personal if p.get("nombre")]
    return [ESCRIBIR_RESPONSABLE_NUEVO] + nombres


def _emoji_estado(estado):
    return {"Pendiente": "🔴", "En proceso": "🟡", "Resuelto": "🟢"}.get(estado, "⚪")


tab_pendientes, tab_minutas, tab_nueva = st.tabs(["📌 Pendientes", "🗒️ Minutas", "➕ Nueva minuta"])

# --------------------------------------------------------------------------
# Pendientes — vista consolidada de TODOS los pendientes de TODAS las
# minutas (con el filtro de tienda cuando aplica), para que el jefe de
# línea/admin les dé seguimiento sin tener que abrir minuta por minuta.
# --------------------------------------------------------------------------
with tab_pendientes:
    if tienda_usuario:
        minutas_p = db.list_minutas_tiendas(tienda=tienda_usuario)
        st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
    else:
        elegido_tienda_p = st.selectbox("Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mn_pend_filtro_tienda")
        minutas_p = db.list_minutas_tiendas(tienda=None if elegido_tienda_p == "Todas" else elegido_tienda_p)

    mostrar_resueltos = st.checkbox("Mostrar también los pendientes ya resueltos", key="mn_pend_mostrar_resueltos")

    filas_pendientes = []
    for m in minutas_p:
        for i, p in enumerate(m.get("pendientes") or []):
            if not mostrar_resueltos and p.get("estado") == "Resuelto":
                continue
            filas_pendientes.append((m, i, p))

    if not filas_pendientes:
        st.caption("No hay pendientes que mostrar con este filtro.")
    else:
        download_excel_button(
            pd.DataFrame([{
                "Minuta": f"MIN-{m['numero']:04d}" if isinstance(m.get("numero"), int) else "—",
                "Tienda": m.get("tienda"), "Fecha reunión": m.get("fecha_reunion"),
                "Pendiente": p.get("descripcion"), "Responsable": p.get("responsable") or "—",
                "Fecha límite": p.get("fecha_limite") or "—", "Estado": p.get("estado"),
            } for m, i, p in filas_pendientes]),
            "pendientes_minutas_tienda.xlsx", key="mn_pend_descargar_excel",
        )

        orden_estado = {"Pendiente": 0, "En proceso": 1, "Resuelto": 2}
        filas_pendientes.sort(key=lambda t: (orden_estado.get(t[2].get("estado"), 9), t[2].get("fecha_limite") or ""))

        for m, i, p in filas_pendientes:
            numero_txt = f"MIN-{m['numero']:04d} · " if isinstance(m.get("numero"), int) else ""
            with st.container(border=True):
                st.markdown(f"{_emoji_estado(p.get('estado'))} **{p.get('descripcion')}**")
                st.caption(
                    f"🏬 {m.get('tienda') or '—'} · 🙋 Responsable: {p.get('responsable') or '—'} · "
                    f"📅 Límite: {p.get('fecha_limite') or 'sin fecha'} · {numero_txt}reunión del {m.get('fecha_reunion') or '—'}"
                )
                seguimiento_previo = p.get("seguimiento") or []
                if seguimiento_previo:
                    with st.expander(f"📜 Historial de seguimiento ({len(seguimiento_previo)})"):
                        for s in seguimiento_previo:
                            st.caption(f"🕒 {(s.get('creado_en') or '')[:16].replace('T', ' ')} — **{s.get('autor_nombre')}**: {s.get('comentario')}")

                if puede_seguimiento:
                    with st.form(f"mn_seguimiento_{m['id']}_{i}"):
                        nuevo_estado = st.selectbox(
                            "Estado", ESTADOS_PENDIENTE_MINUTA,
                            index=ESTADOS_PENDIENTE_MINUTA.index(p.get("estado")) if p.get("estado") in ESTADOS_PENDIENTE_MINUTA else 0,
                            key=f"mn_estado_{m['id']}_{i}",
                        )
                        comentario_nuevo = st.text_input(
                            "Comentario de seguimiento (opcional)", key=f"mn_comentario_{m['id']}_{i}",
                            placeholder="Ej. Ya se coordinó con el proveedor, entrega la próxima semana.",
                        )
                        if st.form_submit_button("💾 Guardar seguimiento", use_container_width=True):
                            db.update_pendiente_minuta(
                                m["id"], i, estado=nuevo_estado, comentario=comentario_nuevo,
                                autor_nombre=user["nombre"],
                            )
                            st.success("Seguimiento guardado.")
                            st.rerun()

# --------------------------------------------------------------------------
# Minutas — historial de reuniones, con su checklist completo.
# --------------------------------------------------------------------------
with tab_minutas:
    if tienda_usuario:
        minutas = db.list_minutas_tiendas(tienda=tienda_usuario)
        st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
    else:
        elegido_tienda_m = st.selectbox("Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mn_lista_filtro_tienda")
        minutas = db.list_minutas_tiendas(tienda=None if elegido_tienda_m == "Todas" else elegido_tienda_m)

    if not minutas:
        st.caption("Todavía no hay minutas registradas.")
    else:
        download_excel_button(
            pd.DataFrame([{
                "N° Minuta": m.get("numero"), "Tienda": m.get("tienda"), "Fecha reunión": m.get("fecha_reunion"),
                "Elaborada por": m.get("creado_por_nombre"),
                "Temas tratados": len(m.get("checklist") or []),
                "Pendientes": len(m.get("pendientes") or []),
                "Pendientes resueltos": sum(1 for p in (m.get("pendientes") or []) if p.get("estado") == "Resuelto"),
            } for m in minutas]),
            "minutas_tienda.xlsx", key="mn_lista_descargar_excel",
        )

        for m in minutas:
            mid = m["id"]
            numero_txt = f"MIN-{m['numero']:04d}" if isinstance(m.get("numero"), int) else "—"
            puede_editar_esta = puede_seguimiento or (
                puede_crear and (user["rol"] == "admin" or m.get("creado_por_id") == user["id"])
            )
            with st.expander(f"🗒️ {numero_txt} — {m.get('tienda') or '—'} · {m.get('fecha_reunion') or '—'}"):
                st.caption(f"Elaborada por: {m.get('creado_por_nombre') or '—'}")

                checklist = m.get("checklist") or []
                if checklist:
                    st.markdown("**Temas tratados:**")
                    for item in checklist:
                        marca = "✅" if item.get("tratado", True) else "⏳"
                        linea = f"{marca} {item.get('tema')}"
                        if item.get("notas"):
                            linea += f" — _{item['notas']}_"
                        st.markdown(f"- {linea}")
                else:
                    st.caption("Sin temas registrados.")

                pendientes_m = m.get("pendientes") or []
                if pendientes_m:
                    st.markdown("**Pendientes:**")
                    for p in pendientes_m:
                        st.markdown(
                            f"- {_emoji_estado(p.get('estado'))} {p.get('descripcion')} "
                            f"(👤 {p.get('responsable') or '—'}, estado: {p.get('estado')})"
                        )
                else:
                    st.caption("Sin pendientes.")

                if puede_editar_esta:
                    st.divider()
                    if st.button("🗑️ Eliminar esta minuta", key=f"mn_eliminar_{mid}"):
                        db.delete_minuta_tienda(mid)
                        st.success("Minuta eliminada.")
                        st.rerun()

# --------------------------------------------------------------------------
# Nueva minuta
# --------------------------------------------------------------------------
with tab_nueva:
    if not puede_crear:
        st.info("Solo el jefe de tienda, sub jefe de tienda, jefe de línea y los administradores pueden crear minutas.")
    else:
        st.session_state.setdefault("mn_checklist_borrador", [])
        st.session_state.setdefault("mn_pendientes_borrador", [])

        if tienda_usuario:
            tienda_nueva = tienda_usuario
            st.caption(f"Tienda: **{tienda_usuario}**")
        else:
            tienda_nueva = st.selectbox("Tienda", TICKET_TIENDAS, key="mn_nueva_tienda")
        fecha_reunion = st.date_input("Fecha de la reunión", value=date.today(), key="mn_nueva_fecha")

        st.divider()
        st.markdown("#### ✅ Temas tratados en la reunión")
        # No se usa st.form aquí a propósito (ver nota más abajo, en
        # Pendientes, sobre por qué un campo condicionado por otro widget no
        # puede ir dentro de un form) — widgets sueltos + botón normal, y se
        # limpian del session_state después de agregar para que el campo
        # quede en blanco listo para el siguiente tema.
        colt1, colt2, colt3 = st.columns([3, 3, 1])
        tema_nuevo = colt1.text_input("Tema", key="mn_tema_input")
        notas_nuevo = colt2.text_input("Notas (opcional)", key="mn_notas_input")
        tratado_nuevo = colt3.checkbox("Tratado", value=True, key="mn_tratado_input")
        if st.button("➕ Agregar tema", key="mn_btn_agregar_tema", use_container_width=True):
            if not tema_nuevo.strip():
                st.error("Escribe el tema antes de agregarlo.")
            else:
                st.session_state["mn_checklist_borrador"].append(
                    {"tema": tema_nuevo.strip(), "notas": notas_nuevo.strip(), "tratado": tratado_nuevo}
                )
                st.session_state.pop("mn_tema_input", None)
                st.session_state.pop("mn_notas_input", None)
                st.rerun()

        if st.session_state["mn_checklist_borrador"]:
            for idx, item in enumerate(st.session_state["mn_checklist_borrador"]):
                c1, c2 = st.columns([6, 1])
                marca = "✅" if item.get("tratado", True) else "⏳"
                texto_item = f"{marca} {item['tema']}" + (f" — _{item['notas']}_" if item.get("notas") else "")
                c1.markdown(texto_item)
                if c2.button("🗑️", key=f"mn_quitar_tema_{idx}"):
                    st.session_state["mn_checklist_borrador"].pop(idx)
                    st.rerun()
        else:
            st.caption("Todavía no has agregado ningún tema.")

        st.divider()
        st.markdown("#### 📌 Pendientes que quedaron de la reunión")
        # Widgets sueltos, no un st.form: "Responsable" necesita revelar un
        # campo de texto en cuanto se elige "Escribir otro nombre", y eso
        # solo pasa con un rerun inmediato — dentro de un form los widgets
        # no reaccionan hasta que se presiona el botón de enviar, así que el
        # campo nuevo aparecería demasiado tarde para poder escribir en él.
        descripcion_nueva = st.text_input("¿Qué queda pendiente?", key="mn_pend_descripcion")
        colp1, colp2 = st.columns(2)
        opciones_resp = _opciones_responsable(tienda_nueva)
        responsable_sel = colp1.selectbox("Responsable", opciones_resp, key="mn_pend_responsable_sel")
        if responsable_sel == ESCRIBIR_RESPONSABLE_NUEVO:
            responsable_texto = colp1.text_input("Nombre del responsable", key="mn_pend_responsable_nuevo")
        else:
            responsable_texto = responsable_sel
        con_fecha = colp2.checkbox("Con fecha límite", key="mn_pend_con_fecha")
        fecha_limite_nueva = colp2.date_input("Fecha límite", value=date.today(), key="mn_pend_fecha_limite") if con_fecha else None
        if st.button("➕ Agregar pendiente", key="mn_btn_agregar_pendiente", use_container_width=True):
            if not descripcion_nueva.strip():
                st.error("Escribe qué queda pendiente antes de agregarlo.")
            else:
                st.session_state["mn_pendientes_borrador"].append({
                    "descripcion": descripcion_nueva.strip(),
                    "responsable": (responsable_texto or "").strip(),
                    "fecha_limite": str(fecha_limite_nueva) if fecha_limite_nueva else None,
                })
                for k in ("mn_pend_descripcion", "mn_pend_responsable_nuevo"):
                    st.session_state.pop(k, None)
                st.rerun()

        if st.session_state["mn_pendientes_borrador"]:
            for idx, p in enumerate(st.session_state["mn_pendientes_borrador"]):
                c1, c2 = st.columns([6, 1])
                texto_p = f"🔴 {p['descripcion']} (👤 {p.get('responsable') or '—'}"
                texto_p += f", límite {p['fecha_limite']})" if p.get("fecha_limite") else ")"
                c1.markdown(texto_p)
                if c2.button("🗑️", key=f"mn_quitar_pend_{idx}"):
                    st.session_state["mn_pendientes_borrador"].pop(idx)
                    st.rerun()
        else:
            st.caption("Todavía no has agregado ningún pendiente.")

        st.divider()
        if st.button("💾 Guardar minuta", key="mn_guardar_minuta", use_container_width=True):
            if not st.session_state["mn_checklist_borrador"] and not st.session_state["mn_pendientes_borrador"]:
                st.error("Agrega al menos un tema o un pendiente antes de guardar la minuta.")
            else:
                db.create_minuta_tienda(
                    user["id"], user["nombre"], tienda_nueva, fecha_reunion,
                    st.session_state["mn_checklist_borrador"], st.session_state["mn_pendientes_borrador"],
                )
                st.session_state["mn_checklist_borrador"] = []
                st.session_state["mn_pendientes_borrador"] = []
                st.success("Minuta guardada.")
                st.rerun()
