from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_RECLAMO
from utils import sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("⚠️ Reclamos")
st.caption("Cliente, número de orden, fecha de reclamo, fecha de solución y estatus.")

tab_lista, tab_nueva = st.tabs(["📋 Reclamos", "➕ Nuevo reclamo"])

with tab_lista:
    filtro_vendedor = vendedor_filter_selector(key="rec_filtro_vendedor")
    filtro_estado = st.multiselect("Filtrar por estatus", ESTADOS_RECLAMO, default=[])

    rows = db.list_reclamos(filtro_vendedor)
    if filtro_estado:
        rows = [r for r in rows if r["estatus"] in filtro_estado]

    if not rows:
        st.info("No hay reclamos registrados con estos filtros.")
    else:
        vendedores = db.list_usuarios()
        df = pd.DataFrame([{
            "ID": r["id"], "Cliente": r["cliente"], "NIT": r["nit"] or "—",
            "Nº orden": r["numero_orden"], "Fecha reclamo": r["fecha_reclamo"],
            "Fecha solución": r["fecha_solucion"] or "—", "Estatus": r["estatus"],
            "Vendedor": db.nombre_vendedor(r["vendedor_id"], vendedores),
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        puede_editar_completo = auth.can_edit()
        puede_cambiar_estado = puede_editar_completo or user["rol"] == "jefe_planta"

        if puede_cambiar_estado:
            st.markdown("#### ✏️ Actualizar estatus / fecha de solución")
            opciones = {f"{r['numero_orden'] or r['id']} — {r['cliente']}": r["id"] for r in rows}
            elegido = st.selectbox("Selecciona un reclamo", ["—"] + list(opciones.keys()))
            if elegido != "—":
                rid = opciones[elegido]
                rec = next(r for r in rows if r["id"] == rid)
                if user["rol"] == "vendedor" and rec["vendedor_id"] != user["id"]:
                    st.warning("Este reclamo pertenece a otro vendedor.")
                else:
                    with st.form(f"editar_rec_{rid}"):
                        estatus = st.selectbox("Estatus", ESTADOS_RECLAMO,
                                                index=ESTADOS_RECLAMO.index(rec["estatus"]))
                        tiene_solucion = estatus in ("Resuelto", "Cerrado")
                        fecha_solucion = st.date_input(
                            "Fecha de solución",
                            value=date.fromisoformat(rec["fecha_solucion"]) if rec["fecha_solucion"] else date.today(),
                            disabled=not tiene_solucion,
                        )
                        if puede_editar_completo:
                            descripcion = st.text_area("Descripción / notas", value=rec["descripcion"] or "")
                        else:
                            descripcion = rec["descripcion"]
                            st.caption(f"Descripción / notas: {descripcion or '—'}")

                        if puede_editar_completo:
                            colf1, colf2 = st.columns(2)
                            guardar = colf1.form_submit_button("Guardar", use_container_width=True)
                            eliminar = colf2.form_submit_button("Eliminar reclamo", use_container_width=True)
                        else:
                            guardar = st.form_submit_button("Guardar estado", use_container_width=True)
                            eliminar = False

                        if guardar:
                            db.update_reclamo(
                                rid, estatus=estatus,
                                fecha_solucion=str(fecha_solucion) if tiene_solucion else None,
                                descripcion=descripcion,
                            )
                            st.success("Reclamo actualizado.")
                            st.rerun()
                        if eliminar:
                            db.delete_reclamo(rid)
                            st.success("Reclamo eliminado.")
                            st.rerun()
        else:
            st.caption("Tu rol es de solo vista: puedes consultar pero no editar reclamos.")

with tab_nueva:
    if not auth.can_edit():
        st.info("Tu rol es de solo vista y no puede registrar reclamos.")
    else:
        with st.form("nuevo_rec_form", clear_on_submit=True):
            if user["rol"] == "admin":
                vendedores = db.list_vendedores()
                opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                vendedor_nombre = st.selectbox("Vendedor responsable", list(opciones_v.keys()))
                vendedor_id = opciones_v[vendedor_nombre]
            else:
                vendedor_id = user["id"]
                st.caption(f"Vendedor responsable: **{user['nombre']}**")

            cliente = st.text_input("Cliente")
            nit = st.text_input("NIT (opcional)")
            numero_orden = st.text_input("Número de orden")
            fecha_reclamo = st.date_input("Fecha del reclamo", value=date.today())
            estatus = st.selectbox("Estatus", ESTADOS_RECLAMO)
            descripcion = st.text_area("Descripción del reclamo")

            if st.form_submit_button("Registrar reclamo", use_container_width=True):
                if not cliente.strip() or not numero_orden.strip():
                    st.error("Cliente y número de orden son obligatorios.")
                else:
                    db.create_reclamo(cliente.strip(), nit.strip(), numero_orden.strip(),
                                       fecha_reclamo, estatus, descripcion, vendedor_id)
                    st.success("Reclamo registrado.")
                    st.rerun()
