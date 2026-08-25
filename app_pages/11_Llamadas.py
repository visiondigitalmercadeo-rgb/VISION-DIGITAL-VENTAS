from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PROSPECTO, TIPOS_LLAMADA
from utils import (
    avatar_color_para, download_excel_button, iniciales_nombre, sidebar_user_box, vendedor_filter_selector,
)

user = auth.current_user()
sidebar_user_box()

st.title("📞 Llamadas")
st.caption("Registro de llamadas a clientes/prospectos: nombre, datos de contacto, NIT, recordatorio, "
           "fecha de seguimiento y si es llamada inicial o de seguimiento.")

ESTADO_EMOJI = {
    "Prospecto": "🔵", "En negociación": "🟠", "Cliente (Ganado)": "🟢", "Perdido": "🔴",
}


def _badge_seguimiento(fecha_str):
    """Etiqueta corta con semáforo según qué tan próxima (o vencida) está la
    fecha de seguimiento — para dar el vistazo rápido tipo CRM."""
    if not fecha_str:
        return None
    try:
        f = date.fromisoformat(fecha_str)
    except ValueError:
        return None
    dias = (f - date.today()).days
    if dias < 0:
        return f"🔴 Vencido — era el {fecha_str}"
    if dias == 0:
        return "🟠 Seguimiento: hoy"
    if dias <= 3:
        return f"🟡 Seguimiento: {fecha_str}"
    return f"🟢 Seguimiento: {fecha_str}"


tab_tablero, tab_nueva = st.tabs(["🗂️ Tablero", "➕ Nueva llamada"])

