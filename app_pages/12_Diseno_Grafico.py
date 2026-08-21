import base64
from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import DISENO_ARCHIVO_MAX_BYTES, ESTADOS_DISENO, ESTADOS_DISENO_INICIALES, LINEAS_VENTA
from utils import archivo_a_b64, diseno_pdf_bytes, download_excel_button, sidebar_user_box, vendedor_filter_selector

user = auth.current_user()
sidebar_user_box()

st.title("🎨 Diseño Gráfico — Nicolás")
st.caption(
    "Tablero de solicitudes de diseño, estilo Trello. El vendedor registra la solicitud (cae en la "
    "columna 'Lista de tareas' o 'Emergencias'); el diseñador la va moviendo por el tablero conforme avanza."
)

COLUMN_EMOJI = {
    "Lista de tareas": "📋", "Emergencias": "🚨", "En proceso": "🔧",
    "Cambios": "✏️", "Entregado": "✅",
}

puede_crear = user["rol"] in ("admin", "vendedor")
puede_mover = user["rol"] in ("admin", "disenador")

tab_tablero, tab_nueva = st.tabs(["🗂️ Tablero", "➕ Nueva solicitud"])

# --------------------------------------------------------------------------
# Tablero
# --------------------------------------------------------------------------
with tab_tablero:
    filtro_vendedor = vendedor_filter_selector(key="dis_filtro_vendedor")
    busqueda = st.text_input("🔎 Buscar por cliente o producto (opcional)", key="dis_busqueda")

    rows = db.list_disenos(filtro_vendedor)  # ya vienen ordenadas: más nueva primero
    if busqueda.strip():
        q = busqueda.strip().lower()
        rows = [
            r for r in rows
            if q in (r.get("cliente") or "").lower() or q in (r.get("producto") or "").lower()
        ]

    if rows:
        download_excel_button(
            pd.DataFrame([{
                "ID": r["id"], "Cliente": r.get("cliente"), "Producto": r.get("producto"),
                "Material": r.get("material"), "Acabado": r.get("acabado"), "Medida": r.get("medida"),
                "Fecha necesaria": r.get("fecha_necesaria"), "Estado": r.get("estado"),
                "Creado": r.get("creado_en"),
                "Vendedor": db.nombre_vendedor(r["vendedor_id"], db.list_usuarios()),
            } for r in rows]),
            "solicitudes_diseno.xlsx", key="dis_descargar_excel",
        )

    vendedores = db.list_usuarios()
    cols = st.columns(len(ESTADOS_DISENO))
    for col, estado in zip(cols, ESTADOS_DISENO):
        items = [r for r in rows if r.get("estado") == estado]
        with col:
            st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
            if not items:
                st.caption("Sin solicitudes.")
            for r in items:
                with st.container(border=True):
                    st.markdown(f"**{r.get('cliente') or 'Sin cliente'}**")
                    st.caption(r.get("producto") or "—")
                    st.caption(f"Vendedor: {db.nombre_vendedor(r['vendedor_id'], vendedores)}")
                    if r.get("fecha_necesaria"):
                        st.caption(f"📅 Necesita: {r['fecha_necesaria']}")
                    st.caption(f"🕒 {(r.get('creado_en') or '')[:16].replace('T', ' ')}")

                    pdf_bytes = diseno_pdf_bytes(r, db.nombre_vendedor(r["vendedor_id"], vendedores))
                    st.download_button(
                        "📄 PDF de la solicitud", data=pdf_bytes, file_name=f"solicitud_{r['id']}.pdf",
                        mime="application/pdf", use_container_width=True, key=f"dis_pdf_{r['id']}",
                    )
                    if r.get("archivo_b64"):
                        st.download_button(
                            f"📎 {r.get('archivo_nombre') or 'archivo adjunto'}",
                            data=base64.b64decode(r["archivo_b64"]),
                            file_name=r.get("archivo_nombre") or "archivo",
                            mime=r.get("archivo_tipo") or "application/octet-stream",
                            use_container_width=True, key=f"dis_file_{r['id']}",
                        )

    st.divider()

    # ----------------------------------------------------------------------
    # Gestionar una solicitud
    # ----------------------------------------------------------------------
    if puede_crear or puede_mover:
        st.markdown("#### ✏️ Gestionar una solicitud")
        if user["rol"] == "vendedor":
            gestionable = [r for r in rows if r["vendedor_id"] == user["id"]]
        else:
            gestionable = rows

        if not gestionable:
            st.caption("No hay solicitudes para gestionar con estos filtros.")
        else:
            opciones = {
                f"[{r['estado']}] {r.get('cliente') or 'Sin cliente'} — {r.get('producto') or ''}": r["id"]
                for r in gestionable
            }
            elegido = st.selectbox("Selecciona una solicitud", ["—"] + list(opciones.keys()), key="dis_gestionar_select")
            if elegido != "—":
                did = opciones[elegido]
                d = db.get_diseno(did)
                puede_editar_esta = puede_crear and (user["rol"] == "admin" or d["vendedor_id"] == user["id"])

                with st.form(f"gestionar_dis_{did}"):
                    if puede_editar_esta:
                        cliente_ed = st.text_input("Nombre del cliente", value=d.get("cliente") or "")
                        c1, c2 = st.columns(2)
                        producto_ed = c1.selectbox(
                            "¿Qué producto es?", LINEAS_VENTA,
                            index=LINEAS_VENTA.index(d["producto"]) if d.get("producto") in LINEAS_VENTA else 0,
                        )
                        material_ed = c2.text_input("¿Qué material es?", value=d.get("material") or "")
                        c3, c4 = st.columns(2)
                        acabado_ed = c3.text_input("¿Qué acabado lleva?", value=d.get("acabado") or "")
                        medida_ed = c4.text_input("Medida del material", value=d.get("medida") or "")
                        fecha_necesaria_ed = st.date_input(
                            "Fecha en que se necesita",
                            value=date.fromisoformat(d["fecha_necesaria"]) if d.get("fecha_necesaria") else date.today(),
                        )
                        nuevo_archivo = st.file_uploader(
                            "Reemplazar archivo adjunto (opcional)", type=["pdf", "png", "jpg", "jpeg"],
                            key=f"dis_archivo_ed_{did}",
                        )
                        st.caption(f"Tamaño máximo del archivo: {DISENO_ARCHIVO_MAX_BYTES // 1000} KB.")
                    else:
                        st.caption(f"Cliente: **{d.get('cliente') or '—'}**")
                        st.caption(
                            f"Producto: {d.get('producto') or '—'} · Material: {d.get('material') or '—'} · "
                            f"Acabado: {d.get('acabado') or '—'}"
                        )
                        st.caption(
                            f"Medida: {d.get('medida') or '—'} · Necesita para: {d.get('fecha_necesaria') or '—'}"
                        )

                    if puede_mover:
                        estado_ed = st.selectbox(
                            "Estado (columna del tablero)", ESTADOS_DISENO,
                            index=ESTADOS_DISENO.index(d["estado"]) if d.get("estado") in ESTADOS_DISENO else 0,
                        )
                    else:
                        estado_ed = d.get("estado")
                        st.caption(f"Estado actual: **{estado_ed}** — solo el diseñador o el administrador lo pueden mover.")

                    if puede_editar_esta:
                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("Guardar cambios", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar solicitud", use_container_width=True)
                    else:
                        guardar = st.form_submit_button("Guardar estado", use_container_width=True)
                        eliminar = False

                    if guardar:
                        error_msg = None
                        update_kwargs = {"estado": estado_ed}
                        if puede_editar_esta:
                            if not cliente_ed.strip():
                                error_msg = "El nombre del cliente es obligatorio."
                            else:
                                update_kwargs.update(
                                    cliente=cliente_ed.strip(), producto=producto_ed,
                                    material=material_ed.strip(), acabado=acabado_ed.strip(),
                                    medida=medida_ed.strip(), fecha_necesaria=str(fecha_necesaria_ed),
                                )
                                if nuevo_archivo is not None:
                                    try:
                                        nombre_a, tipo_a, b64_a = archivo_a_b64(nuevo_archivo, DISENO_ARCHIVO_MAX_BYTES)
                                        update_kwargs.update(
                                            archivo_nombre=nombre_a, archivo_tipo=tipo_a, archivo_b64=b64_a,
                                        )
                                    except ValueError as e:
                                        error_msg = str(e)
                        if error_msg:
                            st.error(error_msg)
                        else:
                            db.update_diseno(did, **update_kwargs)
                            st.success("Solicitud actualizada.")
                            st.rerun()
                    if eliminar:
                        db.delete_diseno(did)
                        st.success("Solicitud eliminada.")
                        st.rerun()
    else:
        st.caption("Tu rol es de solo vista para este tablero.")

# --------------------------------------------------------------------------
# Nueva solicitud
# --------------------------------------------------------------------------
with tab_nueva:
    if not puede_crear:
        st.info("Solo vendedores y administradores pueden crear solicitudes de diseño.")
    else:
        if user["rol"] == "admin":
            vendedores_activos = db.list_vendedores()
            opciones_v = {v["nombre"]: v["id"] for v in vendedores_activos}
            vendedor_nombre_sel = st.selectbox("Vendedor", list(opciones_v.keys()), key="dis_nuevo_vendedor")
            vendedor_id = opciones_v[vendedor_nombre_sel]
        else:
            vendedor_id = user["id"]
            st.caption(f"Vendedor: **{user['nombre']}**")

        with st.form("nueva_solicitud_diseno", clear_on_submit=True):
            tipo_solicitud = st.radio(
                "Tipo de solicitud", ESTADOS_DISENO_INICIALES, horizontal=True,
                help="'Emergencias' aparece en su propia columna del tablero para que el diseñador la vea primero.",
            )
            cliente = st.text_input("Nombre del cliente")
            c1, c2 = st.columns(2)
            producto = c1.selectbox("¿Qué producto es?", LINEAS_VENTA)
            material = c2.text_input("¿Qué material es?")
            c3, c4 = st.columns(2)
            acabado = c3.text_input("¿Qué acabado lleva?")
            medida = c4.text_input("Medida del material (ej. 21x29.7 cm)")
            fecha_necesaria = st.date_input("Fecha en que se necesita", value=date.today())
            archivo = st.file_uploader(
                "Adjuntar archivo de referencia (opcional) — PDF, PNG o JPEG",
                type=["pdf", "png", "jpg", "jpeg"],
            )
            st.caption(f"Tamaño máximo del archivo: {DISENO_ARCHIVO_MAX_BYTES // 1000} KB.")

            if st.form_submit_button("Enviar solicitud", use_container_width=True):
                if not cliente.strip():
                    st.error("El nombre del cliente es obligatorio.")
                else:
                    try:
                        archivo_nombre, archivo_tipo, archivo_b64 = archivo_a_b64(archivo, DISENO_ARCHIVO_MAX_BYTES)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        db.create_diseno(
                            vendedor_id, cliente.strip(), producto, material.strip(), acabado.strip(),
                            medida.strip(), fecha_necesaria, tipo_solicitud,
                            archivo_nombre=archivo_nombre, archivo_tipo=archivo_tipo, archivo_b64=archivo_b64,
                        )
                        st.success(f"Solicitud enviada a la columna '{tipo_solicitud}'.")
                        st.rerun()
