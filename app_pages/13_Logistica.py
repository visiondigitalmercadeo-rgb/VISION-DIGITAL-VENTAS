from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PEDIDO, FRANJAS_PEDIDO, ZONAS_CAPITAL
from utils import download_excel_button, sidebar_user_box

user = auth.current_user()
rol = user["rol"]
sidebar_user_box()

st.title("🚚 Logística — Ruta de reparto")
st.caption(
    "El jefe de logística ingresa los pedidos AM/PM de cada día y asigna un repartidor. "
    "Repartidores y jefe de logística van marcando el estado durante el día; vendedores solo consultan."
)

ESTADO_EMOJI = {"Pendiente": "⚪", "En ruta": "🔵", "Entregado": "🟢", "No entregado": "🔴"}

puede_crear = rol in ("admin", "jefe_logistica")
puede_cambiar_estado = rol in ("admin", "jefe_logistica", "repartidor")

hoy = date.today()
manana = hoy + timedelta(days=1)

tab_vista, tab_nueva = st.tabs(["🗺️ Vista de la ruta", "➕ Nuevo pedido"])

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
    todos_usuarios = db.list_usuarios()

    todos_los_pedidos = hoy_am + hoy_pm + manana_am
    if todos_los_pedidos:
        download_excel_button(
            pd.DataFrame([{
                "Fecha": p.get("fecha"), "Franja": p.get("franja"), "Cliente": p.get("cliente"),
                "Dirección": p.get("direccion"), "Zona": p.get("zona"), "Producto": p.get("producto"),
                "N° orden/factura": p.get("numero_orden"),
                "Vendedor": db.nombre_vendedor(p.get("vendedor_id"), todos_usuarios),
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
                    st.markdown(f"{ESTADO_EMOJI.get(p.get('estado'), '')} **{p.get('cliente') or 'Sin cliente'}**")
                    st.caption(f"📍 {p.get('direccion') or '—'} · {p.get('zona') or '—'}")
                    if p.get("producto"):
                        st.caption(f"📦 {p['producto']}")
                    if p.get("numero_orden"):
                        st.caption(f"🧾 Orden/factura: {p['numero_orden']}")
                    st.caption(f"Vendedor: {db.nombre_vendedor(p.get('vendedor_id'), todos_usuarios)}")
                    st.caption(f"🚚 Repartidor: {db.nombre_vendedor(p.get('repartidor_id'), todos_usuarios)}")
                    st.caption(f"Estado: **{p.get('estado') or '—'}**")
                    if p.get("notas"):
                        st.caption(f"📝 {p['notas']}")

    st.divider()

    # ----------------------------------------------------------------------
    # Gestionar un pedido: jefe de logística / admin editan todo;
    # repartidor solo puede cambiar el estado (y la nota) de lo suyo.
    # ----------------------------------------------------------------------
    if puede_cambiar_estado:
        st.markdown("#### ✏️ Actualizar un pedido")
        gestionables = todos_los_pedidos
        if not gestionables:
            st.caption("No hay pedidos para gestionar con estos filtros.")
        else:
            opciones = {
                f"[{p['fecha']} {p['franja']}] {p.get('cliente') or 'Sin cliente'} — "
                f"{db.nombre_vendedor(p.get('repartidor_id'), todos_usuarios)}": p["id"]
                for p in gestionables
            }
            elegido = st.selectbox("Selecciona un pedido", ["—"] + list(opciones.keys()), key="log_gestionar_select")
            if elegido != "—":
                pid = opciones[elegido]
                p = db.get_pedido(pid)

                with st.form(f"gestionar_pedido_{pid}"):
                    if puede_crear:
                        c1, c2 = st.columns(2)
                        cliente_ed = c1.text_input("Nombre del cliente", value=p.get("cliente") or "")
                        direccion_ed = c2.text_input("Dirección de entrega", value=p.get("direccion") or "")
                        c3, c4 = st.columns(2)
                        zona_ed = c3.selectbox(
                            "Zona", ZONAS_CAPITAL,
                            index=ZONAS_CAPITAL.index(p["zona"]) if p.get("zona") in ZONAS_CAPITAL else 0,
                        )
                        franja_ed = c4.selectbox(
                            "Franja", FRANJAS_PEDIDO,
                            index=FRANJAS_PEDIDO.index(p["franja"]) if p.get("franja") in FRANJAS_PEDIDO else 0,
                        )
                        c5, c6 = st.columns(2)
                        producto_ed = c5.text_input("Producto / descripción", value=p.get("producto") or "")
                        numero_orden_ed = c6.text_input("N° orden/factura", value=p.get("numero_orden") or "")
                        fecha_ed = st.date_input(
                            "Fecha de entrega",
                            value=date.fromisoformat(p["fecha"]) if p.get("fecha") else date.today(),
                        )

                        vendedores_op = {v["nombre"]: v["id"] for v in db.list_vendedores(solo_activos=False)}
                        nombre_vendedor_actual = db.nombre_vendedor(p.get("vendedor_id"), todos_usuarios)
                        c7, c8 = st.columns(2)
                        vendedor_nombre_ed = c7.selectbox(
                            "Vendedor", list(vendedores_op.keys()),
                            index=list(vendedores_op.keys()).index(nombre_vendedor_actual)
                            if nombre_vendedor_actual in vendedores_op else 0,
                        )
                        repartidores_op = {r["nombre"]: r["id"] for r in db.list_repartidores(solo_activos=False)}
                        nombre_repartidor_actual = db.nombre_vendedor(p.get("repartidor_id"), todos_usuarios)
                        repartidor_nombre_ed = c8.selectbox(
                            "Repartidor asignado", list(repartidores_op.keys()),
                            index=list(repartidores_op.keys()).index(nombre_repartidor_actual)
                            if nombre_repartidor_actual in repartidores_op else 0,
                        )
                    else:
                        st.caption(f"Cliente: **{p.get('cliente') or '—'}**")
                        st.caption(f"Dirección: {p.get('direccion') or '—'} · {p.get('zona') or '—'}")
                        st.caption(f"Producto: {p.get('producto') or '—'}")
                        st.caption(f"Fecha/franja: {p.get('fecha') or '—'} {p.get('franja') or ''}")

                    estado_ed = st.selectbox(
                        "Estado", ESTADOS_PEDIDO,
                        index=ESTADOS_PEDIDO.index(p["estado"]) if p.get("estado") in ESTADOS_PEDIDO else 0,
                    )
                    notas_ed = st.text_area(
                        "Notas", value=p.get("notas") or "",
                        help="Por ejemplo, el motivo si el pedido no se pudo entregar.",
                    )

                    if puede_crear:
                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("Guardar cambios", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar pedido", use_container_width=True)
                    else:
                        guardar = st.form_submit_button("Guardar estado", use_container_width=True)
                        eliminar = False

                    if guardar:
                        update_kwargs = {"estado": estado_ed, "notas": notas_ed.strip() or None}
                        if puede_crear:
                            if not cliente_ed.strip() or not direccion_ed.strip():
                                st.error("El nombre del cliente y la dirección son obligatorios.")
                                update_kwargs = None
                            else:
                                update_kwargs.update(
                                    cliente=cliente_ed.strip(), direccion=direccion_ed.strip(),
                                    zona=zona_ed, franja=franja_ed, producto=producto_ed.strip(),
                                    numero_orden=numero_orden_ed.strip(), fecha=str(fecha_ed),
                                    vendedor_id=vendedores_op.get(vendedor_nombre_ed),
                                    repartidor_id=repartidores_op.get(repartidor_nombre_ed),
                                )
                        if update_kwargs:
                            db.update_pedido(pid, **update_kwargs)
                            st.success("Pedido actualizado.")
                            st.rerun()
                    if eliminar:
                        db.delete_pedido(pid)
                        st.success("Pedido eliminado.")
                        st.rerun()
    else:
        st.caption("Tu rol es de solo vista para la ruta de reparto.")

# --------------------------------------------------------------------------
# Nuevo pedido
# --------------------------------------------------------------------------
with tab_nueva:
    if not puede_crear:
        st.info("Solo el jefe de logística y el administrador pueden ingresar pedidos nuevos.")
    else:
        vendedores_disp = db.list_vendedores(solo_activos=True)
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
                direccion = st.text_input("Dirección de entrega")
                c3, c4 = st.columns(2)
                zona = c3.selectbox("Zona de la capital", ZONAS_CAPITAL)
                numero_orden = c4.text_input("N° de orden o factura (opcional)")
                producto = st.text_input("Producto / descripción del pedido (opcional)")

                c5, c6 = st.columns(2)
                vendedor_nombre_sel = c5.selectbox("Vendedor que hizo la venta", [v["nombre"] for v in vendedores_disp])
                repartidor_nombre_sel = c6.selectbox("Repartidor asignado", [r["nombre"] for r in repartidores_disp])

                notas = st.text_area("Notas (opcional)")

                if st.form_submit_button("Registrar pedido", use_container_width=True):
                    if not cliente.strip() or not direccion.strip():
                        st.error("El nombre del cliente y la dirección son obligatorios.")
                    else:
                        vendedor_id = next(v["id"] for v in vendedores_disp if v["nombre"] == vendedor_nombre_sel)
                        repartidor_id = next(r["id"] for r in repartidores_disp if r["nombre"] == repartidor_nombre_sel)
                        db.create_pedido(
                            fecha, franja, cliente.strip(), direccion.strip(), zona,
                            producto.strip() or None, numero_orden.strip() or None,
                            vendedor_id, repartidor_id, notas=notas.strip() or None,
                        )
                        st.success(f"Pedido registrado en {franja} del {fecha}.")
                        st.rerun()
