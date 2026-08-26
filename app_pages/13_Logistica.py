import base64
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import (
    ESTADOS_PEDIDO, ESTADOS_RUTA_EXTRA, FRANJAS_PEDIDO, PEDIDO_FOTO_ENTREGA_MAX_BYTES, TIPOS_RUTA_PEDIDO,
    ZONAS_CAPITAL,
)
from utils import archivo_a_b64, download_excel_button, pedido_pdf_bytes, sidebar_user_box

user = auth.current_user()
rol = user["rol"]
sidebar_user_box()

hoy = date.today()
manana = hoy + timedelta(days=1)

st.title("🚚 Logística — Ruta de reparto")
st.caption(
    "El jefe de logística ingresa los pedidos AM/PM de cada día y asigna un repartidor. "
    "Repartidores y jefe de logística van marcando el estado durante el día; vendedores solo consultan."
)

ESTADO_EMOJI = {"Pendiente": "⚪", "En ruta": "🔵", "Entregado": "🟢", "No entregado": "🔴"}
_MESES_LABEL = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
}


def _label_mes(mes_iso):
    if not mes_iso or "-" not in mes_iso:
        return mes_iso or "—"
    y, m = mes_iso.split("-")
    return f"{_MESES_LABEL.get(m, m)} {y}"


RUTA_EXTRA_CONFIG = {
    "Compras": {
        "icono": "🛒", "label_empresa": "Empresa que visitan", "label_desc": "Descripción de la compra",
    },
    "Trámites": {
        "icono": "📋", "label_empresa": "Empresa que visita", "label_desc": "Descripción del trámite",
    },
    "Papelería": {
        "icono": "📨", "label_empresa": "Departamento o empresa", "label_desc": "Descripción de qué se envió",
    },
}


def _combinar_vendedores(*listas):
    """Combina varias listas de vendedores (usuarios con rol 'vendedor' +
    la lista adicional de Logística) quitando duplicados por nombre — si la
    misma persona aparece en más de una lista (por ejemplo porque ya tenía
    usuario y además se agregó a la lista adicional), se queda con la
    primera aparición, así que los usuarios con acceso al sistema tienen
    prioridad sobre la lista adicional."""
    vistos = set()
    combinados = []
    for lista in listas:
        for v in lista:
            clave = (v.get("nombre") or "").strip().lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            combinados.append(v)
    return combinados

puede_crear = rol in ("admin", "jefe_logistica")
puede_cambiar_estado = rol in ("admin", "jefe_logistica", "repartidor")


def _mostrar_foto_entrega(p):
    """Muestra la foto de comprobante de entrega del pedido, si tiene una."""
    b64 = p.get("foto_entrega_b64")
    if not b64:
        return
    st.caption("📸 Foto de entrega:")
    try:
        st.image(base64.b64decode(b64), width=220)
    except Exception:
        st.caption("(no se pudo mostrar la foto — el archivo podría estar dañado)")


def _productos_column_config():
    return {
        "Cantidad": st.column_config.TextColumn("Cantidad", width="small"),
        "Descripción": st.column_config.TextColumn("Descripción", width="large"),
    }


def _productos_df_inicial(p):
    """DataFrame inicial para la tabla de productos (cantidad + descripción)
    al abrir el formulario de edición — usa la lista 'productos' si el
    pedido ya la tiene, o arma una sola fila a partir del campo 'producto'
    (texto simple, forma antigua) para no perder datos de pedidos viejos."""
    productos = p.get("productos") or []
    if productos:
        return pd.DataFrame([
            {"Cantidad": it.get("cantidad") or "", "Descripción": it.get("descripcion") or ""}
            for it in productos
        ])
    if p.get("producto"):
        return pd.DataFrame([{"Cantidad": "", "Descripción": p["producto"]}])
    return pd.DataFrame([{"Cantidad": "", "Descripción": ""}])


def _productos_desde_editor(df):
    """Convierte la tabla editada (columnas 'Cantidad' y 'Descripción') a
    (lista_productos, resumen_en_una_línea) — la lista completa se guarda
    para el PDF de envío (varias filas), y el resumen es lo que siguen
    mostrando las tarjetas y el reporte Excel (una sola línea por pedido)."""
    productos = []
    for _, fila in df.iterrows():
        cantidad = str(fila.get("Cantidad") or "").strip()
        descripcion = str(fila.get("Descripción") or "").strip()
        if cantidad or descripcion:
            productos.append({"cantidad": cantidad, "descripcion": descripcion})
    resumen = "; ".join(
        f"{it['cantidad']} x {it['descripcion']}" if it["cantidad"] and it["descripcion"]
        else (it["descripcion"] or it["cantidad"])
        for it in productos
    )
    return productos, (resumen or None)


