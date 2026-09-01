from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import APP_URL, COLORADO_DIMENSION_UNIDADES, COLORADO_TIPOS_COLOR, ESTADOS_COLORADO
from utils import money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_colorado()

st.title("🖨️ Colorado")
st.caption(
    "Órdenes de producción de la planta Colorado: arriba, el cronograma con la fecha de entrega de "
    "cada orden; abajo, el tablero de producción (mismo concepto que Phara) para dar seguimiento a "
    "cada una — cada orden es la misma tarjeta en los dos lugares."
    + ("" if puede_editar else " Tu acceso es solo de consulta: puedes ver todo, pero no crear ni mover nada.")
)

COLUMN_EMOJI = {
    "Nuevo": "🆕", "En producción": "🏭", "Acabados": "✂️", "Entregado": "✅",
}
VENCIDO_BG = "#fbe3e3"  # rojo leve — mismo estilo que el resaltado magenta de 'Ventas por mes'

pedidos = db.list_colorado_pedidos()
hoy = date.today()


def _es_vencido(p):
    # Una orden ya entregada no cuenta como "vencida" aunque su fecha de
    # entrega programada haya quedado en el pasado.
    if p.get("estado") == "Entregado":
        return False
    fe = p.get("fecha_entrega")
    return bool(fe) and fe < str(hoy)


def _siguiente_estado(estado_actual):
    """Etapa que sigue en el orden del tablero, o None si ya está en la
    última columna ('Entregado')."""
    if estado_actual not in ESTADOS_COLORADO:
        return None
    i = ESTADOS_COLORADO.index(estado_actual)
    return ESTADOS_COLORADO[i + 1] if i + 1 < len(ESTADOS_COLORADO) else None


def _total_pedido(p):
    """Precio por unidad × cantidad de unidades, o None si falta alguno de
    los dos datos (se calcula, no se guarda aparte, para que nunca quede
    desactualizado si se corrige el precio o la cantidad)."""
    precio = p.get("precio_unidad")
    cantidad = p.get("cantidad_unidades")
    if not precio or not cantidad:
        return None
    return float(precio) * float(cantidad)


def _dimensiones_texto(p):
    ancho, alto, unidad = p.get("dimension_ancho"), p.get("dimension_alto"), p.get("dimension_unidad")
    if not ancho and not alto:
        return None
    return f"{ancho or '—'} x {alto or '—'} {unidad or ''}".strip()


def _avisar_por_correo(asunto, cuerpo):
    """Manda un aviso a los correos configurados (ver abajo). No hace nada
    (ni muestra error) si todavía no hay correos guardados o si el correo
    remitente no está configurado — ver database.correo_disponible."""
    correos = db.get_colorado_correos_aviso()
    if correos:
        db.enviar_correo_aviso(correos, asunto, cuerpo + f"\n\nVer en la plataforma: {APP_URL}")


if puede_editar:
    with st.expander("✉️ Avisos por correo (orden nueva o cambio de columna)"):
        if not db.correo_disponible():
            st.info(
                "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta "
                "de Gmail en la configuración de la plataforma) — mientras tanto, esta sección no manda "
                "nada, pero puedes ir guardando los correos de una vez."
            )
        correos_actuales = db.get_colorado_correos_aviso()
        with st.form("colorado_correos_aviso"):
            correos_texto = st.text_area(
                "Correos que reciben el aviso — uno por línea (o separados por coma)",
                value="\n".join(correos_actuales),
                help="Se les avisa automáticamente cuando se agrega una orden nueva o cuando una tarjeta "
                     "cambia de columna en el tablero (no en otros cambios menores, como corregir una nota).",
            )
            if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                nuevos_correos = [c.strip() for c in correos_texto.replace(",", "\n").split("\n") if c.strip()]
                db.set_colorado_correos_aviso(nuevos_correos)
                st.success("Correos actualizados.")
                st.rerun()


