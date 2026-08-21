from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PROSPECTO, TIPOS_LLAMADA
from utils import download_excel_button, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("📞 Llamadas")
st.caption("Registro de llamadas a clientes/prospectos: nombre, datos de contacto, NIT, recordatorio, "
           "fecha de seguimiento y si es llamada inicial o de seguimiento.")

tab_lista, tab_nueva = st.tabs(["Mis llamadas" if user["rol"] == "vendedor" else "Listado", "➕ Nueva llamada"])

# --------------------------------------------------------------------------
# Listado
# --------------------------------------------------------------------------
with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="lla_filtro_vendedor")
    c1, c2 = st.columns(2)
    filtro_tipo = c1.multiselect("Filtrar por tipo de llamada", TIPOS_LLAMADA, default=[])
    filtro_estado = c2.multiselect("Filtrar por estado", ESTADOS_PROSPECTO, default=[])

    rows = db.list_llamadas(filtro_vendedor)
    if filtro_tipo:
        rows = [r for r in rows if r["tipo_llamada"] in filtro_tipo]
    if filtro_estado:
        rows = [r for r in rows if r["estado"] in filtro_estado]

    if not rows:
        st.info("No hay llamadas registradas con estos filtros.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"],
            "Cliente": r["nombre_cliente"],
            "NIT": r["nit"],
            "Teléfono": r["telefono"],
            "Tipo de llamada": r.get("tipo_llamada") or "—",
            "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
            "Estado": r["estado"],
            "Registrada": r["fecha_registro"],
            "Seguimiento": r["fecha_seguimiento"],
            "Recordatorio": r["recordatorio"],
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "llamadas.xlsx", key="lla_descargar_excel")

        if auth.can_edit():
            st.markdown("#### ✏️ Editar / dar seguimiento")
            opciones = {f"{r['nombre_cliente']} — NIT {r['nit']} — {r.get('tipo_llamada') or ''}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona una llamada", ["—"] + list(opciones.keys()))
            if elegido != "—":
                lid = opciones[elegido]
                l = db.get_llamada(lid)
                if user["rol"] == "vendedor" and l["vendedor_id"] != user["id"]:
                    st.warning("Esta llamada pertenece a otro vendedor; no puedes editarla.")
                else:
                    with st.form(f"editar_llamada_{lid}"):
                        c0a, c0b = st.columns(2)
                        nombre_cliente_ed = c0a.text_input("Nombre del cliente / empresa", value=l["nombre_cliente"] or "")
                        nit_ed = c0b.text_input("NIT", value=l["nit"] or "")
                        c1, c2 = st.columns(2)
                        telefono = c1.text_input("Teléfono", value=l["telefono"] or "")
                        email = c2.text_input("Email", value=l["email"] or "")
                        direccion = st.text_input("Dirección", value=l["direccion"] or "")
                        c3, c4 = st.columns(2)
                        tipo_llamada_ed = c3.selectbox(
                            "Tipo de llamada", TIPOS_LLAMADA,
                            index=TIPOS_LLAMADA.index(l["tipo_llamada"]) if l.get("tipo_llamada") in TIPOS_LLAMADA else 0,
                        )
                        estado = c4.selectbox("Estado", ESTADOS_PROSPECTO,
                                               index=ESTADOS_PROSPECTO.index(l["estado"]) if l["estado"] in ESTADOS_PROSPECTO else 0)
                        fecha_seg = st.date_input(
                            "Próxima fecha de seguimiento",
                            value=date.fromisoformat(l["fecha_seguimiento"]) if l["fecha_seguimiento"] else date.today(),
                        )
                        recordatorio = st.text_input("Recordatorio para el vendedor", value=l["recordatorio"] or "")
                        notas = st.text_area("Notas", value=l["notas"] or "")
                        if st.form_submit_button("Guardar cambios", use_container_width=True):
                            if not nombre_cliente_ed.strip() or not nit_ed.strip():
                                st.error("Nombre del cliente y NIT son obligatorios.")
                            else:
                                db.update_llamada(
                                    lid, nombre_cliente=nombre_cliente_ed.strip(), nit=nit_ed.strip(),
                                    telefono=telefono, email=email, direccion=direccion,
                                    tipo_llamada=tipo_llamada_ed, estado=estado,
                                    fecha_seguimiento=str(fecha_seg),
                                    recordatorio=recordatorio, notas=notas,
                                )
                                st.success("Llamada actualizada.")
                                st.rerun()

                    with st.expander("🗑️ Eliminar esta llamada"):
                        st.caption("Esto elimina el registro de la llamada por completo (no se puede deshacer).")
                        confirmar_borrar = st.checkbox("Confirmo que deseo eliminar esta llamada", key=f"conf_del_llamada_{lid}")
                        if st.button("Eliminar llamada", key=f"btn_del_llamada_{lid}", disabled=not confirmar_borrar):
                            db.delete_llamada(lid)
                            st.success("Llamada eliminada.")
                            st.rerun()
        else:
            st.caption("Tu rol es de solo vista: puedes consultar pero no editar llamadas.")

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