def _render_confirmar_entrega(p, siguiente, cancelar_key):
    """Panel que se abre al intentar marcar un pedido como 'Entregado' desde
    el rol repartidor — exige una foto de comprobante antes de poder
    confirmar, tomada con la cámara del dispositivo o subida de archivos."""
    pid = p["id"]
    st.caption("📸 Antes de confirmar la entrega, sube una foto como comprobante.")
    origen = st.radio(
        "¿Cómo quieres agregar la foto?", ["📷 Tomar foto ahora", "📁 Subir desde mis archivos"],
        key=f"log_foto_origen_{pid}", horizontal=True,
    )
    if origen == "📷 Tomar foto ahora":
        foto = st.camera_input("Foto del pedido entregado", key=f"log_foto_camara_{pid}")
    else:
        foto = st.file_uploader(
            "Foto del pedido entregado", type=["jpg", "jpeg", "png"], key=f"log_foto_archivo_{pid}",
        )

    colc1, colc2 = st.columns(2)
    confirmar = colc1.button("✅ Confirmar entrega", key=f"log_confirmar_entrega_{pid}", use_container_width=True)
    cancelar = colc2.button("Cancelar", key=f"log_cancelar_entrega_{pid}", use_container_width=True)

    if confirmar:
        if foto is None:
            st.error("Debes tomar o subir una foto para confirmar la entrega.")
        else:
            try:
                nombre, tipo, b64 = archivo_a_b64(foto, PEDIDO_FOTO_ENTREGA_MAX_BYTES)
            except ValueError as e:
                st.error(str(e))
            else:
                db.update_pedido(
                    pid, estado=siguiente,
                    foto_entrega_nombre=nombre, foto_entrega_tipo=tipo, foto_entrega_b64=b64,
                )
                st.session_state.pop(cancelar_key, None)
                st.success("Pedido marcado como entregado.")
                st.rerun()
    if cancelar:
        st.session_state.pop(cancelar_key, None)
        st.rerun()