# ---------------------------------------------------------------------------
# Cronograma de entregas (arriba)
# ---------------------------------------------------------------------------
st.markdown("#### 📅 Cronograma de entregas")

vencidos = [p for p in pedidos if _es_vencido(p)]
if vencidos:
    st.warning(f"⚠️ Hay {len(vencidos)} orden(es) con la fecha de entrega ya vencida (resaltadas abajo en rojo).")

if not pedidos:
    st.info("Todavía no hay órdenes registradas para Colorado.")
else:
    pedidos_cronograma = sorted(pedidos, key=lambda p: p.get("fecha_entrega") or "9999-99-99")
    df_cron = pd.DataFrame([{
        "Cliente": p.get("cliente_nombre") or "—",
        "Tipo de pieza": p.get("tipo_pieza") or "—",
        "Cantidad": p.get("cantidad_unidades") if p.get("cantidad_unidades") not in (None, "") else "—",
        "Total": money(_total_pedido(p)) if _total_pedido(p) is not None else "—",
        "Fecha de entrega": p.get("fecha_entrega") or "Sin definir",
        "Etapa": f"{COLUMN_EMOJI.get(p.get('estado'), '')} {p.get('estado') or '—'}",
        "_vencido": _es_vencido(p),
    } for p in pedidos_cronograma])
    styler = df_cron.drop(columns=["_vencido"]).style.apply(
        lambda _: [f"background-color: {VENCIDO_BG}" if v else "" for v in df_cron["_vencido"]], axis=0,
    )
    st.dataframe(styler, use_container_width=True, hide_index=True)