# --------------------------------------------------------------------------
# Tablero (mismo estilo tipo Pipedrive que la pestaña de Prospección)
# --------------------------------------------------------------------------
with tab_tablero:
    filtro_vendedor = vendedor_filter_selector(key="lla_filtro_vendedor")
    fb1, fb2 = st.columns([2, 1])
    busqueda = fb1.text_input("🔎 Buscar por cliente, NIT o teléfono (opcional)", key="lla_busqueda")
    filtro_tipo = fb2.multiselect("Tipo de llamada", TIPOS_LLAMADA, default=[], key="lla_filtro_tipo")

    rows = db.list_llamadas(filtro_vendedor)
    if busqueda.strip():
        q = busqueda.strip().lower()
        rows = [
            r for r in rows
            if q in (r.get("nombre_cliente") or "").lower()
            or q in (r.get("nit") or "").lower()
            or q in (r.get("telefono") or "").lower()
        ]
    if filtro_tipo:
        rows = [r for r in rows if r.get("tipo_llamada") in filtro_tipo]

    vendedores = db.list_usuarios()

    # ------------------------------------------------------------------
    # Resumen numérico rápido
    # ------------------------------------------------------------------
    en_negociacion = sum(1 for r in rows if r.get("estado") == "En negociación")
    ganados = sum(1 for r in rows if r.get("estado") == "Cliente (Ganado)")
    perdidos = sum(1 for r in rows if r.get("estado") == "Perdido")
    llamadas_iniciales = sum(1 for r in rows if r.get("tipo_llamada") == "Llamada inicial")
    llamadas_seguimiento = sum(1 for r in rows if r.get("tipo_llamada") == "Llamada de seguimiento")

    fila1 = st.columns(4)
    fila1[0].metric("Total llamadas", len(rows))
    fila1[1].metric("En negociación", en_negociacion)
    fila1[2].metric("Llamadas iniciales", llamadas_iniciales)
    fila1[3].metric("Llamadas de seguimiento", llamadas_seguimiento)

    fila2 = st.columns(4)
    fila2[0].metric("Clientes ganados", ganados)
    fila2[1].metric("Clientes perdidos", perdidos)

    if rows:
        df_export = pd.DataFrame([{
            "ID": r["id"], "Cliente": r["nombre_cliente"], "NIT": r["nit"], "Teléfono": r["telefono"],
            "Email": r.get("email"), "Tipo de llamada": r.get("tipo_llamada") or "—",
            "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
            "Estado": r["estado"], "Registrada": r["fecha_registro"], "Seguimiento": r["fecha_seguimiento"],
            "Recordatorio": r["recordatorio"],
        } for r in rows])
        download_excel_button(df_export, "llamadas.xlsx", key="lla_descargar_excel")

    st.divider()

    if not auth.can_edit():
        st.caption("Tu rol es de solo vista: puedes consultar pero no editar llamadas.")

    if not rows:
        st.info("No hay llamadas registradas con estos filtros.")
    else:
        cols = st.columns(len(ESTADOS_PROSPECTO))
        for col, estado in zip(cols, ESTADOS_PROSPECTO):
            items = [r for r in rows if r.get("estado") == estado]
            items_ordenados = sorted(items, key=lambda x: x.get("fecha_seguimiento") or "9999-99-99")
            with col:
                st.markdown(f"##### {ESTADO_EMOJI.get(estado, '')} {estado} ({len(items)})")
                if not items_ordenados:
                    st.caption("Sin llamadas.")
                for r in items_ordenados:
                    with st.container(border=True):
                        lid = r["id"]
                        editando_key = f"lla_editando_{lid}"
                        puede_editar_este = auth.can_edit() and (
                            user["rol"] != "vendedor" or r["vendedor_id"] == user["id"]
                        )

                        nombre_vend = db.nombre_vendedor(r["vendedor_id"], vendedores)
                        av_bg = avatar_color_para(nombre_vend)
                        iniciales = iniciales_nombre(nombre_vend)
                        title_col, edit_col = st.columns([5, 1])
                        with title_col:
                            st.markdown(
                                "<div style='display:flex;align-items:center;gap:8px;margin-bottom:4px;'>"
                                f"<span style='width:22px;height:22px;border-radius:50%;background:{av_bg};"
                                "color:white;font-size:0.65rem;font-weight:700;display:flex;align-items:center;"
                                f"justify-content:center;flex-shrink:0;' title='{nombre_vend}'>{iniciales}</span>"
                                f"<span style='font-weight:600;'>{r['nombre_cliente']}</span></div>",
                                unsafe_allow_html=True,
                            )
                        with edit_col:
                            if puede_editar_este:
                                if st.button("✏️", key=f"lla_editar_{lid}", help="Editar esta llamada"):
                                    st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                    st.rerun()
                        st.caption(f"👤 Vendedor: {nombre_vend}")
                        if r.get("tipo_llamada"):
                            st.caption(f"📞 {r['tipo_llamada']}")
                        contacto = " · ".join(x for x in [r.get("telefono"), r.get("email")] if x)
                        if contacto:
                            st.caption(contacto)
                        badge = _badge_seguimiento(r.get("fecha_seguimiento"))
                        if badge:
                            st.caption(badge)
                        if r.get("recordatorio"):
                            st.caption(f"📝 {r['recordatorio']}")
                        if r.get("motivo_perdida"):
                            st.caption(f"❌ Motivo: {r['motivo_perdida']}")

                        if puede_editar_este and st.session_state.get(editando_key):
                            # ------------------------------------------------
                            # Edición en línea (se abrió con el lápiz ✏️)
                            # ------------------------------------------------
                            with st.form(f"editar_llamada_{lid}"):
                                c0a, c0b = st.columns(2)
                                nombre_cliente_ed = c0a.text_input(
                                    "Nombre del cliente / empresa", value=r["nombre_cliente"] or "",
                                )
                                nit_ed = c0b.text_input("NIT", value=r["nit"] or "")
                                c1, c2 = st.columns(2)
                                telefono_ed = c1.text_input("Teléfono", value=r["telefono"] or "")
                                email_ed = c2.text_input("Email", value=r["email"] or "")
                                direccion_ed = st.text_input("Dirección", value=r["direccion"] or "")
                                c3, c4 = st.columns(2)
                                tipo_llamada_ed = c3.selectbox(
                                    "Tipo de llamada", TIPOS_LLAMADA,
                                    index=TIPOS_LLAMADA.index(r["tipo_llamada"]) if r.get("tipo_llamada") in TIPOS_LLAMADA else 0,
                                )
                                estado_ed = c4.selectbox(
                                    "Estado (columna del tablero)", ESTADOS_PROSPECTO,
                                    index=ESTADOS_PROSPECTO.index(r["estado"]) if r["estado"] in ESTADOS_PROSPECTO else 0,
                                )
                                fecha_seg_ed = st.date_input(
                                    "Próxima fecha de seguimiento",
                                    value=date.fromisoformat(r["fecha_seguimiento"]) if r["fecha_seguimiento"] else date.today(),
                                )
                                recordatorio_ed = st.text_input("Recordatorio para el vendedor", value=r["recordatorio"] or "")
                                notas_ed = st.text_area("Notas", value=r["notas"] or "")
                                colg1, colg2 = st.columns(2)
                                guardar = colg1.form_submit_button("💾 Guardar", use_container_width=True)
                                cancelar = colg2.form_submit_button("Cancelar", use_container_width=True)
                                if guardar:
                                    if not nombre_cliente_ed.strip() or not nit_ed.strip():
                                        st.error("Nombre del cliente y NIT son obligatorios.")
                                    else:
                                        db.update_llamada(
                                            lid, nombre_cliente=nombre_cliente_ed.strip(), nit=nit_ed.strip(),
                                            telefono=telefono_ed, email=email_ed, direccion=direccion_ed,
                                            tipo_llamada=tipo_llamada_ed, estado=estado_ed,
                                            fecha_seguimiento=str(fecha_seg_ed),
                                            recordatorio=recordatorio_ed, notas=notas_ed,
                                        )
                                        st.session_state.pop(editando_key, None)
                                        st.success("Llamada actualizada.")
                                        st.rerun()
                                if cancelar:
                                    st.session_state.pop(editando_key, None)
                                    st.rerun()

                            with st.expander("🗑️ Eliminar esta llamada"):
                                st.caption("Esto elimina el registro de la llamada por completo (no se puede deshacer).")
                                confirmar_borrar = st.checkbox(
                                    "Confirmo que deseo eliminar esta llamada", key=f"conf_del_llamada_{lid}",
                                )
                                if st.button(
                                    "Eliminar llamada", key=f"btn_del_llamada_{lid}", disabled=not confirmar_borrar,
                                ):
                                    db.delete_llamada(lid)
                                    st.session_state.pop(editando_key, None)
                                    st.success("Llamada eliminada.")
                                    st.rerun()
                        else:
                            # ------------------------------------------------
                            # Vista normal: acciones rápidas de la tarjeta
                            # ------------------------------------------------
                            if auth.can_edit() and estado == "Prospecto":
                                if st.button(
                                    "➡️ Mover a En negociación", key=f"lla_avanzar_{r['id']}", use_container_width=True,
                                ):
                                    db.update_llamada(r["id"], estado="En negociación")
                                    st.rerun()
                            elif auth.can_edit() and estado == "En negociación":
                                perdiendo_key = f"lla_perdiendo_{r['id']}"
                                if st.session_state.get(perdiendo_key):
                                    motivo = st.text_area(
                                        "¿Por qué se perdió?", key=f"lla_motivo_{r['id']}", height=80,
                                    )
                                    cc1, cc2 = st.columns(2)
                                    if cc1.button(
                                        "Confirmar", key=f"lla_confirmar_perdida_{r['id']}", use_container_width=True,
                                    ):
                                        db.update_llamada(
                                            r["id"], estado="Perdido", motivo_perdida=motivo.strip() or None,
                                        )
                                        st.session_state.pop(perdiendo_key, None)
                                        st.rerun()
                                    if cc2.button(
                                        "Cancelar", key=f"lla_cancelar_perdida_{r['id']}", use_container_width=True,
                                    ):
                                        st.session_state.pop(perdiendo_key, None)
                                        st.rerun()
                                else:
                                    bc1, bc2 = st.columns(2)
                                    if bc1.button(
                                        "✅ Ganado", key=f"lla_ganado_{r['id']}", use_container_width=True,
                                    ):
                                        db.update_llamada(r["id"], estado="Cliente (Ganado)")
                                        st.rerun()
                                    if bc2.button(
                                        "❌ Perdido", key=f"lla_perdido_{r['id']}", use_container_width=True,
                                    ):
                                        st.session_state[perdiendo_key] = True
                                        st.rerun()

    # ----------------------------------------------------------------------
    # Ver también como tabla (para quienes prefieren la vista de lista)
    # ----------------------------------------------------------------------
    with st.expander("📋 Ver también como tabla"):
        filtro_estado_tabla = st.multiselect("Filtrar por estado", ESTADOS_PROSPECTO, default=[], key="lla_filtro_estado_tabla")
        rows_tabla = rows if not filtro_estado_tabla else [r for r in rows if r["estado"] in filtro_estado_tabla]
        if not rows_tabla:
            st.info("No hay llamadas registradas con estos filtros.")
        else:
            df = pd.DataFrame([{
                "ID": r["id"], "Cliente": r["nombre_cliente"], "NIT": r["nit"], "Teléfono": r["telefono"],
                "Tipo de llamada": r.get("tipo_llamada") or "—",
                "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores), "Estado": r["estado"],
                "Registrada": r["fecha_registro"], "Seguimiento": r["fecha_seguimiento"],
                "Recordatorio": r["recordatorio"],
            } for r in rows_tabla])
            st.dataframe(df, use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------
# Nueva llamada
# --------------------------------------------------------------------------
with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede registrar llamadas nuevas.")
    else:
        st.markdown("Ingresa el **NIT** primero: si ya existe en la base de datos, se mostrará una alerta.")
        nit = st.text_input("NIT del cliente", key="nueva_llamada_nit")
        if nit.strip():
            duplicados = db.find_llamadas_by_nit(nit)
            if duplicados:
                vendedores = db.list_usuarios()
                st.info(
                    f"ℹ️ Ya existen {len(duplicados)} llamada(s) registradas con este NIT:"
                )
                for d in duplicados:
                    st.write(
                        f"- **{d['nombre_cliente']}** — {d.get('tipo_llamada') or ''} — estado *{d['estado']}* — "
                        f"vendedor: {db.nombre_vendedor(d['vendedor_id'], vendedores)}"
                    )

        with st.form("nueva_llamada_form", clear_on_submit=True):
            nombre_cliente = st.text_input("Nombre del cliente / empresa")
            c1, c2 = st.columns(2)
            telefono = c1.text_input("Teléfono")
            email = c2.text_input("Email")
            direccion = st.text_input("Dirección")

            if user["rol"] == "admin":
                vendedores = db.list_vendedores()
                opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                vendedor_nombre = st.selectbox("Asignar a vendedor", list(opciones_v.keys()))
                vendedor_id = opciones_v[vendedor_nombre]
            else:
                vendedor_id = user["id"]
                st.caption(f"Se asignará a ti: **{user['nombre']}**")

            c3, c4 = st.columns(2)
            tipo_llamada = c3.selectbox("Tipo de llamada", TIPOS_LLAMADA)
            estado = c4.selectbox("Estado inicial", ESTADOS_PROSPECTO)
            fecha_seguimiento = st.date_input("Fecha de seguimiento", value=date.today() + timedelta(days=3))
            recordatorio = st.text_input("Recordatorio para el vendedor (ej. 'Llamar para confirmar cotización')")
            notas = st.text_area("Notas adicionales")

            enviado = st.form_submit_button("Guardar llamada", use_container_width=True)
            if enviado:
                nit_final = st.session_state.get("nueva_llamada_nit", "").strip()
                if not nombre_cliente.strip() or not nit_final:
                    st.error("Nombre del cliente y NIT son obligatorios.")
                else:
                    db.create_llamada(
                        nombre_cliente.strip(), nit_final, telefono, email, direccion,
                        vendedor_id, fecha_seguimiento, recordatorio, notas, estado, tipo_llamada,
                    )
                    st.success(f"Llamada con '{nombre_cliente}' guardada correctamente.")
                    st.rerun()