def _render_pedido_edit_form(p, editando_key, vendedores_op, repartidores_op, lookup_vendedores, todos_usuarios):
    """Formulario de edición en línea del pedido (se abre con el lápiz ✏️ de
    la tarjeta) — mismo patrón que el lápiz de Prospección. Solo se llama
    para jefe de logística y admin (puede_crear)."""
    pid = p["id"]
    with st.form(f"log_editar_form_{pid}"):
        c1, c2 = st.columns(2)
        cliente_ed = c1.text_input("Nombre del cliente", value=p.get("cliente") or "")
        direccion_ed = c2.text_input("Área/Departamento", value=p.get("direccion") or "")
        c3, c4 = st.columns(2)
        atencion_a_ed = c3.text_input("Atención a (opcional)", value=p.get("atencion_a") or "")
        zona_ed = c4.selectbox(
            "Zona", ZONAS_CAPITAL,
            index=ZONAS_CAPITAL.index(p["zona"]) if p.get("zona") in ZONAS_CAPITAL else 0,
        )
        c5, c6 = st.columns(2)
        franja_ed = c5.selectbox(
            "Franja", FRANJAS_PEDIDO,
            index=FRANJAS_PEDIDO.index(p["franja"]) if p.get("franja") in FRANJAS_PEDIDO else 0,
        )
        numero_orden_ed = c6.text_input("N° orden/factura", value=p.get("numero_orden") or "")
        fecha_ed = st.date_input(
            "Fecha de entrega",
            value=date.fromisoformat(p["fecha"]) if p.get("fecha") else date.today(),
        )
        tipo_ruta_ed = st.selectbox(
            "Tipo de ruta", TIPOS_RUTA_PEDIDO,
            index=TIPOS_RUTA_PEDIDO.index(p["tipo_ruta"]) if p.get("tipo_ruta") in TIPOS_RUTA_PEDIDO else 0,
        )
        st.caption("Productos del envío (cantidad + descripción) — agrega o quita filas con el ➕ / 🗑️ de la tabla.")
        productos_df_ed = st.data_editor(
            _productos_df_inicial(p), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config=_productos_column_config(), key=f"log_productos_ed_{pid}",
        )
        nombre_vendedor_actual = db.nombre_vendedor(p.get("vendedor_id"), lookup_vendedores)
        c7, c8 = st.columns(2)
        vendedor_nombre_ed = c7.selectbox(
            "Vendedor", list(vendedores_op.keys()),
            index=list(vendedores_op.keys()).index(nombre_vendedor_actual)
            if nombre_vendedor_actual in vendedores_op else 0,
        )
        nombre_repartidor_actual = db.nombre_vendedor(p.get("repartidor_id"), todos_usuarios)
        repartidor_nombre_ed = c8.selectbox(
            "Repartidor asignado", list(repartidores_op.keys()),
            index=list(repartidores_op.keys()).index(nombre_repartidor_actual)
            if nombre_repartidor_actual in repartidores_op else 0,
        )
        notas_ed = st.text_area(
            "Notas", value=p.get("notas") or "",
            help="Por ejemplo, el motivo si el pedido no se pudo entregar.",
        )
        colg1, colg2 = st.columns(2)
        guardar = colg1.form_submit_button("💾 Guardar", use_container_width=True)
        cancelar = colg2.form_submit_button("Cancelar", use_container_width=True)
        if guardar:
            if not cliente_ed.strip() or not direccion_ed.strip():
                st.error("El nombre del cliente y el área/departamento son obligatorios.")
            else:
                productos_ed, resumen_ed = _productos_desde_editor(productos_df_ed)
                db.update_pedido(
                    pid, cliente=cliente_ed.strip(), direccion=direccion_ed.strip(),
                    atencion_a=atencion_a_ed.strip() or None,
                    zona=zona_ed, franja=franja_ed, producto=resumen_ed, productos=productos_ed,
                    numero_orden=numero_orden_ed.strip(), fecha=str(fecha_ed),
                    tipo_ruta=tipo_ruta_ed,
                    vendedor_id=vendedores_op.get(vendedor_nombre_ed),
                    repartidor_id=repartidores_op.get(repartidor_nombre_ed),
                    notas=notas_ed.strip() or None,
                )
                st.session_state.pop(editando_key, None)
                st.success("Pedido actualizado.")
                st.rerun()
        if cancelar:
            st.session_state.pop(editando_key, None)
            st.rerun()

    with st.expander("🗑️ Eliminar este pedido"):
        st.caption("Esto elimina el pedido por completo de la ruta (no se puede deshacer).")
        confirmar_borrar = st.checkbox(
            "Confirmo que deseo eliminar este pedido", key=f"log_conf_del_{pid}",
        )
        if st.button("Eliminar pedido", key=f"log_btn_del_{pid}", disabled=not confirmar_borrar):
            db.delete_pedido(pid)
            st.session_state.pop(editando_key, None)
            st.success("Pedido eliminado.")
            st.rerun()


def _render_editar_ruta_extra(r, cfg, editando_key):
    """Formulario de edición en línea (lápiz ✏️) de un registro de Compras/
    Trámites/Papelería — mismo patrón que el resto de Logística. Solo se
    llama para jefe de logística y admin (puede_crear)."""
    rid = r["id"]
    with st.form(f"editar_ruta_extra_{rid}"):
        fecha_ed = st.date_input(
            "Fecha", value=date.fromisoformat(r["fecha"]) if r.get("fecha") else date.today(),
        )
        empresa_ed = st.text_input(cfg["label_empresa"], value=r.get("empresa") or "")
        descripcion_ed = st.text_area(cfg["label_desc"], value=r.get("descripcion") or "")
        repartidores_op_re = {rp["nombre"]: rp["id"] for rp in db.list_repartidores(solo_activos=False)}
        nombre_actual_re = db.nombre_vendedor(r.get("repartidor_id"), todos_usuarios)
        repartidor_nombre_ed = st.selectbox(
            "Repartidor asignado", list(repartidores_op_re.keys()),
            index=list(repartidores_op_re.keys()).index(nombre_actual_re)
            if nombre_actual_re in repartidores_op_re else 0,
        )
        estado_ed = st.selectbox(
            "Estado", ESTADOS_RUTA_EXTRA,
            index=ESTADOS_RUTA_EXTRA.index(r["estado"]) if r.get("estado") in ESTADOS_RUTA_EXTRA else 0,
        )
        colg1, colg2 = st.columns(2)
        guardar = colg1.form_submit_button("💾 Guardar", use_container_width=True)
        cancelar = colg2.form_submit_button("Cancelar", use_container_width=True)
        if guardar:
            if not empresa_ed.strip() or not descripcion_ed.strip():
                st.error(f"{cfg['label_empresa']} y la descripción son obligatorios.")
            else:
                db.update_ruta_extra(
                    rid, fecha=str(fecha_ed), empresa=empresa_ed.strip(), descripcion=descripcion_ed.strip(),
                    repartidor_id=repartidores_op_re.get(repartidor_nombre_ed), estado=estado_ed,
                )
                st.session_state.pop(editando_key, None)
                st.success("Registro actualizado.")
                st.rerun()
        if cancelar:
            st.session_state.pop(editando_key, None)
            st.rerun()

    with st.expander("🗑️ Eliminar este registro"):
        st.caption("Esto elimina el registro por completo (no se puede deshacer).")
        confirmar_borrar_re = st.checkbox(
            "Confirmo que deseo eliminar este registro", key=f"re_conf_del_{rid}",
        )
        if st.button("Eliminar registro", key=f"re_btn_del_{rid}", disabled=not confirmar_borrar_re):
            db.delete_ruta_extra(rid)
            st.session_state.pop(editando_key, None)
            st.success("Registro eliminado.")
            st.rerun()