if puede_editar:
    with st.expander("➕ Agregar orden nueva"):
        with st.form("colorado_nuevo_pedido", clear_on_submit=True):
            st.markdown("**Datos del cliente**")
            cliente_nombre_n = st.text_input("Nombre del cliente")
            c1, c2 = st.columns(2)
            cliente_telefono_n = c1.text_input("Número tel. del cliente (opcional)")
            cliente_correo_n = c2.text_input("Correo electrónico del cliente (opcional)")
            nit_n = st.text_input("NIT del cliente (opcional)")
            direccion_entrega_n = st.text_area("Dirección de entrega (opcional)")

            st.markdown("**Datos de la pieza**")
            tipo_pieza_n = st.text_input("Tipo de pieza (opcional)")
            c3, c4, c5 = st.columns(3)
            dim_ancho_n = c3.number_input("Ancho del arte", min_value=0.0, step=0.1, value=0.0)
            dim_alto_n = c4.number_input("Alto del arte", min_value=0.0, step=0.1, value=0.0)
            dim_unidad_n = c5.selectbox("Unidad", COLORADO_DIMENSION_UNIDADES)
            material_n = st.text_input("Papel o material a usar (opcional)")
            tipo_color_n = st.selectbox("Tipo de color", COLORADO_TIPOS_COLOR)
            acabados_n = st.text_input("Acabados (opcional)")

            st.markdown("**Precio y cantidad**")
            c6, c7 = st.columns(2)
            precio_unidad_n = c6.number_input("Precio por unidad (Q)", min_value=0.0, step=0.01, value=0.0)
            cantidad_unidades_n = c7.number_input("Cantidad de unidades", min_value=0, step=1, value=0)
            if precio_unidad_n and cantidad_unidades_n:
                st.caption(f"Total: {money(precio_unidad_n * cantidad_unidades_n)}")

            notas_n = st.text_area("Notas adicionales (opcional)")
            fecha_entrega_n = st.date_input("Fecha de entrega (opcional)", value=None)

            if st.form_submit_button(f"Agregar a {ESTADOS_COLORADO[0]}", use_container_width=True):
                if not cliente_nombre_n.strip():
                    st.error("El nombre del cliente es obligatorio.")
                else:
                    datos = {
                        "cliente_nombre": cliente_nombre_n.strip(),
                        "cliente_telefono": cliente_telefono_n.strip() or None,
                        "cliente_correo": cliente_correo_n.strip() or None,
                        "nit": nit_n.strip() or None,
                        "direccion_entrega": direccion_entrega_n.strip() or None,
                        "tipo_pieza": tipo_pieza_n.strip() or None,
                        "dimension_ancho": dim_ancho_n or None,
                        "dimension_alto": dim_alto_n or None,
                        "dimension_unidad": dim_unidad_n,
                        "material": material_n.strip() or None,
                        "tipo_color": tipo_color_n,
                        "acabados": acabados_n.strip() or None,
                        "precio_unidad": precio_unidad_n or None,
                        "cantidad_unidades": cantidad_unidades_n or None,
                        "notas": notas_n.strip() or None,
                        "fecha_entrega": str(fecha_entrega_n) if fecha_entrega_n else None,
                    }
                    db.create_colorado_pedido(datos, creado_por_id=user["id"])
                    total_txt = money(precio_unidad_n * cantidad_unidades_n) if (precio_unidad_n and cantidad_unidades_n) else "—"
                    _avisar_por_correo(
                        f"Colorado — Nueva orden: {cliente_nombre_n.strip()}",
                        f"Se agregó una nueva orden de producción en Colorado.\n\n"
                        f"Cliente: {cliente_nombre_n.strip()}\n"
                        f"Tipo de pieza: {tipo_pieza_n.strip() or '—'}\n"
                        f"Cantidad: {cantidad_unidades_n or '—'}\n"
                        f"Total: {total_txt}\n"
                        f"Fecha de entrega: {fecha_entrega_n or 'sin definir'}\n\n"
                        f"Etapa: {ESTADOS_COLORADO[0]}",
                    )
                    st.success(f"Orden agregada al cronograma y a la columna '{ESTADOS_COLORADO[0]}' del tablero.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Tablero de producción (abajo) — mismo concepto que Phara.
# ---------------------------------------------------------------------------
st.markdown("#### 🗂️ Tablero de producción")
if not puede_editar:
    st.caption("Tu acceso es de solo consulta para este tablero.")

cols = st.columns(len(ESTADOS_COLORADO))
for col, estado in zip(cols, ESTADOS_COLORADO):
    items = [p for p in pedidos if p.get("estado") == estado]
    with col:
        st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
        if not items:
            st.caption("Sin órdenes.")
        for p in items:
            with st.container(border=True):
                pid = p["id"]
                editando_key = f"colorado_editando_{pid}"

                title_col2, edit_col = st.columns([5, 1])
                with title_col2:
                    vencido_marca = "🔴 " if _es_vencido(p) else ""
                    st.markdown(f"{vencido_marca}**{p.get('cliente_nombre') or 'Sin cliente'}**")
                with edit_col:
                    if puede_editar:
                        if st.button("✏️", key=f"colorado_editar_{pid}", help="Editar esta orden"):
                            st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                            st.rerun()

                if p.get("tipo_pieza"):
                    st.caption(f"🧩 {p['tipo_pieza']}")
                if p.get("cliente_telefono") or p.get("cliente_correo"):
                    st.caption(f"☎️ {p.get('cliente_telefono') or '—'}  ·  ✉️ {p.get('cliente_correo') or '—'}")
                if p.get("nit"):
                    st.caption(f"🧾 NIT: {p['nit']}")
                if p.get("direccion_entrega"):
                    st.caption(f"📍 {p['direccion_entrega']}")
                dimensiones_txt = _dimensiones_texto(p)
                if dimensiones_txt:
                    st.caption(f"📐 {dimensiones_txt}")
                if p.get("material"):
                    st.caption(f"🧵 Material: {p['material']}")
                if p.get("tipo_color"):
                    st.caption(f"🎨 {p['tipo_color']}")
                if p.get("acabados"):
                    st.caption(f"✨ Acabados: {p['acabados']}")
                if p.get("cantidad_unidades") not in (None, "", 0):
                    st.caption(f"Cantidad: {p['cantidad_unidades']}")
                if p.get("precio_unidad") not in (None, "", 0):
                    st.caption(f"Precio por unidad: {money(p['precio_unidad'])}")
                total_pedido = _total_pedido(p)
                if total_pedido is not None:
                    st.caption(f"💲 Total: {money(total_pedido)}")
                if p.get("notas"):
                    st.caption(f"📝 {p['notas']}")
                st.caption(f"📅 Entrega: {p.get('fecha_entrega') or 'sin definir'}")
                st.caption(f"🕒 {(p.get('creado_en') or '')[:16].replace('T', ' ')}")

                # ------------------------------------------------------------
                # Acciones rápidas: pasar a la siguiente etapa y eliminar,
                # directo desde la tarjeta (sin tener que abrir el formulario
                # de edición) — mismo estilo que Phara.
                # ------------------------------------------------------------
                if puede_editar:
                    siguiente = _siguiente_estado(p.get("estado"))
                    accion_col1, accion_col2 = st.columns(2)
                    with accion_col1:
                        if siguiente:
                            if st.button(
                                f"➡️ {siguiente}", key=f"colorado_avanzar_{pid}", use_container_width=True,
                                help=f"Pasar a la columna «{siguiente}»",
                            ):
                                db.update_colorado_pedido(pid, estado=siguiente)
                                _avisar_por_correo(
                                    f"Colorado — {p.get('cliente_nombre') or 'Orden'} pasó a '{siguiente}'",
                                    f"La orden de '{p.get('cliente_nombre') or 'cliente'}' cambió de columna en "
                                    f"el tablero.\n\n"
                                    f"De: {p.get('estado') or '—'}\nA: {siguiente}\n\n"
                                    f"Fecha de entrega: {p.get('fecha_entrega') or 'sin definir'}",
                                )
                                st.success(f"Orden movida a «{siguiente}».")
                                st.rerun()
                    with accion_col2:
                        if st.button(
                            "🗑️ Eliminar", key=f"colorado_borrar_{pid}", use_container_width=True,
                        ):
                            db.delete_colorado_pedido(pid)
                            st.session_state.pop(editando_key, None)
                            st.success("Orden eliminada.")
                            st.rerun()

                if puede_editar and st.session_state.get(editando_key):
                    with st.form(f"colorado_gestionar_{pid}"):
                        st.markdown("**Datos del cliente**")
                        cliente_nombre_ed = st.text_input(
                            "Nombre del cliente", value=p.get("cliente_nombre") or "",
                        )
                        ce1, ce2 = st.columns(2)
                        cliente_telefono_ed = ce1.text_input(
                            "Número tel. del cliente (opcional)", value=p.get("cliente_telefono") or "",
                        )
                        cliente_correo_ed = ce2.text_input(
                            "Correo electrónico del cliente (opcional)", value=p.get("cliente_correo") or "",
                        )
                        nit_ed = st.text_input("NIT del cliente (opcional)", value=p.get("nit") or "")
                        direccion_entrega_ed = st.text_area(
                            "Dirección de entrega (opcional)", value=p.get("direccion_entrega") or "",
                        )

                        st.markdown("**Datos de la pieza**")
                        tipo_pieza_ed = st.text_input("Tipo de pieza (opcional)", value=p.get("tipo_pieza") or "")
                        ce3, ce4, ce5 = st.columns(3)
                        dim_ancho_ed = ce3.number_input(
                            "Ancho del arte", min_value=0.0, step=0.1, value=float(p.get("dimension_ancho") or 0),
                        )
                        dim_alto_ed = ce4.number_input(
                            "Alto del arte", min_value=0.0, step=0.1, value=float(p.get("dimension_alto") or 0),
                        )
                        dim_unidad_ed = ce5.selectbox(
                            "Unidad", COLORADO_DIMENSION_UNIDADES,
                            index=COLORADO_DIMENSION_UNIDADES.index(p["dimension_unidad"])
                            if p.get("dimension_unidad") in COLORADO_DIMENSION_UNIDADES else 0,
                        )
                        material_ed = st.text_input(
                            "Papel o material a usar (opcional)", value=p.get("material") or "",
                        )
                        tipo_color_ed = st.selectbox(
                            "Tipo de color", COLORADO_TIPOS_COLOR,
                            index=COLORADO_TIPOS_COLOR.index(p["tipo_color"])
                            if p.get("tipo_color") in COLORADO_TIPOS_COLOR else 0,
                        )
                        acabados_ed = st.text_input("Acabados (opcional)", value=p.get("acabados") or "")

                        st.markdown("**Precio y cantidad**")
                        ce6, ce7 = st.columns(2)
                        precio_unidad_ed = ce6.number_input(
                            "Precio por unidad (Q)", min_value=0.0, step=0.01,
                            value=float(p.get("precio_unidad") or 0),
                        )
                        cantidad_unidades_ed = ce7.number_input(
                            "Cantidad de unidades", min_value=0, step=1,
                            value=int(p.get("cantidad_unidades") or 0),
                        )
                        if precio_unidad_ed and cantidad_unidades_ed:
                            st.caption(f"Total: {money(precio_unidad_ed * cantidad_unidades_ed)}")

                        notas_ed = st.text_area("Notas adicionales", value=p.get("notas") or "")
                        fecha_entrega_ed = st.date_input(
                            "Fecha de entrega (opcional)",
                            value=date.fromisoformat(p["fecha_entrega"]) if p.get("fecha_entrega") else None,
                        )
                        estado_ed = st.selectbox(
                            "Etapa (columna del tablero)", ESTADOS_COLORADO,
                            index=ESTADOS_COLORADO.index(p["estado"]) if p.get("estado") in ESTADOS_COLORADO else 0,
                            help="Además de «➡️» (que avanza a la siguiente), aquí puedes mandar la "
                                 "orden a cualquier columna, incluso hacia atrás si fue un error.",
                        )

                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                        cancelar = colf2.form_submit_button("Cancelar", use_container_width=True)

                        if guardar:
                            if not cliente_nombre_ed.strip():
                                st.error("El nombre del cliente es obligatorio.")
                            else:
                                cambio_de_columna = estado_ed != p.get("estado")
                                db.update_colorado_pedido(
                                    pid,
                                    cliente_nombre=cliente_nombre_ed.strip(),
                                    cliente_telefono=cliente_telefono_ed.strip() or None,
                                    cliente_correo=cliente_correo_ed.strip() or None,
                                    nit=nit_ed.strip() or None,
                                    direccion_entrega=direccion_entrega_ed.strip() or None,
                                    tipo_pieza=tipo_pieza_ed.strip() or None,
                                    dimension_ancho=dim_ancho_ed or None,
                                    dimension_alto=dim_alto_ed or None,
                                    dimension_unidad=dim_unidad_ed,
                                    material=material_ed.strip() or None,
                                    tipo_color=tipo_color_ed,
                                    acabados=acabados_ed.strip() or None,
                                    precio_unidad=precio_unidad_ed or None,
                                    cantidad_unidades=cantidad_unidades_ed or None,
                                    notas=notas_ed.strip() or None,
                                    fecha_entrega=str(fecha_entrega_ed) if fecha_entrega_ed else None,
                                    estado=estado_ed,
                                )
                                if cambio_de_columna:
                                    _avisar_por_correo(
                                        f"Colorado — {cliente_nombre_ed.strip()} pasó a '{estado_ed}'",
                                        f"La orden de '{cliente_nombre_ed.strip()}' cambió de columna en el "
                                        f"tablero.\n\n"
                                        f"De: {p.get('estado') or '—'}\n"
                                        f"A: {estado_ed}\n\n"
                                        f"Fecha de entrega: {fecha_entrega_ed or 'sin definir'}",
                                    )
                                st.session_state.pop(editando_key, None)
                                st.success("Orden actualizada.")
                                st.rerun()
                        if cancelar:
                            st.session_state.pop(editando_key, None)
                            st.rerun()
