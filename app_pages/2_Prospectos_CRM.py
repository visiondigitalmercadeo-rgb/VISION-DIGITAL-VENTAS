from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PROSPECTO
from utils import scope_vendedor_id, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("🧾 Prospección (CRM)")
st.caption("Nombre del cliente, datos de contacto, NIT, recordatorio y fecha de seguimiento.")

tab_lista, tab_nueva = st.tabs(["Mis prospectos" if user["rol"] == "vendedor" else "Listado", "➕ Nuevo prospecto"])

# --------------------------------------------------------------------------
# Listado
# --------------------------------------------------------------------------
with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="crm_filtro_vendedor")
    filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_PROSPECTO, default=[])

    rows = db.list_prospectos(filtro_vendedor)
    if filtro_estado:
        rows = [r for r in rows if r["estado"] in filtro_estado]

    if not rows:
        st.info("No hay prospectos registrados con estos filtros.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"],
            "Cliente": r["nombre_cliente"],
            "NIT": r["nit"],
            "Teléfono": r["telefono"],
            "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
            "Estado": r["estado"],
            "Registrado": r["fecha_registro"],
            "Seguimiento": r["fecha_seguimiento"],
            "Recordatorio": r["recordatorio"],
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        if auth.can_edit():
            st.markdown("#### ✏️ Editar / dar seguimiento")
            opciones = {f"{r['nombre_cliente']} — NIT {r['nit']}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona un prospecto", ["—"] + list(opciones.keys()))
            if elegido != "—":
                pid = opciones[elegido]
                p = db.get_prospecto(pid)
                if user["rol"] == "vendedor" and p["vendedor_id"] != user["id"]:
                    st.warning("Este prospecto pertenece a otro vendedor; no puedes editarlo.")
                else:
                    with st.form(f"editar_prospecto_{pid}"):
                        c0a, c0b = st.columns(2)
                        nombre_cliente_ed = c0a.text_input("Nombre del cliente / empresa", value=p["nombre_cliente"] or "")
                        nit_ed = c0b.text_input("NIT", value=p["nit"] or "")
                        c1, c2 = st.columns(2)
                        telefono = c1.text_input("Teléfono", value=p["telefono"] or "")
                        email = c2.text_input("Email", value=p["email"] or "")
                        direccion = st.text_input("Dirección", value=p["direccion"] or "")
                        c3, c4 = st.columns(2)
                        estado = c3.selectbox("Estado", ESTADOS_PROSPECTO,
                                               index=ESTADOS_PROSPECTO.index(p["estado"]) if p["estado"] in ESTADOS_PROSPECTO else 0)
                        fecha_seg = c4.date_input(
                            "Próxima fecha de seguimiento",
                            value=date.fromisoformat(p["fecha_seguimiento"]) if p["fecha_seguimiento"] else date.today(),
                        )
                        recordatorio = st.text_input("Recordatorio para el vendedor", value=p["recordatorio"] or "")
                        notas = st.text_area("Notas", value=p["notas"] or "")
                        if st.form_submit_button("Guardar cambios", use_container_width=True):
                            if not nombre_cliente_ed.strip() or not nit_ed.strip():
                                st.error("Nombre del cliente y NIT son obligatorios.")
                            else:
                                db.update_prospecto(
                                    pid, nombre_cliente=nombre_cliente_ed.strip(), nit=nit_ed.strip(),
                                    telefono=telefono, email=email, direccion=direccion,
                                    estado=estado, fecha_seguimiento=str(fecha_seg),
                                    recordatorio=recordatorio, notas=notas,
                                )
                                st.success("Prospecto actualizado.")
                                st.rerun()

                    with st.expander("🗑️ Eliminar este prospecto"):
                        st.caption(
                            "Esto elimina el prospecto por completo (no se puede deshacer). Las citas, "
                            "cotizaciones u otros registros que lo mencionen no se borran, solo dejan de "
                            "estar vinculados a él."
                        )
                        confirmar_borrar = st.checkbox("Confirmo que deseo eliminar este prospecto", key=f"conf_del_prospecto_{pid}")
                        if st.button("Eliminar prospecto", key=f"btn_del_prospecto_{pid}", disabled=not confirmar_borrar):
                            db.delete_prospecto(pid)
                            st.success("Prospecto eliminado.")
                            st.rerun()
        else:
            st.caption("Tu rol es de solo vista: puedes consultar pero no editar prospectos.")

# --------------------------------------------------------------------------
# Nuevo prospecto
# --------------------------------------------------------------------------
with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede crear prospectos nuevos.")
    else:
        st.markdown("Ingresa el **NIT** primero: si ya existe en la base de datos, se mostrará una alerta.")
        nit = st.text_input("NIT del cliente", key="nuevo_nit")
        if nit.strip():
            duplicados = db.find_prospectos_by_nit(nit)
            if duplicados:
                vendedores = db.list_usuarios()
                st.error(
                    f"⚠️ Este NIT ya existe en la base de datos ({len(duplicados)} registro(s)):"
                )
                for d in duplicados:
                    st.write(
                        f"- **{d['nombre_cliente']}** — estado *{d['estado']}* — "
                        f"vendedor: {db.nombre_vendedor(d['vendedor_id'], vendedores)}"
                    )

        with st.form("nuevo_prospecto_form", clear_on_submit=True):
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
            estado = c3.selectbox("Estado inicial", ESTADOS_PROSPECTO)
            fecha_seguimiento = c4.date_input("Fecha de seguimiento", value=date.today() + timedelta(days=3))
            recordatorio = st.text_input("Recordatorio para el vendedor (ej. 'Llamar para confirmar cotización')")
            notas = st.text_area("Notas adicionales")

            confirmar_duplicado = True
            nit_actual = st.session_state.get("nuevo_nit", "")
            if nit_actual.strip() and db.find_prospectos_by_nit(nit_actual):
                confirmar_duplicado = st.checkbox(
                    "Entiendo que este NIT ya existe y deseo registrarlo de todas formas "
                    "(por ejemplo, un nuevo contacto en la misma empresa)."
                )

            enviado = st.form_submit_button("Guardar prospecto", use_container_width=True)
            if enviado:
                nit_final = st.session_state.get("nuevo_nit", "").strip()
                if not nombre_cliente.strip() or not nit_final:
                    st.error("Nombre del cliente y NIT son obligatorios.")
                elif not confirmar_duplicado:
                    st.error("Debes confirmar que deseas continuar, ya que el NIT ya existe.")
                else:
                    db.create_prospecto(
                        nombre_cliente.strip(), nit_final, telefono, email, direccion,
                        vendedor_id, fecha_seguimiento, recordatorio, notas, estado,
                    )
                    st.success(f"Prospecto '{nombre_cliente}' guardado correctamente.")
                    st.rerun()