def _render_ruta_extra_tab(tipo):
    """Pestaña sencilla de Compras/Trámites/Papelería: formulario de alta
    (empresa/departamento + descripción + repartidor, con fecha) y la lista
    de registros, con filtro por repartidor y un botón rápido para marcar
    cada uno como 'Hecho'."""
    cfg = RUTA_EXTRA_CONFIG[tipo]

    if puede_crear:
        with st.expander(f"➕ Registrar {tipo.lower()}"):
            with st.form(f"nueva_ruta_extra_{tipo}", clear_on_submit=True):
                fecha_re = st.date_input("Fecha", value=hoy, key=f"re_fecha_{tipo}")
                empresa_re = st.text_input(cfg["label_empresa"], key=f"re_empresa_{tipo}")
                descripcion_re = st.text_area(cfg["label_desc"], key=f"re_desc_{tipo}")
                repartidores_disp_re = db.list_repartidores(solo_activos=True)
                repartidor_nombre_re = None
                if not repartidores_disp_re:
                    st.warning(
                        "Todavía no hay ningún usuario con rol 'Repartidor'. Crea uno primero en "
                        "Administración de usuarios (Rol → Repartidor)."
                    )
                else:
                    repartidor_nombre_re = st.selectbox(
                        "Repartidor asignado", [r["nombre"] for r in repartidores_disp_re], key=f"re_rep_{tipo}",
                    )
                if st.form_submit_button(f"Registrar {tipo.lower()}", use_container_width=True):
                    if not repartidores_disp_re:
                        st.error("Registra primero un usuario con rol 'Repartidor'.")
                    elif not empresa_re.strip() or not descripcion_re.strip():
                        st.error(f"{cfg['label_empresa']} y la descripción son obligatorios.")
                    else:
                        repartidor_id_re = next(
                            r["id"] for r in repartidores_disp_re if r["nombre"] == repartidor_nombre_re
                        )
                        db.create_ruta_extra(
                            tipo, fecha_re, empresa_re.strip(), descripcion_re.strip(), repartidor_id_re,
                        )
                        st.success(f"{tipo} registrado.")
                        st.rerun()

    st.divider()

    if rol == "repartidor":
        filtro_rep_re = user["id"]
    else:
        repartidores_filtro_re = db.list_repartidores(solo_activos=False)
        opciones_rep_re = {"Todos": None}
        opciones_rep_re.update({r["nombre"]: r["id"] for r in repartidores_filtro_re})
        elegido_rep_re = st.selectbox(
            "Filtrar por repartidor", list(opciones_rep_re.keys()), key=f"re_filtro_rep_{tipo}",
        )
        filtro_rep_re = opciones_rep_re[elegido_rep_re]

    rutas = db.list_rutas_extra(tipo=tipo, repartidor_id=filtro_rep_re)
    if not rutas:
        st.caption(f"No hay rutas de {tipo.lower()} registradas con este filtro.")
        return

    for r in rutas:
        with st.container(border=True):
            estado_txt = "✅ Hecho" if r.get("estado") == "Hecho" else "⚪ Pendiente"
            st.markdown(f"**{cfg['icono']} {r.get('empresa') or 'Sin nombre'}** · {estado_txt}")
            st.caption(f"📅 {r.get('fecha') or '—'}")
            if r.get("descripcion"):
                st.caption(r["descripcion"])
            st.caption(f"🚚 Repartidor: {db.nombre_vendedor(r.get('repartidor_id'), todos_usuarios)}")

            if puede_cambiar_estado and r.get("estado") != "Hecho":
                if st.button("✅ Marcar como hecho", key=f"re_marcar_{r['id']}", use_container_width=True):
                    db.update_ruta_extra(r["id"], estado="Hecho")
                    st.rerun()

            if puede_crear:
                editando_key_re = f"re_editando_{r['id']}"
                if st.button("✏️ Editar / eliminar", key=f"re_toggle_{r['id']}", use_container_width=True):
                    st.session_state[editando_key_re] = not st.session_state.get(editando_key_re, False)
                    st.rerun()
                if st.session_state.get(editando_key_re):
                    _render_editar_ruta_extra(r, cfg, editando_key_re)


# --------------------------------------------------------------------------
# Datos compartidos entre pestañas.
# --------------------------------------------------------------------------
todos_usuarios = db.list_usuarios()
# El "vendedor que hizo la venta" puede ser un usuario con rol 'vendedor' o
# alguien de la lista adicional de Logística (sin usuario propio) — se
# combinan las dos listas (sin duplicar nombres) para poder mostrar el
# nombre correcto.
lookup_vendedores = _combinar_vendedores(todos_usuarios, db.list_logistica_vendedores(solo_activos=False))

# --------------------------------------------------------------------------
# KPIs rápidos de hoy.
# --------------------------------------------------------------------------
kpi_hoy_am = db.list_pedidos(fecha=hoy, franja="AM")
kpi_hoy_pm = db.list_pedidos(fecha=hoy, franja="PM")
kcol1, kcol2, kcol3 = st.columns([1, 1, 2])
kcol1.metric("🌅 Rutas hoy AM", len(kpi_hoy_am))
kcol2.metric("🌇 Rutas hoy PM", len(kpi_hoy_pm))
with kcol3:
    st.caption("🚚 Rutas de hoy por repartidor")
    conteo_por_repartidor_id = {}
    for pedido_kpi in kpi_hoy_am + kpi_hoy_pm:
        rid = pedido_kpi.get("repartidor_id")
        conteo_por_repartidor_id[rid] = conteo_por_repartidor_id.get(rid, 0) + 1
    filas_rep_kpi = [
        {"Repartidor": r["nombre"], "Rutas hoy": conteo_por_repartidor_id.get(r["id"], 0)}
        for r in db.list_repartidores(solo_activos=True)
    ]
    if filas_rep_kpi:
        filas_rep_kpi.sort(key=lambda f: (-f["Rutas hoy"], f["Repartidor"]))
        st.dataframe(pd.DataFrame(filas_rep_kpi), hide_index=True, use_container_width=True, height=140)
    else:
        st.caption("Todavía no hay repartidores activos registrados.")

st.divider()

tab_vista, tab_compras, tab_tramites, tab_papeleria, tab_historial, tab_nueva = st.tabs(
    ["🗺️ Vista de la ruta", "🛒 Compras", "📋 Trámites", "📨 Papelería", "📜 Historial", "➕ Nuevo pedido"]
)

# --------------------------------------------------------------------------
# Vista de la ruta: Hoy AM, Hoy PM, Mañana AM
# --------------------------------------------------------------------------
with tab_vista:
    if rol == "repartidor":
        filtro_repartidor = user["id"]
    else:
        repartidores_filtro = db.list_repartidores(solo_activos=False)
        opciones_rep = {"Todos": None}
        opciones_rep.update({r["nombre"]: r["id"] for r in repartidores_filtro})
        elegido_rep = st.selectbox("Filtrar por repartidor", list(opciones_rep.keys()), key="log_filtro_repartidor")
        filtro_repartidor = opciones_rep[elegido_rep]

    hoy_am = db.list_pedidos(fecha=hoy, franja="AM", repartidor_id=filtro_repartidor)
    hoy_pm = db.list_pedidos(fecha=hoy, franja="PM", repartidor_id=filtro_repartidor)
    manana_am = db.list_pedidos(fecha=manana, franja="AM", repartidor_id=filtro_repartidor)
    # Opciones para el formulario de edición en línea (lápiz ✏️) de cada tarjeta.
    vendedores_op_todos = {
        v["nombre"]: v["id"] for v in
        _combinar_vendedores(db.list_vendedores(solo_activos=False), db.list_logistica_vendedores(solo_activos=False))
    }
    repartidores_op_todos = {r["nombre"]: r["id"] for r in db.list_repartidores(solo_activos=False)}

    todos_los_pedidos = hoy_am + hoy_pm + manana_am
    if todos_los_pedidos:
        download_excel_button(
            pd.DataFrame([{
                "Fecha": p.get("fecha"), "Franja": p.get("franja"), "Cliente": p.get("cliente"),
                "Área/Departamento": p.get("direccion"), "Zona": p.get("zona"), "Producto": p.get("producto"),
                "N° orden/factura": p.get("numero_orden"),
                "Tipo de ruta": p.get("tipo_ruta") or "—",
                "Vendedor": db.nombre_vendedor(p.get("vendedor_id"), lookup_vendedores),
                "Repartidor": db.nombre_vendedor(p.get("repartidor_id"), todos_usuarios),
                "Estado": p.get("estado"), "Notas": p.get("notas") or "—",
            } for p in todos_los_pedidos]),
            "pedidos_logistica.xlsx", key="log_descargar_excel",
        )

    col1, col2, col3 = st.columns(3)
    columnas = [
        (col1, f"🌅 Hoy AM ({hoy.strftime('%d/%m')})", hoy_am),
        (col2, f"🌇 Hoy PM ({hoy.strftime('%d/%m')})", hoy_pm),
        (col3, f"🌄 Mañana AM ({manana.strftime('%d/%m')})", manana_am),
    ]
    for col, titulo, items in columnas:
        with col:
            st.markdown(f"##### {titulo} ({len(items)})")
            if not items:
                st.caption("Sin pedidos.")
            for p in items:
                with st.container(border=True):
                    pid = p["id"]
                    editando_key = f"log_editando_{pid}"

                    title_col, edit_col = st.columns([5, 1])
                    with title_col:
                        st.markdown(f"{ESTADO_EMOJI.get(p.get('estado'), '')} **{p.get('cliente') or 'Sin cliente'}**")
                    with edit_col:
                        if puede_crear:
                            if st.button("✏️", key=f"log_editar_{pid}", help="Editar este pedido"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()

                    st.caption(f"📍 {p.get('direccion') or '—'} · {p.get('zona') or '—'}")
                    if p.get("atencion_a"):
                        st.caption(f"🙋 Atención a: {p['atencion_a']}")
                    if p.get("producto"):
                        st.caption(f"📦 {p['producto']}")
                    if p.get("numero_orden"):
                        st.caption(f"🧾 Orden/factura: {p['numero_orden']}")
                    if p.get("tipo_ruta"):
                        st.caption(f"🏷️ {p['tipo_ruta']}")
                    st.caption(f"Vendedor: {db.nombre_vendedor(p.get('vendedor_id'), lookup_vendedores)}")
                    st.caption(f"🚚 Repartidor: {db.nombre_vendedor(p.get('repartidor_id'), todos_usuarios)}")
                    st.caption(f"Estado: **{p.get('estado') or '—'}**")
                    if p.get("notas"):
                        st.caption(f"📝 {p['notas']}")
                    _mostrar_foto_entrega(p)
                    st.download_button(
                        "📄 PDF de envío", data=pedido_pdf_bytes(p),
                        file_name=f"envio_{p.get('numero_envio') or pid}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"log_pdf_{pid}",
                    )

                    confirmando_key = f"log_confirmando_entrega_{pid}"
                    if puede_crear and st.session_state.get(editando_key):
                        # --------------------------------------------------
                        # Edición en línea (se abrió con el lápiz ✏️) — solo
                        # jefe de logística y admin.
                        # --------------------------------------------------
                        _render_pedido_edit_form(
                            p, editando_key, vendedores_op_todos, repartidores_op_todos,
                            lookup_vendedores, todos_usuarios,
                        )
                    elif st.session_state.get(confirmando_key):
                        # --------------------------------------------------
                        # Panel abierto para confirmar la entrega con foto
                        # (ver más abajo — solo aplica al repartidor).
                        # --------------------------------------------------
                        estado_actual = p.get("estado") if p.get("estado") in ESTADOS_PEDIDO else ESTADOS_PEDIDO[0]
                        siguiente = ESTADOS_PEDIDO[(ESTADOS_PEDIDO.index(estado_actual) + 1) % len(ESTADOS_PEDIDO)]
                        _render_confirmar_entrega(p, siguiente, confirmando_key)
                    elif puede_cambiar_estado:
                        estado_actual = p.get("estado") if p.get("estado") in ESTADOS_PEDIDO else ESTADOS_PEDIDO[0]
                        siguiente = ESTADOS_PEDIDO[(ESTADOS_PEDIDO.index(estado_actual) + 1) % len(ESTADOS_PEDIDO)]
                        requiere_foto = siguiente == "Entregado" and rol == "repartidor"
                        if requiere_foto:
                            if st.button(
                                f"➡️ Marcar como «{siguiente}» (requiere foto)",
                                key=f"log_avanzar_{pid}", use_container_width=True,
                            ):
                                st.session_state[confirmando_key] = True
                                st.rerun()
                        elif st.button(
                            f"➡️ Marcar como «{siguiente}»", key=f"log_avanzar_{pid}", use_container_width=True,
                        ):
                            db.update_pedido(pid, estado=siguiente)
                            st.rerun()

    st.divider()

    # ----------------------------------------------------------------------
    # Jefe de logística y admin ya editan todo desde el lápiz ✏️ de la
    # tarjeta, arriba. El repartidor no ve ese lápiz — aquí solo puede
    # agregar una nota a sus pedidos (el estado lo cambia con el botón
    # «Marcar como…» de la tarjeta).
    # ----------------------------------------------------------------------
    if rol == "repartidor":
        st.markdown("#### 📝 Agregar nota a un pedido")
        st.caption("Para cambiar el estado, usa el botón «Marcar como…» en la tarjeta del pedido, arriba.")
        gestionables = todos_los_pedidos
        if not gestionables:
            st.caption("No hay pedidos para gestionar con estos filtros.")
        else:
            opciones = {
                f"[{p['fecha']} {p['franja']}] {p.get('cliente') or 'Sin cliente'}": p["id"]
                for p in gestionables
            }
            elegido = st.selectbox("Selecciona un pedido", ["—"] + list(opciones.keys()), key="log_gestionar_select")
            if elegido != "—":
                pid = opciones[elegido]
                p = db.get_pedido(pid)

                with st.form(f"gestionar_pedido_{pid}"):
                    st.caption(f"Cliente: **{p.get('cliente') or '—'}**")
                    st.caption(f"Área/Departamento: {p.get('direccion') or '—'} · {p.get('zona') or '—'}")
                    st.caption(f"Producto: {p.get('producto') or '—'}")
                    st.caption(f"Fecha/franja: {p.get('fecha') or '—'} {p.get('franja') or ''}")
                    notas_ed = st.text_area(
                        "Notas", value=p.get("notas") or "",
                        help="Por ejemplo, el motivo si el pedido no se pudo entregar.",
                    )
                    if st.form_submit_button("Guardar nota", use_container_width=True):
                        db.update_pedido(pid, notas=notas_ed.strip() or None)
                        st.success("Nota guardada.")
                        st.rerun()
    elif not puede_cambiar_estado:
        st.caption("Tu rol es de solo vista para la ruta de reparto.")

# --------------------------------------------------------------------------
# Compras / Trámites / Papelería: rutas sencillas del repartidor que no son
# un envío de mercadería.
# --------------------------------------------------------------------------
with tab_compras:
    _render_ruta_extra_tab("Compras")
with tab_tramites:
    _render_ruta_extra_tab("Trámites")
with tab_papeleria:
    _render_ruta_extra_tab("Papelería")

# --------------------------------------------------------------------------
# Historial: todos los pedidos ya entregados (de cualquier fecha), con
# filtro por repartidor y una tabla de frecuencia de entregas por cliente.
# --------------------------------------------------------------------------
with tab_historial:
    st.caption("Historial de todos los pedidos que ya se marcaron como «Entregado».")

    repartidores_hist = db.list_repartidores(solo_activos=False)
    opciones_rep_hist = {"Todos": None}
    opciones_rep_hist.update({r["nombre"]: r["id"] for r in repartidores_hist})
    elegido_rep_hist = st.selectbox(
        "Filtrar por repartidor", list(opciones_rep_hist.keys()), key="log_hist_filtro_repartidor",
    )
    filtro_rep_hist = opciones_rep_hist[elegido_rep_hist]

    pedidos_hist = db.list_pedidos(repartidor_id=filtro_rep_hist)
    entregados = [p for p in pedidos_hist if p.get("estado") == "Entregado"]
    entregados.sort(key=lambda p: p.get("fecha") or "", reverse=True)

    if not entregados:
        st.caption("Todavía no hay pedidos entregados con este filtro.")
    else:
        df_hist = pd.DataFrame([{
            "Fecha": p.get("fecha"), "Franja": p.get("franja"), "Cliente": p.get("cliente") or "—",
            "Área/Departamento": p.get("direccion") or "—", "Zona": p.get("zona") or "—",
            "Producto": p.get("producto") or "—",
            "Vendedor": db.nombre_vendedor(p.get("vendedor_id"), lookup_vendedores),
            "Repartidor": db.nombre_vendedor(p.get("repartidor_id"), todos_usuarios),
            "N° envío": p.get("numero_envio") or "—",
        } for p in entregados])
        st.markdown(f"##### 📦 {len(entregados)} pedido(s) entregado(s)")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        download_excel_button(
            df_hist, "historial_pedidos_entregados.xlsx", key="log_hist_descargar_excel",
        )

        st.divider()
        st.markdown("##### 📊 Frecuencia de entregas por cliente")
        st.caption("Cantidad de pedidos entregados por cliente — total y desglosado por mes.")
        df_freq = pd.DataFrame([{
            "Cliente": p.get("cliente") or "Sin cliente", "Mes": (p.get("fecha") or "")[:7],
        } for p in entregados])
        tabla_freq = pd.crosstab(df_freq["Cliente"], df_freq["Mes"])
        tabla_freq = tabla_freq.reindex(sorted(tabla_freq.columns), axis=1)
        tabla_freq.columns = [_label_mes(c) for c in tabla_freq.columns]
        tabla_freq["Total"] = tabla_freq.sum(axis=1)
        tabla_freq = tabla_freq.sort_values("Total", ascending=False)
        st.dataframe(tabla_freq, use_container_width=True)

# --------------------------------------------------------------------------
# Nuevo pedido
# --------------------------------------------------------------------------
with tab_nueva:
    if not puede_crear:
        st.info("Solo el jefe de logística y el administrador pueden ingresar pedidos nuevos.")
    else:
        vendedores_disp = sorted(
            _combinar_vendedores(db.list_vendedores(solo_activos=True), db.list_logistica_vendedores(solo_activos=True)),
            key=lambda v: v["nombre"],
        )
        repartidores_disp = db.list_repartidores(solo_activos=True)

        if not vendedores_disp:
            st.warning("Todavía no hay vendedores activos registrados en la plataforma.")
        elif not repartidores_disp:
            st.warning(
                "Todavía no hay ningún usuario con rol 'Repartidor'. Crea uno primero en "
                "Administración de usuarios (Rol → Repartidor)."
            )
        else:
            with st.form("nuevo_pedido_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                fecha = c1.date_input("Fecha de entrega", value=date.today())
                franja = c2.radio("Franja", FRANJAS_PEDIDO, horizontal=True)

                cliente = st.text_input("Nombre del cliente")
                c3, c4 = st.columns(2)
                direccion = c3.text_input("Área/Departamento")
                atencion_a = c4.text_input("Atención a (opcional)")
                c5, c6 = st.columns(2)
                zona = c5.selectbox("Zona de la capital", ZONAS_CAPITAL)
                numero_orden = c6.text_input("N° de orden o factura (opcional)")
                tipo_ruta_sel = st.selectbox("Tipo de ruta", TIPOS_RUTA_PEDIDO)

                st.caption(
                    "Productos del envío (cantidad + descripción, opcional) — agrega o quita filas con el ➕ / 🗑️."
                )
                productos_df_nuevo = st.data_editor(
                    pd.DataFrame([{"Cantidad": "", "Descripción": ""}]),
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    column_config=_productos_column_config(), key="log_productos_nuevo",
                )

                c7, c8 = st.columns(2)
                vendedor_nombre_sel = c7.selectbox("Vendedor que hizo la venta", [v["nombre"] for v in vendedores_disp])
                repartidor_nombre_sel = c8.selectbox("Repartidor asignado", [r["nombre"] for r in repartidores_disp])

                notas = st.text_area("Notas (opcional)")

                if st.form_submit_button("Registrar pedido", use_container_width=True):
                    if not cliente.strip() or not direccion.strip():
                        st.error("El nombre del cliente y el área/departamento son obligatorios.")
                    else:
                        vendedor_id = next(v["id"] for v in vendedores_disp if v["nombre"] == vendedor_nombre_sel)
                        repartidor_id = next(r["id"] for r in repartidores_disp if r["nombre"] == repartidor_nombre_sel)
                        productos_nuevo, resumen_nuevo = _productos_desde_editor(productos_df_nuevo)
                        db.create_pedido(
                            fecha, franja, cliente.strip(), direccion.strip(), zona,
                            resumen_nuevo, numero_orden.strip() or None,
                            vendedor_id, repartidor_id, notas=notas.strip() or None,
                            tipo_ruta=tipo_ruta_sel, atencion_a=atencion_a.strip() or None,
                            productos=productos_nuevo,
                        )
                        st.success(f"Pedido registrado en {franja} del {fecha}.")
                        st.rerun()
